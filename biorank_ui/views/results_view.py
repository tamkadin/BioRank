import customtkinter as ctk
from biorank_ui.state import AppState
from biorank_ui.components import DataTable
from biorank_ui.theme import (
    APP_BG, CARD_BG, BORDER, PRIMARY, TEXT_MAIN, TEXT_MUTED,
    STATUS_RUNNING,
    FONT_FAMILY_HEADER, FONT_FAMILY_BODY
)

class ResultsView(ctk.CTkFrame):
    def __init__(self, master, state: AppState, **kwargs):
        super().__init__(master, fg_color=APP_BG, **kwargs)
        self.state = state
        self._filtered_rows = []
        
        # Horizontal KPI Metric Cards
        self.kpi_container = ctk.CTkFrame(self, fg_color="transparent")
        self.kpi_container.pack(fill="x", padx=20, pady=(20, 10))
        
        for i in range(3):
            self.kpi_container.grid_columnconfigure(i, weight=1, uniform="kpi_cols")
            
        self.kpis = {}
        self.kpi_descriptions = {}
        kpi_configs = [
            ("recall_15", "Recall@15", "OncoKB reference genes captured in top 15."),
            ("recall_100", "Recall@100", "OncoKB reference genes captured in top 100."),
            ("ndcg_15", "nDCG@15", "Position-aware hit quality in top 15."),
            ("ndcg_100", "nDCG@100", "Position-aware hit quality in top 100."),
            ("common_15", "Common@15", "OncoKB overlaps in the top 15."),
            ("common_100", "Common@100", "OncoKB overlaps in the top 100."),
        ]
        
        for idx, (key, title, desc) in enumerate(kpi_configs):
            card = ctk.CTkFrame(self.kpi_container, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8)
            card.grid(row=idx // 3, column=idx % 3, padx=6, pady=4, sticky="nsew")
            
            lbl = ctk.CTkLabel(card, text=title, font=(FONT_FAMILY_HEADER, 13), text_color=TEXT_MUTED)
            lbl.pack(anchor="w", padx=16, pady=(14, 2))
            
            val = ctk.CTkLabel(card, text="0.00", font=(FONT_FAMILY_HEADER, 26, "bold"), text_color=PRIMARY)
            val.pack(anchor="w", padx=16, pady=(0, 2))
            
            d_lbl = ctk.CTkLabel(card, text=desc, font=(FONT_FAMILY_BODY, 11), text_color=TEXT_MUTED, justify="left", wraplength=200)
            d_lbl.pack(anchor="w", padx=16, pady=(0, 14))
            
            self.kpis[key] = val
            self.kpi_descriptions[key] = d_lbl
            
        # Prioritization Spreadsheet Table Area
        self.table_card = ctk.CTkFrame(self, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.table_card.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        
        # Table toolbar controls
        self.toolbar = ctk.CTkFrame(self.table_card, fg_color="transparent")
        self.toolbar.pack(fill="x", padx=18, pady=(18, 10))
        
        self.search_entry = ctk.CTkEntry(self.toolbar, placeholder_text="Search gene symbol...", font=(FONT_FAMILY_BODY, 13), width=240, height=34, corner_radius=6)
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self._on_filter_changed)
        
        self.filter_hits_cb = ctk.CTkCheckBox(self.toolbar, text="OncoKB Hits Only", font=(FONT_FAMILY_BODY, 13), text_color=TEXT_MAIN,
                                              command=self._on_filter_changed, checkbox_height=18, checkbox_width=18)
        self.filter_hits_cb.pack(side="left", padx=10)
        
        self.limit_lbl = ctk.CTkLabel(self.toolbar, text="Show Limit:", font=(FONT_FAMILY_BODY, 13), text_color=TEXT_MAIN)
        self.limit_lbl.pack(side="right", padx=(10, 4))
        
        self.limit_segmented = ctk.CTkSegmentedButton(self.toolbar, values=["100", "500", "All"], 
                                                     command=self._on_limit_changed, font=(FONT_FAMILY_HEADER, 12),
                                                     selected_color=PRIMARY, selected_hover_color=STATUS_RUNNING)
        self.limit_segmented.pack(side="right")
        self.limit_segmented.set("100")
 
        self.source_label = ctk.CTkLabel(
            self.table_card,
            text="No ranking output loaded.",
            font=(FONT_FAMILY_BODY, 11),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.source_label.pack(fill="x", padx=18, pady=(0, 8))
        
        # Grid table
        cols = ("#", "Ensembl ID", "Gene Symbol", "Prioritization Score", "OncoKB Hit")
        col_w = {"#": 50, "Ensembl ID": 180, "Gene Symbol": 140, "Prioritization Score": 180, "OncoKB Hit": 100}
        self.table = DataTable(self.table_card, cols, col_w)
        self.table.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        
    def _on_filter_changed(self, event=None):
        self._refilter_table()
        
    def _on_limit_changed(self, value):
        self._refilter_table()
        
    def _refilter_table(self):
        if not self.state.active_results:
            self.table.clear()
            return
            
        query = self.search_entry.get().strip().upper()
        hits_only = bool(self.filter_hits_cb.get())
        limit = self.limit_segmented.get()
        
        filtered = []
        for r in self.state.active_results:
            symbol = r["gene_symbol"].upper()
            ensembl = r["ensembl_id"].upper()
            is_hit = r["oncokb_hit"]
            
            if query and query not in symbol and query not in ensembl:
                continue
            if hits_only and not is_hit:
                continue
                
            filtered.append(r)
            
        if limit == "100":
            filtered = filtered[:100]
        elif limit == "500":
            filtered = filtered[:500]
            
        rows_to_insert = []
        for r in filtered:
            rows_to_insert.append((
                r["rank"],
                r["ensembl_id"],
                r["gene_symbol"],
                f"{r['score']:.8f}",
                "Yes" if r["oncokb_hit"] else "No"
            ))
            
        self.table.insert_rows(rows_to_insert)

    def update_view(self):
        self.kpi_descriptions["recall_15"].configure(text="OncoKB reference genes captured in top 15.")
        self.kpi_descriptions["recall_100"].configure(text="OncoKB reference genes captured in top 100.")
        self.kpi_descriptions["common_15"].configure(text="OncoKB overlaps in the top 15.")
        self.kpi_descriptions["common_100"].configure(text="OncoKB overlaps in the top 100.")
        self.filter_hits_cb.configure(text="OncoKB Hits Only")
        self.table.tree.heading("OncoKB Hit", text="OncoKB Hit")
        kpis = self.state.kpi_metrics
        self.kpis["recall_15"].configure(text=f"{kpis['recall_15']:.4f}")
        self.kpis["recall_100"].configure(text=f"{kpis['recall_100']:.4f}")
        self.kpis["ndcg_15"].configure(text=f"{kpis['ndcg_15']:.4f}")
        self.kpis["ndcg_100"].configure(text=f"{kpis['ndcg_100']:.4f}")
        self.kpis["common_15"].configure(text=f"{kpis['common_15']}")
        self.kpis["common_100"].configure(text=f"{kpis['common_100']}")
        if self.state.active_result_path:
            self.source_label.configure(
                text=f"Ranking source: {self.state.active_result_path} | Evaluation: {self.state.evaluation_mode}"
            )
        else:
            self.source_label.configure(text="No ranking output loaded.")
        
        self._refilter_table()
