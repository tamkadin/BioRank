import csv
import os
import shutil
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import ttkbootstrap as tb
except ImportError:
    tb = None

from biorank_ui.config import (
    ALGORITHM_LABELS,
    BIORANK_INPUTS,
    COLORS,
    DEFAULT_ALPHA_MAX,
    DEFAULT_ALPHA_MIN,
    DEFAULT_BETA_MAX,
    DEFAULT_BETA_MIN,
    DEFAULT_NDCG_K,
    DEFAULT_OPTUNA_RANDOM_SEED,
    DEFAULT_OPTUNA_TRIALS,
    DEFAULT_PRECISION_K,
    DEFAULT_RECALL_K,
    DISEASES,
    GENE_MAPPING_PATH,
    ONCOKB_PATH,
    build_default_biorank_inputs,
    build_output_paths,
    get_optuna_biorank_compare_output_base,
)
from biorank_ui.ranking_review import show_ranking_result_review


COMPARISON_COLUMNS = [
    ("method_label", "Method"),
    ("alpha", "Alpha"),
    ("beta", "Beta"),
    ("ndcg_at_15", "nDCG@15"),
    ("recall_at_15", "Recall@15"),
    ("ndcg_at_100", "nDCG@100"),
    ("recall_at_100", "Recall@100"),
    ("common_genes_top_100", "Common@100"),
    ("all_hits", "All hits"),
    ("mapped_genes", "Mapped genes"),
    ("selection_score", "Display score"),
    ("ranking_path", "Ranking file"),
    ("note", "Note"),
]

TOP5_COLUMNS = [
    ("candidate_rank", "Selected"),
    ("selection_source", "Selection source"),
    ("trial_number", "Trial"),
    ("alpha", "Alpha"),
    ("beta", "Beta"),
    ("ndcg_at_15", "nDCG@15"),
    ("recall_at_15", "Recall@15"),
    ("ndcg_at_100", "nDCG@100"),
    ("recall_at_100", "Recall@100"),
    ("common_genes_top_100", "Common@100"),
    ("selection_score", "Display score"),
    ("ranking_path", "Ranking file"),
]

TRIAL_COLUMNS = [
    ("trial_number", "Trial"),
    ("alpha", "Alpha"),
    ("beta", "Beta"),
    ("ndcg_at_15", "nDCG@15"),
    ("recall_at_15", "Recall@15"),
    ("ndcg_at_100", "nDCG@100"),
    ("recall_at_100", "Recall@100"),
    ("common_genes_top_100", "Common@100"),
    ("all_hits", "All hits"),
    ("mapped_genes", "Mapped genes"),
    ("selection_score", "Display score"),
    ("state", "State"),
    ("duration_seconds", "Duration"),
    ("error_message", "Error"),
]

PARETO_COLUMNS = [
    ("trial_number", "Trial"),
    ("alpha", "Alpha"),
    ("beta", "Beta"),
    ("ndcg_at_15", "nDCG@15"),
    ("recall_at_15", "Recall@15"),
    ("ndcg_at_100", "nDCG@100"),
    ("recall_at_100", "Recall@100"),
    ("common_genes_top_100", "Common@100"),
    ("selection_score", "Display score"),
]


class AlphaBetaCompareOptimizationWindow:
    def __init__(self, parent, selected_disease):
        self.parent = parent
        self.bootstrap_style = self._init_optional_bootstrap()
        self.window = tk.Toplevel(parent)
        self.window.title("BioRank \u03b1/\u03b2 Optimizer")
        self.window.geometry("1280x820")
        self.window.minsize(1100, 720)
        self.window.configure(bg=COLORS["bg"])
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        self.cancel_event = None
        self.current_result = None
        self.output_dir = None
        self.started_at = None
        self.running = False
        self.best_trial_row = None

        self.row_by_item = {}
        self.table_rows = {}
        self.table_columns = {}

        self.disease_var = tk.StringVar(value=selected_disease)
        self.validation_path_var = tk.StringVar(value=ONCOKB_PATH)
        self.validation_column_var = tk.StringVar(value="Gene")
        self.mapping_path_var = tk.StringVar(value=GENE_MAPPING_PATH)
        self.alpha_min_var = tk.StringVar(value=str(DEFAULT_ALPHA_MIN))
        self.alpha_max_var = tk.StringVar(value=str(DEFAULT_ALPHA_MAX))
        self.beta_min_var = tk.StringVar(value=str(DEFAULT_BETA_MIN))
        self.beta_max_var = tk.StringVar(value=str(DEFAULT_BETA_MAX))
        self.n_trials_var = tk.StringVar(value=str(DEFAULT_OPTUNA_TRIALS))
        self.random_seed_var = tk.StringVar(value=str(DEFAULT_OPTUNA_RANDOM_SEED))
        self.recall_k_var = tk.StringVar(value=str(DEFAULT_RECALL_K))
        self.ndcg_k_var = tk.StringVar(value=str(DEFAULT_NDCG_K))
        self.precision_k_var = tk.StringVar(value=str(DEFAULT_PRECISION_K))
        self.prefer_balanced_var = tk.BooleanVar(value=False)
        self.save_top_rankings_var = tk.BooleanVar(value=True)
        self.export_main_var = tk.BooleanVar(value=False)

        self.input_vars = {key: tk.StringVar() for _label, key, _is_folder in BIORANK_INPUTS}
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_text_var = tk.StringVar(value="0 / 0")
        self.input_status_var = tk.StringVar(value="Inputs: not checked")
        self.input_detail_var = tk.StringVar(value="")
        self.oncokb_status_var = tk.StringVar(value="OncoKB: not checked")
        self.mapping_status_var = tk.StringVar(value="Gene mapping: not checked")
        self.range_summary_var = tk.StringVar()
        self.metric_summary_var = tk.StringVar()
        self.output_path_var = tk.StringVar(value="Output: not created yet")
        self.elapsed_var = tk.StringVar(value="Elapsed: 0s")
        self.current_trial_var = tk.StringVar(value="Ready")
        self.current_metrics_var = tk.StringVar(value="Current metrics will appear here.")
        self.best_so_far_var = tk.StringVar(value="Best BioRank Lite optimized result will appear here.")
        self.quick_summary_var = tk.StringVar(value="Run optimization to see baseline and best optimized results.")
        self.balance_note_var = tk.StringVar(value="")
        self.baseline_vars = {
            "pagerank": tk.StringVar(value="PageRank baseline: pending"),
            "random_walk": tk.StringVar(value="BRWR Lite baseline: pending"),
            "biorank_lite": tk.StringVar(value="BioRank Lite baseline: pending"),
        }

        self._configure_local_styles()
        self._build_layout()
        self._auto_fill_inputs()
        self._center_window()

    def _init_optional_bootstrap(self):
        if tb is None:
            return None
        try:
            return tb.Style(theme="flatly")
        except Exception:
            return None

    def _configure_local_styles(self):
        style = ttk.Style(self.parent)
        style.configure("OptimizerHeader.TFrame", background=COLORS["accent_dark"])
        style.configure("OptimizerTitle.TLabel", background=COLORS["accent_dark"], foreground="#ffffff", font=("Segoe UI", 20, "bold"))
        style.configure("OptimizerSubtitle.TLabel", background=COLORS["accent_dark"], foreground="#dbeafe", font=("Segoe UI", 10))
        style.configure("Badge.TLabel", background=COLORS["accent_soft"], foreground=COLORS["accent_dark"], padding=(8, 3), font=("Segoe UI", 9))
        style.configure("Success.TLabel", foreground=COLORS["success"])
        style.configure("Danger.TLabel", foreground=COLORS["danger"])
        style.configure("Muted.TLabel", foreground=COLORS["muted"])
        style.configure("CardTitle.TLabel", font=("Segoe UI", 11, "bold"), foreground=COLORS["text"])
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 9))

    def _build_layout(self):
        root = ttk.Frame(self.window, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        self._create_header(root).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        content = ttk.Frame(root)
        content.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        content.columnconfigure(0, weight=3, uniform="content")
        content.columnconfigure(1, weight=4, uniform="content")

        self._create_setup_panel(content).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._create_progress_panel(content).grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._create_results_tabs(root).grid(row=2, column=0, sticky="nsew")

    def _create_header(self, parent):
        header = ttk.Frame(parent, style="OptimizerHeader.TFrame", padding=(18, 16))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="BioRank \u03b1/\u03b2 Optimizer", style="OptimizerTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Multi-objective Optuna optimization for BioRank Lite. PageRank, BRWR Lite, and BioRank Lite baseline use alpha=beta=0.5.",
            style="OptimizerSubtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        badges = ttk.Frame(header, style="OptimizerHeader.TFrame")
        badges.grid(row=2, column=0, sticky="w")
        for text in (
            "Mode: BioRank-only optimization",
            "Validation: OncoKB",
            "Baselines: alpha=0.5, beta=0.5",
        ):
            ttk.Label(badges, text=text, style="Badge.TLabel").pack(side="left", padx=(0, 8))
        return header

    def _create_setup_panel(self, parent):
        panel = ttk.Frame(parent)
        panel.columnconfigure(0, weight=1)

        disease_card = ttk.LabelFrame(panel, text="Setup", padding=12)
        disease_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        disease_card.columnconfigure(1, weight=1)
        ttk.Label(disease_card, text="Disease").grid(row=0, column=0, sticky="w", padx=(0, 8))
        disease_box = ttk.Combobox(disease_card, textvariable=self.disease_var, values=DISEASES, state="readonly", width=12)
        disease_box.grid(row=0, column=1, sticky="w")
        disease_box.bind("<<ComboboxSelected>>", lambda _event: self._auto_fill_inputs())
        ttk.Button(disease_card, text="Auto-fill Inputs", command=self._auto_fill_inputs).grid(row=0, column=2, sticky="e", padx=(10, 0))

        self.input_status_label = ttk.Label(disease_card, textvariable=self.input_status_var, style="Muted.TLabel")
        self.input_status_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(disease_card, textvariable=self.input_detail_var, style="Muted.TLabel", justify="left").grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(4, 0),
        )
        self.oncokb_status_label = ttk.Label(disease_card, textvariable=self.oncokb_status_var, style="Muted.TLabel")
        self.oncokb_status_label.grid(row=3, column=0, columnspan=3, sticky="w", pady=(3, 0))
        self.mapping_status_label = ttk.Label(disease_card, textvariable=self.mapping_status_var, style="Muted.TLabel")
        self.mapping_status_label.grid(row=4, column=0, columnspan=3, sticky="w", pady=(3, 0))
        ttk.Button(disease_card, text="View/Edit Input Files", command=self._open_advanced_settings).grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(12, 0),
        )

        optimization_card = ttk.LabelFrame(panel, text="Optimization", padding=12)
        optimization_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        optimization_card.columnconfigure(1, weight=1)
        ttk.Label(optimization_card, text="Trials").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(optimization_card, textvariable=self.n_trials_var, width=10).grid(row=0, column=1, sticky="w", pady=3)
        ttk.Label(optimization_card, text="Random seed").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(optimization_card, textvariable=self.random_seed_var, width=10).grid(row=1, column=1, sticky="w", pady=3)
        ttk.Label(optimization_card, textvariable=self.range_summary_var, style="Muted.TLabel").grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Button(optimization_card, text="Advanced Settings", command=self._open_advanced_settings).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(12, 0),
        )

        metrics_card = ttk.LabelFrame(panel, text="Metrics", padding=12)
        metrics_card.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(metrics_card, textvariable=self.metric_summary_var, justify="left").grid(row=0, column=0, sticky="w")
        ttk.Label(metrics_card, textvariable=self.balance_note_var, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))

        return panel

    def _create_progress_panel(self, parent):
        panel = ttk.Frame(parent)
        panel.columnconfigure(0, weight=1)

        progress_card = ttk.LabelFrame(panel, text="Progress", padding=12)
        progress_card.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        progress_card.columnconfigure(0, weight=1)
        ttk.Label(progress_card, textvariable=self.current_trial_var, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Progressbar(progress_card, variable=self.progress_var, maximum=100).grid(row=1, column=0, sticky="ew", pady=(8, 2))
        ttk.Label(progress_card, textvariable=self.progress_text_var, style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(progress_card, textvariable=self.status_var, wraplength=620).grid(row=3, column=0, sticky="w", pady=(8, 0))

        baseline_frame = ttk.Frame(progress_card)
        baseline_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        for index, key in enumerate(("pagerank", "random_walk", "biorank_lite")):
            ttk.Label(baseline_frame, textvariable=self.baseline_vars[key], style="Muted.TLabel").grid(row=index, column=0, sticky="w", pady=1)

        ttk.Label(progress_card, textvariable=self.current_metrics_var, wraplength=620, style="Muted.TLabel").grid(
            row=5,
            column=0,
            sticky="w",
            pady=(12, 0),
        )
        ttk.Label(progress_card, textvariable=self.best_so_far_var, wraplength=620, style="Muted.TLabel").grid(
            row=6,
            column=0,
            sticky="w",
            pady=(6, 0),
        )
        ttk.Label(progress_card, textvariable=self.elapsed_var, style="Muted.TLabel").grid(row=7, column=0, sticky="w", pady=(10, 0))
        ttk.Label(progress_card, textvariable=self.output_path_var, wraplength=620, style="Muted.TLabel").grid(row=8, column=0, sticky="w", pady=(3, 0))

        summary_card = ttk.LabelFrame(panel, text="Quick Summary", padding=12)
        summary_card.grid(row=1, column=0, sticky="nsew")
        summary_card.columnconfigure(0, weight=1)
        ttk.Label(summary_card, textvariable=self.quick_summary_var, justify="left", wraplength=620).grid(row=0, column=0, sticky="nw")

        action_card = self._create_action_card(panel)
        action_card.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        return panel

    def _create_action_card(self, parent):
        action_card = ttk.LabelFrame(parent, text="Actions", padding=12)
        for column in range(3):
            action_card.columnconfigure(column, weight=1)

        self.start_button = ttk.Button(action_card, text="Start Optimization", style="Primary.TButton", command=self._start)
        self.start_button.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.cancel_button = ttk.Button(action_card, text="Cancel", state="disabled", command=self._cancel)
        self.cancel_button.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=4)
        self.open_output_button = ttk.Button(action_card, text="Open Output Folder", state="disabled", command=self._open_output_folder)
        self.open_output_button.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        self.open_summary_button = ttk.Button(
            action_card,
            text="Open Comparison Summary",
            state="disabled",
            command=lambda: self._open_file("comparison_summary_path"),
        )
        self.open_summary_button.grid(row=1, column=2, sticky="ew", padx=(4, 0), pady=4)
        self.view_selected_button = ttk.Button(action_card, text="Run/View Selected Row", state="disabled", command=self._run_selected_row)
        self.view_selected_button.grid(row=2, column=0, sticky="ew", padx=(0, 4), pady=4)
        self.open_logs_button = ttk.Button(action_card, text="Open Logs", state="disabled", command=lambda: self._open_file("logs_path"))
        self.open_logs_button.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(action_card, text="Close", command=self._close).grid(row=2, column=2, sticky="ew", padx=(4, 0), pady=4)
        return action_card

    def _create_results_tabs(self, parent):
        frame = ttk.Frame(parent)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.notebook = ttk.Notebook(frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.tables = {}
        self.tables["Comparison Summary"] = self._add_table_tab(
            "Comparison Summary",
            "Main comparison: three baselines plus top 5 optimized BioRank configurations.",
            COMPARISON_COLUMNS,
            with_row_actions=True,
        )
        self.tables["Selected BioRank candidates"] = self._add_table_tab(
            "Selected BioRank candidates",
            "Only top 5 optimized BioRank configurations are saved as official ranking files.",
            TOP5_COLUMNS,
        )
        self.tables["All BioRank Trials"] = self._add_table_tab(
            "All BioRank Trials",
            "All Optuna trials for BioRank. Low-ranked trial ranking files are not kept.",
            TRIAL_COLUMNS,
            with_sort=True,
        )
        self.tables["Pareto Front"] = self._add_table_tab(
            "Pareto Front",
            "Pareto front contains trials that are not dominated across the optimization objectives.",
            PARETO_COLUMNS,
        )
        self._add_logs_tab()
        return frame

    def _add_table_tab(self, title, note, columns, with_row_actions=False, with_sort=False):
        tab = ttk.Frame(self.notebook, padding=10)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text=note, style="Muted.TLabel").grid(row=0, column=0, sticky="w")

        if with_sort:
            ttk.Label(top, text="Sort by").grid(row=0, column=1, sticky="e", padx=(8, 4))
            sort_var = tk.StringVar(value="Display score")
            sort_box = ttk.Combobox(
                top,
                textvariable=sort_var,
                values=("Display score", "nDCG@15", "Recall@15", "nDCG@100", "Recall@100", "Common@100"),
                state="readonly",
                width=16,
            )
            sort_box.grid(row=0, column=2, sticky="e")
            sort_box.bind("<<ComboboxSelected>>", lambda _event: self._sort_trials(sort_var.get()))

        table = self._create_table(tab)
        table.grid(row=1, column=0, sticky="nsew")
        self.table_columns[id(table)] = columns

        if with_row_actions:
            actions = ttk.Frame(tab)
            actions.grid(row=2, column=0, sticky="ew", pady=(8, 0))
            ttk.Button(actions, text="View Ranking", command=self._run_selected_row).pack(side="left", padx=(0, 8))
            ttk.Button(actions, text="Open Ranking File", command=self._open_selected_ranking_file).pack(side="left", padx=(0, 8))
            ttk.Button(actions, text="Copy Selected Row", command=self._copy_selected_row).pack(side="left")

        self.notebook.add(tab, text=title)
        return table

    def _add_logs_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        actions = ttk.Frame(tab)
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(actions, text="Refresh Logs", command=self._refresh_logs_tab).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Open logs.txt", command=lambda: self._open_file("logs_path")).pack(side="left")

        self.logs_text = tk.Text(tab, height=12, wrap="none")
        self.logs_text.grid(row=1, column=0, sticky="nsew")
        scrollbar_y = ttk.Scrollbar(tab, orient="vertical", command=self.logs_text.yview)
        scrollbar_x = ttk.Scrollbar(tab, orient="horizontal", command=self.logs_text.xview)
        self.logs_text.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        scrollbar_y.grid(row=1, column=1, sticky="ns")
        scrollbar_x.grid(row=2, column=0, sticky="ew")
        self.notebook.add(tab, text="Logs")

    def _create_table(self, parent):
        table_frame = ttk.Frame(parent)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        table = ttk.Treeview(table_frame, show="headings", height=12)
        table.grid(row=0, column=0, sticky="nsew")
        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
        scrollbar_x = ttk.Scrollbar(table_frame, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        return table_frame

    def _table_widget(self, table_frame):
        return next(child for child in table_frame.winfo_children() if isinstance(child, ttk.Treeview))

    def _open_advanced_settings(self):
        dialog = tk.Toplevel(self.window)
        dialog.title("Advanced Settings")
        dialog.geometry("980x620")
        dialog.minsize(860, 560)
        dialog.transient(self.window)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(dialog)
        notebook.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self._build_advanced_inputs_tab(notebook)
        self._build_advanced_search_tab(notebook)
        self._build_advanced_metrics_tab(notebook)
        self._build_advanced_output_tab(notebook)

        actions = ttk.Frame(dialog, padding=(12, 0, 12, 12))
        actions.grid(row=1, column=0, sticky="ew")
        ttk.Button(actions, text="Use Recommended Settings", command=self._use_recommended_settings).pack(side="left")
        ttk.Button(actions, text="Close", command=lambda: self._close_advanced(dialog)).pack(side="right")
        self._center_child(dialog)

    def _build_advanced_inputs_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=12)
        frame.columnconfigure(1, weight=1)
        row = 0
        for label, key, _is_folder in BIORANK_INPUTS:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
            ttk.Entry(frame, textvariable=self.input_vars[key]).grid(row=row, column=1, sticky="ew", pady=4)
            ttk.Button(frame, text="Browse", command=lambda var=self.input_vars[key]: self._browse_var(var)).grid(row=row, column=2, sticky="e", padx=(8, 0), pady=4)
            row += 1

        ttk.Label(frame, text="OncoKB/reference file").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.validation_path_var).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(frame, text="Browse", command=lambda: self._browse_var(self.validation_path_var)).grid(row=row, column=2, sticky="e", padx=(8, 0), pady=4)
        row += 1
        ttk.Label(frame, text="OncoKB gene column").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.validation_column_var, width=18).grid(row=row, column=1, sticky="w", pady=4)
        row += 1
        ttk.Label(frame, text="Gene symbol mapping file").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.mapping_path_var).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(frame, text="Browse", command=lambda: self._browse_var(self.mapping_path_var)).grid(row=row, column=2, sticky="e", padx=(8, 0), pady=4)
        notebook.add(frame, text="Input files")

    def _build_advanced_search_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=12)
        for column in range(4):
            frame.columnconfigure(column, weight=1)
        fields = (
            ("alpha_min", self.alpha_min_var),
            ("alpha_max", self.alpha_max_var),
            ("beta_min", self.beta_min_var),
            ("beta_max", self.beta_max_var),
            ("n_trials", self.n_trials_var),
            ("random_seed", self.random_seed_var),
        )
        for index, (label, variable) in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            ttk.Label(frame, text=label).grid(row=row, column=column, sticky="w", pady=6, padx=(0, 8))
            ttk.Entry(frame, textvariable=variable, width=14).grid(row=row, column=column + 1, sticky="w", pady=6)
        ttk.Label(
            frame,
            text=(
                "Alpha/beta bounds are inclusive. With 0.0 -> 1.0, Optuna first evaluates exact boundary "
                "combinations before sampled trials. Random seed repeats the same Optuna suggestion sequence."
            ),
            style="Muted.TLabel",
            wraplength=760,
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(12, 0))
        notebook.add(frame, text="Search space")

    def _build_advanced_metrics_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=12)
        fields = (
            ("Recall K", self.recall_k_var),
            ("nDCG K", self.ndcg_k_var),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 8))
            ttk.Entry(frame, textvariable=variable, width=14).grid(row=row, column=1, sticky="w", pady=6)
        notebook.add(frame, text="Metrics")

    def _build_advanced_output_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=12)
        ttk.Checkbutton(
            frame,
            text="Save ranking files for baselines and top 5 only",
            variable=self.save_top_rankings_var,
            state="disabled",
        ).grid(row=0, column=0, sticky="w", pady=6)
        ttk.Checkbutton(
            frame,
            text="Export selected ranking as main output",
            variable=self.export_main_var,
        ).grid(row=1, column=0, sticky="w", pady=6)
        ttk.Label(
            frame,
            text="Optimizer output is isolated under output/<DISEASE>/optuna_biorank_compare/<timestamp>/.",
            style="Muted.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))
        notebook.add(frame, text="Output")

    def _close_advanced(self, dialog):
        self._refresh_summaries()
        self._update_input_status()
        dialog.destroy()

    def _auto_fill_inputs(self):
        defaults = build_default_biorank_inputs(self.disease_var.get())
        for key, variable in self.input_vars.items():
            variable.set(defaults.get(key, ""))
        self.validation_path_var.set(ONCOKB_PATH)
        self.mapping_path_var.set(GENE_MAPPING_PATH)
        self._refresh_summaries()
        self._update_input_status()

    def _use_recommended_settings(self):
        self.alpha_min_var.set(str(DEFAULT_ALPHA_MIN))
        self.alpha_max_var.set(str(DEFAULT_ALPHA_MAX))
        self.beta_min_var.set(str(DEFAULT_BETA_MIN))
        self.beta_max_var.set(str(DEFAULT_BETA_MAX))
        self.n_trials_var.set(str(DEFAULT_OPTUNA_TRIALS))
        self.random_seed_var.set(str(DEFAULT_OPTUNA_RANDOM_SEED))
        self.recall_k_var.set(str(DEFAULT_RECALL_K))
        self.ndcg_k_var.set(str(DEFAULT_NDCG_K))
        self.precision_k_var.set(str(DEFAULT_PRECISION_K))
        self.validation_path_var.set(ONCOKB_PATH)
        self.validation_column_var.set("Gene")
        self.mapping_path_var.set(GENE_MAPPING_PATH)
        self.prefer_balanced_var.set(False)
        self.export_main_var.set(False)
        self._refresh_summaries()
        self._update_input_status()

    def _refresh_summaries(self):
        self.range_summary_var.set(
            f"Alpha range: {self.alpha_min_var.get()} -> {self.alpha_max_var.get()}\n"
            f"Beta range:  {self.beta_min_var.get()} -> {self.beta_max_var.get()}"
        )
        self.metric_summary_var.set(
            "Objectives:\n"
            f"- Maximize nDCG@{self.ndcg_k_var.get()}\n"
            f"- Maximize Recall@{self.recall_k_var.get()}\n"
            "- Maximize Common@100\n\n"
            "Displayed only, not Optuna objectives: nDCG@15, Recall@15, Display score.\n"
            "Top-5 display score:\n"
            "0.25 Recall@15 + 0.25 nDCG@15 + 0.25 Recall@100 + 0.25 nDCG@100"
        )
        self.balance_note_var.set("")

    def _update_input_status(self):
        input_paths = [variable.get().strip() for variable in self.input_vars.values()]
        detected = sum(1 for path in input_paths if path and os.path.exists(path))
        total = len(input_paths)
        self.input_status_var.set(f"Inputs: {detected}/{total} detected")
        self.input_status_label.configure(style="Success.TLabel" if detected == total else "Danger.TLabel")
        detail_labels = {
            "ppi_file_path": "PPI",
            "co_expression_file_path": "Co-expression",
            "seed_file_path": "Seed",
            "secondary_seed_file_path": "DE genes",
            "map__gene__ontologies_file_path": "Ontology",
            "disease_ontology_file_path": "Disease ontology",
        }
        detail_lines = []
        for key, variable in self.input_vars.items():
            status = "Ready" if variable.get().strip() and os.path.exists(variable.get().strip()) else "Missing"
            detail_lines.append(f"{detail_labels.get(key, key)}: {status}")
        self.input_detail_var.set(" | ".join(detail_lines[:3]) + "\n" + " | ".join(detail_lines[3:]))

        oncokb_ok = os.path.exists(self.validation_path_var.get().strip())
        self.oncokb_status_var.set("OncoKB: detected" if oncokb_ok else "OncoKB: missing")
        self.oncokb_status_label.configure(style="Success.TLabel" if oncokb_ok else "Danger.TLabel")

        mapping_path = self.mapping_path_var.get().strip()
        mapping_ok = bool(mapping_path) and os.path.exists(mapping_path)
        self.mapping_status_var.set("Gene mapping: detected" if mapping_ok else "Gene mapping: missing")
        self.mapping_status_label.configure(style="Success.TLabel" if mapping_ok else "Danger.TLabel")

    def _start(self):
        try:
            config = self._collect_config()
        except ValueError as exc:
            messagebox.showerror("Invalid optimization config", str(exc), parent=self.window)
            return

        self.cancel_event = threading.Event()
        self.current_result = None
        self.best_trial_row = None
        self.started_at = time.perf_counter()
        self.running = True
        self.output_path_var.set(f"Output: {config['output_dir']}")
        self._set_running_state(True)
        self._reset_progress_state()
        self._clear_tables()

        threading.Thread(target=self._run_optimizer_task, args=(config,), daemon=True).start()

    def _run_optimizer_task(self, config):
        try:
            from BioRank.optimization.biorank_alpha_beta_optimizer import BioRankAlphaBetaOptimizer

            optimizer = BioRankAlphaBetaOptimizer(
                cancellation_event=self.cancel_event,
                progress_callback=self._thread_progress,
                **config,
            )
            result = optimizer.run()
        except Exception as exc:
            self.parent.after(0, lambda: self._finish_error(str(exc)))
            return

        self.parent.after(0, lambda: self._finish_success(result))

    def _collect_config(self):
        disease = self.disease_var.get()
        input_paths = {key: variable.get().strip() for key, variable in self.input_vars.items()}
        for label, key, _is_folder in BIORANK_INPUTS:
            value = input_paths.get(key, "")
            if not value:
                raise ValueError(f"Missing {label}.")
            if not os.path.exists(value):
                raise ValueError(f"{label} does not exist.")

        validation_path = self.validation_path_var.get().strip()
        if not validation_path:
            raise ValueError("Missing OncoKB file.")
        if not os.path.exists(validation_path):
            raise ValueError("Missing OncoKB file.")

        mapping_path = self.mapping_path_var.get().strip()
        if mapping_path and not os.path.exists(mapping_path):
            raise ValueError("Gene mapping file does not exist.")

        try:
            alpha_min = float(self.alpha_min_var.get())
            alpha_max = float(self.alpha_max_var.get())
            beta_min = float(self.beta_min_var.get())
            beta_max = float(self.beta_max_var.get())
            n_trials = int(self.n_trials_var.get())
            random_seed = int(self.random_seed_var.get())
            recall_k = int(self.recall_k_var.get())
            ndcg_k = int(self.ndcg_k_var.get())
            precision_k = int(self.precision_k_var.get())
        except ValueError as exc:
            raise ValueError("Trials, seed, ranges, and metric K values must be numeric.") from exc

        if n_trials < 1:
            raise ValueError("Invalid n_trials.")
        if not 0.0 <= alpha_min < alpha_max <= 1.0:
            raise ValueError("Alpha range must use inclusive bounds in [0, 1] and min must be less than max.")
        if not 0.0 <= beta_min < beta_max <= 1.0:
            raise ValueError("Beta range must use inclusive bounds in [0, 1] and min must be less than max.")
        if min(recall_k, ndcg_k, precision_k) < 1:
            raise ValueError("Metric K values must be at least 1.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = get_optuna_biorank_compare_output_base(disease) / timestamp
        self.output_dir = output_dir
        return {
            "cancer_type": disease,
            "input_paths": input_paths,
            "validation_file_path": validation_path,
            "validation_gene_column": self.validation_column_var.get().strip() or "Gene",
            "gene_mapping_file_path": mapping_path,
            "alpha_range": (alpha_min, alpha_max),
            "beta_range": (beta_min, beta_max),
            "n_trials": n_trials,
            "metric_config": {"recall_k": recall_k, "ndcg_k": ndcg_k, "precision_k": precision_k},
            "output_dir": str(output_dir),
            "prefer_balanced_top5": False,
            "random_seed": random_seed,
        }

    def _thread_progress(self, payload):
        self.parent.after(0, lambda: self._update_progress(payload))

    def _update_progress(self, payload):
        if not self._window_exists():
            return
        self._update_elapsed()
        phase = payload.get("phase", "")
        status = payload.get("status", "")
        if phase == "baselines":
            self.current_trial_var.set("Running baselines")
            self.status_var.set(status)
            algorithm = payload.get("baseline_algorithm")
            state = payload.get("baseline_state")
            if algorithm in self.baseline_vars and state:
                labels = {"pagerank": "PageRank baseline", "random_walk": "BRWR Lite baseline", "biorank_lite": "BioRank Lite baseline"}
                self.baseline_vars[algorithm].set(f"{labels[algorithm]}: {state}")
            return

        trial_number = payload.get("trial_number")
        try:
            total = max(1, int(self.n_trials_var.get()))
        except ValueError:
            total = 1
        if trial_number is not None:
            current = min(trial_number + 1, total)
            self.progress_var.set(min(100.0, current * 100.0 / total))
            self.progress_text_var.set(f"{current} / {total}")
            self.current_trial_var.set(f"BioRank Lite Optuna Trial {current} / {total}")

        alpha = payload.get("alpha")
        beta = payload.get("beta")
        if alpha is not None and beta is not None:
            self.status_var.set(f"{status} | alpha={alpha:.4f} beta={beta:.4f}")
        else:
            self.status_var.set(status)

        metrics = payload.get("metrics") or {}
        if metrics:
            self.current_metrics_var.set(
                "Current trial: nDCG@15={:.4f} | Recall@15={:.4f} | nDCG@100={:.4f} | Recall@100={:.4f} | Common@100={} | Score={:.4f}".format(
                    metrics.get("ndcg_at_15", 0.0),
                    metrics.get("recall_at_15", 0.0),
                    metrics.get("ndcg_at_100", 0.0),
                    metrics.get("recall_at_100", 0.0),
                    metrics.get("common_genes_top_100", 0),
                    metrics.get("selection_score", 0.0),
                )
            )

        best_row = payload.get("best_row")
        if best_row:
            self.best_trial_row = best_row
            self.best_so_far_var.set(
                "Best top-5 display score so far: {:.4f} | alpha={:.4f} | beta={:.4f}".format(
                    float(best_row.get("selection_score", 0.0)),
                    float(best_row.get("alpha", 0.0)),
                    float(best_row.get("beta", 0.0)),
                )
            )

    def _finish_success(self, result):
        if not self._window_exists():
            return
        self.current_result = result
        self.running = False
        self._set_running_state(False)
        self.progress_var.set(100.0)
        self.status_var.set(f"Optimization completed. Output: {result.output_dir}")
        self.output_path_var.set(f"Output: {result.output_dir}")
        self._load_result_tables(result)
        self._update_quick_summary(result)
        self.notebook.select(0)
        self._show_completion_dialog(result)

    def _finish_error(self, error_message):
        if not self._window_exists():
            return
        self.running = False
        self._set_running_state(False)
        self.status_var.set("Optimization failed.")
        messagebox.showerror("Optimization error", error_message, parent=self.window)

    def _cancel(self):
        if self.cancel_event is not None:
            self.cancel_event.set()
            self.cancel_button.config(state="disabled")
            self.status_var.set("Cancelling optimization...")

    def _set_running_state(self, running):
        self.start_button.config(state="disabled" if running else "normal")
        self.cancel_button.config(state="normal" if running else "disabled")
        output_state = "normal" if self.current_result else "disabled"
        self.open_output_button.config(state=output_state)
        self.open_summary_button.config(state=output_state)
        self.view_selected_button.config(state=output_state)
        self.open_logs_button.config(state=output_state)

    def _reset_progress_state(self):
        self.progress_var.set(0.0)
        self.progress_text_var.set(f"0 / {self.n_trials_var.get()}")
        self.status_var.set("Running baselines...")
        self.current_trial_var.set("Running baselines")
        self.current_metrics_var.set("Current metrics will appear here.")
        self.best_so_far_var.set("Best BioRank Lite optimized result will appear here.")
        self.quick_summary_var.set("Optimization is running.")
        for key, variable in self.baseline_vars.items():
            label = {"pagerank": "PageRank baseline", "random_walk": "BRWR Lite baseline", "biorank_lite": "BioRank Lite baseline"}[key]
            variable.set(f"{label}: pending")

    def _load_result_tables(self, result):
        self._load_table(self.tables["Comparison Summary"], result.comparison_summary_path, COMPARISON_COLUMNS)
        self._load_table(self.tables["Selected BioRank candidates"], result.selected_candidates_path, TOP5_COLUMNS)
        self._load_table(self.tables["All BioRank Trials"], result.biorank_trial_history_path, TRIAL_COLUMNS)
        self._load_table(self.tables["Pareto Front"], result.biorank_pareto_trials_path, PARETO_COLUMNS)
        self._load_logs(result.logs_path)

    def _load_table(self, table_frame, file_path, columns):
        table = self._table_widget(table_frame)
        rows = self._read_tsv(file_path)
        self._populate_table(table, rows, columns)

    def _populate_table(self, table, rows, columns):
        table.delete(*table.get_children())
        table_id = id(table)
        self.table_rows[table_id] = rows
        self.table_columns[table_id] = columns
        table["columns"] = [label for _source, label in columns]
        for source, label in columns:
            table.heading(label, text=label, command=lambda s=source, t=table: self._sort_table(t, s))
            width = 230 if source in ("ranking_path", "note", "error_message") else 115
            table.column(label, width=width, anchor="w")
        for row in rows:
            values = [self._format_cell(row, source) for source, _label in columns]
            item_id = table.insert("", "end", values=values)
            self.row_by_item[item_id] = row

    def _sort_table(self, table, source):
        rows = list(self.table_rows.get(id(table), []))
        if not rows:
            return
        descending = getattr(table, "_sort_descending", False)
        rows.sort(key=lambda row: self._sort_value(row.get(source, "")), reverse=descending)
        table._sort_descending = not descending
        self._populate_table(table, rows, self.table_columns[id(table)])

    def _sort_trials(self, label):
        key_map = {
            "Display score": "selection_score",
            "nDCG@15": "ndcg_at_15",
            "Recall@15": "recall_at_15",
            "nDCG@100": "ndcg_at_100",
            "Recall@100": "recall_at_100",
            "Common@100": "common_genes_top_100",
        }
        table = self._table_widget(self.tables["All BioRank Trials"])
        rows = list(self.table_rows.get(id(table), []))
        rows.sort(key=lambda row: self._sort_value(row.get(key_map[label], "")), reverse=True)
        self._populate_table(table, rows, TRIAL_COLUMNS)

    def _sort_value(self, value):
        try:
            return (0, float(value))
        except (TypeError, ValueError):
            return (1, str(value))

    def _format_cell(self, row, source):
        if source == "alpha" and row.get("alpha_used") == "No":
            return "N/A"
        value = row.get(source, "")
        try:
            if source in {
                "alpha",
                "beta",
                "recall_at_15",
                "ndcg_at_15",
                "recall_at_100",
                "ndcg_at_100",
                "selection_score",
                "duration_seconds",
            }:
                return f"{float(value):.4f}"
        except (TypeError, ValueError):
            return value
        return value

    def _load_logs(self, file_path):
        self.logs_text.config(state="normal")
        self.logs_text.delete("1.0", tk.END)
        if file_path and os.path.exists(file_path):
            with open(file_path, encoding="utf-8") as fp:
                self.logs_text.insert("1.0", fp.read())
        self.logs_text.config(state="disabled")

    def _refresh_logs_tab(self):
        if not self.current_result:
            return
        self._load_logs(self.current_result.logs_path)

    def _clear_tables(self):
        self.row_by_item.clear()
        for table_frame in self.tables.values():
            table = self._table_widget(table_frame)
            table.delete(*table.get_children())
        if hasattr(self, "logs_text"):
            self.logs_text.config(state="normal")
            self.logs_text.delete("1.0", tk.END)
            self.logs_text.config(state="disabled")

    def _get_selected_row(self):
        for table_frame in self.tables.values():
            table = self._table_widget(table_frame)
            selection = table.selection()
            if selection:
                return self.row_by_item.get(selection[0])
        return None

    def _run_selected_row(self):
        selected = self._get_selected_row()
        if not selected:
            messagebox.showerror("No row selected", "Select a row with a saved ranking file first.", parent=self.window)
            return

        ranking_path = selected.get("ranking_path", "")
        if not ranking_path or not os.path.exists(ranking_path):
            messagebox.showerror("Missing ranking", "Selected row does not have a saved ranking file.", parent=self.window)
            return

        algorithm = selected.get("algorithm") or "biorank_lite"
        method_label = selected.get("method_label") or f"BioRank Lite selected #{selected.get('candidate_rank', '')}".strip()

        if self.export_main_var.get():
            try:
                main_paths = build_output_paths(self.disease_var.get(), algorithm)
                shutil.copyfile(ranking_path, main_paths["ranking"])
            except Exception as exc:
                messagebox.showerror("Export error", str(exc), parent=self.window)
                return

        show_ranking_result_review(
            self.parent,
            method_label or ALGORITHM_LABELS.get(algorithm, algorithm),
            self.disease_var.get(),
            {"ranking": ranking_path},
        )

    def _open_selected_ranking_file(self):
        selected = self._get_selected_row()
        if not selected or not selected.get("ranking_path"):
            messagebox.showerror("No ranking selected", "Select a row with a saved ranking file first.", parent=self.window)
            return
        self._open_path(selected["ranking_path"])

    def _copy_selected_row(self):
        selected = self._get_selected_row()
        if not selected:
            messagebox.showerror("No row selected", "Select a row first.", parent=self.window)
            return
        text = "\t".join(str(value) for value in selected.values())
        self.window.clipboard_clear()
        self.window.clipboard_append(text)
        self.status_var.set("Selected row copied to clipboard.")

    def _update_quick_summary(self, result):
        rows = self._read_tsv(result.comparison_summary_path)
        if not rows:
            self.quick_summary_var.set("No comparison rows were written.")
            return
        lines = ["Best comparison"]
        for row in rows[:4]:
            alpha = row.get("alpha")
            if row.get("alpha_used") == "No":
                alpha = "N/A"
            lines.append(
                "\n{} | alpha={} beta={}\nnDCG@15={} | Recall@15={} | nDCG@100={} | Recall@100={} | Common@100={}".format(
                    row.get("method_label", ""),
                    alpha,
                    row.get("beta", ""),
                    row.get("ndcg_at_15", ""),
                    row.get("recall_at_15", ""),
                    row.get("ndcg_at_100", ""),
                    row.get("recall_at_100", ""),
                    row.get("common_genes_top_100", ""),
                )
            )
        self.quick_summary_var.set("\n".join(lines))

    def _show_completion_dialog(self, result):
        rows = self._read_tsv(result.comparison_summary_path)
        dialog = tk.Toplevel(self.window)
        dialog.title("Optimization completed")
        dialog.geometry("900x420")
        dialog.minsize(760, 360)
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        header = ttk.Frame(dialog, padding=(16, 14))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text=f"Optimization completed for {self.disease_var.get()}",
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Results are loaded in the Comparison Summary tab. PageRank alpha is N/A because Original PageRank ignores personalization.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        table_frame = ttk.Frame(dialog, padding=(16, 0, 16, 10))
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        columns = ("Method", "Alpha", "Beta", "nDCG@15", "Recall@15", "nDCG@100", "Recall@100", "Common@100", "Display score")
        table = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
        table.grid(row=0, column=0, sticky="nsew")
        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll_y.set)
        scroll_y.grid(row=0, column=1, sticky="ns")
        for column in columns:
            table.heading(column, text=column)
            table.column(column, width=130 if column != "Method" else 190, anchor="w")
        for row in rows:
            alpha = "N/A" if row.get("alpha_used") == "No" else self._format_cell(row, "alpha")
            table.insert(
                "",
                "end",
                values=(
                    row.get("method_label", ""),
                    alpha,
                    self._format_cell(row, "beta"),
                    self._format_cell(row, "ndcg_at_15"),
                    self._format_cell(row, "recall_at_15"),
                    self._format_cell(row, "ndcg_at_100"),
                    self._format_cell(row, "recall_at_100"),
                    row.get("common_genes_top_100", ""),
                    self._format_cell(row, "selection_score"),
                ),
            )

        actions = ttk.Frame(dialog, padding=(16, 0, 16, 14))
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="Open Output Folder", command=self._open_output_folder).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(
            actions,
            text="Open Comparison Summary",
            command=lambda: self._open_file("comparison_summary_path"),
        ).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(actions, text="Close", command=dialog.destroy).grid(row=0, column=3)
        self._center_child(dialog)

    def _read_tsv(self, file_path):
        if not file_path or not os.path.exists(file_path):
            return []
        with open(file_path, newline="", encoding="utf-8-sig") as fp:
            return list(csv.DictReader(fp, delimiter="\t"))

    def _open_output_folder(self):
        if self.current_result:
            self._open_path(self.current_result.output_dir)
        elif self.output_dir:
            self._open_path(str(self.output_dir))
        else:
            messagebox.showinfo("No output yet", "Run optimization first.", parent=self.window)

    def _open_file(self, attr_name):
        if not self.current_result:
            messagebox.showinfo("No output yet", "Run optimization first.", parent=self.window)
            return
        self._open_path(getattr(self.current_result, attr_name))

    def _open_path(self, path):
        if not path or not os.path.exists(path):
            messagebox.showerror("Missing path", f"Path does not exist:\n{path}", parent=self.window)
            return
        try:
            os.startfile(path)
        except AttributeError:
            messagebox.showinfo("Path", path, parent=self.window)

    def _browse_var(self, variable):
        path = filedialog.askopenfilename(parent=self.window)
        if path:
            variable.set(path)
            self._update_input_status()

    def _update_elapsed(self):
        if self.started_at is None:
            return
        elapsed = int(time.perf_counter() - self.started_at)
        minutes, seconds = divmod(elapsed, 60)
        self.elapsed_var.set(f"Elapsed: {minutes}m {seconds}s")

    def _close(self):
        if self.running:
            if not messagebox.askyesno("Optimization running", "Cancel optimization and close this window?", parent=self.window):
                return
            self._cancel()
        self.window.destroy()

    def _window_exists(self):
        try:
            return self.window.winfo_exists()
        except tk.TclError:
            return False

    def _center_window(self):
        self.window.update_idletasks()
        self._center_child(self.window)

    def _center_child(self, window):
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
