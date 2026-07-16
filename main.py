import os
import sys
import threading
import time
from tkinter import filedialog, messagebox

import customtkinter as ctk

# Imports configurations, themes, states, and components
from biorank_ui.config import (
    DATASET_PROFILES,
    DISEASES,
    EVALUATION_MODES,
    build_default_state_file_paths,
    get_validation_reference_path,
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
            ("dashboard", "1. Input Data Configuration"),
            ("preprocessing", "2. Data Preprocessing"),
            ("ranking", "3. Priority Gene Ranking"),
            ("optimization", "4. Parameter Optimization")
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
        
        self.disease_lbl = ctk.CTkLabel(self.headerbar, text="Cancer:", font=(FONT_FAMILY_HEADER, 14), text_color=TEXT_MAIN)
        self.disease_lbl.pack(side="left", padx=(12, 4))
        
        self.disease_combo = ctk.CTkComboBox(self.headerbar, values=DISEASES, font=(FONT_FAMILY_HEADER, 15),
                                             fg_color=APP_BG, text_color=TEXT_MAIN, button_color=PRIMARY,
                                             button_hover_color=STATUS_RUNNING, height=34, width=88, command=self._on_disease_changed)
        self.disease_combo.pack(side="left", padx=4)
        self.disease_combo.set(self.app_state.current_disease)

        self.dataset_profile_lbl = ctk.CTkLabel(
            self.headerbar,
            text="Dataset:",
            font=(FONT_FAMILY_HEADER, 14),
            text_color=TEXT_MAIN,
        )
        self.dataset_profile_lbl.pack(side="left", padx=(12, 4))
        self.dataset_profile_combo = ctk.CTkComboBox(
            self.headerbar,
            values=DATASET_PROFILES,
            font=(FONT_FAMILY_HEADER, 14),
            fg_color=APP_BG,
            text_color=TEXT_MAIN,
            button_color=PRIMARY,
            button_hover_color=STATUS_RUNNING,
            height=34,
            width=112,
            command=self._on_dataset_profile_changed,
        )
        self.dataset_profile_combo.pack(side="left", padx=4)
        self.dataset_profile_combo.set(self.app_state.dataset_profile)

        self.evaluation_mode_lbl = ctk.CTkLabel(
            self.headerbar,
            text="Eval:",
            font=(FONT_FAMILY_HEADER, 14),
            text_color=TEXT_MAIN,
        )
        self.evaluation_mode_lbl.pack(side="left", padx=(12, 4))
        self.evaluation_mode_combo = ctk.CTkComboBox(
            self.headerbar,
            values=EVALUATION_MODES,
            font=(FONT_FAMILY_HEADER, 13),
            fg_color=APP_BG,
            text_color=TEXT_MAIN,
            button_color=PRIMARY,
            button_hover_color=STATUS_RUNNING,
            height=34,
            width=150,
            command=self._on_evaluation_mode_changed,
        )
        self.evaluation_mode_combo.pack(side="left", padx=4)
        self.evaluation_mode_combo.set(self.app_state.evaluation_mode)
        self.evaluation_mode_combo.configure(state="disabled")
        
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
            "dashboard": DashboardView(self.view_container, self.app_state, self.browse_dataset_card_file),
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
            self.header_status_lbl.configure(text=f"| Status: {self.app_state.dataset_profile} is incomplete for {value}")
            messagebox.showwarning("Dataset profile incomplete", self._format_missing_profile_message(missing))
        else:
            self.header_status_lbl.configure(text=f"| Status: Disease profile shifted to {value}")

    def _on_dataset_profile_changed(self, value):
        if self.app_state.is_running:
            messagebox.showwarning("Run in progress", "Cannot change dataset while a pipeline task is running.")
            self.dataset_profile_combo.set(self.app_state.dataset_profile)
            return
        self.app_state.set_dataset_profile(value)
        self.evaluation_mode_combo.set(self.app_state.evaluation_mode)
        missing = self._missing_profile_files([self.app_state.current_disease])
        if missing:
            self.header_status_lbl.configure(text=f"| Status: {value} is incomplete for {self.app_state.current_disease}")
            messagebox.showwarning("Dataset profile incomplete", self._format_missing_profile_message(missing))
        else:
            self.header_status_lbl.configure(text=f"| Status: Using {value}")

    def _on_evaluation_mode_changed(self, value):
        if self.app_state.is_running:
            messagebox.showwarning("Run in progress", "Cannot change evaluation mode while a pipeline task is running.")
            self.evaluation_mode_combo.set(self.app_state.evaluation_mode)
            return
        self.app_state.set_evaluation_mode(value)
        missing = self._missing_profile_files([self.app_state.current_disease])
        if missing:
            self.header_status_lbl.configure(text=f"| Status: {value} inputs are incomplete")
            messagebox.showwarning("Evaluation inputs incomplete", self._format_missing_profile_message(missing))
        else:
            self.header_status_lbl.configure(text=f"| Status: Evaluation mode {value}")

    def browse_dataset_card_file(self, key):
        if self.app_state.is_running:
            messagebox.showwarning("Run in progress", "Cannot change input files while a pipeline task is running.")
            return
        file_path = filedialog.askopenfilename(title="Select Biological Dataset Path",
                                               filetypes=[("Tab Separated Values", "*.tsv;*.txt"), ("All Files", "*.*")])
        if file_path:
            self.app_state.set_file_path(key, file_path)
            self.header_status_lbl.configure(text=f"| Loaded manual file override for: {key}")

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
            messagebox.showerror("Dataset profile incomplete", self._format_missing_profile_message(missing))
            return
        self.app_state.is_running = True
        self.app_state.cancel_event.clear()

        self.views["ranking"].show_run_tab()
        self.on_state_updated()
        total_pairs = sum(len(job["pairs"]) for job in batch_jobs)
        self.views["ranking"].add_log(
            f"Starting batch ranking queue: {len(batch_jobs)} disease block(s), {total_pairs} job(s)."
        )
        self.views["ranking"].add_log(f"Dataset profile: {self.app_state.dataset_profile}")
        self.views["ranking"].add_log(f"Evaluation mode: {self.app_state.evaluation_mode}")

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

    def trigger_optuna_tuning(self, n_trials, seed, diseases=None):
        diseases = list(diseases or [self.app_state.current_disease])
        missing = self._missing_profile_files(diseases)
        if missing:
            messagebox.showerror("Dataset profile incomplete", self._format_missing_profile_message(missing))
            return
        self.app_state.is_running = True
        self.app_state.cancel_event.clear()
        self._optuna_ui_start_time = time.perf_counter()
        
        def cancel_work():
            self.app_state.cancel_event.set()
            self.app_state.optuna_status_text = "Cancellation requested. Waiting for current pipeline checkpoint..."
            self.app_state.add_optuna_log("Cancellation requested by user.")
            self.header_status_lbl.configure(text="| Optuna optimization abort requested...")
            if hasattr(self, "optuna_cancel_btn") and self.optuna_cancel_btn.winfo_exists():
                self.optuna_cancel_btn.configure(state="disabled", text="Cancelling...")
            self.views["optimization"].update_view()
            
        self.views["optimization"].run_btn.configure(state="disabled", text="Tuning...")
        self.views["optimization"].trials_entry.configure(state="disabled")
        self.views["optimization"].seed_entry.configure(state="disabled")
        self._set_optional_optimization_widget_state("balance_cb", "disabled")
        
        self.optuna_cancel_btn = ctk.CTkButton(self.views["optimization"].config_card, text="✕ Cancel Run", 
                                                fg_color=STATUS_ERROR, hover_color="#990000", text_color="#FFFFFF",
                                                height=36, width=120, command=cancel_work)
        self.optuna_cancel_btn.grid(row=1, column=1, rowspan=2, columnspan=2, padx=(150, 20), pady=4, sticky="e")
        
        self.app_state.reset_optuna_queue(diseases, max_trials=n_trials)
        self.app_state.add_optuna_log(f"Dataset profile: {self.app_state.dataset_profile}")
        self.app_state.add_optuna_log(f"Evaluation mode: {self.app_state.evaluation_mode}")
        self.app_state.add_optuna_log(f"Optimization queue: {', '.join(diseases)}")
        self._schedule_optuna_heartbeat()
        
        def bg_run():
            try:
                for index, disease in enumerate(diseases, start=1):
                    if self.app_state.cancel_event.is_set():
                        raise InterruptedError("Task cancelled by user.")
                    self.app_state.set_optuna_current_disease(disease, diseases[index:])
                    self.app_state.add_optuna_log(f"Running optimization for {disease}. Remaining queue: {', '.join(diseases[index:]) or 'none'}")
                    file_map = self._file_map_for_disease(disease)

                    def disease_callback(progress, status_text, disease=disease, index=index):
                        combined = ((index - 1) + progress) / max(len(diseases), 1)
                        self.async_optuna_update(combined, f"[{index}/{len(diseases)}] {disease}: {status_text}")

                    result = self.service.run_optuna_tuning(
                        disease,
                        file_map,
                        n_trials,
                        seed,
                        disease_callback,
                        self.app_state.cancel_event,
                    )
                    self.app_state.add_optuna_disease_summary(
                        disease,
                        result.output_dir,
                        list(self.app_state.optuna_comparison),
                    )
                    self.app_state.add_optuna_log(f"Completed optimization for {disease}.")
                self.app_state.set_optuna_current_disease("", [])
                self.after(0, lambda: self.async_optuna_completed(len(diseases)))
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

    def _missing_profile_files(self, diseases):
        missing = {}
        for disease in dict.fromkeys(diseases):
            file_map = self._file_map_for_disease(disease)
            labels = []
            if not file_map.get("seed") or not os.path.isfile(file_map["seed"]):
                labels.append("seed set")
            if not file_map.get("disease_ontology") or not os.path.isfile(file_map["disease_ontology"]):
                labels.append("disease ontology")
            validation_path = get_validation_reference_path(
                disease,
                self.app_state.dataset_profile,
                self.app_state.evaluation_mode,
            )
            if not validation_path or not os.path.isfile(validation_path):
                labels.append("evaluation reference")
            if labels:
                missing[disease] = labels
        return missing

    def _format_missing_profile_message(self, missing):
        details = "\n".join(f"- {disease}: {', '.join(labels)}" for disease, labels in missing.items())
        return (
            f"{self.app_state.dataset_profile} / {self.app_state.evaluation_mode} "
            f"is missing required files:\n{details}"
        )

    def _schedule_optuna_heartbeat(self):
        if not self.app_state.is_running or self._optuna_ui_start_time is None:
            self._optuna_heartbeat_job = None
            return

        self.app_state.optuna_elapsed_time = time.perf_counter() - self._optuna_ui_start_time
        self.views["optimization"].update_view()
        self._optuna_heartbeat_job = self.after(500, self._schedule_optuna_heartbeat)

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
        self.after(0, lambda: self._handle_optuna_progress(progress, status_text))
        
    def _handle_optuna_progress(self, progress, status_text):
        self.app_state.progress_percentage = progress
        self.app_state.progress_text = status_text
        self.header_status_lbl.configure(text=f"| Status: {status_text}")
        self.views["optimization"].update_view()
        
    def async_optuna_completed(self, disease_count=1):
        self.app_state.is_running = False
        self._optuna_ui_start_time = None
        self.app_state.set_optuna_current_disease("", [])
        if hasattr(self, "optuna_cancel_btn") and self.optuna_cancel_btn.winfo_exists():
            self.optuna_cancel_btn.destroy()
        
        self.views["optimization"].run_btn.configure(state="normal", text="Start Optuna Engine")
        self.views["optimization"].trials_entry.configure(state="normal")
        self.views["optimization"].seed_entry.configure(state="normal")
        self._set_optional_optimization_widget_state("balance_cb", "normal")
        
        self.header_status_lbl.configure(text=f"| Status: Optuna search completed successfully for {disease_count} disease(s).")
        self.views["optimization"].update_view()
        
    def async_optuna_cancelled(self, msg):
        self.app_state.is_running = False
        self._optuna_ui_start_time = None
        self.app_state.optuna_phase = "cancelled"
        self.app_state.optuna_status_text = msg
        self.app_state.set_optuna_current_disease("", [])
        self.app_state.add_optuna_log(msg)
        if hasattr(self, "optuna_cancel_btn") and self.optuna_cancel_btn.winfo_exists():
            self.optuna_cancel_btn.destroy()
        
        self.views["optimization"].run_btn.configure(state="normal", text="Start Optuna Engine")
        self.views["optimization"].trials_entry.configure(state="normal")
        self.views["optimization"].seed_entry.configure(state="normal")
        self._set_optional_optimization_widget_state("balance_cb", "normal")
        
        self.header_status_lbl.configure(text=f"| Status: {msg}")
        self.views["optimization"].update_view()
        
    def async_optuna_failed(self, msg):
        self.app_state.is_running = False
        self._optuna_ui_start_time = None
        self.app_state.optuna_phase = "failed"
        self.app_state.optuna_status_text = msg
        self.app_state.set_optuna_current_disease("", [])
        self.app_state.add_optuna_log(f"ERROR: {msg}")
        if hasattr(self, "optuna_cancel_btn") and self.optuna_cancel_btn.winfo_exists():
            self.optuna_cancel_btn.destroy()
        
        self.views["optimization"].run_btn.configure(state="normal", text="Start Optuna Engine")
        self.views["optimization"].trials_entry.configure(state="normal")
        self.views["optimization"].seed_entry.configure(state="normal")
        self._set_optional_optimization_widget_state("balance_cb", "normal")
        
        self.header_status_lbl.configure(text="| Status: Optimization Trial Failure")
        messagebox.showerror("Optuna Error Exception", msg)
        self.views["optimization"].update_view()

    def on_state_updated(self):
        for view in self.views.values():
            if view.winfo_viewable():
                if hasattr(view, "update_view"):
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
