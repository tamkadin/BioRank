import csv
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from biorank_qt import theme
from biorank_qt.workers.optimizer_worker import OptimizerWorker
from biorank_ui.config import (
    BIORANK_INPUTS,
    DEFAULT_ALPHA_MAX,
    DEFAULT_ALPHA_MIN,
    DEFAULT_BETA_MAX,
    DEFAULT_BETA_MIN,
    DEFAULT_CANDIDATE_SELECTION_MODE,
    DEFAULT_MAX_SELECTED_CANDIDATES,
    DEFAULT_NDCG_K,
    DEFAULT_OPTUNA_RANDOM_SEED,
    DEFAULT_OPTUNA_TRIALS,
    DEFAULT_PRECISION_K,
    DEFAULT_RECALL_K,
    DISEASES,
    GENE_MAPPING_PATH,
    ONCOKB_PATH,
    build_default_biorank_inputs,
    get_optuna_biorank_compare_output_base,
)


class BioRankOptimizerWindow(QWidget):
    def __init__(self, selected_disease="BRCA"):
        super().__init__()
        self.setWindowTitle("BioRank alpha/beta Optimizer")
        self.resize(1280, 820)
        self.setMinimumSize(1120, 720)

        self.input_paths = {}
        self.output_dir = None
        self.result = None
        self.worker = None
        self.worker_thread = None

        self._build_ui()
        self.disease_combo.setCurrentText(selected_disease if selected_disease in DISEASES else "BRCA")
        self.auto_fill_inputs()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._create_header())

        content = QGridLayout()
        content.setContentsMargins(18, 16, 18, 12)
        content.setHorizontalSpacing(16)
        content.setVerticalSpacing(12)
        content.setColumnStretch(0, 4)
        content.setColumnStretch(1, 5)
        content.addWidget(self._create_setup_panel(), 0, 0)
        content.addWidget(self._create_progress_panel(), 0, 1)
        content_widget = QWidget()
        content_widget.setLayout(content)
        root.addWidget(content_widget, 0)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_comparison_tab(), "Comparison")
        self.tabs.addTab(self._create_trial_history_tab(), "Trial History")
        root.addWidget(self.tabs, 1)

    def _create_header(self):
        header = QFrame()
        header.setObjectName("Header")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(24, 18, 24, 16)
        title = QLabel("BioRank alpha/beta Optimizer")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel(
            "Multi-objective Optuna optimization for BioRank Lite. PageRank, BRWR Lite, and BioRank Lite baseline use alpha=beta=0.5."
        )
        subtitle.setObjectName("HeaderSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        badges = QHBoxLayout()
        for text in ("BioRank-only optimization", "OncoKB validation", "Baselines: alpha=beta=0.5"):
            badge = QLabel(text)
            badge.setObjectName("Badge")
            badges.addWidget(badge)
        badges.addStretch(1)
        layout.addLayout(badges)
        return header

    def _create_setup_panel(self):
        panel = QFrame()
        panel.setObjectName("Card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(self._card_title("Setup"))
        disease_row = QHBoxLayout()
        disease_row.addWidget(QLabel("Disease"))
        self.disease_combo = QComboBox()
        self.disease_combo.addItems(DISEASES)
        self.disease_combo.currentTextChanged.connect(self.auto_fill_inputs)
        disease_row.addWidget(self.disease_combo)
        self.auto_fill_button = QPushButton("Auto-fill")
        self.auto_fill_button.clicked.connect(self.auto_fill_inputs)
        disease_row.addWidget(self.auto_fill_button)
        disease_row.addStretch(1)
        layout.addLayout(disease_row)

        self.input_status_labels = {}
        status_grid = QGridLayout()
        status_items = [
            ("PPI", "ppi_file_path"),
            ("Co-expression", "co_expression_file_path"),
            ("Seed", "seed_file_path"),
            ("DE genes", "secondary_seed_file_path"),
            ("Ontology", "map__gene__ontologies_file_path"),
            ("Disease ontology", "disease_ontology_file_path"),
            ("OncoKB", "oncokb"),
            ("Gene mapping", "gene_mapping"),
        ]
        for index, (label, key) in enumerate(status_items):
            name = QLabel(label)
            value = QLabel("Missing")
            value.setObjectName("Missing")
            self.input_status_labels[key] = value
            status_grid.addWidget(name, index // 2, (index % 2) * 2)
            status_grid.addWidget(value, index // 2, (index % 2) * 2 + 1)
        layout.addLayout(status_grid)

        self.advanced_button = QPushButton("Advanced Settings")
        self.advanced_button.clicked.connect(self.open_advanced_settings)
        layout.addWidget(self.advanced_button)

        layout.addWidget(self._card_title("Optimization"))
        opt_grid = QGridLayout()
        self.trials_spin = QSpinBox()
        self.trials_spin.setRange(1, 10000)
        self.trials_spin.setValue(DEFAULT_OPTUNA_TRIALS)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2_000_000_000)
        self.seed_spin.setValue(DEFAULT_OPTUNA_RANDOM_SEED)
        opt_grid.addWidget(QLabel("Trials"), 0, 0)
        opt_grid.addWidget(self.trials_spin, 0, 1)
        opt_grid.addWidget(QLabel("Random seed"), 1, 0)
        opt_grid.addWidget(self.seed_spin, 1, 1)
        seed_note = QLabel("Same seed repeats the same Optuna suggestion sequence; change it to explore a different sequence.")
        seed_note.setWordWrap(True)
        opt_grid.addWidget(seed_note, 2, 0, 1, 2)
        opt_grid.addWidget(QLabel("Alpha range: 0.0 -> 1.0 inclusive"), 3, 0, 1, 2)
        opt_grid.addWidget(QLabel("Beta range: 0.0 -> 1.0 inclusive"), 4, 0, 1, 2)
        layout.addLayout(opt_grid)

        layout.addWidget(self._card_title("Objectives"))
        objective_label = QLabel(
            "Maximize nDCG@100, Recall@100, and Common@100.\n"
            "nDCG@15, Recall@15, and display score are shown for comparison only."
        )
        objective_label.setWordWrap(True)
        layout.addWidget(objective_label)

        layout.addWidget(self._card_title("Actions"))
        action_row = QHBoxLayout()
        self.start_button = QPushButton("Start Optimization")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.start_optimization)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("DangerButton")
        self.cancel_button.clicked.connect(self.cancel_optimization)
        self.cancel_button.setEnabled(False)
        self.run_again_button = QPushButton("Run Again")
        self.run_again_button.clicked.connect(self.start_optimization)
        self.run_again_button.setEnabled(False)
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.run_again_button)
        layout.addLayout(action_row)
        layout.addStretch(1)
        return panel

    def _create_progress_panel(self):
        panel = QFrame()
        panel.setObjectName("Card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self._card_title("Progress"))
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.trial_label = QLabel("0 / 0")
        self.metrics_label = QLabel("Current metrics will appear here.")
        self.metrics_label.setWordWrap(True)
        self.best_label = QLabel("Best BioRank Lite optimized result will appear here.")
        self.best_label.setWordWrap(True)
        self.baseline_label = QLabel("PageRank baseline: pending\nBRWR Lite baseline: pending\nBioRank Lite baseline: pending")
        self.baseline_label.setWordWrap(True)
        self.output_label = QLabel("Output: not created yet")
        self.output_label.setObjectName("Muted")
        self.output_label.setWordWrap(True)
        for widget in (self.trial_label, self.baseline_label, self.metrics_label, self.best_label, self.output_label):
            layout.addWidget(widget)

        layout.addWidget(self._card_title("Quick Summary"))
        self.quick_summary_label = QLabel("Run optimization to see baseline and selected BioRank candidate results.")
        self.quick_summary_label.setWordWrap(True)
        layout.addWidget(self.quick_summary_label)
        layout.addStretch(1)
        return panel

    def _create_comparison_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.comparison_table = QTableWidget(0, 13)
        self.comparison_columns = [
            "Method",
            "Alpha",
            "Beta",
            "nDCG@15",
            "Recall@15",
            "nDCG@100",
            "Recall@100",
            "Common@100",
            "All hits",
            "Mapped genes",
            "Display score",
            "Selection source",
            "Note",
        ]
        self.comparison_table.setHorizontalHeaderLabels(self.comparison_columns)
        self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.comparison_table.horizontalHeader().setStretchLastSection(True)
        self.comparison_table.setAlternatingRowColors(True)
        layout.addWidget(self.comparison_table)
        return tab

    def _create_trial_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.trial_table = QTableWidget(0, 9)
        self.trial_columns = [
            "Trial",
            "Alpha",
            "Beta",
            "nDCG@15",
            "Recall@15",
            "nDCG@100",
            "Recall@100",
            "Common@100",
            "Display score",
        ]
        self.trial_table.setHorizontalHeaderLabels(self.trial_columns)
        self.trial_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.trial_table.horizontalHeader().setStretchLastSection(True)
        self.trial_table.setAlternatingRowColors(True)
        layout.addWidget(self.trial_table)
        return tab

    def _card_title(self, text):
        label = QLabel(text)
        label.setObjectName("CardTitle")
        return label

    def auto_fill_inputs(self):
        disease = self.disease_combo.currentText() if hasattr(self, "disease_combo") else "BRCA"
        self.input_paths = build_default_biorank_inputs(disease)
        self.oncokb_path = ONCOKB_PATH
        self.gene_mapping_path = GENE_MAPPING_PATH
        self.alpha_min = DEFAULT_ALPHA_MIN
        self.alpha_max = DEFAULT_ALPHA_MAX
        self.beta_min = DEFAULT_BETA_MIN
        self.beta_max = DEFAULT_BETA_MAX
        self.recall_k = DEFAULT_RECALL_K
        self.ndcg_k = DEFAULT_NDCG_K
        self.precision_k = DEFAULT_PRECISION_K
        self.candidate_selection_mode = DEFAULT_CANDIDATE_SELECTION_MODE
        self.max_selected_candidates = DEFAULT_MAX_SELECTED_CANDIDATES
        self._update_input_status()

    def _update_input_status(self):
        for key in [item[1] for item in BIORANK_INPUTS]:
            ready = bool(self.input_paths.get(key)) and os.path.exists(self.input_paths.get(key))
            self._set_status_label(self.input_status_labels[key], ready)
        self._set_status_label(self.input_status_labels["oncokb"], os.path.exists(getattr(self, "oncokb_path", "")))
        self._set_status_label(self.input_status_labels["gene_mapping"], os.path.exists(getattr(self, "gene_mapping_path", "")))

    def _set_status_label(self, label, ready):
        label.setText("Ready" if ready else "Missing")
        label.setObjectName("Ready" if ready else "Missing")
        label.style().unpolish(label)
        label.style().polish(label)

    def open_advanced_settings(self):
        dialog = AdvancedSettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            dialog.apply_to_window(self)
            self._update_input_status()

    def start_optimization(self):
        try:
            config = self._build_run_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid configuration", str(exc))
            return

        self.output_dir = Path(config["output_dir"])
        self.output_label.setText(f"Output: {self.output_dir}")
        self.status_label.setText("Starting optimization...")
        self.progress_bar.setValue(0)
        self.comparison_table.setRowCount(0)
        self.trial_table.setRowCount(0)

        self.worker_thread = QThread(self)
        self.worker = OptimizerWorker(config)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.handle_progress)
        self.worker.completed.connect(self.handle_completed)
        self.worker.failed.connect(self.handle_failed)
        self.worker.cancelled.connect(self.handle_cancelled)
        self.worker.completed.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker.cancelled.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self._set_running_state(True)
        self.worker_thread.start()

    def _build_run_config(self):
        missing = [label for label, key, _optional in BIORANK_INPUTS if not self.input_paths.get(key) or not os.path.exists(self.input_paths[key])]
        if missing:
            raise ValueError(f"Missing input files: {', '.join(missing)}")
        if not os.path.exists(self.oncokb_path):
            raise ValueError("Missing OncoKB/reference file.")
        if not os.path.exists(self.gene_mapping_path):
            raise ValueError("Missing gene mapping file.")
        if not 0.0 <= self.alpha_min < self.alpha_max <= 1.0:
            raise ValueError("Alpha range must use inclusive bounds in [0, 1] and satisfy min < max.")
        if not 0.0 <= self.beta_min < self.beta_max <= 1.0:
            raise ValueError("Beta range must use inclusive bounds in [0, 1] and satisfy min < max.")

        disease = self.disease_combo.currentText()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = get_optuna_biorank_compare_output_base(disease) / timestamp
        return {
            "cancer_type": disease,
            "input_paths": dict(self.input_paths),
            "validation_file_path": self.oncokb_path,
            "validation_gene_column": "Gene",
            "gene_mapping_file_path": self.gene_mapping_path,
            "alpha_range": (self.alpha_min, self.alpha_max),
            "beta_range": (self.beta_min, self.beta_max),
            "n_trials": int(self.trials_spin.value()),
            "random_seed": int(self.seed_spin.value()),
            "metric_config": {
                "recall_k": self.recall_k,
                "ndcg_k": self.ndcg_k,
                "precision_k": self.precision_k,
            },
            "prefer_balanced_top5": False,
            "candidate_selection_mode": self.candidate_selection_mode,
            "max_selected_candidates": self.max_selected_candidates,
            "output_dir": str(output_dir),
        }

    def handle_progress(self, payload):
        status = payload.get("status")
        if status:
            self.status_label.setText(status)
        trial_number = payload.get("trial_number")
        if trial_number is not None:
            current = min(int(trial_number) + 1, self.trials_spin.value())
            total = self.trials_spin.value()
            self.progress_bar.setValue(int(current * 100 / max(total, 1)))
            self.trial_label.setText(f"{current} / {total}")
        metrics = payload.get("metrics")
        if metrics:
            self.metrics_label.setText(
                "Current trial:\n"
                f"nDCG@15 = {self._fmt(metrics.get('ndcg_at_15'))}\n"
                f"Recall@15 = {self._fmt(metrics.get('recall_at_15'))}\n"
                f"nDCG@100 = {self._fmt(metrics.get('ndcg_at_100'))}\n"
                f"Recall@100 = {self._fmt(metrics.get('recall_at_100'))}\n"
                f"Common@100 = {metrics.get('common_genes_top_100', '')}"
            )
        best_row = payload.get("best_row")
        if best_row:
            self.best_label.setText(
                "Best display score so far:\n"
                f"Score = {self._fmt(best_row.get('selection_score'))}\n"
                f"alpha = {self._fmt(best_row.get('alpha'))}\n"
                f"beta = {self._fmt(best_row.get('beta'))}"
            )
        baseline_algorithm = payload.get("baseline_algorithm")
        baseline_state = payload.get("baseline_state")
        if baseline_algorithm and baseline_state:
            current_text = self.baseline_label.text().splitlines()
            labels = {
                "pagerank": "PageRank baseline",
                "random_walk": "BRWR Lite baseline",
                "biorank_lite": "BioRank Lite baseline",
            }
            target = labels.get(baseline_algorithm)
            updated = []
            for line in current_text:
                if target and line.startswith(target):
                    updated.append(f"{target}: {baseline_state}")
                else:
                    updated.append(line)
            self.baseline_label.setText("\n".join(updated))

    def handle_completed(self, result):
        self.result = result
        self._set_running_state(False)
        self.progress_bar.setValue(100)
        self.status_label.setText("Optimization completed.")
        self._load_results(result)

    def handle_failed(self, message):
        self._set_running_state(False)
        self.status_label.setText("Optimization failed.")
        QMessageBox.critical(self, "Optimization failed", message)

    def handle_cancelled(self, message):
        self._set_running_state(False)
        self.status_label.setText("Optimization cancelled.")
        QMessageBox.information(self, "Optimization cancelled", message or "Cancelled by user.")

    def cancel_optimization(self):
        if self.worker:
            self.worker.cancel()
            self.status_label.setText("Cancelling...")

    def _set_running_state(self, running):
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.run_again_button.setEnabled(not running and self.result is not None)

    def _load_results(self, result):
        rows = self._read_tsv(result.comparison_summary_path)
        self._populate_comparison(rows)
        self._populate_trial_history(result.biorank_trial_history_path)
        self._update_quick_summary(rows)
        self.tabs.setCurrentIndex(0)

    def _populate_comparison(self, rows):
        self.comparison_table.setRowCount(len(rows))
        best_values = self._best_values(
            rows,
            ["ndcg_at_15", "recall_at_15", "ndcg_at_100", "recall_at_100", "common_genes_top_100", "selection_score"],
        )
        top_row_index = self._top_row_index(rows, "selection_score")
        for row_index, row in enumerate(rows):
            alpha = "N/A" if row.get("alpha_used") == "No" else self._fmt(row.get("alpha"))
            values = [
                row.get("method_label", ""),
                alpha,
                self._fmt(row.get("beta")),
                self._fmt(row.get("ndcg_at_15")),
                self._fmt(row.get("recall_at_15")),
                self._fmt(row.get("ndcg_at_100")),
                self._fmt(row.get("recall_at_100")),
                row.get("common_genes_top_100", ""),
                row.get("all_hits", ""),
                row.get("mapped_genes", ""),
                self._fmt(row.get("selection_score")),
                row.get("selection_source", ""),
                row.get("note", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in range(1, 11):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                source_key = {
                    3: "ndcg_at_15",
                    4: "recall_at_15",
                    5: "ndcg_at_100",
                    6: "recall_at_100",
                    7: "common_genes_top_100",
                    10: "selection_score",
                }.get(column)
                if source_key and self._matches_best(row.get(source_key), best_values.get(source_key)):
                    self._mark_best_item(item)
                elif row_index == top_row_index:
                    self._mark_top_item(item)
                self.comparison_table.setItem(row_index, column, item)

    def _populate_trial_history(self, path):
        rows = self._read_tsv(path)
        self.trial_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("trial_number", ""),
                self._fmt(row.get("alpha")),
                self._fmt(row.get("beta")),
                self._fmt(row.get("ndcg_at_15")),
                self._fmt(row.get("recall_at_15")),
                self._fmt(row.get("ndcg_at_100")),
                self._fmt(row.get("recall_at_100")),
                row.get("common_genes_top_100", ""),
                self._fmt(row.get("selection_score")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.trial_table.setItem(row_index, column, item)

    def _update_quick_summary(self, rows):
        lines = []
        for row in rows[:4]:
            alpha = "N/A" if row.get("alpha_used") == "No" else self._fmt(row.get("alpha"))
            lines.append(
                f"{row.get('method_label')}: alpha={alpha}, beta={self._fmt(row.get('beta'))}, "
                f"nDCG15={self._fmt(row.get('ndcg_at_15'))}, Recall15={self._fmt(row.get('recall_at_15'))}, "
                f"nDCG100={self._fmt(row.get('ndcg_at_100'))}, Recall100={self._fmt(row.get('recall_at_100'))}"
            )
        self.quick_summary_label.setText("\n".join(lines) if lines else "No comparison rows were generated.")

    def _read_tsv(self, path):
        with open(path, newline="", encoding="utf-8-sig") as fp:
            return list(csv.DictReader(fp, delimiter="\t"))

    def _fmt(self, value):
        try:
            return f"{float(value):.4f}"
        except (TypeError, ValueError):
            return str(value or "")

    def _best_values(self, rows, keys):
        best = {}
        for key in keys:
            values = [self._float(row.get(key)) for row in rows]
            best[key] = max(values) if values else None
        return best

    def _top_row_index(self, rows, key):
        if not rows:
            return None
        return max(range(len(rows)), key=lambda index: self._float(rows[index].get(key)))

    def _matches_best(self, value, best_value):
        return best_value is not None and abs(self._float(value) - best_value) < 1e-12

    def _float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _mark_best_item(self, item):
        item.setBackground(QColor("#E8F5E9"))
        item.setForeground(QColor("#166534"))
        font = QFont(item.font())
        font.setBold(True)
        item.setFont(font)

    def _mark_top_item(self, item):
        item.setBackground(QColor("#EAF4FF"))
        font = QFont(item.font())
        font.setBold(True)
        item.setFont(font)


class AdvancedSettingsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.setWindowTitle("Advanced Settings")
        self.resize(900, 560)
        self.window = window
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._create_input_tab(), "Input Files")
        tabs.addTab(self._create_search_tab(), "Search Space")
        tabs.addTab(self._create_metric_tab(), "Metrics")
        tabs.addTab(self._create_candidate_tab(), "Candidate Selection")
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_input_tab(self):
        tab = QWidget()
        grid = QGridLayout(tab)
        self.path_edits = {}
        rows = [(label, key) for label, key, _optional in BIORANK_INPUTS]
        rows.extend([("OncoKB/reference file", "oncokb"), ("Gene mapping file", "gene_mapping")])
        for row_index, (label, key) in enumerate(rows):
            grid.addWidget(QLabel(label), row_index, 0)
            edit = QLineEdit(self._path_value(key))
            self.path_edits[key] = edit
            grid.addWidget(edit, row_index, 1)
            button = QPushButton("Browse")
            button.clicked.connect(lambda _checked=False, current_key=key: self._browse(current_key))
            grid.addWidget(button, row_index, 2)
        grid.setColumnStretch(1, 1)
        return tab

    def _create_search_tab(self):
        tab = QWidget()
        grid = QGridLayout(tab)
        self.alpha_min_edit = self._number_edit(self.window.alpha_min)
        self.alpha_max_edit = self._number_edit(self.window.alpha_max)
        self.beta_min_edit = self._number_edit(self.window.beta_min)
        self.beta_max_edit = self._number_edit(self.window.beta_max)
        fields = [
            ("alpha min", self.alpha_min_edit),
            ("alpha max", self.alpha_max_edit),
            ("beta min", self.beta_min_edit),
            ("beta max", self.beta_max_edit),
        ]
        for row, (label, widget) in enumerate(fields):
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(widget, row, 1)
        note = QLabel("Bounds are inclusive. With 0.0 -> 1.0, Optuna first evaluates exact boundary combinations before sampled trials.")
        note.setWordWrap(True)
        grid.addWidget(note, len(fields), 0, 1, 3)
        grid.setColumnStretch(2, 1)
        return tab

    def _create_metric_tab(self):
        tab = QWidget()
        grid = QGridLayout(tab)
        self.recall_k_spin = QSpinBox()
        self.recall_k_spin.setRange(1, 10000)
        self.recall_k_spin.setValue(self.window.recall_k)
        self.ndcg_k_spin = QSpinBox()
        self.ndcg_k_spin.setRange(1, 10000)
        self.ndcg_k_spin.setValue(self.window.ndcg_k)
        self.precision_k_spin = QSpinBox()
        self.precision_k_spin.setRange(1, 10000)
        self.precision_k_spin.setValue(self.window.precision_k)
        for row, (label, widget) in enumerate([("Recall K", self.recall_k_spin), ("nDCG K", self.ndcg_k_spin)]):
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(widget, row, 1)
        return tab

    def _create_candidate_tab(self):
        tab = QWidget()
        grid = QGridLayout(tab)
        self.selection_mode_combo = QComboBox()
        self.selection_mode_combo.addItem("Pareto first, then fill by display score", "pareto")
        self.selection_mode_combo.addItem("Top display score only", "top_display_score")
        index = self.selection_mode_combo.findData(self.window.candidate_selection_mode)
        self.selection_mode_combo.setCurrentIndex(max(index, 0))
        self.max_candidates_spin = QSpinBox()
        self.max_candidates_spin.setRange(1, 20)
        self.max_candidates_spin.setValue(self.window.max_selected_candidates)
        note = QLabel("Display score is only used after multi-objective Optuna for choosing rows to show and save.")
        note.setWordWrap(True)
        grid.addWidget(QLabel("Selection mode"), 0, 0)
        grid.addWidget(self.selection_mode_combo, 0, 1)
        grid.addWidget(QLabel("Max selected candidates"), 1, 0)
        grid.addWidget(self.max_candidates_spin, 1, 1)
        grid.addWidget(note, 2, 0, 1, 2)
        return tab

    def apply_to_window(self, window):
        for key, edit in self.path_edits.items():
            if key == "oncokb":
                window.oncokb_path = edit.text().strip()
            elif key == "gene_mapping":
                window.gene_mapping_path = edit.text().strip()
            else:
                window.input_paths[key] = edit.text().strip()
        window.alpha_min = float(self.alpha_min_edit.text())
        window.alpha_max = float(self.alpha_max_edit.text())
        window.beta_min = float(self.beta_min_edit.text())
        window.beta_max = float(self.beta_max_edit.text())
        window.recall_k = self.recall_k_spin.value()
        window.ndcg_k = self.ndcg_k_spin.value()
        window.precision_k = self.precision_k_spin.value()
        window.candidate_selection_mode = self.selection_mode_combo.currentData()
        window.max_selected_candidates = self.max_candidates_spin.value()

    def _browse(self, key):
        path, _filter = QFileDialog.getOpenFileName(self, "Select input file")
        if path:
            self.path_edits[key].setText(path)

    def _path_value(self, key):
        if key == "oncokb":
            return self.window.oncokb_path
        if key == "gene_mapping":
            return self.window.gene_mapping_path
        return self.window.input_paths.get(key, "")

    def _number_edit(self, value):
        edit = QLineEdit(str(value))
        edit.setMaximumWidth(140)
        return edit
