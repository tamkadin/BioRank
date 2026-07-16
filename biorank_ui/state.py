import os
import threading
from datetime import datetime

from biorank_ui.config import (
    DATASET_PROFILE_DEFAULT,
    DATASET_PROFILES,
    DISEASES,
    EVALUATION_MODE_ONCOKB,
    EVALUATION_MODES,
    build_default_state_file_paths,
)


def default_file_paths():
    return {
        "ppi": "",
        "coexpression": "",
        "seed": "",
        "de_genes": "",
        "ontology_map": "",
        "disease_ontology": "",
    }


def default_file_statuses():
    return {key: "Missing" for key in default_file_paths()}


def default_kpi_metrics():
    return {
        "recall_15": 0.0,
        "recall_100": 0.0,
        "ndcg_15": 0.0,
        "ndcg_100": 0.0,
        "precision": 0.0,
        "common_15": 0,
        "common_100": 0,
        "all_hits": 0,
        "mapped_ratio": 0.0,
    }


class AppState:
    def __init__(self):
        self._listeners = []
        
        self.current_disease = "BRCA"
        self.dataset_profile = DATASET_PROFILE_DEFAULT
        self.evaluation_mode = EVALUATION_MODE_ONCOKB
        self.selected_algorithm = "BioRank Lite"
        self.alpha = 0.20
        self.beta = 0.20
        
        self.file_paths = default_file_paths()
        self.file_statuses = default_file_statuses()
        self.preprocessing_statuses = {1: "Pending", 2: "Pending", 3: "Pending", 4: "Pending"}
        
        # State execution statuses
        self.is_running = False
        self.progress_percentage = 0.0
        self.progress_text = "Ready"
        self.cancel_event = threading.Event()
        
        # Prioritization & Aggregate Network Results
        self.network_summary = {"nodes": 0, "edges": 0}
        self.preview_nodes = []  # list of strings
        self.preview_edges = []  # list of tuples (source, target, weight)
        self.active_results = [] # list of dicts: rank, ensembl_id, gene_symbol, score, oncokb_hit
        self.active_result_path = ""
        self.active_network_path = ""
        self.active_metadata_path = ""
        self.active_run_id = ""
        self.active_run_config = {}
        
        # KPI calculations
        self.kpi_metrics = default_kpi_metrics()
        
        # Optuna Tuning Dashboard metrics
        self.optuna_trials = []  # list of trials dicts
        self.optuna_current_trial = 0
        self.optuna_max_trials = 200
        self.optuna_elapsed_time = 0.0
        self.optuna_status_text = "Idle"
        self.optuna_phase = "idle"
        self.optuna_logs = []
        self.optuna_baselines = {
            "pagerank": "pending",
            "random_walk": "pending",
            "biorank_lite": "pending",
        }
        self.optuna_comparison = []  # comparison table rows
        self.optuna_balanced_candidates = False
        self.optuna_current_disease = ""
        self.optuna_disease_queue = []
        self.optuna_completed_diseases = []
        self.optuna_disease_summary = []
        
        # Auto-detect initial disease inputs
        self.auto_detect_files()
        
    def add_listener(self, callback):
        self._listeners.append(callback)
        
    def notify_listeners(self):
        for cb in self._listeners:
            try:
                cb()
            except Exception as e:
                print(f"Error notifying state observer: {e}")
                
    def reset_network_and_results(self):
        self.network_summary = {"nodes": 0, "edges": 0}
        self.preview_nodes = []
        self.preview_edges = []
        self.active_network_path = ""
        self.reset_results()

    def reset_results(self):
        self.active_results = []
        self.active_result_path = ""
        self.active_metadata_path = ""
        self.active_run_id = ""
        self.active_run_config = {}
        self.kpi_metrics = default_kpi_metrics()

    def reset_optuna(self, max_trials=None):
        self.optuna_trials = []
        self.optuna_current_trial = 0
        if max_trials is not None:
            self.optuna_max_trials = int(max_trials)
        self.optuna_elapsed_time = 0.0
        self.optuna_status_text = "Starting optimization..."
        self.optuna_phase = "starting"
        self.optuna_logs = []
        self.optuna_baselines = {
            "pagerank": "pending",
            "random_walk": "pending",
            "biorank_lite": "pending",
        }
        self.optuna_comparison = []

    def reset_optuna_queue(self, diseases, max_trials=None):
        self.reset_optuna(max_trials=max_trials)
        self.optuna_current_disease = ""
        self.optuna_disease_queue = list(diseases)
        self.optuna_completed_diseases = []
        self.optuna_disease_summary = []

    def set_optuna_current_disease(self, disease, remaining_queue):
        self.optuna_current_disease = disease
        self.optuna_disease_queue = list(remaining_queue)

    def add_optuna_disease_summary(self, disease, output_dir, comparison_rows):
        if not comparison_rows:
            row = {
                "disease": disease,
                "top_choice": "No completed result",
                "alpha": "",
                "beta": "",
                "ndcg_15": 0.0,
                "recall_15": 0.0,
                "common_15": 0,
                "ndcg_100": 0.0,
                "recall_100": 0.0,
                "common_100": 0,
                "output_dir": output_dir,
            }
        else:
            def objective_key(item):
                try:
                    return (float(item[6]), float(item[7]), float(item[8]))
                except (TypeError, ValueError, IndexError):
                    return (0.0, 0.0, 0.0)

            best = max(comparison_rows, key=objective_key)
            row = {
                "disease": disease,
                "top_choice": best[0],
                "alpha": best[1],
                "beta": best[2],
                "ndcg_15": best[3],
                "recall_15": best[4],
                "common_15": best[5],
                "ndcg_100": best[6],
                "recall_100": best[7],
                "common_100": best[8],
                "output_dir": output_dir,
            }
        self.optuna_disease_summary.append(row)
        self.optuna_completed_diseases.append(disease)

    def add_optuna_log(self, message):
        text = str(message)
        if not text.startswith("["):
            text = f"[{datetime.now().strftime('%H:%M:%S')}] {text}"
        self.optuna_logs.append(text)
        if len(self.optuna_logs) > 200:
            self.optuna_logs = self.optuna_logs[-200:]

    def set_alpha(self, value):
        value = float(value)
        if abs(self.alpha - value) < 1e-9:
            return
        self.alpha = value
        self.reset_results()

    def set_beta(self, value):
        value = float(value)
        if abs(self.beta - value) < 1e-9:
            return
        self.beta = value
        self.reset_network_and_results()

    def set_algorithm(self, algorithm):
        if self.selected_algorithm == algorithm:
            return
        self.selected_algorithm = algorithm
        self.reset_results()

    def set_disease(self, disease):
        if disease in DISEASES:
            self.current_disease = disease
            self.preprocessing_statuses.update({2: "Pending", 3: "Pending", 4: "Pending"})
            self.auto_detect_files()
            self.reset_network_and_results()
            self.notify_listeners()

    def set_dataset_profile(self, dataset_profile):
        if dataset_profile not in DATASET_PROFILES:
            raise ValueError(f"Unknown dataset profile: {dataset_profile}")
        if self.dataset_profile == dataset_profile:
            return
        self.dataset_profile = dataset_profile
        self.auto_detect_files()
        self.reset_network_and_results()
        self.notify_listeners()

    def set_evaluation_mode(self, evaluation_mode):
        if evaluation_mode not in EVALUATION_MODES:
            raise ValueError(f"Unknown evaluation mode: {evaluation_mode}")
        if self.evaluation_mode == evaluation_mode:
            return
        self.evaluation_mode = evaluation_mode
        self.auto_detect_files()
        self.reset_network_and_results()
        self.notify_listeners()
            
    def auto_detect_files(self):
        defaults = build_default_state_file_paths(
            self.current_disease,
            self.dataset_profile,
            self.evaluation_mode,
        )

        for state_key in self.file_paths:
            path = defaults.get(state_key, "")
            self.file_paths[state_key] = path
            if path and os.path.exists(path):
                self.file_statuses[state_key] = "Ready"
            else:
                self.file_statuses[state_key] = "Missing"
                
    def set_file_path(self, key, path):
        if key in self.file_paths:
            self.file_paths[key] = path
            if path and os.path.exists(path):
                self.file_statuses[key] = "Ready"
            else:
                self.file_statuses[key] = "Missing"
            self.reset_network_and_results()
            self.notify_listeners()
