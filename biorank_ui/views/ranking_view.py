from tkinter import messagebox

import customtkinter as ctk
from biorank_ui.config import ALGORITHM_LABELS, DISEASES, RANKING_ALGORITHMS
from biorank_ui.state import AppState
from biorank_ui.theme import (
    APP_BG, CARD_BG, BORDER, PRIMARY, SOFT_BLUE, TEXT_MAIN, TEXT_MUTED,
    STATUS_RUNNING, STATUS_ERROR,
    FONT_FAMILY_HEADER, FONT_FAMILY_BODY
)
from biorank_ui.views.results_view import ResultsView

ALGORITHMS = tuple(ALGORITHM_LABELS[algorithm] for algorithm in RANKING_ALGORITHMS)

class RankingView(ctk.CTkFrame):
    def __init__(self, master, state: AppState, build_net_callback, preview_net_callback, run_algo_callback, batch_run_callback=None, **kwargs):
        super().__init__(master, fg_color=APP_BG, **kwargs)
        self.state = state
        self.build_net_callback = build_net_callback
        self.preview_net_callback = preview_net_callback
        self.run_algo_callback = run_algo_callback
        self.batch_run_callback = batch_run_callback
        self.network_built = False
        self._syncing_controls = False
        self.batch_jobs = []
        
        # Configure layout for main frame (contains the Tabview)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Tabview
        self.tabview = ctk.CTkTabview(self, fg_color="transparent")
        self.tabview.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.run_tab = self.tabview.add("Run Algorithm")
        self.result_tab = self.tabview.add("Ranking Results")
        
        # Grid splits inside self.run_tab: Left (Parameters Tuning), Right (Prioritization Execution)
        self.run_tab.grid_columnconfigure(0, weight=1, uniform="ranking_cols")
        self.run_tab.grid_columnconfigure(1, weight=1, uniform="ranking_cols")
        self.run_tab.grid_rowconfigure(0, weight=1)
        
        # Left card panel (parent is run_tab)
        self.left_panel = ctk.CTkFrame(self.run_tab, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.left_panel.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="nsew")
        
        self.lp_title = ctk.CTkLabel(self.left_panel, text="Hyperparameter Tuning & Configurations", font=(FONT_FAMILY_HEADER, 18), text_color=TEXT_MAIN)
        self.lp_title.pack(anchor="w", padx=24, pady=(24, 16))

        self.run_mode_tabs = ctk.CTkTabview(self.left_panel, fg_color="transparent")
        self.run_mode_tabs.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.single_run_tab = self.run_mode_tabs.add("Single Run")
        self.batch_run_tab = self.run_mode_tabs.add("Batch Queue")
        
        # Algorithm selector block
        self.algo_lbl = ctk.CTkLabel(self.single_run_tab, text="Prioritization Engine Model:", font=(FONT_FAMILY_HEADER, 14), text_color=TEXT_MAIN)
        self.algo_lbl.pack(anchor="w", padx=10, pady=(10, 4))
        
        self.algo_dropdown = ctk.CTkOptionMenu(self.single_run_tab, values=ALGORITHMS, fg_color=PRIMARY, button_color=PRIMARY,
                                               button_hover_color=STATUS_RUNNING, text_color="#FFFFFF",
                                               font=(FONT_FAMILY_HEADER, 14), height=38, corner_radius=6, command=self._on_algorithm_changed)
        self.algo_dropdown.pack(fill="x", padx=10, pady=(0, 18))
        
        # Alpha parameter card block
        self.alpha_card = ctk.CTkFrame(self.single_run_tab, fg_color=APP_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.alpha_card.pack(fill="x", padx=10, pady=8)
        
        self.alpha_header_frame = ctk.CTkFrame(self.alpha_card, fg_color="transparent")
        self.alpha_header_frame.pack(fill="x", padx=14, pady=(14, 2))
        self.alpha_title = ctk.CTkLabel(self.alpha_header_frame, text="Alpha (α) Vector Factor", font=(FONT_FAMILY_HEADER, 14), text_color=TEXT_MAIN)
        self.alpha_title.pack(side="left")
        
        self.alpha_entry = ctk.CTkEntry(self.alpha_header_frame, width=60, height=26, font=(FONT_FAMILY_HEADER, 13, "bold"), text_color=PRIMARY, fg_color=CARD_BG, border_color=BORDER, justify="center")
        self.alpha_entry.pack(side="right")
        self.alpha_entry.insert(0, f"{state.alpha:.2f}")
        self.alpha_entry.bind("<KeyRelease>", self._on_alpha_entry_changed)
        
        self.alpha_slider = ctk.CTkSlider(self.alpha_card, from_=0.0, to=1.0, number_of_steps=100, 
                                           command=self._on_alpha_slider_moved, height=16)
        self.alpha_slider.pack(fill="x", padx=14, pady=8)
        self.alpha_slider.set(state.alpha)
        
        self.alpha_desc = ctk.CTkLabel(self.alpha_card, text="Biological annotation prioritization weight versus seed topological graph structures.", font=(FONT_FAMILY_BODY, 12), text_color=TEXT_MUTED, justify="left", wraplength=400)
        self.alpha_desc.pack(fill="x", padx=14, pady=(0, 14), anchor="w")
        
        # Beta parameter card block
        self.beta_card = ctk.CTkFrame(self.single_run_tab, fg_color=APP_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.beta_card.pack(fill="x", padx=10, pady=8)
        
        self.beta_header_frame = ctk.CTkFrame(self.beta_card, fg_color="transparent")
        self.beta_header_frame.pack(fill="x", padx=14, pady=(14, 2))
        self.beta_title = ctk.CTkLabel(self.beta_header_frame, text="Beta (β) Integration Combiner", font=(FONT_FAMILY_HEADER, 14), text_color=TEXT_MAIN)
        self.beta_title.pack(side="left")
        
        self.beta_entry = ctk.CTkEntry(self.beta_header_frame, width=60, height=26, font=(FONT_FAMILY_HEADER, 13, "bold"), text_color=PRIMARY, fg_color=CARD_BG, border_color=BORDER, justify="center")
        self.beta_entry.pack(side="right")
        self.beta_entry.insert(0, f"{state.beta:.2f}")
        self.beta_entry.bind("<KeyRelease>", self._on_beta_entry_changed)
        
        self.beta_slider = ctk.CTkSlider(self.beta_card, from_=0.0, to=1.0, number_of_steps=100,
                                          command=self._on_beta_slider_moved, height=16)
        self.beta_slider.pack(fill="x", padx=14, pady=8)
        self.beta_slider.set(state.beta)
        
        self.beta_desc = ctk.CTkLabel(self.beta_card, text="Convex aggregates mixture weight of PPI network (β) versus Pearson co-expressions graph (1-β).", font=(FONT_FAMILY_BODY, 12), text_color=TEXT_MUTED, justify="left", wraplength=400)
        self.beta_desc.pack(fill="x", padx=14, pady=(0, 14), anchor="w")
        
        self._build_batch_ranking_card()

        # Right card panel (parent is run_tab)
        self.right_panel = ctk.CTkFrame(self.run_tab, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.right_panel.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="nsew")
        
        self.rp_title = ctk.CTkLabel(self.right_panel, text="Prioritization Model Executions", font=(FONT_FAMILY_HEADER, 18), text_color=TEXT_MAIN)
        self.rp_title.pack(anchor="w", padx=24, pady=(24, 16))
        
        # Status block
        self.summary_card = ctk.CTkFrame(self.right_panel, fg_color=APP_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.summary_card.pack(fill="x", padx=24, pady=10, ipady=12)
        
        self.summary_title = ctk.CTkLabel(self.summary_card, text="Execution Integration Summary", font=(FONT_FAMILY_HEADER, 15), text_color=TEXT_MAIN)
        self.summary_title.pack(anchor="w", padx=20, pady=(16, 6))
        
        self.nodes_lbl = ctk.CTkLabel(self.summary_card, text="Network status: Unaggregated", font=(FONT_FAMILY_BODY, 14), text_color=TEXT_MUTED)
        self.nodes_lbl.pack(anchor="w", padx=20, pady=2)
        
        self.edges_lbl = ctk.CTkLabel(self.summary_card, text="Algorithm selection: BioRank Lite Model", font=(FONT_FAMILY_BODY, 14), text_color=TEXT_MUTED)
        self.edges_lbl.pack(anchor="w", padx=20, pady=(2, 16))
        
        # Console Log Panel
        self.console_card = ctk.CTkFrame(self.right_panel, fg_color="#0F172A", border_color="#1E293B", border_width=1, corner_radius=8)
        self.console_card.pack(fill="both", expand=True, padx=24, pady=10)
        
        self.console_title = ctk.CTkLabel(self.console_card, text="System Log Console", font=(FONT_FAMILY_HEADER, 12, "bold"), text_color="#38BDF8")
        self.console_title.pack(anchor="w", padx=12, pady=(8, 4))
        
        self.log_text = ctk.CTkTextbox(self.console_card, fg_color="#0F172A", text_color="#38BDF8", font=("Consolas", 12), border_width=0, corner_radius=0)
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log_text.configure(state="disabled")
        
        # Button actions frame
        self.actions_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.actions_frame.pack(fill="x", padx=24, pady=(6, 20))
        
        self.build_net_btn = ctk.CTkButton(self.actions_frame, text="Build Integrated Network", font=(FONT_FAMILY_HEADER, 15, "bold"),
                                            fg_color=PRIMARY, hover_color=STATUS_RUNNING, text_color="#FFFFFF",
                                            height=46, corner_radius=6, command=self.build_net_callback)
        
        self.preview_net_btn = ctk.CTkButton(self.actions_frame, text="Preview Network Structure", font=(FONT_FAMILY_HEADER, 15, "bold"),
                                              fg_color=SOFT_BLUE, text_color=PRIMARY, hover_color=BORDER,
                                              height=46, corner_radius=6, command=self.preview_net_callback)
        
        self.run_algo_btn = ctk.CTkButton(self.actions_frame, text="Run Prioritization Algorithm", font=(FONT_FAMILY_HEADER, 15, "bold"),
                                           fg_color=STATUS_RUNNING, hover_color="#0D47A1", text_color="#FFFFFF",
                                           height=46, corner_radius=6, command=self.run_algo_callback)
                                           
        self.rebuild_net_btn = ctk.CTkButton(self.actions_frame, text="Re-build Integrated Network", font=(FONT_FAMILY_HEADER, 13, "bold"),
                                              fg_color=SOFT_BLUE, text_color=TEXT_MUTED, hover_color=BORDER,
                                              height=40, corner_radius=6, command=self.build_net_callback)
                                              
        self.cancel_btn = ctk.CTkButton(self.actions_frame, text="Cancel Active Execution", font=(FONT_FAMILY_HEADER, 15, "bold"),
                                        fg_color=STATUS_ERROR, hover_color="#990000", text_color="#FFFFFF",
                                        height=46, corner_radius=6, command=self._on_cancel_clicked)
        
        # Embed ResultsView inside self.result_tab
        self.results_view = ResultsView(self.result_tab, self.state)
        self.results_view.pack(fill="both", expand=True)
        
        # Load selections from AppState without firing parameter-change handlers.
        self.update_view()

    def _build_batch_ranking_card(self):
        self.batch_card = ctk.CTkFrame(self.batch_run_tab, fg_color=APP_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.batch_card.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            self.batch_card,
            text="Batch Ranking Queue",
            font=(FONT_FAMILY_HEADER, 14),
            text_color=TEXT_MAIN,
        ).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(
            self.batch_card,
            text="Add one disease at a time, then assign alpha,beta pairs for that disease. One pair per line.",
            font=(FONT_FAMILY_BODY, 12),
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=440,
        ).pack(fill="x", padx=14, pady=(0, 6), anchor="w")

        ctk.CTkLabel(
            self.batch_card,
            text="Prioritization Engine Model:",
            font=(FONT_FAMILY_HEADER, 13),
            text_color=TEXT_MAIN,
        ).pack(anchor="w", padx=14, pady=(0, 4))
        self.batch_algo_dropdown = ctk.CTkOptionMenu(
            self.batch_card,
            values=ALGORITHMS,
            fg_color=PRIMARY,
            button_color=PRIMARY,
            button_hover_color=STATUS_RUNNING,
            text_color="#FFFFFF",
            font=(FONT_FAMILY_HEADER, 13),
            height=32,
            corner_radius=6,
            command=self._on_algorithm_changed,
        )
        self.batch_algo_dropdown.pack(fill="x", padx=14, pady=(0, 8))
        self.batch_algo_dropdown.set(self.state.selected_algorithm)

        self.batch_disease_dropdown = ctk.CTkOptionMenu(
            self.batch_card,
            values=DISEASES,
            fg_color=PRIMARY,
            button_color=PRIMARY,
            button_hover_color=STATUS_RUNNING,
            text_color="#FFFFFF",
            font=(FONT_FAMILY_HEADER, 13),
            height=32,
            corner_radius=6,
        )
        self.batch_disease_dropdown.pack(fill="x", padx=14, pady=(0, 8))
        self.batch_disease_dropdown.set(self.state.current_disease)

        self.batch_pairs_text = ctk.CTkTextbox(
            self.batch_card,
            height=54,
            fg_color=CARD_BG,
            text_color=TEXT_MAIN,
            font=("Consolas", 12),
            border_color=BORDER,
            border_width=1,
        )
        self.batch_pairs_text.pack(fill="x", padx=14, pady=(0, 8))
        self.batch_pairs_text.insert("1.0", f"{self.state.alpha:.2f},{self.state.beta:.2f}")

        action_frame = ctk.CTkFrame(self.batch_card, fg_color="transparent")
        action_frame.pack(fill="x", padx=14, pady=(0, 8))
        self.batch_current_btn = ctk.CTkButton(
            action_frame,
            text="Use Current",
            width=94,
            height=30,
            fg_color=SOFT_BLUE,
            text_color=PRIMARY,
            hover_color=BORDER,
            command=self._select_current_batch_disease,
        )
        self.batch_current_btn.pack(side="left", padx=(0, 8))
        self.batch_add_btn = ctk.CTkButton(
            action_frame,
            text="Add Disease",
            width=106,
            height=30,
            fg_color=SOFT_BLUE,
            text_color=PRIMARY,
            hover_color=BORDER,
            command=self._on_add_batch_disease_clicked,
        )
        self.batch_add_btn.pack(side="left", padx=(0, 8))
        self.batch_clear_btn = ctk.CTkButton(
            action_frame,
            text="Clear Queue",
            width=96,
            height=30,
            fg_color=SOFT_BLUE,
            text_color=PRIMARY,
            hover_color=BORDER,
            command=self._clear_batch_queue,
        )
        self.batch_clear_btn.pack(side="left", padx=(0, 8))
        self.batch_run_btn = ctk.CTkButton(
            action_frame,
            text="Run Queue",
            width=110,
            height=30,
            fg_color=PRIMARY,
            hover_color=STATUS_RUNNING,
            text_color="#FFFFFF",
            command=self._on_batch_run_clicked,
        )
        self.batch_run_btn.pack(side="right")

        self.batch_queue_text = ctk.CTkTextbox(
            self.batch_card,
            height=74,
            fg_color="#FFFFFF",
            text_color=TEXT_MAIN,
            font=("Consolas", 11),
            border_color=BORDER,
            border_width=1,
        )
        self.batch_queue_text.pack(fill="x", padx=14, pady=(0, 12))
        self.batch_queue_text.configure(state="disabled")
        self._refresh_batch_queue_text()
        
    def show_results_tab(self):
        self.tabview.set("Ranking Results")
        
    def show_run_tab(self):
        self.tabview.set("Run Algorithm")

    def _on_algorithm_changed(self, value):
        if self._syncing_controls:
            return
        if self.state.selected_algorithm != value:
            self.state.set_algorithm(value)
        other_dropdown = self.batch_algo_dropdown if self.algo_dropdown.get() == value else self.algo_dropdown
        other_dropdown.set(value)
        self.edges_lbl.configure(text=f"Algorithm selection: {value} Model")
        
        if value == "Original PageRank":
            self.alpha_slider.configure(state="disabled")
            self.alpha_entry.configure(state="normal")
            self.alpha_entry.delete(0, "end")
            self.alpha_entry.insert(0, "N/A")
            self.alpha_entry.configure(state="disabled")
        else:
            self.alpha_entry.configure(state="normal")
            self.alpha_slider.configure(state="normal")
            try:
                val = float(self.alpha_entry.get())
                if not (0.0 <= val <= 1.0):
                    raise ValueError
            except ValueError:
                self.alpha_entry.delete(0, "end")
                self.alpha_entry.insert(0, f"{self.alpha_slider.get():.2f}")
            
    def _on_alpha_slider_moved(self, val):
        if self._syncing_controls:
            return
        self.state.set_alpha(val)
        if self.algo_dropdown.get() != "Original PageRank":
            self.alpha_entry.delete(0, "end")
            self.alpha_entry.insert(0, f"{val:.2f}")
            self.alpha_entry.configure(border_color=BORDER)
            self.results_view.update_view()
            
    def _on_beta_slider_moved(self, val):
        if self._syncing_controls:
            return
        self.state.set_beta(val)
        self.beta_entry.delete(0, "end")
        self.beta_entry.insert(0, f"{val:.2f}")
        self.beta_entry.configure(border_color=BORDER)
        self._refresh_execution_summary()
        
    def _on_alpha_entry_changed(self, event):
        if self._syncing_controls:
            return
        val_str = self.alpha_entry.get()
        try:
            val = float(val_str)
            if 0.0 <= val <= 1.0:
                self.alpha_entry.configure(border_color=BORDER)
                self.alpha_slider.set(val)
                self.state.set_alpha(val)
                self.results_view.update_view()
            else:
                self.alpha_entry.configure(border_color=STATUS_ERROR)
        except ValueError:
            self.alpha_entry.configure(border_color=STATUS_ERROR)

    def _on_beta_entry_changed(self, event):
        if self._syncing_controls:
            return
        val_str = self.beta_entry.get()
        try:
            val = float(val_str)
            if 0.0 <= val <= 1.0:
                self.beta_entry.configure(border_color=BORDER)
                self.beta_slider.set(val)
                self.state.set_beta(val)
                self._refresh_execution_summary()
            else:
                self.beta_entry.configure(border_color=STATUS_ERROR)
        except ValueError:
            self.beta_entry.configure(border_color=STATUS_ERROR)
            
    def _on_cancel_clicked(self):
        self.state.cancel_event.set()
        self.add_log("Cancellation requested by user. Aborting...")

    def _select_current_batch_disease(self):
        self.batch_disease_dropdown.set(self.state.current_disease)

    def _on_batch_run_clicked(self):
        if self.batch_run_callback is None:
            return
        if not self.batch_jobs:
            messagebox.showerror("Invalid batch ranking queue", "Add at least one disease to the queue.")
            return
        self.batch_run_callback(list(self.batch_jobs))

    def _on_add_batch_disease_clicked(self):
        try:
            disease = self.batch_disease_dropdown.get()
            pairs = self._parse_batch_pairs()
        except ValueError as exc:
            messagebox.showerror("Invalid batch ranking queue", str(exc))
            return
        self.batch_jobs.append({"disease": disease, "pairs": pairs})
        self._refresh_batch_queue_text()

    def _clear_batch_queue(self):
        self.batch_jobs = []
        self._refresh_batch_queue_text()

    def _refresh_batch_queue_text(self):
        lines = []
        for index, job in enumerate(self.batch_jobs, start=1):
            pair_text = "; ".join(f"{alpha:.4f},{beta:.4f}" for alpha, beta in job["pairs"])
            lines.append(f"{index}. {job['disease']} -> {pair_text}")
        text = "\n".join(lines) if lines else "Queue is empty. Add disease-specific alpha,beta pairs."
        self.batch_queue_text.configure(state="normal")
        self.batch_queue_text.delete("1.0", "end")
        self.batch_queue_text.insert("1.0", text)
        self.batch_queue_text.configure(state="disabled")

    def _parse_batch_pairs(self):
        raw_text = self.batch_pairs_text.get("1.0", "end").strip()
        if not raw_text:
            raise ValueError("Enter at least one alpha,beta pair.")

        pairs = []
        for line_number, line in enumerate(raw_text.splitlines(), start=1):
            cleaned = line.strip()
            if not cleaned:
                continue
            cleaned = cleaned.replace(";", ",").replace(" ", ",")
            parts = [part for part in cleaned.split(",") if part]
            if len(parts) != 2:
                raise ValueError(f"Line {line_number} must be alpha,beta.")
            try:
                alpha, beta = float(parts[0]), float(parts[1])
            except ValueError as exc:
                raise ValueError(f"Line {line_number} contains non-numeric alpha/beta.") from exc
            if not (0.0 <= alpha <= 1.0 and 0.0 <= beta <= 1.0):
                raise ValueError(f"Line {line_number} must use alpha and beta in [0, 1].")
            pairs.append((alpha, beta))

        if not pairs:
            raise ValueError("Enter at least one alpha,beta pair.")
        return pairs
        
    def add_log(self, text):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {text}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        
    def update_button_states(self):
        self.build_net_btn.pack_forget()
        self.preview_net_btn.pack_forget()
        self.run_algo_btn.pack_forget()
        self.rebuild_net_btn.pack_forget()
        self.cancel_btn.pack_forget()
        if hasattr(self, "batch_run_btn"):
            self.algo_dropdown.configure(state="disabled" if self.state.is_running else "normal")
            self.batch_run_btn.configure(state="disabled" if self.state.is_running else "normal")
            self.batch_add_btn.configure(state="disabled" if self.state.is_running else "normal")
            self.batch_clear_btn.configure(state="disabled" if self.state.is_running else "normal")
            self.batch_current_btn.configure(state="disabled" if self.state.is_running else "normal")
            self.batch_disease_dropdown.configure(state="disabled" if self.state.is_running else "normal")
            self.batch_algo_dropdown.configure(state="disabled" if self.state.is_running else "normal")
        
        if self.state.is_running:
            self.cancel_btn.pack(fill="x", pady=6)
        else:
            if self.network_built:
                self.run_algo_btn.pack(fill="x", pady=6)
                self.preview_net_btn.pack(fill="x", pady=6)
                self.rebuild_net_btn.pack(fill="x", pady=(18, 6))
            else:
                self.build_net_btn.pack(fill="x", pady=6)

    def _refresh_execution_summary(self):
        if self.state.network_summary["nodes"] > 0:
            self.network_built = True
            self.nodes_lbl.configure(text=f"Network status: Aggregated ({self.state.network_summary['nodes']} nodes, {self.state.network_summary['edges']} edges)")
        else:
            self.network_built = False
            self.nodes_lbl.configure(text="Network status: Unaggregated")
        self.update_button_states()
        self.results_view.update_view()
        
    def update_view(self):
        self._syncing_controls = True
        try:
            self.algo_dropdown.set(self.state.selected_algorithm)
            self.batch_algo_dropdown.set(self.state.selected_algorithm)
            self.edges_lbl.configure(text=f"Algorithm selection: {self.state.selected_algorithm} Model")

            if self.state.selected_algorithm == "Original PageRank":
                self.alpha_slider.configure(state="disabled")
                self.alpha_entry.configure(state="normal")
                self.alpha_entry.delete(0, "end")
                self.alpha_entry.insert(0, "N/A")
                self.alpha_entry.configure(state="disabled")
            else:
                self.alpha_entry.configure(state="normal")
                self.alpha_slider.configure(state="normal")
                self.alpha_entry.delete(0, "end")
                self.alpha_entry.insert(0, f"{self.state.alpha:.2f}")
                self.alpha_slider.set(self.state.alpha)

            self.beta_entry.delete(0, "end")
            self.beta_entry.insert(0, f"{self.state.beta:.2f}")
            self.beta_slider.set(self.state.beta)
        finally:
            self._syncing_controls = False
        
        self._refresh_execution_summary()
