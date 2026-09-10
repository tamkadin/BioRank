import os
import tempfile
import unittest
from pathlib import Path

from biorank_ui.config import (
    ALGORITHM_BIORANK,
    ALGORITHM_BIORANK_LITE,
    ALGORITHM_BRWR,
    ALGORITHM_BRWR_LITE,
    ALGORITHM_ORIGINAL_PAGERANK,
    DATASET_PROFILE_DEFAULT,
    DATASET_PROFILE_NEW,
    EVALUATION_MODE_DISEASE_ONCOKB,
    EVALUATION_MODE_DISPLAY_LABELS,
    EVALUATION_MODE_ONCOKB,
    SEED_PROFILE_LABELS,
    build_batch_output_paths,
    build_default_biorank_inputs,
    build_default_state_file_paths,
    get_validation_reference_path,
    build_output_paths,
    get_algorithm_slug,
    get_dataset_profile_label,
    get_dataset_profile_value,
    get_evaluation_mode_label,
    get_evaluation_mode_value,
    resolve_dataset_dir,
    state_file_paths_to_backend,
)
from biorank_ui.components import compact_parent_path
from biorank_ui.state import AppState
from biorank_ui.views.optimization_view import format_trial_timeline_row


class UiConfigWiringTest(unittest.TestCase):
    def test_seed_profile_labels_map_without_changing_internal_values(self):
        self.assertEqual(SEED_PROFILE_LABELS, ("Original", "Enriched"))
        self.assertEqual(get_dataset_profile_label(DATASET_PROFILE_DEFAULT), "Original")
        self.assertEqual(get_dataset_profile_label(DATASET_PROFILE_NEW), "Enriched")
        self.assertEqual(get_dataset_profile_value("Original"), DATASET_PROFILE_DEFAULT)
        self.assertEqual(get_dataset_profile_value("Enriched"), DATASET_PROFILE_NEW)

    def test_evaluation_mode_labels_map_without_changing_internal_values(self):
        self.assertEqual(EVALUATION_MODE_DISPLAY_LABELS, ("Pan-cancer OncoKB", "Cancer-specific OncoKB"))
        self.assertEqual(get_evaluation_mode_label(EVALUATION_MODE_ONCOKB), "Pan-cancer OncoKB")
        self.assertEqual(get_evaluation_mode_label(EVALUATION_MODE_DISEASE_ONCOKB), "Cancer-specific OncoKB")
        self.assertEqual(get_evaluation_mode_value("Pan-cancer OncoKB"), EVALUATION_MODE_ONCOKB)
        self.assertEqual(get_evaluation_mode_value("Cancer-specific OncoKB"), EVALUATION_MODE_DISEASE_ONCOKB)

    def test_renamed_dataset_directory_is_detected_from_its_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            renamed_data = repo_root / "biorank_inputs"
            for marker in ("ppi_network", "seed_set", "ontology_network"):
                (renamed_data / marker).mkdir(parents=True, exist_ok=True)

            resolved = resolve_dataset_dir(repo_root, environ={})

            self.assertEqual(resolved, renamed_data.resolve())

    def test_dataset_environment_variable_accepts_relative_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)

            resolved = resolve_dataset_dir(
                repo_root,
                environ={"BIORANK_DATA_DIR": "external_inputs"},
            )

            self.assertEqual(resolved, (repo_root / "external_inputs").resolve())

    def test_compact_parent_path_keeps_nearest_folder_context(self):
        path = os.path.join("root", "project", "data_set", "ppi_network", "HIPPIE.tsv")

        displayed = compact_parent_path(path, max_length=24)

        self.assertLessEqual(len(displayed), 24)
        self.assertTrue(displayed.endswith(os.path.join("data_set", "ppi_network")))

    def test_algorithm_labels_map_to_backend_slugs(self):
        self.assertEqual(get_algorithm_slug("BioRank"), ALGORITHM_BIORANK)
        self.assertEqual(get_algorithm_slug("BioRank Lite"), ALGORITHM_BIORANK_LITE)
        self.assertEqual(get_algorithm_slug("BRWR"), ALGORITHM_BRWR)
        self.assertEqual(get_algorithm_slug("BRWR Lite"), ALGORITHM_BRWR_LITE)
        self.assertEqual(get_algorithm_slug("Original PageRank"), ALGORITHM_ORIGINAL_PAGERANK)

    def test_output_paths_accept_ui_algorithm_label(self):
        paths = build_output_paths("BRCA", "Original PageRank")
        self.assertTrue(paths["ranking"].endswith(os.path.join("BRCA", "BRCA_original_pagerank_ranking.tsv")))
        paths = build_output_paths("BRCA", "BioRank Lite")
        self.assertTrue(paths["ranking"].endswith(os.path.join("BRCA", "BRCA_biorank_lite_ranking.tsv")))
        paths = build_output_paths("BRCA", "BRWR")
        self.assertTrue(paths["ranking"].endswith(os.path.join("BRCA", "BRCA_brwr_ranking.tsv")))

    def test_batch_output_paths_include_batch_id_and_parameter_pair(self):
        paths = build_batch_output_paths("COAD", "BioRank Lite", 0.25, 1.0, "batch123")

        self.assertIn(os.path.join("COAD", "batch_ranking", "batch123"), paths["ranking"])
        self.assertTrue(paths["ranking"].endswith("COAD_biorank_lite_a0.25_b1_ranking.tsv"))
        self.assertTrue(paths["network"].endswith("COAD_a0.25_b1_integrated_network.tsv"))

    def test_state_file_paths_map_to_backend_keys(self):
        file_paths = {
            "ppi": "ppi.tsv",
            "coexpression": "coexpr.tsv",
            "seed": "seed.txt",
            "de_genes": "de.tsv",
            "ontology_map": "ontology.tsv",
            "disease_ontology": "disease_ontology.tsv",
        }

        backend = state_file_paths_to_backend(file_paths)

        self.assertEqual(backend["ppi_file_path"], "ppi.tsv")
        self.assertEqual(backend["co_expression_file_path"], "coexpr.tsv")
        self.assertEqual(backend["seed_file_path"], "seed.txt")
        self.assertEqual(backend["secondary_seed_file_path"], "de.tsv")
        self.assertEqual(backend["map__gene__ontologies_file_path"], "ontology.tsv")
        self.assertEqual(backend["disease_ontology_file_path"], "disease_ontology.tsv")

    def test_default_state_file_paths_use_state_keys_for_batch_jobs(self):
        file_paths = build_default_state_file_paths("BRCA")

        self.assertEqual(
            set(file_paths),
            {"ppi", "coexpression", "seed", "de_genes", "ontology_map", "disease_ontology"},
        )

    def test_seed_enrichment_replaces_only_seed_and_disease_ontology(self):
        default_inputs = build_default_biorank_inputs("BRCA", DATASET_PROFILE_DEFAULT)
        new_inputs = build_default_biorank_inputs("BRCA", DATASET_PROFILE_NEW)

        self.assertIn(os.path.join("seed_set", "New", "TCGA-BRCA_seed.txt"), new_inputs["seed_file_path"])
        self.assertTrue(new_inputs["disease_ontology_file_path"].endswith("TCGA-BRCA_disease_ontologies_new_22_6.txt"))
        for key in (
            "ppi_file_path",
            "co_expression_file_path",
            "secondary_seed_file_path",
            "map__gene__ontologies_file_path",
        ):
            self.assertEqual(new_inputs[key], default_inputs[key])

    def test_seed_enrichment_does_not_fallback_when_new_files_are_missing(self):
        new_inputs = build_default_biorank_inputs("BLCA", DATASET_PROFILE_NEW)

        self.assertEqual(new_inputs["seed_file_path"], "")
        self.assertEqual(new_inputs["disease_ontology_file_path"], "")

    def test_switching_dataset_profile_refreshes_state_paths(self):
        state = AppState()

        state.set_dataset_profile(DATASET_PROFILE_NEW)

        self.assertEqual(state.dataset_profile, DATASET_PROFILE_NEW)
        self.assertIn(os.path.join("seed_set", "New"), state.file_paths["seed"])
        self.assertTrue(state.file_paths["disease_ontology"].endswith("new_22_6.txt"))

    def test_dataset_profile_switch_keeps_oncokb_evaluation(self):
        state = AppState()
        state.set_dataset_profile(DATASET_PROFILE_NEW)

        state.set_dataset_profile(DATASET_PROFILE_DEFAULT)

        self.assertEqual(state.evaluation_mode, EVALUATION_MODE_ONCOKB)
        self.assertIn(os.path.join("seed_set", "TCGA-BRCA_seed.txt"), state.file_paths["seed"])

    def test_validation_reference_is_oncokb_for_all_dataset_profiles(self):
        self.assertEqual(
            get_validation_reference_path("BRCA", DATASET_PROFILE_DEFAULT, EVALUATION_MODE_ONCOKB),
            get_validation_reference_path("BRCA", DATASET_PROFILE_NEW, EVALUATION_MODE_ONCOKB),
        )

    def test_disease_specific_validation_reference_uses_current_disease(self):
        brca_path = get_validation_reference_path("BRCA", DATASET_PROFILE_DEFAULT, EVALUATION_MODE_DISEASE_ONCOKB)
        coad_path = get_validation_reference_path("COAD", DATASET_PROFILE_DEFAULT, EVALUATION_MODE_DISEASE_ONCOKB)

        self.assertIn("BRCA", brca_path)
        self.assertIn("COAD", coad_path)
        self.assertNotEqual(brca_path, coad_path)

    def test_state_switching_disease_refreshes_disease_specific_validation(self):
        state = AppState()
        state.set_evaluation_mode(EVALUATION_MODE_DISEASE_ONCOKB)
        brca_path = state.validation_file_path

        state.set_disease("COAD")

        self.assertIn("BRCA", brca_path)
        self.assertIn("COAD", state.validation_file_path)
        self.assertNotEqual(brca_path, state.validation_file_path)

    def test_manual_disease_specific_validation_override_is_per_disease(self):
        state = AppState()
        state.set_evaluation_mode(EVALUATION_MODE_DISEASE_ONCOKB)
        state.set_validation_file_path("custom_brca.csv", disease="BRCA")
        state.set_disease("COAD")

        self.assertNotEqual(state.validation_file_path, "custom_brca.csv")

        state.set_disease("BRCA")

        self.assertEqual(state.validation_file_path, "custom_brca.csv")

    def test_beta_change_invalidates_network_and_results(self):
        state = AppState()
        state.network_summary = {"nodes": 10, "edges": 20}
        state.preview_nodes = ["A"]
        state.active_results = [{"rank": 1}]
        state.active_result_path = "ranking.tsv"

        state.set_beta(0.7)

        self.assertEqual(state.network_summary, {"nodes": 0, "edges": 0})
        self.assertEqual(state.preview_nodes, [])
        self.assertEqual(state.active_results, [])
        self.assertEqual(state.active_result_path, "")

    def test_same_parameter_values_do_not_clear_existing_results(self):
        state = AppState()
        state.active_results = [{"rank": 1, "ensembl_id": "ENSG1"}]
        state.active_result_path = "ranking.tsv"
        state.network_summary = {"nodes": 10, "edges": 20}
        state.preview_nodes = ["ENSG1"]

        state.set_alpha(state.alpha)
        state.set_beta(state.beta)
        state.set_algorithm(state.selected_algorithm)

        self.assertEqual(state.active_results, [{"rank": 1, "ensembl_id": "ENSG1"}])
        self.assertEqual(state.active_result_path, "ranking.tsv")
        self.assertEqual(state.network_summary, {"nodes": 10, "edges": 20})
        self.assertEqual(state.preview_nodes, ["ENSG1"])

    def test_optuna_reset_initializes_progress_log_state(self):
        state = AppState()

        state.reset_optuna(max_trials=12)
        state.add_optuna_log("Running PageRank baseline...")

        self.assertEqual(state.optuna_current_trial, 0)
        self.assertEqual(state.optuna_max_trials, 12)
        self.assertEqual(state.optuna_phase, "starting")
        self.assertEqual(state.optuna_baselines["pagerank"], "pending")
        self.assertRegex(state.optuna_logs[-1], r"^\[\d{2}:\d{2}:\d{2}\] Running PageRank baseline\.\.\.$")

    def test_kpi_metric_state_contains_top_15_and_top_100_fields(self):
        state = AppState()

        for key in ("recall_15", "recall_100", "ndcg_15", "ndcg_100", "common_15", "common_100"):
            self.assertIn(key, state.kpi_metrics)

    def test_trial_timeline_header_and_values_use_identical_column_offsets(self):
        columns = (
            "Trial", "Alpha", "Beta", "nDCG15", "Recall15",
            "Common15", "nDCG100", "Recall100", "Common100",
        )
        values = ("T1", "A1", "B1", "N15", "R15", "C15", "N100", "R100", "C100")
        header = format_trial_timeline_row(columns, columns)
        row = format_trial_timeline_row(columns, values)

        self.assertEqual(len(header), len(row))
        for column, value in zip(columns, values):
            self.assertEqual(header.index(column), row.index(value))


if __name__ == "__main__":
    unittest.main()
