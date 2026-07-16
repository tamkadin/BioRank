import customtkinter as ctk
from biorank_ui.state import AppState
from biorank_ui.components import DatasetCard
from biorank_ui.theme import (
    APP_BG, CARD_BG, BORDER, TEXT_MAIN, TEXT_MUTED,
    FONT_FAMILY_HEADER, FONT_FAMILY_BODY
)

class DashboardView(ctk.CTkFrame):
    def __init__(self, master, state: AppState, browse_callback, **kwargs):
        super().__init__(master, fg_color=APP_BG, **kwargs)
        self.state = state
        self.browse_callback = browse_callback
        
        # Configure overall grid resizing
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Readiness card
        self.grid_rowconfigure(1, weight=1) # Dataset cards grid
        
        # Pipeline Readiness Overview Card
        self.readiness_card = ctk.CTkFrame(self, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8)
        self.readiness_card.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        self.rc_title = ctk.CTkLabel(self.readiness_card, text="Cancer Gene Prioritization Pipeline Readiness", font=(FONT_FAMILY_HEADER, 19), text_color=TEXT_MAIN if 'TEXT_MAIN' in globals() else "#102A43")
        self.rc_title.pack(anchor="w", padx=20, pady=(18, 6))
        
        self.rc_status = ctk.CTkLabel(self.readiness_card, text="", font=(FONT_FAMILY_BODY, 15), text_color=TEXT_MUTED if 'TEXT_MUTED' in globals() else "#627D98")
        self.rc_status.pack(anchor="w", padx=20, pady=(0, 18))
        
        # Grid layout for 6 inputs cards
        self.grid_container = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_container.grid(row=1, column=0, padx=20, pady=(10, 20), sticky="nsew")
        
        for c in range(3):
            self.grid_container.grid_columnconfigure(c, weight=1, uniform="dataset_grid")
        for r in range(2):
            self.grid_container.grid_rowconfigure(r, weight=0)
        self.grid_container.grid_rowconfigure(2, weight=1) # Spacer row at the bottom
            
        self.cards = {}
        dataset_titles = [
            ("Protein-Protein Interactions (PPI)", "ppi"),
            ("Tumor Gene Co-expression Matrix", "coexpression"),
            ("Disease Driver Seed Genes Set", "seed"),
            ("Differentially Expressed (DE) Genes", "de_genes"),
            ("Bipartite Gene-Ontology Mappings", "ontology_map"),
            ("Enriched Disease-Specific Ontologies", "disease_ontology")
        ]
        
        for idx, (title, key) in enumerate(dataset_titles):
            row = idx // 3
            col = idx % 3
            card = DatasetCard(self.grid_container, title, key, initial_path=state.file_paths[key], 
                               initial_status=state.file_statuses[key], browse_callback=self.browse_callback)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self.cards[key] = card
            
        self.update_view()
        
    def update_view(self):
        # Update Readiness Card description
        ready_count = sum(1 for status in self.state.file_statuses.values() if status == "Ready")
        self.rc_status.configure(text=f"Database Integrator: {ready_count}/6 datasets verified. Ready to configure hyperparameter propagation models.")
        
        # Update cards values
        for key, card in self.cards.items():
            card.update_state(self.state.file_paths[key], self.state.file_statuses[key])
