from tkinter import BooleanVar, messagebox

import customtkinter as ctk

from biorank_ui.config import DISEASES
from biorank_ui.state import AppState
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
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.header_frame = ctk.CTkFrame(self, fg_color=SOFT_BLUE, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        for index, column in enumerate(columns):
            self.header_frame.grid_columnconfigure(index, weight=1)
            label = ctk.CTkLabel(
                self.header_frame,
                text=column,
                font=(FONT_FAMILY_HEADER, 12, "bold"),
                text_color=TEXT_MAIN,
                anchor="w",
                width=column_widths.get(column, 90),
            )
            label.grid(row=0, column=index, sticky="ew", padx=6, pady=8)

        self.body = ctk.CTkScrollableFrame(self, fg_color="#FFFFFF", corner_radius=0)
        self.body.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        for index in range(len(columns)):
            self.body.grid_columnconfigure(index, weight=1)

    def set_rows(self, rows, best_columns=None, top_row_index=None, top_row_columns=None, empty_text="No results yet."):
        for child in self.body.winfo_children():
            child.destroy()

        if not rows:
            empty = ctk.CTkLabel(
                self.body,
                text=empty_text,
                font=(FONT_FAMILY_BODY, 13),
                text_color=TEXT_MUTED,
                anchor="w",
            )
            empty.grid(row=0, column=0, columnspan=len(self.columns), sticky="ew", padx=10, pady=12)
            return

        best_columns = set(best_columns or [])
        top_row_columns = set(top_row_columns) if top_row_columns is not None else None
        for row_index, row in enumerate(rows):
            row_is_top = row_index == top_row_index
            for col_index, value in enumerate(row):
                is_best = col_index in best_columns and self._is_best_marker(value)
                is_top_cell = row_is_top and (top_row_columns is None or col_index in top_row_columns)
                display_value = self._strip_marker(value)
                fg_color = "#E8F5E9" if is_best else ("#EAF4FF" if is_top_cell else ("#FFFFFF" if row_index % 2 == 0 else APP_BG))
                text_color = STATUS_READY if is_best else TEXT_MAIN
                font = (FONT_FAMILY_BODY, 12, "bold") if is_best or is_top_cell else (FONT_FAMILY_BODY, 12)
                label = ctk.CTkLabel(
                    self.body,
                    text=display_value,
                    font=font,
                    text_color=text_color,
                    fg_color=fg_color,
                    anchor="w",
                    width=self.column_widths.get(self.columns[col_index], 90),
                    corner_radius=4 if is_best or is_top_cell else 0,
                )
                label.grid(row=row_index, column=col_index, sticky="ew", padx=2, pady=2)

    def _is_best_marker(self, value):
        return isinstance(value, str) and value.startswith("__BEST__")

    def _strip_marker(self, value):
        if self._is_best_marker(value):
            return value.replace("__BEST__", "", 1)
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
        self.disease_vars = {}
        self.disease_checkboxes = {}

        self.grid_columnconfigure(0, weight=6, uniform="opt_cols")
        self.grid_columnconfigure(1, weight=5, uniform="opt_cols")
        self.grid_rowconfigure(0, weight=1)

        self.left_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.left_panel.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="nsew")
        self.left_panel.grid_rowconfigure(0, weight=3, uniform="left_rows")
        self.left_panel.grid_rowconfigure(1, weight=2, uniform="left_rows")
        self.left_panel.grid_columnconfigure(0, weight=1)

        self.result_tabs = ctk.CTkTabview(self.left_panel, fg_color="transparent")
        self.result_tabs.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.live_tab = self.result_tabs.add("Live Comparison")
        self.summary_tab = self.result_tabs.add("Disease Summary")

        self.table_card = ctk.CTkFrame(self.live_tab, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.table_card.pack(fill="both", expand=True)
        self.table_title = ctk.CTkLabel(
            self.table_card,
            text="Live Comparison: Baselines vs Current Top Candidates",
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

        summary_cols = ("Disease", "Top Choice", "Alpha", "Beta", "nDCG15", "Recall15", "Common15", "nDCG100", "Recall100", "Common100")
        summary_widths = {
            "Disease": 70,
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
            text="Trial Timeline Results",
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
            text="Run Optuna for one disease profile.",
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

        self.run_btn = ctk.CTkButton(
            self.config_card,
            text="Start Optuna Engine",
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
            text="Optuna Progress & Log Console",
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

        self.start_opt_callback(trials, seed, diseases)

    def _select_current_disease(self):
        self.single_disease_dropdown.set(self.state.current_disease)
        for disease, variable in self.disease_vars.items():
            variable.set(disease == self.state.current_disease)

    def _select_all_diseases(self):
        for variable in self.disease_vars.values():
            variable.set(True)

    def update_view(self):
        self._sync_disease_queue_controls()
        self._update_progress()
        self._update_log_console()
        self._update_comparison_table()
        self._update_disease_summary_table()
        self._update_trial_table()

    def _update_trial_table(self):
        rows = []
        for trial in self.state.optuna_trials:
            rows.append(
                (
                    str(trial["trial_id"]),
                    self._fmt(trial["alpha"]),
                    self._fmt(trial["beta"]),
                    self._fmt(trial["ndcg_15"]),
                    self._fmt(trial["recall_15"]),
                    str(trial.get("common_15", 0)),
                    self._fmt(trial["ndcg_100"]),
                    self._fmt(trial["recall_100"]),
                    str(trial["common_100"]),
                )
            )
        self.trial_table.set_rows(rows)

    def _update_progress(self):
        if self.state.is_running:
            baseline = self.state.optuna_baselines
            current_disease = self.state.optuna_current_disease or "pending"
            remaining_queue = ", ".join(self.state.optuna_disease_queue) if self.state.optuna_disease_queue else "none"
            completed = ", ".join(self.state.optuna_completed_diseases) if self.state.optuna_completed_diseases else "none"
            self._progress_summary = (
                f"Tuning Engine: {self.state.optuna_phase}\n"
                f"Status: {self.state.optuna_status_text}\n"
                f"Current disease: {current_disease}\n"
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
            metric_columns=(4, 5, 6, 7, 8, 9),
            objective_columns=(7, 8, 9),
        )
        summary_key = (tuple(marked_rows), tuple(sorted(best_columns)), top_row_index)
        if summary_key == self._disease_summary_key:
            return
        self._disease_summary_key = summary_key
        self.disease_summary_table.set_rows(
            marked_rows,
            best_columns=best_columns,
            top_row_index=top_row_index,
            top_row_columns=(0, 1, 4, 5, 6, 7, 8, 9),
            empty_text="Completed disease summaries will appear here.",
        )

    def _sync_disease_queue_controls(self):
        if self.state.is_running:
            key = ("running", self.state.optuna_current_disease, tuple(self.state.optuna_disease_queue))
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

    def _float(self, value):
        try:
            return float(str(value).replace("__BEST__", ""))
        except (TypeError, ValueError):
            return 0.0

    def _strip_marker(self, value):
        return str(value).replace("__BEST__", "", 1)
