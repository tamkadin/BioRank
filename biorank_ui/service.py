import csv
import os
import time
from datetime import datetime

from biorank_ui.config import (
    ALGORITHM_LABELS,
    ALGORITHM_BIORANK_LITE,
    ALGORITHM_ORIGINAL_PAGERANK,
    DEFAULT_ALPHA_MAX,
    DEFAULT_ALPHA_MIN,
    DEFAULT_BETA_MAX,
    DEFAULT_BETA_MIN,
    DEFAULT_CANDIDATE_SELECTION_MODE,
    DEFAULT_MAX_SELECTED_CANDIDATES,
    DEFAULT_NDCG_K,
    DEFAULT_PRECISION_K,
    DEFAULT_RECALL_K,
    GENE_MAPPING_PATH,
    ONCOKB_PATH,
    PREVIEW_EDGE_LIMIT,
    PREVIEW_NODE_LIMIT,
    build_batch_output_paths,
    build_output_paths,
    get_algorithm_slug,
    get_validation_reference_path,
    get_optuna_biorank_compare_output_base,
    state_file_paths_to_backend,
)
from BioRank.metrics.ranking_metrics import (
    evaluate_ranking_against_oncokb,
    load_gene_mapping,
    load_truth_genes,
)


class BackendService:
    def __init__(self, state):
        self.state = state
        self._prepared_runner = None
        self._prepared_signature = None

    def run_preprocessing_step(self, step_index, inputs, callback, cancel_event):
        runners = {
            1: self._run_ontology_graph_preprocessing,
            2: self._run_disease_ontology_preprocessing,
            3: self._run_tcga_preprocessing,
            4: self._run_expression_preprocessing,
        }
        runner = runners.get(step_index)
        if runner is None:
            raise ValueError(f"Unknown preprocessing step: {step_index}")
        runner(inputs, callback, cancel_event)

    def run_build_network(self, disease_code, file_map, beta, callback, cancel_event):
        callback(0.0, "Validating six BioRank input datasets...")
        input_paths = self._normalize_and_validate_input_paths(file_map)
        self._check_cancelled(cancel_event)

        callback(0.15, "Loading biological inputs and weighting PPI edges...")
        runner = self._create_runner(
            input_paths=input_paths,
            algorithm=ALGORITHM_BIORANK_LITE,
            alpha=self.state.alpha,
            beta=beta,
            output_file_path=None,
            cancel_event=cancel_event,
            progress_callback=lambda payload: callback(0.15, payload.get("status", "Building network...")),
        )
        runner.prepare_network()
        self._check_cancelled(cancel_event)

        output_paths = build_output_paths(disease_code, ALGORITHM_BIORANK_LITE)
        callback(0.85, f"Saving integrated network to {output_paths['network']}...")
        runner.save_network(output_paths["network"])

        self._prepared_runner = runner
        self._prepared_signature = self._network_signature(disease_code, input_paths, beta)
        self.state.network_summary = runner.get_network_summary()
        self.state.preview_nodes = runner.iter_network_nodes(PREVIEW_NODE_LIMIT)
        self.state.preview_edges = runner.iter_network_edges(PREVIEW_EDGE_LIMIT)
        self.state.active_network_path = output_paths["network"]
        self.state.active_run_config = {
            "disease": disease_code,
            "dataset_profile": self.state.dataset_profile,
            "evaluation_mode": self.state.evaluation_mode,
            "beta": beta,
            "input_paths": dict(input_paths),
            "network_path": output_paths["network"],
        }
        callback(1.0, "Integrated network built from real BioRank inputs.")

    def run_ranking_pipeline(self, disease_code, file_map, alpha, beta, algo_name, callback, cancel_event, output_paths=None):
        algorithm = get_algorithm_slug(algo_name)
        input_paths = self._normalize_and_validate_input_paths(file_map)
        self._validate_reference_paths(disease_code)
        output_paths = output_paths or build_output_paths(disease_code, algorithm)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        callback(0.05, f"Preparing {ALGORITHM_LABELS.get(algorithm, algorithm)} pipeline...")
        signature = self._network_signature(disease_code, input_paths, beta)
        if self._prepared_runner is not None and self._prepared_signature == signature:
            runner = self._prepared_runner
            runner.alpha = alpha
            runner.algorithm = algorithm
            runner.output_file_path = output_paths["ranking"]
            runner.cancellation_event = cancel_event
            runner.progress_callback = lambda payload: callback(0.55, payload.get("status", "Running ranking core..."))
            callback(0.20, "Using the integrated network currently shown in preview.")
            if not os.path.exists(output_paths["network"]):
                runner.save_network(output_paths["network"])
        else:
            callback(0.20, "Rebuilding integrated network for the selected beta/configuration...")
            runner = self._create_runner(
                input_paths=input_paths,
                algorithm=algorithm,
                alpha=alpha,
                beta=beta,
                output_file_path=output_paths["ranking"],
                cancel_event=cancel_event,
                progress_callback=lambda payload: callback(0.20, payload.get("status", "Preparing ranking pipeline...")),
            )
            runner.prepare_network()
            runner.save_network(output_paths["network"])
            self._prepared_runner = runner
            self._prepared_signature = signature
            self.state.network_summary = runner.get_network_summary()
            self.state.preview_nodes = runner.iter_network_nodes(PREVIEW_NODE_LIMIT)
            self.state.preview_edges = runner.iter_network_edges(PREVIEW_EDGE_LIMIT)
            self.state.active_network_path = output_paths["network"]

        self._check_cancelled(cancel_event)
        callback(0.55, "Running ranking core until convergence...")
        runner.execute_ranking()
        self._check_cancelled(cancel_event)

        callback(0.85, "Writing ranking with gene mapping and computing OncoKB metrics...")
        self._enrich_ranking_output(output_paths["ranking"], disease_code)
        self._load_ranking_into_state(output_paths["ranking"], disease_code)
        self.state.active_result_path = output_paths["ranking"]
        self.state.active_metadata_path = ""
        self.state.active_run_id = run_id
        self.state.active_run_config = self._build_run_config(
            disease=disease_code,
            algorithm=algorithm,
            alpha=alpha,
            beta=beta,
            input_paths=input_paths,
            network_path=output_paths["network"],
            ranking_path=output_paths["ranking"],
            runtime_seconds=runner.total_runtime_seconds,
        )
        callback(1.0, f"Ranking saved with gene mapping: {output_paths['ranking']}.")

    def run_ranking_batch(self, jobs, algo_name, callback, cancel_event):
        if not jobs:
            raise ValueError("Batch ranking requires at least one job.")

        algorithm = get_algorithm_slug(algo_name)
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_rows = []
        total_jobs = len(jobs)

        for index, job in enumerate(jobs, start=1):
            self._check_cancelled(cancel_event)
            disease = job["disease"]
            alpha = float(job["alpha"])
            beta = float(job["beta"])
            output_paths = build_batch_output_paths(disease, algorithm, alpha, beta, batch_id)
            callback((index - 1) / total_jobs, f"Batch {index}/{total_jobs}: {disease} alpha={alpha:.4f} beta={beta:.4f}")

            def job_callback(progress, status):
                combined = ((index - 1) + progress) / total_jobs
                callback(combined, f"[{index}/{total_jobs}] {disease} a={alpha:.4f} b={beta:.4f}: {status}")

            self.run_ranking_pipeline(
                disease,
                job["file_map"],
                alpha,
                beta,
                algorithm,
                job_callback,
                cancel_event,
                output_paths=output_paths,
            )
            summary_rows.append(
                {
                    "job": index,
                    "disease": disease,
                    "dataset_profile": self.state.dataset_profile,
                    "evaluation_mode": self.state.evaluation_mode,
                    "algorithm": algorithm,
                    "alpha": alpha,
                    "beta": beta,
                    "ranking_path": output_paths["ranking"],
                    "network_path": output_paths["network"],
                    "recall_15": self.state.kpi_metrics.get("recall_15", 0.0),
                    "ndcg_15": self.state.kpi_metrics.get("ndcg_15", 0.0),
                    "recall_100": self.state.kpi_metrics.get("recall_100", 0.0),
                    "ndcg_100": self.state.kpi_metrics.get("ndcg_100", 0.0),
                    "common_15": self.state.kpi_metrics.get("common_15", 0),
                    "common_100": self.state.kpi_metrics.get("common_100", 0),
                }
            )

        self._write_batch_summary(summary_rows)
        callback(1.0, f"Batch ranking completed: {total_jobs} jobs.")

    def run_optuna_tuning(self, disease_code, file_map, n_trials, seed, callback, cancel_event):
        from BioRank.optimization.biorank_alpha_beta_optimizer import (
            BioRankAlphaBetaOptimizer,
            OptimizationCancelled,
        )

        input_paths = self._normalize_and_validate_input_paths(file_map)
        self._validate_reference_paths(disease_code)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = get_optuna_biorank_compare_output_base(disease_code) / timestamp
        self.state.reset_optuna(max_trials=n_trials)
        start_time = time.perf_counter()
        live_baseline_rows = {}

        def progress_adapter(payload):
            self.state.optuna_elapsed_time = time.perf_counter() - start_time
            self.state.optuna_phase = payload.get("phase", self.state.optuna_phase)
            status = payload.get("status", "Running optimization...")
            self.state.optuna_status_text = status

            baseline_algorithm = payload.get("baseline_algorithm")
            baseline_state = payload.get("baseline_state")
            if baseline_algorithm and baseline_state:
                self.state.optuna_baselines[baseline_algorithm] = baseline_state
            baseline_row = payload.get("baseline_row")
            if baseline_row:
                live_baseline_rows[baseline_row.get("algorithm", baseline_algorithm)] = self._comparison_tuple_from_optimizer_row(baseline_row)
                self._update_live_optuna_comparison(live_baseline_rows)

            trial_number = payload.get("trial_number")
            if trial_number is not None:
                self.state.optuna_current_trial = int(trial_number) + 1
                alpha = payload.get("alpha")
                beta = payload.get("beta")
                if alpha is not None and beta is not None:
                    status = f"{status} | alpha={float(alpha):.4f}, beta={float(beta):.4f}"
                    self.state.optuna_status_text = status

            metrics = payload.get("metrics") or {}
            if metrics and payload.get("alpha") is not None and payload.get("beta") is not None:
                self.state.optuna_trials.append(
                    {
                        "trial_id": int(trial_number) + 1,
                        "alpha": float(payload["alpha"]),
                        "beta": float(payload["beta"]),
                        "recall_15": float(metrics.get("recall_at_15", 0.0)),
                        "ndcg_15": float(metrics.get("ndcg_at_15", 0.0)),
                        "common_15": int(float(metrics.get("common_genes_top_15", 0))),
                        "recall_100": float(metrics.get("recall_at_100", 0.0)),
                        "ndcg_100": float(metrics.get("ndcg_at_100", 0.0)),
                        "common_100": int(float(metrics.get("common_genes_top_100", 0))),
                        "display_score": float(metrics.get("selection_score", 0.0)),
                    }
                )
                self.state.add_optuna_log(
                    "Trial {}/{} complete: alpha={:.4f}, beta={:.4f}, nDCG@15={:.4f}, Recall@15={:.4f}, Common@15={}, nDCG@100={:.4f}, Recall@100={:.4f}, Common@100={}".format(
                        self.state.optuna_current_trial,
                        int(n_trials),
                        float(payload["alpha"]),
                        float(payload["beta"]),
                        float(metrics.get("ndcg_at_15", 0.0)),
                        float(metrics.get("recall_at_15", 0.0)),
                        int(float(metrics.get("common_genes_top_15", 0))),
                        float(metrics.get("ndcg_at_100", 0.0)),
                        float(metrics.get("recall_at_100", 0.0)),
                        int(float(metrics.get("common_genes_top_100", 0))),
                    )
                )
                self._update_live_optuna_comparison(live_baseline_rows)
            elif status:
                self.state.add_optuna_log(status)

            progress = self.state.optuna_current_trial / max(int(n_trials), 1)
            callback(progress, payload.get("status", "Running optimization..."))

        validation_path = self._validation_reference_path(disease_code)
        optimizer = BioRankAlphaBetaOptimizer(
            cancer_type=disease_code,
            input_paths=input_paths,
            validation_file_path=validation_path,
            validation_gene_column="Gene",
            gene_mapping_file_path=GENE_MAPPING_PATH,
            alpha_range=(DEFAULT_ALPHA_MIN, DEFAULT_ALPHA_MAX),
            beta_range=(DEFAULT_BETA_MIN, DEFAULT_BETA_MAX),
            n_trials=int(n_trials),
            metric_config={
                "recall_k": DEFAULT_RECALL_K,
                "ndcg_k": DEFAULT_NDCG_K,
                "precision_k": DEFAULT_PRECISION_K,
            },
            output_dir=str(output_dir),
            prefer_balanced_top5=False,
            random_seed=int(seed),
            candidate_selection_mode=DEFAULT_CANDIDATE_SELECTION_MODE,
            max_selected_candidates=DEFAULT_MAX_SELECTED_CANDIDATES,
            validation_mode=self.state.evaluation_mode,
            cancellation_event=cancel_event,
            progress_callback=progress_adapter,
        )

        try:
            result = optimizer.run()
        except OptimizationCancelled as exc:
            raise InterruptedError(str(exc)) from exc

        self._load_optimizer_result(result)
        self.state.optuna_elapsed_time = time.perf_counter() - start_time
        self.state.optuna_phase = "completed"
        self.state.optuna_status_text = f"Optimization completed. Output: {result.output_dir}"
        self.state.add_optuna_log(self.state.optuna_status_text)
        callback(1.0, f"Optimization completed. Output: {result.output_dir}")
        return result

    def _update_live_optuna_comparison(self, baseline_rows):
        baseline_order = ("pagerank", "random_walk", "biorank_lite")
        rows = [baseline_rows[key] for key in baseline_order if key in baseline_rows]
        top_trials = sorted(
            self.state.optuna_trials,
            key=self._trial_objective_key,
            reverse=True,
        )[:DEFAULT_MAX_SELECTED_CANDIDATES]
        for trial in top_trials:
            rows.append(
                (
                    f"BioRank trial #{trial['trial_id']}",
                    self._fmt(trial.get("alpha")),
                    self._fmt(trial.get("beta")),
                    self._fmt(trial.get("ndcg_15")),
                    self._fmt(trial.get("recall_15")),
                    str(trial.get("common_15", 0)),
                    self._fmt(trial.get("ndcg_100")),
                    self._fmt(trial.get("recall_100")),
                    str(trial.get("common_100", 0)),
                )
            )
        self.state.optuna_comparison = rows

    def _comparison_tuple_from_optimizer_row(self, row):
        alpha = "No (Uniform)" if row.get("alpha_used") == "No" else self._fmt(row.get("alpha"))
        return (
            row.get("method_label", ""),
            alpha,
            self._fmt(row.get("beta")),
            self._fmt(row.get("ndcg_at_15")),
            self._fmt(row.get("recall_at_15")),
            str(int(self._float(row.get("common_genes_top_15")))),
            self._fmt(row.get("ndcg_at_100")),
            self._fmt(row.get("recall_at_100")),
            str(int(self._float(row.get("common_genes_top_100")))),
        )

    def _run_ontology_graph_preprocessing(self, inputs, callback, cancel_event):
        from data_preprocessing.compute_ontology_graph import OntologyGraph

        self._validate_preprocessing_inputs(
            inputs,
            ("go_file_path", "kegg_file_path", "reactome_file_path", "uniprot_mapping_path", "kegg_mapping_path"),
            ("output_file_path",),
        )
        self._check_cancelled(cancel_event)
        callback(0.05, "Building GO/KEGG/Reactome ontology graph...")
        OntologyGraph(
            inputs["go_file_path"], inputs["kegg_file_path"], inputs["reactome_file_path"],
            inputs["output_file_path"], inputs["uniprot_mapping_path"], inputs["kegg_mapping_path"],
        ).run()
        self._check_cancelled(cancel_event)
        self._record_preprocessing_output("ontology_map", inputs["output_file_path"])
        self.state.preprocessing_statuses[1] = "Completed"
        callback(1.0, f"Ontology graph ready: {inputs['output_file_path']}")

    def _run_disease_ontology_preprocessing(self, inputs, callback, cancel_event):
        from data_preprocessing.compute_disease_specific_ontologies import DiseaseOntologies

        self._validate_preprocessing_inputs(
            inputs, ("ontology_file_path", "seed_file_path"), ("output_file_path",)
        )
        self._check_cancelled(cancel_event)
        callback(0.1, "Running real disease-specific ontology enrichment...")
        DiseaseOntologies(
            inputs["ontology_file_path"], inputs["seed_file_path"], inputs["output_file_path"]
        ).run(overwrite=True)
        self._check_cancelled(cancel_event)
        self._record_preprocessing_output("ontology_map", inputs["ontology_file_path"])
        self._record_preprocessing_output("seed", inputs["seed_file_path"])
        self._record_preprocessing_output("disease_ontology", inputs["output_file_path"])
        self.state.preprocessing_statuses[2] = "Completed"
        callback(1.0, f"Disease-specific ontology ready: {inputs['output_file_path']}")

    def _run_tcga_preprocessing(self, inputs, callback, cancel_event):
        from data_preprocessing.TCGA_analyzer import TCGAAnalyzer

        self._validate_preprocessing_inputs(
            inputs,
            ("sample_sheet_file_path", "manifest_file_path"),
            output_dirs=("tcga_directory_path", "output_dir_path"),
        )
        self._check_cancelled(cancel_event)
        callback(0.05, "Reading GDC metadata and TCGA RNA-seq files...")
        output_files = TCGAAnalyzer(
            inputs["sample_sheet_file_path"], inputs["manifest_file_path"],
            inputs["tcga_directory_path"], inputs["output_dir_path"],
        ).create_tumor_control_table()
        self._check_cancelled(cancel_event)
        if not output_files:
            raise ValueError("No tumor/control tables were generated. Check the manifest, sample sheet, and RNA-seq directory.")
        self.state.preprocessing_statuses[3] = "Completed"
        callback(1.0, f"Created {len(output_files)} tumor/control table(s) in {inputs['output_dir_path']}")

    def _run_expression_preprocessing(self, inputs, callback, cancel_event):
        from data_preprocessing.compute_co_expression_and_de_genes import create_de_genes, get_top_correlations

        self._validate_preprocessing_inputs(
            inputs,
            ("tumor_file_path", "control_file_path", "identifier_file_path"),
            ("de_output_file_path", "coexpression_output_file_path"),
        )
        self._check_cancelled(cancel_event)
        callback(0.05, "Computing differentially expressed genes...")
        create_de_genes(
            inputs["tumor_file_path"], inputs["control_file_path"], inputs["de_output_file_path"],
            identifier_file_path=inputs["identifier_file_path"],
        )
        self._check_cancelled(cancel_event)
        callback(0.45, "Computing tumor co-expression network (Pearson > 0.7)...")
        get_top_correlations(
            inputs["tumor_file_path"], inputs["coexpression_output_file_path"],
            inputs["identifier_file_path"], threshold=0.7, is_gtex=False,
        )
        self._check_cancelled(cancel_event)
        self._record_preprocessing_output("de_genes", inputs["de_output_file_path"])
        self._record_preprocessing_output("coexpression", inputs["coexpression_output_file_path"])
        self.state.preprocessing_statuses[4] = "Completed"
        callback(1.0, "DE genes and co-expression network are ready.")

    @staticmethod
    def _validate_preprocessing_inputs(inputs, required_files, output_files=(), output_dirs=()):
        for key in required_files:
            raw_path = inputs.get(key, "")
            path = os.path.abspath(os.path.expanduser(raw_path)) if raw_path else ""
            if not path or not os.path.isfile(path):
                raise ValueError(f"Required input file does not exist: {inputs.get(key, '') or key}")
            inputs[key] = path
        for key in output_dirs:
            raw_path = inputs.get(key, "")
            path = os.path.abspath(os.path.expanduser(raw_path)) if raw_path else ""
            if key == "output_dir_path" and path:
                os.makedirs(path, exist_ok=True)
            if not path or not os.path.isdir(path):
                raise ValueError(f"Required directory does not exist: {inputs.get(key, '') or key}")
            inputs[key] = path
        for key in output_files:
            raw_path = inputs.get(key, "")
            path = os.path.abspath(os.path.expanduser(raw_path)) if raw_path else ""
            if not path:
                raise ValueError(f"Output path is required: {key}")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            inputs[key] = path

    def _record_preprocessing_output(self, state_key, path):
        self.state.file_paths[state_key] = path
        self.state.file_statuses[state_key] = (
            "Ready" if os.path.isfile(path) and os.path.getsize(path) > 0 else "Missing"
        )

    def _normalize_and_validate_input_paths(self, file_map):
        input_paths = state_file_paths_to_backend(file_map)
        expected_columns = {
            "ppi_file_path": ("PPI network", 2),
            "co_expression_file_path": ("Co-expression network", 3),
            "seed_file_path": ("Seed genes", 1),
            "secondary_seed_file_path": ("DE genes", 2),
            "map__gene__ontologies_file_path": ("Gene-ontology mapping", 3),
            "disease_ontology_file_path": ("Disease-specific ontologies", 2),
        }
        for key, (label, min_columns) in expected_columns.items():
            path = input_paths.get(key, "")
            if not path:
                raise ValueError(f"Missing required input: {label}.")
            if not os.path.exists(path):
                raise ValueError(f"{label} file does not exist: {path}")
            self._validate_min_columns(path, min_columns, label)
        return input_paths

    def _validate_reference_paths(self, disease_code=None):
        validation_path = self._validation_reference_path(disease_code)
        if not os.path.exists(validation_path):
            raise ValueError(f"Evaluation reference file does not exist: {validation_path}")
        if not os.path.exists(GENE_MAPPING_PATH):
            raise ValueError(f"Gene mapping file does not exist: {GENE_MAPPING_PATH}")

    def _validation_reference_path(self, disease_code=None):
        if not disease_code:
            return ONCOKB_PATH
        return get_validation_reference_path(
            disease_code,
            getattr(self.state, "dataset_profile", "Dataset"),
            getattr(self.state, "evaluation_mode", "OncoKB"),
        )

    def _validate_min_columns(self, path, min_columns, label):
        with open(path, newline="", encoding="utf-8-sig") as fp:
            reader = csv.reader(fp, delimiter="\t")
            for row in reader:
                if not row or all(not cell.strip() for cell in row):
                    continue
                if len(row) < min_columns:
                    raise ValueError(f"{label} must have at least {min_columns} tab-separated columns: {path}")
                return
        raise ValueError(f"{label} file is empty: {path}")

    def _create_runner(self, input_paths, algorithm, alpha, beta, output_file_path, cancel_event, progress_callback=None):
        from BioRank.BioRank import BioRankCancerGeneRanking

        return BioRankCancerGeneRanking(
            ppi_file_path=input_paths["ppi_file_path"],
            co_expression_file_path=input_paths["co_expression_file_path"],
            seed_file_path=input_paths["seed_file_path"],
            secondary_seed_file_path=input_paths["secondary_seed_file_path"],
            map__gene__ontologies_file_path=input_paths["map__gene__ontologies_file_path"],
            disease_ontology_file_path=input_paths["disease_ontology_file_path"],
            matrix_aggregation_policy="convex_combination",
            personalization_vector_creation_policies=["biological", "topological"],
            personalization_vector_aggregation_policy="Sum",
            alpha=float(alpha),
            beta=float(beta),
            network_weight_flag=True,
            algorithm=algorithm,
            output_file_path=output_file_path,
            auto_run=False,
            cancellation_event=cancel_event,
            progress_callback=progress_callback,
        )

    def _load_ranking_into_state(self, ranking_path, disease_code=None):
        rows, ranked_genes, gene_mapping, truth_genes = self._read_ranked_gene_rows(
            ranking_path,
            disease_code=disease_code,
            trust_existing_hit=True,
        )
        active_results = []

        for row in rows:
            try:
                score = float(row["Score"])
            except ValueError:
                score = 0.0
            active_results.append(
                {
                    "rank": int(row["Rank"]),
                    "ensembl_id": row["GeneNames"],
                    "gene_symbol": row["GeneSymbol"],
                    "score": score,
                    "oncokb_hit": row["OncoKBHit"] == "Yes",
                }
            )

        metrics_100 = evaluate_ranking_against_oncokb(
            ranked_genes,
            truth_genes,
            gene_mapping=gene_mapping,
            recall_k=DEFAULT_RECALL_K,
            ndcg_k=DEFAULT_NDCG_K,
            precision_k=DEFAULT_PRECISION_K,
        )
        metrics_15 = evaluate_ranking_against_oncokb(
            ranked_genes,
            truth_genes,
            gene_mapping=gene_mapping,
            recall_k=15,
            ndcg_k=15,
            precision_k=DEFAULT_PRECISION_K,
        )
        self.state.active_results = active_results
        self.state.kpi_metrics = {
            "recall_15": metrics_15["recall"],
            "recall_100": metrics_100["recall"],
            "ndcg_15": metrics_15["ndcg"],
            "ndcg_100": metrics_100["ndcg"],
            "precision": metrics_15["precision"],
            "common_15": metrics_15["common_genes"],
            "common_100": metrics_100["common_genes"],
            "all_hits": metrics_100["all_hits"],
            "mapped_ratio": metrics_100["mapped_genes"] / len(active_results) if active_results else 0.0,
        }

    def _enrich_ranking_output(self, ranking_path, disease_code=None):
        rows, _, _, _ = self._read_ranked_gene_rows(
            ranking_path,
            disease_code=disease_code,
            trust_existing_hit=False,
        )

        with open(ranking_path, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=["Rank", "GeneNames", "GeneSymbol", "Score", "OncoKBHit"],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(rows)

    def _read_ranked_gene_rows(self, ranking_path, disease_code=None, trust_existing_hit=True):
        gene_mapping = load_gene_mapping(GENE_MAPPING_PATH)
        truth_genes = load_truth_genes(self._validation_reference_path(disease_code), "Gene")
        truth_symbols = {str(gene).strip().upper() for gene in truth_genes}

        rows = []
        ranked_genes = []
        with open(ranking_path, newline="", encoding="utf-8-sig") as fp:
            reader = csv.DictReader(fp, delimiter="\t")
            for rank, row in enumerate(reader, start=1):
                ensembl_id = (row.get("GeneNames") or row.get("name") or "").strip()
                if not ensembl_id:
                    continue
                base_id = ensembl_id.split(".")[0]
                gene_symbol = (row.get("GeneSymbol") or "").strip() or gene_mapping.get(base_id, base_id)
                score = (row.get("Score") or row.get("score") or "0.0").strip()
                oncokb_hit = self._is_oncokb_hit(
                    row.get("OncoKBHit"),
                    gene_symbol,
                    truth_symbols,
                    trust_existing_hit=trust_existing_hit,
                )
                ranked_genes.append(ensembl_id)
                rows.append(
                    {
                        "Rank": rank,
                        "GeneNames": ensembl_id,
                        "GeneSymbol": gene_symbol,
                        "Score": score,
                        "OncoKBHit": "Yes" if oncokb_hit else "No",
                    }
                )
        return rows, ranked_genes, gene_mapping, truth_genes

    @staticmethod
    def _is_oncokb_hit(raw_hit_value, gene_symbol, truth_symbols, trust_existing_hit=True):
        if trust_existing_hit:
            hit_value = (raw_hit_value or "").strip().lower()
            if hit_value in {"yes", "true", "1"}:
                return True
            if hit_value in {"no", "false", "0"}:
                return False
        return gene_symbol.strip().upper() in truth_symbols

    def _load_optimizer_result(self, result):
        trial_rows = self._read_tsv(result.biorank_trial_history_path)
        self.state.optuna_trials = [
            {
                "trial_id": int(float(row.get("trial_number", 0))) + 1,
                "alpha": self._float(row.get("alpha")),
                "beta": self._float(row.get("beta")),
                "recall_15": self._float(row.get("recall_at_15")),
                "ndcg_15": self._float(row.get("ndcg_at_15")),
                "common_15": int(self._float(row.get("common_genes_top_15"))),
                "recall_100": self._float(row.get("recall_at_100")),
                "ndcg_100": self._float(row.get("ndcg_at_100")),
                "common_100": int(self._float(row.get("common_genes_top_100"))),
                "display_score": self._float(row.get("selection_score")),
            }
            for row in trial_rows
            if row.get("state") == "COMPLETE"
        ]
        comparison_rows = self._read_tsv(result.comparison_summary_path)
        self.state.optuna_comparison = []
        for row in comparison_rows:
            self.state.optuna_comparison.append(self._comparison_tuple_from_optimizer_row(row))

    def _build_run_config(self, disease, algorithm, alpha, beta, input_paths, network_path, ranking_path, runtime_seconds):
        return {
            "disease": disease,
            "dataset_profile": self.state.dataset_profile,
            "evaluation_mode": self.state.evaluation_mode,
            "algorithm": algorithm,
            "algorithm_label": ALGORITHM_LABELS.get(algorithm, algorithm),
            "alpha": alpha,
            "beta": beta,
            "alpha_used": algorithm != ALGORITHM_ORIGINAL_PAGERANK,
            "beta_used": True,
            "damping_factor": 0.85,
            "convergence_threshold": 1e-6,
            "input_paths": dict(input_paths),
            "network_path": network_path,
            "ranking_path": ranking_path,
            "runtime_seconds": runtime_seconds,
        }

    def _network_signature(self, disease_code, input_paths, beta):
        return (
            disease_code,
            round(float(beta), 8),
            tuple(sorted((key, os.path.abspath(path)) for key, path in input_paths.items())),
        )

    def _read_tsv(self, path):
        if not path or not os.path.exists(path):
            return []
        with open(path, newline="", encoding="utf-8-sig") as fp:
            return list(csv.DictReader(fp, delimiter="\t"))

    def _write_batch_summary(self, rows):
        if not rows:
            return
        fieldnames = [
            "job",
            "disease",
            "dataset_profile",
            "evaluation_mode",
            "algorithm",
            "alpha",
            "beta",
            "recall_15",
            "ndcg_15",
            "recall_100",
            "ndcg_100",
            "common_15",
            "common_100",
            "ranking_path",
            "network_path",
        ]
        rows_by_dir = {}
        for row in rows:
            rows_by_dir.setdefault(os.path.dirname(row["ranking_path"]), []).append(row)
        for output_dir, output_rows in rows_by_dir.items():
            summary_path = os.path.join(output_dir, "batch_summary.tsv")
            with open(summary_path, "w", newline="", encoding="utf-8") as fp:
                writer = csv.DictWriter(fp, fieldnames=fieldnames, delimiter="\t")
                writer.writeheader()
                writer.writerows(output_rows)

    def _float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _trial_objective_key(self, trial):
        return (
            self._float(trial.get("ndcg_100")),
            self._float(trial.get("recall_100")),
            self._float(trial.get("common_100")),
        )

    def _fmt(self, value):
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value or "")

    def _check_cancelled(self, cancel_event):
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Task cancelled by user.")
