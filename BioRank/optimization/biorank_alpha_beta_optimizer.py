import csv
import itertools
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from BioRank.BioRank import BioRankCancerGeneRanking
from BioRank.metrics.ranking_metrics import (
    evaluate_ranking_against_oncokb,
    load_gene_mapping,
    load_truth_genes,
    optuna_display_score,
)
from BioRank.optimization.ablation_config import (
    ABLATION_MODE_FULL,
    ablation_label,
    ablation_pipeline_config,
    normalize_ablation_mode,
    required_input_keys,
)
from BioRank.optimization.fast_biorank_lite import FastBioRankLiteContext


ALGORITHM_PAGERANK = "pagerank"
ALGORITHM_BIORANK = "biorank_lite"
ALGORITHM_BRWR = "random_walk"

BASELINE_ALPHA = 0.5
BASELINE_BETA = 0.5
DEFAULT_MAX_SELECTED_CANDIDATES = 5
SELECTION_MODE_PARETO = "pareto"
SELECTION_MODE_TOP_DISPLAY_SCORE = "top_display_score"

TRIAL_FIELDS = [
    "trial_number",
    "ablation_mode",
    "ablation_label",
    "alpha",
    "beta",
    "alpha_used",
    "beta_used",
    "ndcg_at_15",
    "recall_at_15",
    "common_genes_top_15",
    "ndcg_at_100",
    "recall_at_100",
    "common_genes_top_100",
    "all_hits",
    "mapped_genes",
    "selection_score",
    "state",
    "duration_seconds",
    "error_message",
]

COMPARISON_FIELDS = [
    "row_order",
    "method_label",
    "algorithm",
    "variant_type",
    "selection_source",
    "ablation_mode",
    "ablation_label",
    "alpha",
    "beta",
    "alpha_used",
    "beta_used",
    "ndcg_at_15",
    "recall_at_15",
    "common_genes_top_15",
    "ndcg_at_100",
    "recall_at_100",
    "common_genes_top_100",
    "all_hits",
    "mapped_genes",
    "selection_score",
    "ranking_path",
    "note",
]

SELECTED_CANDIDATE_FIELDS = [
    "candidate_rank",
    "trial_number",
    "selection_source",
    "ablation_mode",
    "ablation_label",
    "alpha",
    "beta",
    "alpha_used",
    "beta_used",
    "ndcg_at_15",
    "recall_at_15",
    "common_genes_top_15",
    "ndcg_at_100",
    "recall_at_100",
    "common_genes_top_100",
    "all_hits",
    "mapped_genes",
    "selection_score",
    "ranking_path",
]

PARETO_FIELDS = [
    "trial_number",
    "ablation_mode",
    "ablation_label",
    "alpha",
    "beta",
    "alpha_used",
    "beta_used",
    "ndcg_at_15",
    "recall_at_15",
    "common_genes_top_15",
    "ndcg_at_100",
    "recall_at_100",
    "common_genes_top_100",
    "selection_score",
]


class OptimizationCancelled(RuntimeError):
    pass


@dataclass
class BioRankAlphaBetaOptimizationResult:
    output_dir: str
    comparison_summary_path: str
    biorank_trial_history_path: str
    selected_candidates_path: str
    biorank_pareto_trials_path: str
    summary_path: str
    logs_path: str
    comparison_rows: list


class BioRankAlphaBetaOptimizer:
    def __init__(
        self,
        cancer_type,
        input_paths,
        validation_file_path,
        validation_gene_column,
        gene_mapping_file_path,
        alpha_range,
        beta_range,
        n_trials,
        metric_config,
        output_dir,
        prefer_balanced_top5=False,
        random_seed=42,
        candidate_selection_mode=SELECTION_MODE_PARETO,
        max_selected_candidates=DEFAULT_MAX_SELECTED_CANDIDATES,
        validation_mode="oncokb_reference",
        ablation_mode=ABLATION_MODE_FULL,
        cancellation_event=None,
        pause_event=None,
        progress_callback=None,
    ):
        self.cancer_type = cancer_type
        self.input_paths = input_paths
        self.validation_file_path = validation_file_path
        self.validation_gene_column = validation_gene_column
        self.gene_mapping_file_path = gene_mapping_file_path
        self.alpha_range = alpha_range
        self.beta_range = beta_range
        self.n_trials = n_trials
        self.metric_config = metric_config
        self.output_dir = Path(output_dir)
        self.rankings_dir = self.output_dir / "rankings"
        self.prefer_balanced_top5 = prefer_balanced_top5
        self.random_seed = random_seed
        self.candidate_selection_mode = candidate_selection_mode
        self.max_selected_candidates = int(max_selected_candidates or DEFAULT_MAX_SELECTED_CANDIDATES)
        self.validation_mode = validation_mode
        self.ablation_mode = normalize_ablation_mode(ablation_mode)
        self.ablation_label = ablation_label(self.ablation_mode)
        self.ablation_config = ablation_pipeline_config(self.ablation_mode)
        self.cancellation_event = cancellation_event
        self.pause_event = pause_event
        self.progress_callback = progress_callback
        self._pause_announced = False

        self.recall_k = int(metric_config.get("recall_k", 100))
        self.ndcg_k = int(metric_config.get("ndcg_k", 100))
        self.precision_k = int(metric_config.get("precision_k", 15))

        self.truth_genes = set()
        self.gene_mapping = {}
        self.trial_rows = []
        self.pareto_rows = []
        self.selected_candidate_rows = []
        self.comparison_rows = []
        self._baseline_network_runner = None
        self._baseline_network_beta = None
        self._prepared_input_cache = {}
        self._matrix_aggregation_cache = {}
        self._personalization_vector_cache = {}
        self._fast_biorank_lite_context = None

        self.comparison_summary_path = self.output_dir / "comparison_summary.tsv"
        self.biorank_trial_history_path = self.output_dir / "biorank_trial_history.tsv"
        self.selected_candidates_path = self.output_dir / "selected_biorank_candidates.tsv"
        self.biorank_pareto_trials_path = self.output_dir / "biorank_pareto_trials.tsv"
        self.summary_path = self.output_dir / "optimization_summary.json"
        self.log_path = self.output_dir / "logs.txt"

    def run(self):
        self._check_cancelled()
        self._validate_config()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.rankings_dir.mkdir(exist_ok=True)
        self._log(f"Start BioRank alpha/beta optimization at {datetime.now().isoformat(timespec='seconds')}")
        self._log(f"Disease: {self.cancer_type}")
        self._log(f"Ablation mode: {self.ablation_label} ({self.ablation_mode})")
        self._log(f"Active optimization parameters: {', '.join(self._active_parameters())}")
        self._log(
            "Fixed inactive parameters: "
            f"alpha={self.ablation_config['fixed_alpha']}, beta={self.ablation_config['fixed_beta']}"
        )
        self._log(f"Input paths: {self.input_paths}")
        self._log(f"Validation mode: {self.validation_mode}")
        self._log(f"Validation path: {self.validation_file_path}")
        self._log(f"Random seed: {self.random_seed}")

        self.truth_genes = load_truth_genes(self.validation_file_path, self.validation_gene_column)
        if not self.truth_genes:
            raise ValueError("Evaluation reference set is empty.")
        self.gene_mapping = load_gene_mapping(self.gene_mapping_file_path)

        baseline_rows = self._run_baselines()
        self.trial_rows, self.pareto_rows = self._run_biorank_optuna()
        self.selected_candidate_rows = self.select_biorank_candidates(self.trial_rows, self.pareto_rows)
        self.selected_candidate_rows = self.generate_selected_candidate_rankings(self.selected_candidate_rows)
        self.comparison_rows = self.build_comparison_summary(baseline_rows, self.selected_candidate_rows)
        self.save_outputs()
        self._log("Optimization finished.")

        return BioRankAlphaBetaOptimizationResult(
            output_dir=str(self.output_dir),
            comparison_summary_path=str(self.comparison_summary_path),
            biorank_trial_history_path=str(self.biorank_trial_history_path),
            selected_candidates_path=str(self.selected_candidates_path),
            biorank_pareto_trials_path=str(self.biorank_pareto_trials_path),
            summary_path=str(self.summary_path),
            logs_path=str(self.log_path),
            comparison_rows=self.comparison_rows,
        )

    def _run_baselines(self):
        alpha, beta = self._baseline_parameters()
        parameter_text = self._parameter_text(alpha, beta)
        self._emit_progress(
            status=f"Running baselines for {self.ablation_label} with {parameter_text}...",
            phase="baselines",
        )
        rows = []

        self._emit_progress(
            status="Running PageRank baseline...",
            phase="baselines",
            baseline_algorithm=ALGORITHM_PAGERANK,
            baseline_state="running",
        )
        row = self._run_and_evaluate(
            algorithm=ALGORITHM_PAGERANK,
            alpha=alpha,
            beta=beta,
            method_label="PageRank baseline",
            variant_type="baseline",
            selection_source="baseline",
            ranking_filename=(
                "pagerank_baseline_"
                f"{self._parameter_filename(None, self._reported_parameter('beta', beta))}_ranking.tsv"
            ),
            alpha_used="No",
            beta_used=self._flag_text(self.ablation_config["beta_used"]),
            note=f"alpha ignored for Original PageRank; {parameter_text}",
            save_ranking=True,
        )
        rows.append(row)
        self._emit_progress(
            status="PageRank baseline completed.",
            phase="baselines",
            baseline_algorithm=ALGORITHM_PAGERANK,
            baseline_state="completed",
            baseline_row=row,
        )

        self._emit_progress(
            status="Running BRWR Lite baseline...",
            phase="baselines",
            baseline_algorithm=ALGORITHM_BRWR,
            baseline_state="running",
        )
        row = self._run_and_evaluate(
            algorithm=ALGORITHM_BRWR,
            alpha=alpha,
            beta=beta,
            method_label="BRWR Lite baseline",
            variant_type="baseline",
            selection_source="baseline",
            ranking_filename=(
                "brwr_baseline_"
                f"{self._parameter_filename(self._reported_parameter('alpha', alpha), self._reported_parameter('beta', beta))}_ranking.tsv"
            ),
            alpha_used=self._flag_text(self.ablation_config["alpha_used"]),
            beta_used=self._flag_text(self.ablation_config["beta_used"]),
            note=f"baseline {parameter_text}",
            save_ranking=True,
        )
        rows.append(row)
        self._emit_progress(
            status="BRWR Lite baseline completed.",
            phase="baselines",
            baseline_algorithm=ALGORITHM_BRWR,
            baseline_state="completed",
            baseline_row=row,
        )

        self._emit_progress(
            status="Running BioRank Lite baseline...",
            phase="baselines",
            baseline_algorithm=ALGORITHM_BIORANK,
            baseline_state="running",
        )
        row = self._run_and_evaluate(
            algorithm=ALGORITHM_BIORANK,
            alpha=alpha,
            beta=beta,
            method_label="BioRank Lite baseline",
            variant_type="baseline",
            selection_source="baseline",
            ranking_filename=(
                "biorank_lite_baseline_"
                f"{self._parameter_filename(self._reported_parameter('alpha', alpha), self._reported_parameter('beta', beta))}_ranking.tsv"
            ),
            alpha_used=self._flag_text(self.ablation_config["alpha_used"]),
            beta_used=self._flag_text(self.ablation_config["beta_used"]),
            note=f"baseline {parameter_text}",
            save_ranking=True,
        )
        rows.append(row)
        self._emit_progress(
            status="BioRank Lite baseline completed.",
            phase="baselines",
            baseline_algorithm=ALGORITHM_BIORANK,
            baseline_state="completed",
            baseline_row=row,
        )
        self._emit_progress(status="Baselines completed.", phase="baselines")
        return rows

    def _run_biorank_optuna(self):
        try:
            import optuna
            from optuna.samplers import NSGAIISampler
        except ImportError as exc:
            raise RuntimeError("Optuna is not installed. Install requirements.txt before running optimization.") from exc

        study = optuna.create_study(
            directions=["maximize", "maximize", "maximize"],
            sampler=NSGAIISampler(seed=self.random_seed),
            storage=f"sqlite:///{(self.output_dir / 'optuna_study.db').resolve().as_posix()}",
            load_if_exists=True,
        )
        self._enqueue_boundary_trials(study)

        def objective(trial):
            self._check_cancelled()
            alpha, beta = self._trial_parameters(trial)
            reported_alpha = self._reported_parameter("alpha", alpha)
            reported_beta = self._reported_parameter("beta", beta)
            self._emit_progress(
                status=f"Running {self.ablation_label} trial {trial.number + 1}/{self.n_trials}",
                phase="optuna",
                trial_number=trial.number,
                alpha=reported_alpha,
                beta=reported_beta,
                effective_alpha=alpha,
                effective_beta=beta,
                ablation_mode=self.ablation_mode,
                ablation_label=self.ablation_label,
            )
            row = self._run_biorank_trial(trial.number, alpha, beta)
            self.trial_rows.append(row)
            self._append_tsv_row(self.biorank_trial_history_path, TRIAL_FIELDS, row)
            complete_rows = [item for item in self.trial_rows if item["state"] == "COMPLETE"]
            best_row = max(complete_rows, key=self._objective_rank_key) if complete_rows else None
            trial.set_user_attr("recall_at_15", row["recall_at_15"])
            trial.set_user_attr("ndcg_at_15", row["ndcg_at_15"])
            trial.set_user_attr("common_genes_top_15", row["common_genes_top_15"])
            trial.set_user_attr("recall_at_100", row["recall_at_100"])
            trial.set_user_attr("ndcg_at_100", row["ndcg_at_100"])
            trial.set_user_attr("common_genes_top_100", row["common_genes_top_100"])
            trial.set_user_attr("selection_score", row["selection_score"])
            self._emit_progress(
                status=f"Finished {self.ablation_label} trial {trial.number + 1}/{self.n_trials}",
                phase="optuna",
                trial_number=trial.number,
                alpha=reported_alpha,
                beta=reported_beta,
                effective_alpha=alpha,
                effective_beta=beta,
                ablation_mode=self.ablation_mode,
                ablation_label=self.ablation_label,
                metrics=row,
                best_row=best_row,
            )
            return (
                row["ndcg_at_100"],
                row["recall_at_100"],
                row["common_genes_top_100"],
            )

        try:
            study.optimize(objective, n_trials=self.n_trials, n_jobs=1)
        except OptimizationCancelled:
            self._log("Optimization cancelled by user.")
            raise

        pareto_rows = self._write_pareto_trials(study)
        return self.trial_rows, pareto_rows

    def _enqueue_boundary_trials(self, study):
        boundary_trials = self._boundary_param_sets()[: self.n_trials]
        for params in boundary_trials:
            study.enqueue_trial(params)
        if boundary_trials:
            formatted = ", ".join(str(params) for params in boundary_trials)
            self._log(f"Queued exact search-space boundary trials: {formatted}")

    def _boundary_param_sets(self):
        dimensions = []
        if self.ablation_config["alpha_used"]:
            dimensions.append(("alpha", tuple(float(value) for value in self.alpha_range)))
        if self.ablation_config["beta_used"]:
            dimensions.append(("beta", tuple(float(value) for value in self.beta_range)))

        candidates = [
            dict(zip((name for name, _values in dimensions), values))
            for values in itertools.product(*(values for _name, values in dimensions))
        ]
        unique = []
        seen = set()
        for params in candidates:
            key = tuple(params.items())
            if key in seen:
                continue
            seen.add(key)
            unique.append(params)
        return unique

    def _run_biorank_trial(self, trial_number, alpha, beta):
        start = time.perf_counter()
        row = {
            "trial_number": trial_number,
            "ablation_mode": self.ablation_mode,
            "ablation_label": self.ablation_label,
            "alpha": self._reported_parameter("alpha", alpha),
            "beta": self._reported_parameter("beta", beta),
            "alpha_used": self._flag_text(self.ablation_config["alpha_used"]),
            "beta_used": self._flag_text(self.ablation_config["beta_used"]),
            "recall_at_15": 0.0,
            "ndcg_at_15": 0.0,
            "common_genes_top_15": 0,
            "recall_at_100": 0.0,
            "ndcg_at_100": 0.0,
            "common_genes_top_100": 0,
            "all_hits": 0,
            "mapped_genes": 0,
            "selection_score": 0.0,
            "state": "COMPLETE",
            "duration_seconds": 0.0,
            "error_message": "",
        }
        try:
            metrics = self._run_and_score(
                ALGORITHM_BIORANK,
                alpha,
                beta,
                output_file_path=None,
            )
            row.update(metrics)
            row["selection_score"] = optuna_display_score(
                row["recall_at_15"],
                row["ndcg_at_15"],
                row["recall_at_100"],
                row["ndcg_at_100"],
            )
        except Exception as exc:
            if self.cancellation_event is not None and self.cancellation_event.is_set():
                raise OptimizationCancelled("Optimization cancelled by user.") from exc
            row["state"] = "FAIL"
            row["error_message"] = str(exc)
            self._log(f"{self.ablation_label} trial {trial_number} failed: {exc}")
        finally:
            row["duration_seconds"] = time.perf_counter() - start
        return row

    def _run_and_evaluate(
        self,
        algorithm,
        alpha,
        beta,
        method_label,
        variant_type,
        selection_source,
        ranking_filename,
        alpha_used,
        beta_used,
        note,
        save_ranking,
    ):
        ranking_path = self.rankings_dir / ranking_filename
        metrics = self._run_and_score(
            algorithm,
            alpha,
            beta,
            output_file_path=str(ranking_path) if save_ranking else None,
            reuse_baseline_network=variant_type == "baseline",
        )
        score = optuna_display_score(
            metrics["recall_at_15"],
            metrics["ndcg_at_15"],
            metrics["recall_at_100"],
            metrics["ndcg_at_100"],
        )
        return {
            "method_label": method_label,
            "algorithm": algorithm,
            "variant_type": variant_type,
            "selection_source": selection_source,
            "ablation_mode": self.ablation_mode,
            "ablation_label": self.ablation_label,
            "alpha": alpha if alpha_used == "Yes" else None,
            "beta": beta if beta_used == "Yes" else None,
            "alpha_used": alpha_used,
            "beta_used": beta_used,
            "recall_at_15": metrics["recall_at_15"],
            "ndcg_at_15": metrics["ndcg_at_15"],
            "common_genes_top_15": metrics["common_genes_top_15"],
            "recall_at_100": metrics["recall_at_100"],
            "ndcg_at_100": metrics["ndcg_at_100"],
            "common_genes_top_100": metrics["common_genes_top_100"],
            "all_hits": metrics["all_hits"],
            "mapped_genes": metrics["mapped_genes"],
            "selection_score": score,
            "ranking_path": str(ranking_path) if save_ranking else "",
            "note": note,
        }

    def _run_and_score(
        self,
        algorithm,
        alpha,
        beta,
        output_file_path=None,
        reuse_baseline_network=False,
        return_ranking=False,
    ):
        self._check_cancelled()

        if algorithm == ALGORITHM_BIORANK and self._can_use_fast_biorank_lite():
            return self._run_and_score_fast_biorank_lite(
                alpha,
                beta,
                output_file_path=output_file_path,
                return_ranking=return_ranking,
            )

        def emit_pipeline_progress(payload):
            status = payload.get("status", "Running ranking pipeline...")
            self._emit_progress(
                **{
                    **payload,
                    "status": status,
                    "phase": payload.get("phase", "pipeline"),
                    "algorithm": algorithm,
                    "alpha": alpha,
                    "beta": beta,
                }
            )

        try:
            should_reuse_network = reuse_baseline_network or not self.ablation_config["beta_used"]
            if (
                should_reuse_network
                and self._baseline_network_runner is not None
                and self._baseline_network_beta == float(beta)
            ):
                runner = self._baseline_network_runner
                runner.alpha = alpha
                runner.beta = beta
                runner.algorithm = algorithm
                runner.output_file_path = output_file_path
                runner.cancellation_event = self.cancellation_event
                runner.progress_callback = emit_pipeline_progress
                self._emit_progress(
                    status=f"Reusing prepared beta={beta} network for {algorithm}.",
                    phase="baselines" if reuse_baseline_network else "pipeline",
                    algorithm=algorithm,
                    alpha=alpha,
                    beta=beta,
                )
            else:
                runner = BioRankCancerGeneRanking(
                    ppi_file_path=self.input_paths["ppi_file_path"],
                    co_expression_file_path=self._optional_input("co_expression_file_path"),
                    seed_file_path=self.input_paths["seed_file_path"],
                    secondary_seed_file_path=self._optional_input("secondary_seed_file_path"),
                    map__gene__ontologies_file_path=self._optional_input("map__gene__ontologies_file_path"),
                    disease_ontology_file_path=self._optional_input("disease_ontology_file_path"),
                    matrix_aggregation_policy=self.ablation_config["matrix_aggregation_policy"],
                    personalization_vector_creation_policies=self.ablation_config[
                        "personalization_vector_creation_policies"
                    ],
                    personalization_vector_aggregation_policy="Sum",
                    alpha=alpha,
                    beta=beta,
                    network_weight_flag=self.ablation_config["network_weight_flag"],
                    algorithm=algorithm,
                    output_file_path=output_file_path,
                    auto_run=False,
                    cancellation_event=self.cancellation_event,
                    progress_callback=emit_pipeline_progress,
                    prepared_input_cache=self._prepared_input_cache,
                    matrix_aggregation_cache=self._matrix_aggregation_cache,
                    personalization_vector_cache=self._personalization_vector_cache,
                )
                runner.prepare_network()
                if should_reuse_network:
                    self._baseline_network_runner = runner
                    self._baseline_network_beta = float(beta)
            self._check_cancelled()
            runner.execute_ranking()
            self._check_cancelled()
            ranked_list = list(runner.ranked_list)
            ranked_genes = [gene for gene, _score in ranked_list]
            metrics_100 = evaluate_ranking_against_oncokb(
                ranked_genes,
                self.truth_genes,
                gene_mapping=self.gene_mapping,
                recall_k=100,
                ndcg_k=100,
                precision_k=self.precision_k,
            )
            metrics_15 = evaluate_ranking_against_oncokb(
                ranked_genes,
                self.truth_genes,
                gene_mapping=self.gene_mapping,
                recall_k=15,
                ndcg_k=15,
                precision_k=self.precision_k,
            )
            result = {
                "recall_at_15": metrics_15["recall"],
                "ndcg_at_15": metrics_15["ndcg"],
                "common_genes_top_15": metrics_15["common_genes"],
                "recall_at_100": metrics_100["recall"],
                "ndcg_at_100": metrics_100["ndcg"],
                "common_genes_top_100": metrics_100["common_genes"],
                "all_hits": metrics_100["all_hits"],
                "mapped_genes": metrics_100["mapped_genes"],
            }
            if return_ranking:
                return result, ranked_list
            return result
        except Exception as exc:
            if self.cancellation_event is not None and self.cancellation_event.is_set():
                raise OptimizationCancelled("Optimization cancelled by user.") from exc
            raise

    def _run_and_score_fast_biorank_lite(
        self,
        alpha,
        beta,
        output_file_path=None,
        return_ranking=False,
    ):
        try:
            context = self._get_fast_biorank_lite_context()
            ranked_list = context.run(alpha, beta)
            ranked_genes = [gene for gene, _score in ranked_list]
            metrics_100 = evaluate_ranking_against_oncokb(
                ranked_genes,
                self.truth_genes,
                gene_mapping=self.gene_mapping,
                recall_k=100,
                ndcg_k=100,
                precision_k=self.precision_k,
            )
            metrics_15 = evaluate_ranking_against_oncokb(
                ranked_genes,
                self.truth_genes,
                gene_mapping=self.gene_mapping,
                recall_k=15,
                ndcg_k=15,
                precision_k=self.precision_k,
            )
            result = {
                "recall_at_15": metrics_15["recall"],
                "ndcg_at_15": metrics_15["ndcg"],
                "common_genes_top_15": metrics_15["common_genes"],
                "recall_at_100": metrics_100["recall"],
                "ndcg_at_100": metrics_100["ndcg"],
                "common_genes_top_100": metrics_100["common_genes"],
                "all_hits": metrics_100["all_hits"],
                "mapped_genes": metrics_100["mapped_genes"],
            }
            if output_file_path is not None:
                self._write_ranking_tsv(Path(output_file_path), ranked_list)
            if return_ranking:
                return result, ranked_list
            return result
        except Exception as exc:
            if self.cancellation_event is not None and self.cancellation_event.is_set():
                raise OptimizationCancelled("Optimization cancelled by user.") from exc
            raise

    def _get_fast_biorank_lite_context(self):
        if self._fast_biorank_lite_context is None:
            self._fast_biorank_lite_context = FastBioRankLiteContext(
                self.input_paths,
                self.ablation_config,
                cancellation_event=self.cancellation_event,
                progress_callback=lambda payload: self._emit_progress(**payload),
            )
        return self._fast_biorank_lite_context

    def _can_use_fast_biorank_lite(self):
        for key in required_input_keys(self.ablation_mode):
            path = self.input_paths.get(key)
            if not path or not os.path.exists(path):
                return False
        return True

    def select_biorank_candidates(self, trial_rows, pareto_rows):
        complete_rows = [row for row in trial_rows if row["state"] == "COMPLETE"]
        if not complete_rows:
            return []

        def by_objectives(rows):
            return sorted(rows, key=self._objective_rank_key, reverse=True)

        selected = []
        selected_trials = set()

        if self.candidate_selection_mode == SELECTION_MODE_PARETO:
            pareto_trial_numbers = {row["trial_number"] for row in pareto_rows}
            pareto_candidates = [row for row in complete_rows if row["trial_number"] in pareto_trial_numbers]
            for row in by_objectives(pareto_candidates):
                selected.append({**row, "selection_source": "pareto_selected"})
                selected_trials.add(row["trial_number"])
                if len(selected) >= self.max_selected_candidates:
                    return self._rank_selected_candidates(selected)

        for row in by_objectives(complete_rows):
            if row["trial_number"] in selected_trials:
                continue
            selected.append({**row, "selection_source": "top_objective_metrics"})
            selected_trials.add(row["trial_number"])
            if len(selected) >= self.max_selected_candidates:
                break

        return self._rank_selected_candidates(selected)

    def _rank_selected_candidates(self, rows):
        ranked_rows = []
        for index, row in enumerate(rows, start=1):
            ranked_rows.append({"candidate_rank": index, **row})
        return ranked_rows

    def generate_selected_candidate_rankings(self, candidate_rows):
        ranked_rows = []
        for row in candidate_rows:
            candidate_rank = int(row["candidate_rank"])
            filename = (
                f"biorank_lite_selected{candidate_rank}_"
                f"{self._parameter_filename(row.get('alpha'), row.get('beta'))}_ranking.tsv"
            )
            ranking_path = self.rankings_dir / filename
            alpha = self._effective_parameter("alpha", row.get("alpha"))
            beta = self._effective_parameter("beta", row.get("beta"))
            _metrics, ranked_list = self._run_and_score(
                ALGORITHM_BIORANK,
                alpha,
                beta,
                output_file_path=None,
                return_ranking=True,
            )
            self._write_ranking_tsv(ranking_path, ranked_list)
            ranked_rows.append({**row, "ranking_path": str(ranking_path)})
        return ranked_rows

    def build_comparison_summary(self, baseline_rows, candidate_rows):
        rows = []
        for index, row in enumerate(baseline_rows, start=1):
            rows.append({"row_order": index, **row})
        start_index = len(rows) + 1
        for offset, row in enumerate(candidate_rows, start=0):
            rows.append(
                {
                    "row_order": start_index + offset,
                    "method_label": f"BioRank Lite selected #{row['candidate_rank']}",
                    "algorithm": ALGORITHM_BIORANK,
                    "variant_type": "optimized_candidate",
                    "selection_source": row["selection_source"],
                    "ablation_mode": self.ablation_mode,
                    "ablation_label": self.ablation_label,
                    "alpha": row["alpha"],
                    "beta": row["beta"],
                    "alpha_used": self._flag_text(self.ablation_config["alpha_used"]),
                    "beta_used": self._flag_text(self.ablation_config["beta_used"]),
                    "recall_at_15": row["recall_at_15"],
                    "ndcg_at_15": row["ndcg_at_15"],
                    "common_genes_top_15": row["common_genes_top_15"],
                    "recall_at_100": row["recall_at_100"],
                    "ndcg_at_100": row["ndcg_at_100"],
                    "common_genes_top_100": row["common_genes_top_100"],
                    "all_hits": row["all_hits"],
                    "mapped_genes": row["mapped_genes"],
                    "selection_score": row["selection_score"],
                    "ranking_path": row["ranking_path"],
                    "note": "BioRank Lite optimized selected candidate",
                }
            )
        return rows

    def save_outputs(self):
        self._write_tsv(self.biorank_trial_history_path, TRIAL_FIELDS, self.trial_rows)
        self._write_tsv(self.selected_candidates_path, SELECTED_CANDIDATE_FIELDS, self.selected_candidate_rows)
        self._write_tsv(self.comparison_summary_path, COMPARISON_FIELDS, self.comparison_rows)
        payload = {
            "cancer_type": self.cancer_type,
            "ablation_mode": self.ablation_mode,
            "ablation_label": self.ablation_label,
            "pipeline_config": self.ablation_config,
            "active_optimization_parameters": self._active_parameters(),
            "inactive_parameter_values": {
                name: self.ablation_config[f"fixed_{name}"]
                for name in ("alpha", "beta")
                if not self.ablation_config[f"{name}_used"]
            },
            "optimization_type": "multi_objective",
            "objectives": [
                "maximize nDCG@100",
                "maximize Recall@100",
                "maximize Common genes@100",
            ],
            "sampler": "NSGAIISampler",
            "random_seed": self.random_seed,
            "boundary_trials": self._boundary_param_sets()[: self.n_trials],
            "candidate_selection_rank": "nDCG@100, then Recall@100, then Common@100",
            "display_score_note": "Legacy selection_score is retained in TSV/JSON for backward compatibility only; UI candidate selection uses nDCG@100, Recall@100, and Common@100.",
            "candidate_selection_mode": self.candidate_selection_mode,
            "max_selected_candidates": self.max_selected_candidates,
            "n_trials": self.n_trials,
            "alpha_range": list(self.alpha_range) if self.ablation_config["alpha_used"] else None,
            "beta_range": list(self.beta_range) if self.ablation_config["beta_used"] else None,
            "validation_mode": self.validation_mode,
            "validation_file_path": self.validation_file_path,
            "validation_gene_column": self.validation_gene_column,
            "baseline_alpha": BASELINE_ALPHA if self.ablation_config["alpha_used"] else None,
            "baseline_beta": BASELINE_BETA if self.ablation_config["beta_used"] else None,
            "metric_config": self.metric_config,
            "prefer_balanced_top5": self.prefer_balanced_top5,
            "selected_candidates": self.selected_candidate_rows,
            "output_files": {
                "comparison_summary": str(self.comparison_summary_path),
                "biorank_trial_history": str(self.biorank_trial_history_path),
                "selected_biorank_candidates": str(self.selected_candidates_path),
                "biorank_pareto_trials": str(self.biorank_pareto_trials_path),
                "logs": str(self.log_path),
            },
        }
        with open(self.summary_path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)

    def _write_pareto_trials(self, study):
        rows = []
        by_trial = {row["trial_number"]: row for row in self.trial_rows}
        for trial in study.best_trials:
            source = by_trial.get(trial.number)
            if not source:
                continue
            rows.append(
                {
                    "trial_number": trial.number,
                    "ablation_mode": self.ablation_mode,
                    "ablation_label": self.ablation_label,
                    "alpha": trial.params.get("alpha"),
                    "beta": trial.params.get("beta"),
                    "alpha_used": self._flag_text(self.ablation_config["alpha_used"]),
                    "beta_used": self._flag_text(self.ablation_config["beta_used"]),
                    "recall_at_15": source["recall_at_15"],
                    "ndcg_at_15": source["ndcg_at_15"],
                    "common_genes_top_15": source["common_genes_top_15"],
                    "recall_at_100": source["recall_at_100"],
                    "ndcg_at_100": source["ndcg_at_100"],
                    "common_genes_top_100": source["common_genes_top_100"],
                    "selection_score": source["selection_score"],
                }
            )
        self._write_tsv(self.biorank_pareto_trials_path, PARETO_FIELDS, rows)
        return rows

    def _objective_rank_key(self, row):
        return (
            self._safe_float(row.get("ndcg_at_100")),
            self._safe_float(row.get("recall_at_100")),
            self._safe_float(row.get("common_genes_top_100")),
        )

    def _optional_input(self, key):
        if key in required_input_keys(self.ablation_mode):
            return self.input_paths[key]
        return None

    def _active_parameters(self):
        return [
            name
            for name in ("alpha", "beta")
            if self.ablation_config[f"{name}_used"]
        ]

    def _trial_parameters(self, trial):
        alpha = (
            trial.suggest_float("alpha", self.alpha_range[0], self.alpha_range[1])
            if self.ablation_config["alpha_used"]
            else self.ablation_config["fixed_alpha"]
        )
        beta = (
            trial.suggest_float("beta", self.beta_range[0], self.beta_range[1])
            if self.ablation_config["beta_used"]
            else self.ablation_config["fixed_beta"]
        )
        return float(alpha), float(beta)

    def _baseline_parameters(self):
        alpha = BASELINE_ALPHA if self.ablation_config["alpha_used"] else self.ablation_config["fixed_alpha"]
        beta = BASELINE_BETA if self.ablation_config["beta_used"] else self.ablation_config["fixed_beta"]
        return float(alpha), float(beta)

    def _reported_parameter(self, name, value):
        return value if self.ablation_config[f"{name}_used"] else None

    def _effective_parameter(self, name, value):
        if self.ablation_config[f"{name}_used"]:
            return float(value)
        return float(self.ablation_config[f"fixed_{name}"])

    def _parameter_text(self, alpha, beta):
        alpha_text = f"alpha={alpha:.4f}" if self.ablation_config["alpha_used"] else "alpha=N/A"
        beta_text = f"beta={beta:.4f}" if self.ablation_config["beta_used"] else "beta=N/A"
        return f"{alpha_text}, {beta_text}"

    def _parameter_filename(self, alpha, beta):
        alpha_text = f"a{float(alpha):.4f}" if alpha is not None else "aNA"
        beta_text = f"b{float(beta):.4f}" if beta is not None else "bNA"
        return f"{alpha_text}_{beta_text}"

    def _flag_text(self, value):
        return "Yes" if value else "No"

    def _safe_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _write_tsv(self, path, fieldnames, rows):
        with open(path, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def _append_tsv_row(self, path, fieldnames, row):
        write_header = not path.exists() or path.stat().st_size == 0
        with open(path, "a", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def _write_ranking_tsv(self, path, ranked_list):
        with open(path, "w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp, delimiter="\t")
            writer.writerow(["GeneNames", "Score"])
            writer.writerows([[gene, score] for gene, score in ranked_list])

    def _validate_config(self):
        for key in required_input_keys(self.ablation_mode):
            path = self.input_paths.get(key)
            if not path:
                raise ValueError(f"Missing {key}.")
            if not os.path.exists(path):
                raise ValueError(f"Input file does not exist: {path}")
        if not os.path.exists(self.validation_file_path):
            raise ValueError(f"Validation file does not exist: {self.validation_file_path}")
        if self.gene_mapping_file_path and not os.path.exists(self.gene_mapping_file_path):
            raise ValueError(f"Gene mapping file does not exist: {self.gene_mapping_file_path}")
        if self.ablation_config["alpha_used"] and not 0.0 <= self.alpha_range[0] < self.alpha_range[1] <= 1.0:
            raise ValueError("Invalid alpha range. Use inclusive values in [0, 1] with min < max.")
        if self.ablation_config["beta_used"] and not 0.0 <= self.beta_range[0] < self.beta_range[1] <= 1.0:
            raise ValueError("Invalid beta range. Use inclusive values in [0, 1] with min < max.")
        if self.n_trials < 1:
            raise ValueError("n_trials must be at least 1.")
        if self.max_selected_candidates < 1:
            raise ValueError("max_selected_candidates must be at least 1.")
        allowed_modes = {SELECTION_MODE_PARETO, SELECTION_MODE_TOP_DISPLAY_SCORE}
        if self.candidate_selection_mode not in allowed_modes:
            raise ValueError(f"Invalid candidate selection mode: {self.candidate_selection_mode}")

    def _check_cancelled(self):
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise OptimizationCancelled("Optimization cancelled by user.")
        self._wait_if_paused()
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise OptimizationCancelled("Optimization cancelled by user.")

    def _wait_if_paused(self):
        if self.pause_event is None or not self.pause_event.is_set():
            self._pause_announced = False
            return

        if not self._pause_announced:
            self._pause_announced = True
            self._emit_progress(
                status="Optimization paused safely. Resume to continue with the next checkpoint.",
                phase="paused",
            )

        while self.pause_event.is_set():
            if self.cancellation_event is not None and self.cancellation_event.is_set():
                raise OptimizationCancelled("Optimization cancelled by user.")
            time.sleep(0.2)

        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise OptimizationCancelled("Optimization cancelled by user.")
        self._pause_announced = False
        self._emit_progress(status="Optimization resumed.", phase="optuna")

    def _emit_progress(self, **payload):
        status = payload.get("status")
        if status:
            self._log(status)
        if self.progress_callback is not None:
            self.progress_callback(payload)

    def _log(self, message):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as fp:
            fp.write(message + "\n")
