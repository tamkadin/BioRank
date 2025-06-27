import tkinter as tk
from tkinter import filedialog, messagebox
import os
import time
import sys
import shutil
import pandas as pd
from improved_pagerank.ImprovedPageRank import ImprovedPageRankCancerGeneRanking
from data_preprocessing.compute_ontology_graph import OntologyGraph
from data_preprocessing.compute_disease_specific_ontologies import DiseaseOntologies
from data_preprocessing.compute_co_expression_and_de_genes import create_de_genes, get_top_correlations
from data_preprocessing.TCGA_analyzer import TCGAAnalyzer

class PageRankGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Cancer Gene Prioritization Tool")
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, "icon.ico")
        else:
            icon_path = os.path.abspath("icon.ico")
        self.root.iconbitmap(default=icon_path)
        self.root.geometry("1000x400")
        self.root.configure(bg="white")

        main_frame = tk.Frame(self.root, bg="white")
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        self.left_frame = tk.LabelFrame(main_frame, text="Run PageRank", font=("Segoe UI", 12, "bold"), bg="white")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.right_frame = tk.LabelFrame(main_frame, text="Data Preprocessing", font=("Segoe UI", 12, "bold"), bg="white")
        self.right_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.last_output_path = None
        self.init_run_buttons()
        self.init_preprocess_tab()

    def styled_button(self, parent, text, command):
        return tk.Button(parent, text=text, bg="#0078D7", fg="white", font=("Segoe UI", 10, "bold"), command=command, relief="flat", padx=10, pady=5)

    def init_run_buttons(self):
        tk.Label(self.left_frame, text="Choose a Algorithm:", font=("Arial", 12, "bold")).pack(pady=10)
        self.styled_button(self.left_frame, "▶ BioRank (Enhanced PageRank)", self.open_enhanced_pagerank_window).pack(pady=10)

    def open_enhanced_pagerank_window(self):
        self.create_pagerank_input_window("BioRank (Enhanced PageRank)", algorithm="biorank")

    def create_pagerank_input_window(self, title, algorithm):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("700x400")
        entries = {}

        def add_input(label, key):
            frame = tk.Frame(window)
            frame.pack(fill="x", padx=10, pady=6)
            tk.Label(frame, text=label, width=35, anchor="w").pack(side="left")
            entry = tk.Entry(frame, width=50)
            entry.pack(side="left", padx=5)
            entries[key] = entry
            tk.Button(frame, text="Browse", command=lambda e=entry: self.browse_file(e, window)).pack(side="left")

        add_input("PPI Network (-p):", "ppi")
        add_input("Co-expression Network (-c):", "coexpr")
        add_input("Seed Genes File (-s):", "seed")
        add_input("Differentially Expressed Genes (-de):", "deg")
        add_input("Gene-Ontology Mapping File (-a):", "anno")
        add_input("Disease-Specific Ontologies (-do):", "disease_onto")

        def run():
            args = {
                "ppi_file_path": entries["ppi"].get(),
                "co_expression_file_path": entries["coexpr"].get(),
                "seed_file_path": entries["seed"].get(),
                "secondary_seed_file_path": entries["deg"].get(),
                "map__gene__ontologies_file_path": entries["anno"].get(),
                "disease_ontology_file_path": entries["disease_onto"].get(),
                "matrix_aggregation_policy": "convex_combination",
                "personalization_vector_creation_policies": ["topological", "biological"],
                "personalization_vector_aggregation_policy": "Sum",
                "alpha": 0.5,
                "beta": 0.5,
                "network_weight_flag": True
            }
            os.makedirs("output", exist_ok=True)
            output_path = "output/LATEST_RESULT.csv"
            args["output_file_path"] = output_path
            args["algorithm"] = algorithm
            try:
                ImprovedPageRankCancerGeneRanking(**args)
                messagebox.showinfo("Done", f"✅ {title} completed.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        self.styled_button(window, "▶ Run", run).pack(pady=10)
        tk.Button(window, text="🔙 Back", command=window.destroy).pack(pady=(0, 10))

    def init_preprocess_tab(self):
        tk.Label(self.right_frame, text="Choose a preprocessing function:", font=("Arial", 12, "bold")).pack(pady=10)

        button_width = 35
        actions = [
            ("Compute Ontology Graph", self.run_ontology_graph),
            ("Compute Disease-Specific Ontologies", self.run_disease_ontologies),
            ("Compute DE Genes + Co-expression", self.run_de_genes_and_coexpr),
            ("Create Tumor-Control Table", self.run_tcga_table)
        ]
        for text, command in actions:
            tk.Button(
                self.right_frame, text=text,
                width=button_width,
                font=("Segoe UI", 10, "bold"),
                bg="#0078D7", fg="white",
                command=command
            ).pack(pady=5)

    def browse_file(self, entry, parent):
        path = filedialog.askopenfilename(parent=parent)
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def browse_folder(self, entry, parent):
        path = filedialog.askdirectory(parent=parent)
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def save_as(self):
        if not self.last_output_path or not os.path.exists(self.last_output_path):
            messagebox.showerror("No result", "No result file found.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv")
        if path:
            shutil.copyfile(self.last_output_path, path)
            messagebox.showinfo("Saved", f"✅ File saved to:\n{path}")

    def create_input_window(self, title, inputs, process_func, output_files):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("700x450")
        entries = {}

        for label, key, is_folder in inputs:
            frame = tk.Frame(window)
            frame.pack(fill="x", padx=10, pady=5)
            tk.Label(frame, text=label, width=35, anchor="w").pack(side="left")
            entry = tk.Entry(frame, width=50)
            entry.pack(side="left", padx=5)
            entries[key] = entry
            browse = self.browse_folder if is_folder else self.browse_file
            tk.Button(frame, text="Browse", command=lambda e=entry, b=browse: b(e, window)).pack(side="left")

        tk.Label(window, text="Output file(s) will be generated internally.").pack(pady=(5, 0))

        def run():
            files = {k: e.get() for k, e in entries.items()}
            if all(files.values()):
                os.makedirs("output", exist_ok=True)
                paths = {key: os.path.join("output", name) for key, name in output_files.items()}
                process_func(files, paths)

                def save():
                    for key, out_file in paths.items():
                        path = filedialog.asksaveasfilename(title=f"Save {key}", defaultextension=os.path.splitext(out_file)[1], parent=window)
                        if path:
                            shutil.copyfile(out_file, path)
                    messagebox.showinfo("Saved", "✅ Files saved successfully.", parent=window)

                self.styled_button(window, "💾 Save Result(s)", save).pack(pady=5)
                messagebox.showinfo("Done", f"✅ {title} completed.", parent=window)
            else:
                messagebox.showerror("Missing File", "Please select all required files.", parent=window)

        self.styled_button(window, "Run", run).pack(pady=10)
        tk.Button(window, text="🔙 Back", command=window.destroy).pack(pady=(0, 10))

    def run_ontology_graph(self):
        self.create_input_window(
            "Compute Ontology Graph",
            [
                ("GO .gaf File:", "go", False),
                ("KEGG File:", "kegg", False),
                ("Reactome File:", "reactome", False),
                ("Uniprot-Ensembl Mapping File:", "uniprot", False),
                ("KEGG-Uniprot Mapping File:", "keggmap", False)
            ],
            lambda f, p: OntologyGraph(
                GO_file_path=f["go"],
                KEGG_file_path=f["kegg"],
                Reactome_file_path=f["reactome"],
                output_file_path=p["ontology"],
                uniprot_mapping_path=f["uniprot"],
                kegg_mapping_path=f["keggmap"]
            ).run(),
            {"ontology": "ontology_output.tsv"}
        )

    def run_disease_ontologies(self):
        self.create_input_window(
            "Compute Disease-Specific Ontologies",
            [
                ("Ontology Graph File:", "onto", False),
                ("Seed Genes File:", "seed", False)
            ],
            lambda f, p: DiseaseOntologies(
                ontology_graph_file_path=f["onto"],
                disease_seed_file_path=f["seed"],
                output_file_path=p["disease"]
            ).run(),
            {"disease": "disease_ontology_output.txt"}
        )

    def run_de_genes_and_coexpr(self):
        self.create_input_window(
            "Compute DE Genes + Co-expression",
            [
                ("Tumor Expression Table:", "tumor", False),
                ("Control Expression Table:", "control", False),
                ("Identifier File:", "identifier", False)
            ],
            lambda f, p: (
                create_de_genes(
                    tumor_file_path=f["tumor"],
                    control_file_path=f["control"],
                    output_file_path=p["de"],
                    threshold=2.5,
                    identifier_file_path=f["identifier"]
                ),
                get_top_correlations(
                    expression_file_path=f["tumor"],
                    output_file_path=p["coexpr"],
                    identifier_file_path=f["identifier"],
                    threshold=0.7
                )
            ),
            {"de": "de_genes.tsv", "coexpr": "coexpression.tsv"}
        )

    def run_tcga_table(self):
        self.create_input_window(
            "Create Tumor-Control Table",
            [
                ("GDC Sample Sheet:", "gdc", False),
                ("Manifest File:", "manifest", False),
                ("RNA-seq Directory:", "rna_dir", True),
                ("Output Directory:", "output_dir", True)
            ],
            lambda f, p: TCGAAnalyzer(
                sample_sheet_file_path=f["gdc"],
                manifest_file_path=f["manifest"],
                TCGA_directory_path=f["rna_dir"],
                output_dir_path=f["output_dir"]
            ).create_tumor_control_table(),
            {}
        )

if __name__ == '__main__':
    root = tk.Tk()
    app = PageRankGUI(root)
    root.mainloop()
