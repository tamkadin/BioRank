from tkinter import BooleanVar, messagebox, ttk

import customtkinter as ctk

from biorank_ui.config import DISEASES
from biorank_ui.state import AppState
from BioRank.optimization.ablation_config import (
    ABLATION_MODE_FULL,
    ABLATION_MODE_LABELS,
    ABLATION_MODE_ORDER,
    ablation_label,
)
from biorank_ui.theme import (
    APP_BG,
    CARD_BG,
    BORDER,
    PRIMARY,
    SOFT_BLUE,
    TEXT_MAIN,
    TEXT_MUTED,
    STATUS_READY,
    STATUS_RUNNING,
    FONT_FAMILY_HEADER,
    FONT_FAMILY_BODY,
)


class HighlightTable(ctk.CTkFrame):
    def __init__(self, master, columns, column_widths, **kwargs):
        super().__init__(master, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8, **kwargs)
        self.columns = columns
        self.column_widths = column_widths
        self._last_key = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        style = ttk.Style(self)
        style.configure(
            "Optimization.Treeview",
            background="#FFFFFF",
            foreground=TEXT_MAIN,
            fieldbackground="#FFFFFF",
            rowheight=30,
            font=(FONT_FAMILY_BODY, 11),
        )
        style.configure(
            "Optimization.Treeview.Heading",
            background=SOFT_BLUE,
            foreground=TEXT_MAIN,
            font=(FONT_FAMILY_HEADER, 11, "bold"),
        )

        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show="headings",
            selectmode="browse",
            style="Optimization.Treeview",
        )
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=(6, 0))
        self.vsb.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=(6, 0))
        self.hsb.grid(row=1, column=0, sticky="ew", padx=(6, 0), pady=(0, 6))

        for column in columns:
            self.tree.heading(column, text=column, anchor="w")
            self.tree.column(
                column,
                width=column_widths.get(column, 90),
                minwidth=55,
                anchor="w",
                stretch=True,
            )

        self.tree.tag_configure("even", background="#FFFFFF")
        self.tree.tag_configure("odd", background=APP_BG)
        self.tree.tag_configure("best", background="#E8F5E9", foreground=STATUS_READY)
        self.tree.tag_configure("top", background="#EAF4FF", foreground=PRIMARY)
        self.tree.tag_configure("empty", background="#FFFFFF", foreground=TEXT_MUTED)

    def set_rows(self, rows, best_columns=None, top_row_index=None, top_row_columns=None, empty_text="No results yet."):
        del top_row_columns
        key = (tuple(rows), tuple(sorted(best_columns or [])), top_row_index, empty_text)
        if key == self._last_key:
            return
        self._last_key = key

        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)

        if not rows:
            values = [empty_text] + [""] * (len(self.columns) - 1)
            self.tree.insert("", "end", values=values, tags=("empty",))
            return

        best_columns = set(best_columns or [])
        for row_index, row in enumerate(rows):
            has_best = any(
                index in best_columns and self._is_best_marker(value)
                for index, value in enumerate(row)
            )
            values = tuple(self._strip_marker(value) for value in row)
            if row_index == top_row_index:
                tag = "top"
            elif has_best:
                tag = "best"
            else:
                tag = "even" if row_index % 2 == 0 else "odd"
            self.tree.insert("", "end", values=values, tags=(tag,))

    def _is_best_marker(self, value):
        return isinstance(value, str) and value.startswith("__BEST__")

    def _strip_marker(self, value):
        if self._is_best_marker(value):
            return f"{value.replace('__BEST__', '', 1)} *"
        return value


TRIAL_TIMELINE_COLUMN_CHARS = {
    "Trial": 6,
    "Alpha": 8,
    "Beta": 8,
    "nDCG15": 8,
    "Recall15": 9,
    "Common15": 9,
    "nDCG100": 9,
    "Recall100": 10,
    "Common100": 10,
}


def format_trial_timeline_row(columns, row):
    cells = []
    for column, value in zip(columns, row):
        width = TRIAL_TIMELINE_COLUMN_CHARS.get(column, 8)
        text = str(value)[:width]
        cells.append(text.ljust(width))
    return " ".join(cells) + "\n"


class TrialTimelineTable(ctk.CTkFrame):
    def __init__(self, master, columns, column_widths, **kwargs):
        super().__init__(master, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8, **kwargs)
        self.columns = columns
        self.column_widths = column_widths
        self._row_count = 0
        self._last_key = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.header_text = ctk.CTkTextbox(
            self,
            height=40,
            fg_color=SOFT_BLUE,
            text_color=TEXT_MAIN,
            font=("Consolas", 12, "bold"),
            border_color=BORDER,
            border_width=1,
            corner_radius=8,
            wrap="none",
            activate_scrollbars=False,
        )
        self.header_text.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        self.header_text.insert("1.0", format_trial_timeline_row(self.columns, self.columns))
        self.header_text.configure(state="disabled")

        self.text = ctk.CTkTextbox(
            self,
            fg_color="#FFFFFF",
            text_color=TEXT_MAIN,
            font=("Consolas", 12),
            border_color=BORDER,
            border_width=1,
            corner_radius=8,
            wrap="none",
        )
        self.text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def set_rows(self, rows):
        key = (len(rows), rows[-1] if rows else None)
        if key == self._last_key:
            return
        self._last_key = key

        if len(rows) < self._row_count:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.configure(state="disabled")
            self._row_count = 0

        was_at_bottom = self._row_count == 0 or self.text.yview()[1] >= 0.98
        new_rows = rows[self._row_count :]
        if new_rows:
            self.text.configure(state="normal")
            self.text.insert("end", "".join(self._format_row(row) for row in new_rows))
            if was_at_bottom:
                self.text.see("end")
            self.text.configure(state="disabled")
        self._row_count = len(rows)

    def _format_row(self, row):
        return format_trial_timeline_row(self.columns, row)


class OptimizationView(ctk.CTkFrame):
    def __init__(self, master, state: AppState, start_opt_callback, **kwargs):
        super().__init__(master, fg_color=APP_BG, **kwargs)
        self.state = state
        self.start_opt_callback = start_opt_callback
        self._trial_table_key = None
        self._comparison_table_key = None
        self._progress_summary = "Tuning Engine: idle\nStatus: Idle\nCompleted trial results: 0 / 200\nElapsed time: 0.0s"
        self._rendered_log_count = 0
        self._last_rendered_log = None
        self._disease_summary_key = None
        self._queue_control_key = None
        self._trial_rows_cache = []
        self._trial_rows_source_count = 0
        self.disease_vars = {}
        self.disease_checkboxes = {}
        self.ablation_vars = {}
        self.ablation_checkboxes = {}

        self.grid_columnconfigure(0, weight=6, uniform="opt_cols")
        self.grid_columnconfigure(1, weight=5, uniform="opt_cols")
        self.grid_rowconfigure(0, weight=1)

        self.left_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.left_panel.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="nsew")
        self.left_panel.grid_rowconfigure(0, weight=3, uniform="left_rows")
        self.left_panel.grid_rowconfigure(1, weight=2, uniform="left_rows")
        self.left_panel.grid_columnconfigure(0, weight=1)

        self.result_tabs = ctk.CTkTabview(
            self.left_panel,
            fg_color="transparent",
            command=self._on_result_tab_changed,
        )
        self.result_tabs.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.live_tab = self.result_tabs.add("Live Comparison")
        self.summary_tab = self.result_tabs.add("Disease Summary")

        self.table_card = ctk.CTkFrame(self.live_tab, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.table_card.pack(fill="both", expand=True)
        self.table_title = ctk.CTkLabel(
            self.table_card,
            text="Baselines and Selected BioRank Candidates",
            font=(FONT_FAMILY_HEADER, 17),
            text_color=TEXT_MAIN,
        )
        self.table_title.pack(anchor="w", padx=20, pady=(16, 4))
        self.top_choice_lbl = ctk.CTkLabel(
            self.table_card,
            text="Top choice: waiting for comparison results.",
            font=(FONT_FAMILY_BODY, 12),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.top_choice_lbl.pack(fill="x", padx=20, pady=(0, 8))
        comparison_cols = ("Model", "Alpha", "Beta", "nDCG15", "Recall15", "Common15", "nDCG100", "Recall100", "Common100")
        comparison_widths = {
            "Model": 150,
            "Alpha": 64,
            "Beta": 64,
            "nDCG15": 72,
            "Recall15": 72,
            "Common15": 72,
            "nDCG100": 76,
            "Recall100": 78,
            "Common100": 82,
        }
        self.table = HighlightTable(self.table_card, comparison_cols, comparison_widths)
        self.table.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        summary_cols = ("Disease", "Case", "Top Choice", "Alpha", "Beta", "nDCG15", "Recall15", "Common15", "nDCG100", "Recall100", "Common100")
        summary_widths = {
            "Disease": 70,
            "Case": 150,
            "Top Choice": 150,
            "Alpha": 62,
            "Beta": 62,
            "nDCG15": 68,
            "Recall15": 68,
            "Common15": 70,
            "nDCG100": 72,
            "Recall100": 74,
            "Common100": 78,
        }
        self.disease_summary_table = HighlightTable(self.summary_tab, summary_cols, summary_widths)
        self.disease_summary_table.pack(fill="both", expand=True, padx=0, pady=0)

        self.trial_card = ctk.CTkFrame(self.left_panel, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.trial_card.grid(row=1, column=0, sticky="nsew")
        self.trial_title = ctk.CTkLabel(
            self.trial_card,
            text="Trial Metrics",
            font=(FONT_FAMILY_HEADER, 13),
            text_color=TEXT_MAIN,
        )
        self.trial_title.pack(anchor="w", padx=20, pady=(14, 6))
        trial_cols = ("Trial", "Alpha", "Beta", "nDCG15", "Recall15", "Common15", "nDCG100", "Recall100", "Common100")
        trial_widths = {
            "Trial": 54,
            "Alpha": 62,
            "Beta": 62,
            "nDCG15": 68,
            "Recall15": 68,
            "Common15": 70,
            "nDCG100": 72,
            "Recall100": 74,
            "Common100": 78,
        }
        self.trial_table = TrialTimelineTable(self.trial_card, trial_cols, trial_widths)
        self.trial_table.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=0, column=1, padx=(10, 20), pady=20, sticky="nsew")

        self.config_card = ctk.CTkFrame(self.right_panel, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.config_card.pack(fill="x", pady=(0, 10))
        self.config_card.grid_columnconfigure(0, weight=1)
        self.config_card.grid_columnconfigure(1, weight=1)

        self.config_title = ctk.CTkLabel(self.config_card, text="Hyperparameter Optimization (Optuna)", font=(FONT_FAMILY_HEADER, 17), text_color=TEXT_MAIN)
        self.config_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 12))

        self.trials_lbl = ctk.CTkLabel(self.config_card, text="Number of Trials:", font=(FONT_FAMILY_BODY, 13), text_color=TEXT_MAIN)
        self.trials_lbl.grid(row=1, column=0, sticky="w", padx=(20, 10), pady=4)

        self.trials_entry = ctk.CTkEntry(self.config_card, width=120, height=32, font=(FONT_FAMILY_BODY, 13), corner_radius=6)
        self.trials_entry.grid(row=1, column=1, sticky="w", pady=4)
        self.trials_entry.insert(0, str(state.optuna_max_trials))

        self.seed_lbl = ctk.CTkLabel(self.config_card, text="Random Seed:", font=(FONT_FAMILY_BODY, 13), text_color=TEXT_MAIN)
        self.seed_lbl.grid(row=2, column=0, sticky="w", padx=(20, 10), pady=4)

        self.seed_entry = ctk.CTkEntry(self.config_card, width=120, height=32, font=(FONT_FAMILY_BODY, 13), corner_radius=6)
        self.seed_entry.grid(row=2, column=1, sticky="w", pady=4)
        self.seed_entry.insert(0, "42")

        self.opt_mode_tabs = ctk.CTkTabview(self.config_card, fg_color="transparent", height=160)
        self.opt_mode_tabs.grid(row=3, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 8))
        self.single_opt_tab = self.opt_mode_tabs.add("Single Disease")
        self.batch_opt_tab = self.opt_mode_tabs.add("Batch Queue")

        ctk.CTkLabel(
            self.single_opt_tab,
            text="Optimize alpha and beta for one cancer type.",
            font=(FONT_FAMILY_BODY, 13),
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 6))
        self.single_disease_dropdown = ctk.CTkOptionMenu(
            self.single_opt_tab,
            values=DISEASES,
            fg_color=PRIMARY,
            button_color=PRIMARY,
            button_hover_color=STATUS_RUNNING,
            text_color="#FFFFFF",
            font=(FONT_FAMILY_HEADER, 14),
            height=34,
            corner_radius=6,
        )
        self.single_disease_dropdown.pack(fill="x", padx=10, pady=(0, 8))
        self.single_disease_dropdown.set(self.state.current_disease)

        self.disease_queue_lbl = ctk.CTkLabel(
            self.batch_opt_tab,
            text="Sequential disease queue",
            font=(FONT_FAMILY_HEADER, 14),
            text_color=TEXT_MAIN,
            anchor="w",
        )
        self.disease_queue_lbl.pack(fill="x", padx=10, pady=(8, 4))
        self.disease_queue_frame = ctk.CTkFrame(self.batch_opt_tab, fg_color="transparent")
        self.disease_queue_frame.pack(fill="x", padx=10, pady=(0, 4))
        for index, disease in enumerate(DISEASES):
            variable = BooleanVar(value=disease == self.state.current_disease)
            self.disease_vars[disease] = variable
            checkbox = ctk.CTkCheckBox(
                self.disease_queue_frame,
                text=disease,
                variable=variable,
                font=(FONT_FAMILY_BODY, 13),
                checkbox_width=20,
                checkbox_height=20,
                width=90,
            )
            checkbox.grid(row=index // 4, column=index % 4, sticky="w", padx=(0, 8), pady=2)
            self.disease_checkboxes[disease] = checkbox
        self.disease_queue_actions = ctk.CTkFrame(self.batch_opt_tab, fg_color="transparent")
        self.disease_queue_actions.pack(fill="x", padx=10, pady=(0, 8))
        self.disease_current_btn = ctk.CTkButton(
            self.disease_queue_actions,
            text="Current",
            width=82,
            height=28,
            fg_color=SOFT_BLUE,
            text_color=PRIMARY,
            hover_color=BORDER,
            command=self._select_current_disease,
        )
        self.disease_current_btn.pack(side="left", padx=(0, 8))
        self.disease_all_btn = ctk.CTkButton(
            self.disease_queue_actions,
            text="All diseases",
            width=100,
            height=28,
            fg_color=SOFT_BLUE,
            text_color=PRIMARY,
            hover_color=BORDER,
            command=self._select_all_diseases,
        )
        self.disease_all_btn.pack(side="left")

        self.ablation_lbl = ctk.CTkLabel(
            self.config_card,
            text="Ablation cases",
            font=(FONT_FAMILY_HEADER, 14),
            text_color=TEXT_MAIN,
            anchor="w",
        )
        self.ablation_lbl.grid(row=4, column=0, columnspan=2, sticky="w", padx=20, pady=(8, 4))
        self.ablation_frame = ctk.CTkFrame(self.config_card, fg_color="transparent")
        self.ablation_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 4))
        for index, mode in enumerate(ABLATION_MODE_ORDER):
            variable = BooleanVar(value=mode == ABLATION_MODE_FULL)
            self.ablation_vars[mode] = variable
            checkbox = ctk.CTkCheckBox(
                self.ablation_frame,
                text=ABLATION_MODE_LABELS[mode],
                variable=variable,
                font=(FONT_FAMILY_BODY, 12),
                checkbox_width=20,
                checkbox_height=20,
            )
            checkbox.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 12), pady=2)
            self.ablation_checkboxes[mode] = checkbox
        self.ablation_actions = ctk.CTkFrame(self.config_card, fg_color="transparent")
        self.ablation_actions.grid(row=6, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 8))
        self.ablation_full_btn = ctk.CTkButton(
            self.ablation_actions,
            text="Full only",
            width=82,
            height=28,
            fg_color=SOFT_BLUE,
            text_color=PRIMARY,
            hover_color=BORDER,
            command=self._select_full_ablation,
        )
        self.ablation_full_btn.pack(side="left", padx=(0, 8))
        self.ablation_all_btn = ctk.CTkButton(
            self.ablation_actions,
            text="All cases",
            width=92,
            height=28,
            fg_color=SOFT_BLUE,
            text_color=PRIMARY,
            hover_color=BORDER,
            command=self._select_all_ablation,
        )
        self.ablation_all_btn.pack(side="left")

        self.run_btn = ctk.CTkButton(
            self.config_card,
            text="Start Optimization",
            font=(FONT_FAMILY_HEADER, 13, "bold"),
            fg_color=PRIMARY,
            hover_color=STATUS_RUNNING,
            text_color="#FFFFFF",
            height=40,
            corner_radius=6,
            command=self._on_start_opt,
        )
        self.run_btn.grid(row=1, column=1, rowspan=2, columnspan=2, padx=(150, 20), pady=4, sticky="e")

        self.console_card = ctk.CTkFrame(self.right_panel, fg_color="#0F172A", border_color="#1E293B", border_width=1, corner_radius=8)
        self.console_card.pack(fill="both", expand=True, pady=(10, 0))
        self.console_title = ctk.CTkLabel(
            self.console_card,
            text="Optimization Progress",
            font=(FONT_FAMILY_HEADER, 12, "bold"),
            text_color="#38BDF8",
        )
        self.console_title.pack(anchor="w", padx=12, pady=(8, 4))
        self.progress_label = ctk.CTkLabel(
            self.console_card,
            text=self._progress_summary,
            font=("Consolas", 12),
            text_color="#BAE6FD",
            fg_color="#0F172A",
            justify="left",
            anchor="w",
        )
        self.progress_label.pack(fill="x", padx=12, pady=(0, 6))
        self.log_text = ctk.CTkTextbox(
            self.console_card,
            fg_color="#0F172A",
            text_color="#38BDF8",
            font=("Consolas", 12),
            border_width=0,
            corner_radius=0,
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log_text.configure(state="disabled")

    def _on_start_opt(self):
        try:
            trials = int(self.trials_entry.get())
            seed = int(self.seed_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Entries", "Number of trials and seed must be valid integer numbers.")
            return
        if self.opt_mode_tabs.get() == "Single Disease":
            diseases = [self.single_disease_dropdown.get()]
        else:
            diseases = [disease for disease, variable in self.disease_vars.items() if variable.get()]
        if not diseases:
            messagebox.showerror("Invalid Disease Queue", "Select at least one disease for optimization.")
            return

        ablation_modes = [mode for mode, variable in self.ablation_vars.items() if variable.get()]
        if not ablation_modes:
            messagebox.showerror("Invalid Ablation Queue", "Select at least one ablation case.")
            return

        self.start_opt_callback(trials, seed, diseases, ablation_modes)

    def _select_current_disease(self):
        self.single_disease_dropdown.set(self.state.current_disease)
        for disease, variable in self.disease_vars.items():
            variable.set(disease == self.state.current_disease)

    def _select_all_diseases(self):
        for variable in self.disease_vars.values():
            variable.set(True)

    def _select_full_ablation(self):
        for mode, variable in self.ablation_vars.items():
            variable.set(mode == ABLATION_MODE_FULL)

    def _select_all_ablation(self):
        for variable in self.ablation_vars.values():
            variable.set(True)

    def update_view(self):
        self._sync_disease_queue_controls()
        self._update_progress()
        self._update_log_console()
        self._update_active_result_table()
        self._update_trial_table()

    def _on_result_tab_changed(self):
        self._update_active_result_table()

    def _update_active_result_table(self):
        if self.result_tabs.get() == "Disease Summary":
            self._update_disease_summary_table()
        else:
            self._update_comparison_table()

    def _update_trial_table(self):
        trials = self.state.optuna_trials
        if len(trials) < self._trial_rows_source_count:
            self._trial_rows_cache = []
            self._trial_rows_source_count = 0
            if not trials:
                self.trial_table.set_rows([])
                return

        if len(trials) == self._trial_rows_source_count:
            return

        for trial in trials[self._trial_rows_source_count:]:
            self._trial_rows_cache.append(
                (
                    str(trial["trial_id"]),
                    self._fmt_parameter(trial["alpha"]),
                    self._fmt_parameter(trial["beta"]),
                    self._fmt(trial["ndcg_15"]),
                    self._fmt(trial["recall_15"]),
                    str(trial.get("common_15", 0)),
                    self._fmt(trial["ndcg_100"]),
                    self._fmt(trial["recall_100"]),
                    str(trial["common_100"]),
                )
            )
        self._trial_rows_source_count = len(trials)
        self.trial_table.set_rows(self._trial_rows_cache)

    def _update_progress(self):
        if self.state.is_running:
            baseline = self.state.optuna_baselines
            current_disease = self.state.optuna_current_disease or "pending"
            current_case = ablation_label(self.state.optuna_current_ablation) if self.state.optuna_current_disease else "pending"
            remaining_queue = ", ".join(self.state.optuna_disease_queue) if self.state.optuna_disease_queue else "none"
            completed = ", ".join(self.state.optuna_completed_diseases) if self.state.optuna_completed_diseases else "none"
            self._progress_summary = (
                f"Tuning Engine: {self.state.optuna_phase}\n"
                f"Status: {self.state.optuna_status_text}\n"
                f"Current disease: {current_disease}\n"
                f"Current case: {current_case}\n"
                f"Queue: {remaining_queue}\n"
                f"Completed diseases: {completed}\n"
                f"Current trial: {self.state.optuna_current_trial} / {self.state.optuna_max_trials}\n"
                f"Completed trial results: {len(self.state.optuna_trials)}\n"
                f"Baselines: PageRank={baseline['pagerank']}, BRWR Lite={baseline['random_walk']}, BioRank Lite={baseline['biorank_lite']}\n"
                f"Elapsed time: {self.state.optuna_elapsed_time:.1f}s"
            )
            return

        trial_count = len(self.state.optuna_trials)
        completed = ", ".join(self.state.optuna_completed_diseases) if self.state.optuna_completed_diseases else "none"
        self._progress_summary = (
            f"Tuning Engine: {self.state.optuna_phase}\n"
            f"Status: {self.state.optuna_status_text}\n"
            f"Completed diseases: {completed}\n"
            f"Completed trial results: {trial_count} / {self.state.optuna_max_trials}\n"
            f"Elapsed time: {self.state.optuna_elapsed_time:.1f}s"
        )

    def _update_log_console(self):
        self.progress_label.configure(text=self._progress_summary)
        logs = self.state.optuna_logs
        if not logs:
            if self._rendered_log_count:
                self.log_text.configure(state="normal")
                self.log_text.delete("1.0", "end")
                self.log_text.configure(state="disabled")
            self._rendered_log_count = 0
            self._last_rendered_log = None
            return

        rebuild = len(logs) < self._rendered_log_count
        if not rebuild and self._last_rendered_log in logs:
            last_index = len(logs) - 1 - list(reversed(logs)).index(self._last_rendered_log)
            new_logs = logs[last_index + 1 :]
        elif not rebuild and self._rendered_log_count <= len(logs):
            new_logs = logs[self._rendered_log_count :]
        else:
            new_logs = logs
        if not new_logs and logs[-1] != self._last_rendered_log:
            rebuild = True
            new_logs = logs
        if not new_logs:
            return

        was_at_bottom = self.log_text.yview()[1] >= 0.98
        self.log_text.configure(state="normal")
        line_count = int(float(self.log_text.index("end-1c"))) if self._rendered_log_count else 0
        if rebuild or line_count > 600:
            self.log_text.delete("1.0", "end")
            new_logs = logs
        self.log_text.insert("end", "\n".join(new_logs) + "\n")
        if was_at_bottom:
            self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self._rendered_log_count = len(logs)
        self._last_rendered_log = logs[-1]

    def _update_comparison_table(self):
        rows, best_columns, top_row_index = self._mark_best_cells(
            self.state.optuna_comparison,
            metric_columns=(3, 4, 5, 6, 7, 8),
            objective_columns=(6, 7, 8),
        )
        table_key = (tuple(rows), tuple(sorted(best_columns)), top_row_index)
        if table_key == self._comparison_table_key:
            return
        self._comparison_table_key = table_key
        if rows and top_row_index is not None:
            top_row = rows[top_row_index]
            self.top_choice_lbl.configure(
                text=(
                    f"Top choice: {self._strip_marker(top_row[0])} | "
                    f"nDCG100 {self._strip_marker(top_row[6])} | "
                    f"Recall100 {self._strip_marker(top_row[7])} | "
                    f"Common100 {self._strip_marker(top_row[8])}"
                ),
                text_color=STATUS_READY,
                font=(FONT_FAMILY_BODY, 12, "bold"),
            )
        else:
            self.top_choice_lbl.configure(
                text="Top choice: waiting for comparison results.",
                text_color=TEXT_MUTED,
                font=(FONT_FAMILY_BODY, 12),
            )
        self.table.set_rows(
            rows,
            best_columns=best_columns,
            top_row_index=top_row_index,
            top_row_columns=(0, 3, 4, 5, 6, 7, 8),
            empty_text="Baseline and selected BioRank candidate results will appear here.",
        )

    def _update_disease_summary_table(self):
        rows = []
        for summary in self.state.optuna_disease_summary:
            rows.append(
                (
                    summary["disease"],
                    summary.get("ablation_label", ""),
                    summary["top_choice"],
                    self._fmt(summary["alpha"]),
                    self._fmt(summary["beta"]),
                    self._fmt(summary["ndcg_15"]),
                    self._fmt(summary["recall_15"]),
                    str(summary["common_15"]),
                    self._fmt(summary["ndcg_100"]),
                    self._fmt(summary["recall_100"]),
                    str(summary["common_100"]),
                )
            )

        marked_rows, best_columns, top_row_index = self._mark_best_cells(
            rows,
            metric_columns=(5, 6, 7, 8, 9, 10),
            objective_columns=(8, 9, 10),
        )
        summary_key = (tuple(marked_rows), tuple(sorted(best_columns)), top_row_index)
        if summary_key == self._disease_summary_key:
            return
        self._disease_summary_key = summary_key
        self.disease_summary_table.set_rows(
            marked_rows,
            best_columns=best_columns,
            top_row_index=top_row_index,
            top_row_columns=(0, 1, 2, 5, 6, 7, 8, 9, 10),
            empty_text="Completed disease summaries will appear here.",
        )

    def _sync_disease_queue_controls(self):
        if self.state.is_running:
            key = (
                "running",
                self.state.optuna_current_disease,
                self.state.optuna_current_ablation,
                tuple(self.state.optuna_disease_queue),
            )
            if key == self._queue_control_key:
                return
            self._queue_control_key = key
            self.single_disease_dropdown.configure(state="disabled")
            remaining = set(self.state.optuna_disease_queue)
            for disease, variable in self.disease_vars.items():
                variable.set(disease in remaining)
                checkbox = self.disease_checkboxes.get(disease)
                if checkbox is not None:
                    checkbox.configure(state="disabled")
            self.disease_current_btn.configure(state="disabled")
            self.disease_all_btn.configure(state="disabled")
            for checkbox in self.ablation_checkboxes.values():
                checkbox.configure(state="disabled")
            self.ablation_full_btn.configure(state="disabled")
            self.ablation_all_btn.configure(state="disabled")
            return

        key = ("idle",)
        if key == self._queue_control_key:
            return
        self._queue_control_key = key
        self.single_disease_dropdown.configure(state="normal")
        if self.single_disease_dropdown.get() not in DISEASES:
            self.single_disease_dropdown.set(self.state.current_disease)
        for checkbox in self.disease_checkboxes.values():
            checkbox.configure(state="normal")
        self.disease_current_btn.configure(state="normal")
        self.disease_all_btn.configure(state="normal")
        for checkbox in self.ablation_checkboxes.values():
            checkbox.configure(state="normal")
        self.ablation_full_btn.configure(state="normal")
        self.ablation_all_btn.configure(state="normal")

    def _mark_best_cells(self, rows, metric_columns, objective_columns):
        if not rows:
            return [], set(), None

        best_values = {}
        for column in metric_columns:
            values = [self._float(row[column]) for row in rows]
            best_values[column] = max(values) if values else 0.0

        top_row_index = max(
            range(len(rows)),
            key=lambda index: tuple(self._float(rows[index][column]) for column in objective_columns),
        )
        marked_rows = []
        for row in rows:
            marked = []
            for column, value in enumerate(row):
                if column in best_values and abs(self._float(value) - best_values[column]) < 1e-12:
                    marked.append(f"__BEST__{value}")
                else:
                    marked.append(value)
            marked_rows.append(tuple(marked))
        return marked_rows, set(metric_columns), top_row_index

    def _fmt(self, value):
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value or "")

    def _fmt_parameter(self, value):
        return "N/A" if value in (None, "") else self._fmt(value)

    def _float(self, value):
        try:
            return float(str(value).replace("__BEST__", ""))
        except (TypeError, ValueError):
            return 0.0

    def _strip_marker(self, value):
        return str(value).replace("__BEST__", "", 1)
