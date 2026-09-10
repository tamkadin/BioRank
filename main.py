import os
import sys
import threading
import time
from tkinter import filedialog, messagebox

import customtkinter as ctk

# Imports configurations, themes, states, and components
from biorank_ui.config import (
    DATASET_DIR,
    DISEASES,
    EVALUATION_MODE_DISPLAY_LABELS,
    SEED_PROFILE_LABELS,
    build_default_state_file_paths,
    get_dataset_profile_label,
    get_dataset_profile_value,
    get_evaluation_mode_label,
    get_evaluation_mode_value,
)
from BioRank.optimization.ablation_config import (
    ABLATION_MODE_FULL,
    ablation_label,
    required_input_keys,
)
from biorank_ui.theme import (
    APP_BG, CARD_BG, BORDER, PRIMARY, DEEP_BLUE, SOFT_BLUE, TEXT_MAIN, TEXT_MUTED,
    STATUS_READY, STATUS_RUNNING, STATUS_ERROR,
    FONT_FAMILY_HEADER, FONT_FAMILY_BODY
)
from biorank_ui.state import AppState
from biorank_ui.service import BackendService
from biorank_ui.components import DataTable, ProgressOverlay
from biorank_ui.preprocessing_dialog import PreprocessingInputDialog

# Imports modular subviews
from biorank_ui.views.dashboard_view import DashboardView
from biorank_ui.views.preprocessing_view import PreprocessingView
from biorank_ui.views.ranking_view import RankingView
from biorank_ui.views.optimization_view import OptimizationView

OPTUNA_UI_UPDATE_DELAY_MS = 250
OPTUNA_HEARTBEAT_MS = 1000


class BioRankApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("BioRank: Cancer Gene Prioritization Workspace")
        
        # Responsive Window Fitting (Initial geometry safe for OS scaling, maximizes immediately)
        self.geometry("1200x750")
        self.minsize(1024, 640)
        self._maximize_window()
        
        # Central state and backend service instances
        self.app_state = AppState()
        self.service = BackendService(self.app_state)
        
        # Register state listeners
        self.app_state.add_listener(self.on_state_updated)
        
        # Grid splits: Column 0 (Sidebar), Column 1 (Main content container)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar layout
        self.sidebar_frame = ctk.CTkFrame(self, fg_color=DEEP_BLUE, corner_radius=0, width=240)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)
        
        # Content layout container
        self.main_container = ctk.CTkFrame(self, fg_color=APP_BG, corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew")
        
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=0) # HeaderBar
        self.main_container.grid_rowconfigure(1, weight=1) # View frames container
        
        self._build_sidebar()
        self._build_headerbar()
        self._build_content_views()
        
        self.overlay = None
        self.preprocessing_input_drafts = {}
        self._optuna_ui_start_time = None
        self._optuna_heartbeat_job = None
        self._optuna_update_job = None
        self._pending_optuna_update = None
        self.active_view_key = None
        
        # Mount initial Dashboard view
        self.switch_view("dashboard")
        
    def _maximize_window(self):
        try:
            # Native Windows maximize
            self.state('zoomed')
        except Exception:
            try:
                # macOS / Linux maximize fallback
                self.wm_attributes('-zoomed', True)
            except Exception:
                pass

    def _build_sidebar(self):
        self.logo_lbl = ctk.CTkLabel(self.sidebar_frame, text="BioRank Workspace", font=(FONT_FAMILY_HEADER, 21, "bold"), text_color="#FFFFFF")
        self.logo_lbl.pack(padx=20, pady=28, anchor="w")
        
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "1. Input Data Readiness"),
            ("preprocessing", "2. Data Preprocessing"),
            ("ranking", "3. Cancer Gene Ranking"),
            ("optimization", "4. Parameter Optimization"),
        ]
        
        for key, label in nav_items:
            btn = ctk.CTkButton(self.sidebar_frame, text=label, font=(FONT_FAMILY_HEADER, 15),
                                 fg_color="transparent", text_color="#FFFFFF", hover_color="#1E88E5",
                                 height=42, anchor="w", corner_radius=6, command=lambda k=key: self.switch_view(k))
            btn.pack(fill="x", padx=16, pady=4)
            self.nav_buttons[key] = btn
            
        self.footer_lbl = ctk.CTkLabel(self.sidebar_frame, text="BioRank v2.0\nCreated by Nguyen Huu Tam", font=(FONT_FAMILY_BODY, 12), text_color="#89AECF", justify="center")
        self.footer_lbl.pack(side="bottom", pady=24)

    def _build_headerbar(self):
        self.headerbar = ctk.CTkFrame(self.main_container, fg_color=CARD_BG, height=64, corner_radius=0, border_color=BORDER, border_width=1)
        self.headerbar.grid(row=0, column=0, sticky="ew")
        
        self.disease_lbl = ctk.CTkLabel(self.headerbar, text="Cancer type:", font=(FONT_FAMILY_HEADER, 14), text_color=TEXT_MAIN)
        self.disease_lbl.pack(side="left", padx=(12, 4))
        
        self.disease_combo = ctk.CTkComboBox(self.headerbar, values=DISEASES, font=(FONT_FAMILY_HEADER, 15),
                                             fg_color=APP_BG, text_color=TEXT_MAIN, button_color=PRIMARY,
                                             button_hover_color=STATUS_RUNNING, height=34, width=88, command=self._on_disease_changed)
        self.disease_combo.pack(side="left", padx=4)
        self.disease_combo.set(self.app_state.current_disease)

        self.dataset_profile_lbl = ctk.CTkLabel(
            self.headerbar,
            text="Seed profile:",
            font=(FONT_FAMILY_HEADER, 14),
            text_color=TEXT_MAIN,
        )
        self.dataset_profile_lbl.pack(side="left", padx=(12, 4))
        self.dataset_profile_combo = ctk.CTkComboBox(
            self.headerbar,
            values=SEED_PROFILE_LABELS,
            font=(FONT_FAMILY_HEADER, 14),
            fg_color=APP_BG,
            text_color=TEXT_MAIN,
            button_color=PRIMARY,
            button_hover_color=STATUS_RUNNING,
            height=34,
            width=108,
            command=self._on_dataset_profile_changed,
        )
        self.dataset_profile_combo.pack(side="left", padx=4)
        self.dataset_profile_combo.set(
            get_dataset_profile_label(self.app_state.dataset_profile)
        )

        self.validation_reference_lbl = ctk.CTkLabel(
            self.headerbar,
            text="Validation set:",
            font=(FONT_FAMILY_HEADER, 13),
            text_color=TEXT_MUTED,
        )
        self.validation_reference_lbl.pack(side="left", padx=(16, 4))
        self.validation_reference_combo = ctk.CTkComboBox(
            self.headerbar,
            values=EVALUATION_MODE_DISPLAY_LABELS,
            font=(FONT_FAMILY_HEADER, 13),
            fg_color=APP_BG,
            text_color=TEXT_MAIN,
            button_color=PRIMARY,
            button_hover_color=STATUS_RUNNING,
            height=34,
            width=175,
            command=self._on_evaluation_mode_changed,
        )
        self.validation_reference_combo.pack(side="left", padx=4)
        self.validation_reference_combo.set(
            get_evaluation_mode_label(self.app_state.evaluation_mode)
        )
        
        self.header_status_lbl = ctk.CTkLabel(self.headerbar, text="| Status: Idle", font=(FONT_FAMILY_BODY, 14), text_color=TEXT_MUTED)
        self.header_status_lbl.pack(side="left", padx=15)
        
        self.active_indicator = ctk.CTkLabel(self.headerbar, text="● Online Ready", font=(FONT_FAMILY_HEADER, 13, "bold"), text_color=STATUS_READY)
        self.active_indicator.pack(side="right", padx=20)

    def _build_content_views(self):
        self.view_container = ctk.CTkFrame(self.main_container, fg_color="transparent", corner_radius=0)
        self.view_container.grid(row=1, column=0, sticky="nsew")
        
        self.view_container.grid_columnconfigure(0, weight=1)
        self.view_container.grid_rowconfigure(0, weight=1)
        
        # Mount views dynamically
        self.views = {
            "dashboard": DashboardView(self.view_container, self.app_state, self.browse_dataset_card_file, self.browse_validation_reference_file),
            "preprocessing": PreprocessingView(self.view_container, self.app_state, self.trigger_preprocessing_step),
            "ranking": RankingView(self.view_container, self.app_state, self.build_network, self.open_preview_window, self.run_prioritization, self.run_ranking_batch),
            "optimization": OptimizationView(self.view_container, self.app_state, self.trigger_optuna_tuning)
        }
        
        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")
            
    def switch_view(self, view_key):
        if view_key not in self.views: return
        
        for key, btn in self.nav_buttons.items():
            if key == view_key:
                btn.configure(fg_color=PRIMARY)
            else:
                btn.configure(fg_color="transparent")
                
        self.views[view_key].tkraise()
        self.active_view_key = view_key
        
        if hasattr(self.views[view_key], "update_view"):
            self.views[view_key].update_view()

    def _on_disease_changed(self, value):
        if self.app_state.is_running:
            messagebox.showwarning("Run in progress", "Cannot change disease while a pipeline task is running.")
            self.disease_combo.set(self.app_state.current_disease)
            return
        self.app_state.set_disease(value)
        missing = self._missing_profile_files([value])
        if missing:
            profile_label = get_dataset_profile_label(self.app_state.dataset_profile)
            self.header_status_lbl.configure(text=f"| Status: {profile_label} inputs incomplete for {value}")
            messagebox.showwarning("Seed profile incomplete", self._format_missing_profile_message(missing))
        else:
            self.header_status_lbl.configure(text=f"| Status: Cancer type set to {value}")

    def _on_dataset_profile_changed(self, value):
        if self.app_state.is_running:
            messagebox.showwarning("Run in progress", "Cannot change the seed profile while a pipeline task is running.")
            self.dataset_profile_combo.set(
                get_dataset_profile_label(self.app_state.dataset_profile)
            )
            return
        dataset_profile = get_dataset_profile_value(value)
        self.app_state.set_dataset_profile(dataset_profile)
        missing = self._missing_profile_files([self.app_state.current_disease])
        if missing:
            self.header_status_lbl.configure(text=f"| Status: {value} inputs incomplete for {self.app_state.current_disease}")
            messagebox.showwarning("Seed profile incomplete", self._format_missing_profile_message(missing))
        else:
            self.header_status_lbl.configure(text=f"| Status: Using {value} seed profile")

    def _on_evaluation_mode_changed(self, value):
        if self.app_state.is_running:
            messagebox.showwarning("Run in progress", "Cannot change validation set while a pipeline task is running.")
            self.validation_reference_combo.set(
                get_evaluation_mode_label(self.app_state.evaluation_mode)
            )
            return
        evaluation_mode = get_evaluation_mode_value(value)
        self.app_state.set_evaluation_mode(evaluation_mode)
        missing = self._missing_profile_files([self.app_state.current_disease])
        if missing:
            self.header_status_lbl.configure(text=f"| Status: {value} validation missing for {self.app_state.current_disease}")
            messagebox.showwarning("Validation reference missing", self._format_missing_profile_message(missing))
        else:
            self.header_status_lbl.configure(text=f"| Status: Using {value} validation")

    def browse_dataset_card_file(self, key):
        if self.app_state.is_running:
            messagebox.showwarning("Run in progress", "Cannot change input files while a pipeline task is running.")
            return
        input_labels = {
            "ppi": "PPI network",
            "coexpression": "co-expression network",
            "seed": "cancer gene seed set",
            "de_genes": "differentially expressed genes",
            "ontology_map": "gene-ontology annotation network",
            "disease_ontology": "disease-specific ontology terms",
        }
        current_path = self.app_state.file_paths.get(key, "")
        initial_dir = os.path.dirname(current_path) if current_path else DATASET_DIR
        if not os.path.isdir(initial_dir):
            initial_dir = DATASET_DIR
        input_label = input_labels.get(key, "biological input")
        file_path = filedialog.askopenfilename(
            title=f"Select {input_label}",
            initialdir=initial_dir,
            filetypes=[("Tab/text files", ("*.tsv", "*.txt", "*.csv")), ("All files", "*")],
        )
        if file_path:
            self.app_state.set_file_path(key, file_path)
            self.header_status_lbl.configure(text=f"| Status: Selected {input_label}")

    def browse_validation_reference_file(self):
        if self.app_state.is_running:
            messagebox.showwarning("Run in progress", "Cannot change validation file while a pipeline task is running.")
            return
        current_path = getattr(self.app_state, "validation_file_path", "")
        initial_dir = os.path.dirname(current_path) if current_path else DATASET_DIR
        if not os.path.isdir(initial_dir):
            initial_dir = DATASET_DIR
        file_path = filedialog.askopenfilename(
            title=f"Select {get_evaluation_mode_label(self.app_state.evaluation_mode)} file",
            initialdir=initial_dir,
            filetypes=[("CSV files", "*.csv"), ("Tab/text files", ("*.tsv", "*.txt")), ("All files", "*")],
        )
        if file_path:
            self.app_state.set_validation_file_path(file_path)
            self.header_status_lbl.configure(
                text=f"| Status: Selected {get_evaluation_mode_label(self.app_state.evaluation_mode)} reference"
            )

    # --- Asynchronous Tasks Dispatches ---
    def show_overlay(self, cancel_callback):
        self.overlay = ProgressOverlay(self, cancel_callback=cancel_callback)
        self.overlay.place(x=240, y=0, relwidth=1.0, relheight=1.0)
        self.overlay.tkraise()
        
    def remove_overlay(self):
        if self.overlay:
            self.overlay.place_forget()
            self.overlay.destroy()
            self.overlay = None

    def trigger_preprocessing_step(self, step_idx):
        if self.app_state.is_running:
            messagebox.showwarning("Run in progress", "Wait for the current task before starting preprocessing.")
            return
        PreprocessingInputDialog(
            self,
            step_idx,
            self.app_state.current_disease,
            dict(self.app_state.file_paths),
            lambda inputs: self._start_preprocessing_step(step_idx, inputs),
            initial_values=self.preprocessing_input_drafts.get((step_idx, self.app_state.current_disease), {}),
            back_callback=lambda values: self.preprocessing_input_drafts.__setitem__(
                (step_idx, self.app_state.current_disease), values
            ),
        )

    def _start_preprocessing_step(self, step_idx, inputs):
        self.preprocessing_input_drafts[(step_idx, self.app_state.current_disease)] = dict(inputs)

        self.app_state.is_running = True
        self.app_state.cancel_event.clear()
        
        def cancel_work():
            self.app_state.cancel_event.set()
            self.header_status_lbl.configure(text="| Aborting preprocessing step...")
            
        self.show_overlay(cancel_work)
        
        def bg_run():
            try:
                self.service.run_preprocessing_step(
                    step_idx, inputs, self.async_progress_update, self.app_state.cancel_event
                )
                self.after(0, lambda: self.async_task_completed(f"Preprocessing Step {step_idx} Completed successfully."))
            except InterruptedError as ie:
                message = str(ie)
                self.after(0, lambda message=message: self.async_task_cancelled(message))
            except Exception as e:
                message = f"Step {step_idx} Error: {str(e)}"
                self.after(0, lambda message=message: self.async_task_failed(message))
                
        threading.Thread(target=bg_run, daemon=True).start()

    def build_network(self):
        self.app_state.is_running = True
        self.app_state.cancel_event.clear()
        
        # Ensure they are on the run execution panel tab
        self.views["ranking"].show_run_tab()
        
        # We don't call self.show_overlay here. Instead, we trigger an immediate state refresh so button cancel shows up.
        self.on_state_updated()
        self.views["ranking"].add_log("Starting network aggregate combination process...")
        
        def bg_run():
            try:
                self.service.run_build_network(self.app_state.current_disease, self.app_state.file_paths, 
                                               self.app_state.beta, self.async_progress_update, self.app_state.cancel_event)
                self.after(0, lambda: self.async_task_completed("Network aggregation constructed."))
            except InterruptedError as ie:
                message = str(ie)
                self.after(0, lambda message=message: self.async_task_cancelled(message))
            except Exception as e:
                message = f"Aggregation Matrix Error: {str(e)}"
                self.after(0, lambda message=message: self.async_task_failed(message))
                
        threading.Thread(target=bg_run, daemon=True).start()

    def run_prioritization(self):
        self.app_state.is_running = True
        self.app_state.cancel_event.clear()
        
        # Ensure they are on the run execution panel tab
        self.views["ranking"].show_run_tab()
        
        # We don't call self.show_overlay here. Instead, we trigger an immediate state refresh so button cancel shows up.
        self.on_state_updated()
        self.views["ranking"].add_log("Starting gene prioritization algorithm...")
        
        def bg_run():
            try:
                self.service.run_ranking_pipeline(self.app_state.current_disease, self.app_state.file_paths, self.app_state.alpha, 
                                                  self.app_state.beta, self.app_state.selected_algorithm, 
                                                  self.async_progress_update, self.app_state.cancel_event)
                self.after(0, lambda: self.async_task_completed("Ranking algorithm converged. Rendering results."))
                self.after(0, lambda: [self.switch_view("ranking"), self.views["ranking"].show_results_tab()])
            except InterruptedError as ie:
                message = str(ie)
                self.after(0, lambda message=message: self.async_task_cancelled(message))
            except Exception as e:
                message = f"Core Algorithm Error: {str(e)}"
                self.after(0, lambda message=message: self.async_task_failed(message))
                
        threading.Thread(target=bg_run, daemon=True).start()

    def run_ranking_batch(self, batch_jobs):
        missing = self._missing_profile_files([job["disease"] for job in batch_jobs])
        if missing:
            messagebox.showerror("Seed profile incomplete", self._format_missing_profile_message(missing))
            return
        self.app_state.is_running = True
        self.app_state.cancel_event.clear()

        self.views["ranking"].show_run_tab()
        self.on_state_updated()
        total_pairs = sum(len(job["pairs"]) for job in batch_jobs)
        self.views["ranking"].add_log(
            f"Starting batch ranking queue: {len(batch_jobs)} disease block(s), {total_pairs} job(s)."
        )
        self.views["ranking"].add_log(
            f"Seed profile: {get_dataset_profile_label(self.app_state.dataset_profile)}"
        )
        self.views["ranking"].add_log(
            f"Validation reference: {get_evaluation_mode_label(self.app_state.evaluation_mode)}"
        )

        jobs = []
        for batch_job in batch_jobs:
            disease = batch_job["disease"]
            file_map = self._file_map_for_disease(disease)
            for alpha, beta in batch_job["pairs"]:
                jobs.append(
                    {
                        "disease": disease,
                        "file_map": dict(file_map),
                        "alpha": alpha,
                        "beta": beta,
                    }
                )

        def bg_run():
            try:
                self.service.run_ranking_batch(
                    jobs,
                    self.app_state.selected_algorithm,
                    self.async_progress_update,
                    self.app_state.cancel_event,
                )
                self.after(0, lambda: self.async_task_completed(f"Batch ranking completed: {len(jobs)} jobs."))
                self.after(0, lambda: [self.switch_view("ranking"), self.views["ranking"].show_results_tab()])
            except InterruptedError as ie:
                message = str(ie)
                self.after(0, lambda message=message: self.async_task_cancelled(message))
            except Exception as e:
                message = f"Batch Ranking Error: {str(e)}"
                self.after(0, lambda message=message: self.async_task_failed(message))

        threading.Thread(target=bg_run, daemon=True).start()

    def trigger_optuna_tuning(self, n_trials, seed, diseases=None, ablation_modes=None):
        diseases = list(diseases or [self.app_state.current_disease])
        ablation_modes = list(ablation_modes or [ABLATION_MODE_FULL])
        jobs = [
            {"disease": disease, "ablation_mode": ablation_mode}
            for disease in diseases
            for ablation_mode in ablation_modes
        ]
        missing = self._missing_profile_files(diseases, ablation_modes=ablation_modes)
        if missing:
            messagebox.showerror("Seed profile incomplete", self._format_missing_profile_message(missing))
            return
        self.app_state.is_running = True
        self.app_state.cancel_event.clear()
        self.app_state.pause_event.clear()
        self.app_state.optuna_is_paused = False
        self._optuna_ui_start_time = time.perf_counter()
        
        def cancel_work():
            self.app_state.cancel_event.set()
            self.app_state.pause_event.clear()
            self.app_state.optuna_status_text = "Cancellation requested. Waiting for current pipeline checkpoint..."
            self.app_state.add_optuna_log("Cancellation requested by user.")
            self.header_status_lbl.configure(text="| Optuna optimization abort requested...")
            if hasattr(self, "optuna_cancel_btn") and self.optuna_cancel_btn.winfo_exists():
                self.optuna_cancel_btn.configure(state="disabled", text="Cancelling...")
            if hasattr(self, "optuna_pause_btn") and self.optuna_pause_btn.winfo_exists():
                self.optuna_pause_btn.configure(state="disabled")
            self.views["optimization"].update_view()

        def toggle_pause():
            if self.app_state.pause_event.is_set():
                self.app_state.pause_event.clear()
                self.app_state.optuna_is_paused = False
                self.app_state.optuna_phase = "resuming"
                self.app_state.optuna_status_text = "Resume requested. Continuing optimization..."
                self.app_state.add_optuna_log("Resume requested by user.")
                self.optuna_pause_btn.configure(text="Pause")
            else:
                self.app_state.pause_event.set()
                self.app_state.optuna_is_paused = True
                self.app_state.optuna_phase = "pause_requested"
                self.app_state.optuna_status_text = "Pause requested. Waiting for a safe optimization checkpoint..."
                self.app_state.add_optuna_log("Pause requested by user.")
                self.optuna_pause_btn.configure(text="Resume")
            self.views["optimization"].update_view()
            
        self.views["optimization"].run_btn.configure(state="disabled", text="Tuning...")
        self.views["optimization"].trials_entry.configure(state="disabled")
        self.views["optimization"].seed_entry.configure(state="disabled")
        self._set_optional_optimization_widget_state("balance_cb", "disabled")
        
        self.optuna_action_frame = ctk.CTkFrame(
            self.views["optimization"].config_card,
            fg_color=CARD_BG,
        )
        self.optuna_action_frame.grid(row=1, column=1, rowspan=2, columnspan=2, padx=(120, 20), pady=4, sticky="e")
        self.optuna_pause_btn = ctk.CTkButton(
            self.optuna_action_frame,
            text="Pause",
            fg_color=SOFT_BLUE,
            hover_color=BORDER,
            text_color=PRIMARY,
            height=36,
            width=96,
            command=toggle_pause,
        )
        self.optuna_pause_btn.pack(side="left", padx=(0, 8))
        self.optuna_cancel_btn = ctk.CTkButton(
            self.optuna_action_frame,
            text="Cancel Run",
            fg_color=STATUS_ERROR,
            hover_color="#990000",
            text_color="#FFFFFF",
            height=36,
            width=110,
            command=cancel_work,
        )
        self.optuna_cancel_btn.pack(side="left")
        
        self.app_state.reset_optuna_queue(jobs, max_trials=n_trials)
        self.app_state.add_optuna_log(
            f"Seed profile: {get_dataset_profile_label(self.app_state.dataset_profile)}"
        )
        self.app_state.add_optuna_log(
            f"Validation reference: {get_evaluation_mode_label(self.app_state.evaluation_mode)}"
        )
        self.app_state.add_optuna_log(
            "Optimization queue: "
            + ", ".join(f"{job['disease']} / {ablation_label(job['ablation_mode'])}" for job in jobs)
        )
        self._schedule_optuna_heartbeat()
        
        def bg_run():
            try:
                for index, job in enumerate(jobs, start=1):
                    while self.app_state.pause_event.is_set():
                        if self.app_state.cancel_event.is_set():
                            raise InterruptedError("Task cancelled by user.")
                        time.sleep(0.2)
                    if self.app_state.cancel_event.is_set():
                        raise InterruptedError("Task cancelled by user.")
                    disease = job["disease"]
                    ablation_mode = job["ablation_mode"]
                    ablation_name = ablation_label(ablation_mode)
                    self.app_state.set_optuna_current_disease(disease, jobs[index:], ablation_mode=ablation_mode)
                    remaining = ", ".join(
                        f"{item['disease']} / {ablation_label(item['ablation_mode'])}"
                        for item in jobs[index:]
                    )
                    self.app_state.add_optuna_log(
                        f"Running optimization for {disease} / {ablation_name}. Remaining queue: {remaining or 'none'}"
                    )
                    file_map = self._file_map_for_disease(disease)

                    def disease_callback(progress, status_text, disease=disease, ablation_name=ablation_name, index=index):
                        combined = ((index - 1) + progress) / max(len(jobs), 1)
                        self.async_optuna_update(
                            combined,
                            f"[{index}/{len(jobs)}] {disease} / {ablation_name}: {status_text}",
                        )

                    result = self.service.run_optuna_tuning(
                        disease,
                        file_map,
                        n_trials,
                        seed,
                        disease_callback,
                        self.app_state.cancel_event,
                        pause_event=self.app_state.pause_event,
                        ablation_mode=ablation_mode,
                    )
                    self.app_state.add_optuna_disease_summary(
                        disease,
                        result.output_dir,
                        list(self.app_state.optuna_comparison),
                        ablation_mode=ablation_mode,
                    )
                    self.app_state.add_optuna_log(f"Completed optimization for {disease} / {ablation_name}.")
                self.app_state.set_optuna_current_disease("", [])
                self.after(0, lambda: self.async_optuna_completed(len(jobs)))
            except InterruptedError as ie:
                message = str(ie)
                self.after(0, lambda message=message: self.async_optuna_cancelled(message))
            except Exception as e:
                message = str(e)
                self.after(0, lambda message=message: self.async_optuna_failed(message))
                
        threading.Thread(target=bg_run, daemon=True).start()

    def _file_map_for_disease(self, disease):
        if disease == self.app_state.current_disease:
            return dict(self.app_state.file_paths)
        return build_default_state_file_paths(
            disease,
            self.app_state.dataset_profile,
            self.app_state.evaluation_mode,
        )

    def _missing_profile_files(self, diseases, ablation_modes=None):
        missing = {}
        ablation_modes = list(ablation_modes or [ABLATION_MODE_FULL])
        state_to_backend = {
            "ppi": "ppi_file_path",
            "coexpression": "co_expression_file_path",
            "seed": "seed_file_path",
            "de_genes": "secondary_seed_file_path",
            "ontology_map": "map__gene__ontologies_file_path",
            "disease_ontology": "disease_ontology_file_path",
        }
        labels_by_backend = {
            "ppi_file_path": "PPI network",
            "co_expression_file_path": "co-expression network",
            "seed_file_path": "seed set",
            "secondary_seed_file_path": "DE genes",
            "map__gene__ontologies_file_path": "gene-ontology mapping",
            "disease_ontology_file_path": "disease ontology",
        }
        for disease in dict.fromkeys(diseases):
            file_map = self._file_map_for_disease(disease)
            labels = set()
            for ablation_mode in ablation_modes:
                backend_keys = required_input_keys(ablation_mode)
                for state_key, backend_key in state_to_backend.items():
                    if backend_key not in backend_keys:
                        continue
                    if not file_map.get(state_key) or not os.path.isfile(file_map[state_key]):
                        labels.add(f"{labels_by_backend[backend_key]} ({ablation_label(ablation_mode)})")
            validation_path = self.app_state.validation_path_for(disease)
            if not validation_path or not os.path.isfile(validation_path):
                labels.add(f"{get_evaluation_mode_label(self.app_state.evaluation_mode)} validation reference")
            if labels:
                missing[disease] = sorted(labels)
        return missing

    def _format_missing_profile_message(self, missing):
        details = "\n".join(f"- {disease}: {', '.join(labels)}" for disease, labels in missing.items())
        return (
            f"{get_dataset_profile_label(self.app_state.dataset_profile)} seed profile "
            f"with {get_evaluation_mode_label(self.app_state.evaluation_mode)} validation is missing required files:\n{details}"
        )

    def _schedule_optuna_heartbeat(self):
        if not self.app_state.is_running or self._optuna_ui_start_time is None:
            self._optuna_heartbeat_job = None
            return

        self.app_state.optuna_elapsed_time = time.perf_counter() - self._optuna_ui_start_time
        if self.active_view_key == "optimization":
            self.views["optimization"].update_view()
        self._optuna_heartbeat_job = self.after(OPTUNA_HEARTBEAT_MS, self._schedule_optuna_heartbeat)

    def _set_optional_optimization_widget_state(self, widget_name, state):
        widget = getattr(self.views["optimization"], widget_name, None)
        if widget is not None:
            widget.configure(state=state)

    # --- Main Thread updates dispatches ---
    def async_progress_update(self, progress, status_text):
        self.after(0, lambda: self._handle_progress_update(progress, status_text))
        
    def _handle_progress_update(self, progress, status_text):
        self.app_state.progress_percentage = progress
        self.app_state.progress_text = status_text
        if self.overlay:
            self.overlay.update_progress(progress, status_text)
        # Log to ranking console if active
        self.views["ranking"].add_log(status_text)
            
    def async_task_completed(self, success_message):
        self.app_state.is_running = False
        self.remove_overlay()
        self.header_status_lbl.configure(text=f"| Status: {success_message}")
        self.active_indicator.configure(text="● Online Ready", text_color=STATUS_READY)
        self.views["ranking"].add_log(f"SUCCESS: {success_message}")
        self.on_state_updated()
        
    def async_task_cancelled(self, cancel_message):
        self.app_state.is_running = False
        self.remove_overlay()
        self.header_status_lbl.configure(text=f"| Status: {cancel_message}")
        self.active_indicator.configure(text="● Aborted", text_color=STATUS_ERROR)
        self.views["ranking"].add_log(f"ABORTED: {cancel_message}")
        self.on_state_updated()
        
    def async_task_failed(self, error_message):
        self.app_state.is_running = False
        self.remove_overlay()
        self.header_status_lbl.configure(text=f"| Status: Task Failure")
        self.active_indicator.configure(text="● Error Exception", text_color=STATUS_ERROR)
        self.views["ranking"].add_log(f"ERROR: {error_message}")
        messagebox.showerror("Analytical Failure", error_message)
        self.on_state_updated()

    def async_optuna_update(self, progress, status_text):
        self._pending_optuna_update = (progress, status_text)
        if self._optuna_update_job is None:
            self._optuna_update_job = self.after(OPTUNA_UI_UPDATE_DELAY_MS, self._flush_optuna_update)

    def _flush_optuna_update(self):
        self._optuna_update_job = None
        pending = self._pending_optuna_update
        self._pending_optuna_update = None
        if pending is not None:
            self._handle_optuna_progress(*pending)
        
    def _handle_optuna_progress(self, progress, status_text):
        self.app_state.progress_percentage = progress
        self.app_state.progress_text = status_text
        self.header_status_lbl.configure(text=f"| Status: {status_text}")
        if self.active_view_key == "optimization":
            self.views["optimization"].update_view()
        
    def async_optuna_completed(self, disease_count=1):
        self._clear_pending_optuna_update()
        self.app_state.is_running = False
        self.app_state.pause_event.clear()
        self.app_state.optuna_is_paused = False
        self._optuna_ui_start_time = None
        self.app_state.set_optuna_current_disease("", [])
        self._destroy_optuna_action_controls()
        
        self.views["optimization"].run_btn.configure(state="normal", text="Start Optimization")
        self.views["optimization"].trials_entry.configure(state="normal")
        self.views["optimization"].seed_entry.configure(state="normal")
        self._set_optional_optimization_widget_state("balance_cb", "normal")
        
        self.header_status_lbl.configure(text=f"| Status: Optuna search completed successfully for {disease_count} job(s).")
        self.views["optimization"].update_view()
        
    def async_optuna_cancelled(self, msg):
        self._clear_pending_optuna_update()
        self.app_state.is_running = False
        self.app_state.pause_event.clear()
        self.app_state.optuna_is_paused = False
        self._optuna_ui_start_time = None
        self.app_state.optuna_phase = "cancelled"
        self.app_state.optuna_status_text = msg
        self.app_state.set_optuna_current_disease("", [])
        self.app_state.add_optuna_log(msg)
        self._destroy_optuna_action_controls()
        
        self.views["optimization"].run_btn.configure(state="normal", text="Start Optimization")
        self.views["optimization"].trials_entry.configure(state="normal")
        self.views["optimization"].seed_entry.configure(state="normal")
        self._set_optional_optimization_widget_state("balance_cb", "normal")
        
        self.header_status_lbl.configure(text=f"| Status: {msg}")
        self.views["optimization"].update_view()
        
    def async_optuna_failed(self, msg):
        self._clear_pending_optuna_update()
        self.app_state.is_running = False
        self.app_state.pause_event.clear()
        self.app_state.optuna_is_paused = False
        self._optuna_ui_start_time = None
        self.app_state.optuna_phase = "failed"
        self.app_state.optuna_status_text = msg
        self.app_state.set_optuna_current_disease("", [])
        self.app_state.add_optuna_log(f"ERROR: {msg}")
        self._destroy_optuna_action_controls()
        
        self.views["optimization"].run_btn.configure(state="normal", text="Start Optimization")
        self.views["optimization"].trials_entry.configure(state="normal")
        self.views["optimization"].seed_entry.configure(state="normal")
        self._set_optional_optimization_widget_state("balance_cb", "normal")
        
        self.header_status_lbl.configure(text="| Status: Optimization Trial Failure")
        messagebox.showerror("Optuna Error Exception", msg)
        self.views["optimization"].update_view()

    def _destroy_optuna_action_controls(self):
        frame = getattr(self, "optuna_action_frame", None)
        if frame is not None and frame.winfo_exists():
            frame.destroy()

    def _clear_pending_optuna_update(self):
        if self._optuna_update_job is not None:
            self.after_cancel(self._optuna_update_job)
        self._optuna_update_job = None
        self._pending_optuna_update = None

    def on_state_updated(self):
        if hasattr(self, "dataset_profile_combo"):
            self.dataset_profile_combo.set(
                get_dataset_profile_label(self.app_state.dataset_profile)
            )
        if hasattr(self, "validation_reference_combo"):
            self.validation_reference_combo.set(
                get_evaluation_mode_label(self.app_state.evaluation_mode)
            )
        view = self.views.get(self.active_view_key)
        if view is not None and hasattr(view, "update_view"):
            view.update_view()
                    
    def open_preview_window(self):
        if not self.app_state.preview_nodes:
            messagebox.showwarning("Empty Network", "No aggregated network models available. Run Build Network initially.")
            return
            
        preview = ctk.CTkToplevel(self)
        preview.title(f"Aggregated Network preview: {self.app_state.current_disease}")
        preview.geometry("960x640")
        preview.resizable(False, False)
        preview.transient(self)
        
        container = ctk.CTkFrame(preview, fg_color=APP_BG, corner_radius=0)
        container.pack(fill="both", expand=True)
        
        title_lbl = ctk.CTkLabel(container, text=f"Network aggregation structure: {self.app_state.current_disease}",
                                 font=(FONT_FAMILY_HEADER, 18), text_color=TEXT_MAIN)
        title_lbl.pack(anchor="w", padx=20, pady=(20, 10))
        
        summary_lbl = ctk.CTkLabel(container, text=f"Total vertices universe: {self.app_state.network_summary['nodes']} | Total directed combinations edges: {self.app_state.network_summary['edges']}",
                                   font=(FONT_FAMILY_BODY, 13), text_color=TEXT_MUTED)
        summary_lbl.pack(anchor="w", padx=20, pady=(0, 14))
        
        tabview = ctk.CTkTabview(container, fg_color="transparent")
        tabview.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        node_tab = tabview.add("Vertices (First 1000)")
        edge_tab = tabview.add("Edges (First 2000)")
        
        nodes_table = DataTable(node_tab, ("Vertex Ensembl ID",), {"Vertex Ensembl ID": 400})
        nodes_table.pack(fill="both", expand=True)
        nodes_table.insert_rows([(n,) for n in self.app_state.preview_nodes])
        
        edges_table = DataTable(edge_tab, ("Source Vertex", "Target Vertex", "Convex Weight"),
                                {"Source Vertex": 240, "Target Vertex": 240, "Convex Weight": 140})
        edges_table.pack(fill="both", expand=True)
        edges_table.insert_rows([(e[0], e[1], f"{e[2]:.6f}") for e in self.app_state.preview_edges])
        
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        run_btn = ctk.CTkButton(btn_frame, text="Run Prioritization", font=(FONT_FAMILY_HEADER, 13, "bold"),
                                 fg_color=PRIMARY, hover_color=DEEP_BLUE, text_color="#FFFFFF",
                                 height=40, corner_radius=6, command=lambda: [preview.destroy(), self.run_prioritization()])
        run_btn.pack(side="left")
        
        close_btn = ctk.CTkButton(btn_frame, text="Close Preview", font=(FONT_FAMILY_HEADER, 13, "bold"),
                                   fg_color=SOFT_BLUE, text_color=PRIMARY, hover_color=BORDER,
                                   height=40, corner_radius=6, command=preview.destroy)
        close_btn.pack(side="right")

if __name__ == "__main__":
    app = BioRankApp()
    app.mainloop()
