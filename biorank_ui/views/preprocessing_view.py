import customtkinter as ctk
from biorank_ui.state import AppState
from biorank_ui.theme import (
    APP_BG, CARD_BG, BORDER, PRIMARY, SOFT_BLUE, TEXT_MAIN, TEXT_MUTED,
    STATUS_READY, STATUS_MISSING, STATUS_RUNNING,
    FONT_FAMILY_HEADER, FONT_FAMILY_BODY
)

class PreprocessingView(ctk.CTkFrame):
    def __init__(self, master, state: AppState, run_step_callback, **kwargs):
        super().__init__(master, fg_color=APP_BG, **kwargs)
        self.state = state
        self.run_step_callback = run_step_callback
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.scrollable = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        self.steps = {}
        steps_data = [
            (1, "Step 1: Compute Bipartite Pathway Ontology Graph", 
             "Builds cross-reference associations mappings linking GO, KEGG, Reactome annotations with Ensembl IDs.",
             ["ontology_map"]),
            (2, "Step 2: Compute Enriched Disease-Specific Ontologies", 
             "Runs Fisher's exact statistics test with FDR corrections (p < 1e-5) to identify seed functional enrichments.",
             ["disease_ontology"]),
            (3, "Step 3: Process Clinical Tumor-Control Expression Matrices", 
             "Parses manifest lists and extracts GDC normal control / tumor clinical RNA-seq profiles.",
             []),
            (4, "Step 4: Calculate DE Genes & Co-expression PCC Weights", 
             "Filters genes relative to node lists, evaluates log z-score (>2.5), and computes Pearson correlations correlations (>0.7).",
             ["de_genes", "coexpression"])
        ]
        
        for step_idx, title, desc, outputs in steps_data:
            card = ctk.CTkFrame(self.scrollable, fg_color=CARD_BG, border_color=BORDER, border_width=1, corner_radius=8)
            card.pack(fill="x", pady=10, ipady=12)
            
            card.grid_columnconfigure(0, weight=0)
            card.grid_columnconfigure(1, weight=1)
            card.grid_columnconfigure(2, weight=0)
            
            # Indicator bubble
            bubble = ctk.CTkLabel(card, text=str(step_idx), font=(FONT_FAMILY_HEADER, 15, "bold"),
                                  fg_color=SOFT_BLUE, text_color=PRIMARY, width=36, height=36, corner_radius=18)
            bubble.grid(row=0, column=0, padx=20, pady=20, rowspan=2)
            
            # Step header
            header = ctk.CTkLabel(card, text=title, font=(FONT_FAMILY_HEADER, 16), text_color=TEXT_MAIN, anchor="w")
            header.grid(row=0, column=1, sticky="w", pady=(18, 2))
            
            # Description
            desc_lbl = ctk.CTkLabel(card, text=desc, font=(FONT_FAMILY_BODY, 13), text_color=TEXT_MUTED, anchor="w", justify="left")
            desc_lbl.grid(row=1, column=1, sticky="w", pady=(0, 14))
            
            # Run button and status label
            run_btn = ctk.CTkButton(card, text="Select Inputs & Run", font=(FONT_FAMILY_HEADER, 13, "bold"),
                                     fg_color=PRIMARY, hover_color=STATUS_RUNNING, text_color="#FFFFFF",
                                     height=36, width=160, corner_radius=6, command=lambda s=step_idx: self.run_step_callback(s))
            run_btn.grid(row=0, column=2, padx=20, pady=(18, 6), sticky="e")
            
            status_lbl = ctk.CTkLabel(card, text="Unprocessed", font=(FONT_FAMILY_HEADER, 12, "bold"), text_color=STATUS_MISSING)
            status_lbl.grid(row=1, column=2, padx=20, pady=(0, 14), sticky="e")
            
            self.steps[step_idx] = {"button": run_btn, "status": status_lbl, "outputs": outputs}
            
        self.update_view()
        
    def update_view(self):
        for idx, step in self.steps.items():
            step["button"].configure(state="disabled" if self.state.is_running else "normal")
            outputs = step["outputs"]
            if not outputs:
                if self.state.preprocessing_statuses.get(idx) == "Completed":
                    step["status"].configure(text="Completed", text_color=STATUS_READY)
                else:
                    step["status"].configure(text="Select inputs", text_color=STATUS_RUNNING)
                continue
                
            all_ready = True
            for out in outputs:
                if self.state.file_statuses.get(out, "Missing") != "Ready":
                    all_ready = False
                    break
                    
            if all_ready:
                step["status"].configure(text="Completed", text_color=STATUS_READY)
            else:
                step["status"].configure(text="Unprocessed", text_color=STATUS_MISSING)
