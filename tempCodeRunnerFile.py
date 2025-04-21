class PageRankGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Cancer Gene Prioritization Tool")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')

        self.run_tab = ttk.Frame(self.notebook)
        self.preprocess_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.run_tab, text='Run PageRank')
        self.notebook.add(self.preprocess_tab, text='Data Preprocessing')

        self.last_output_path = None
        self.init_run_tab()
        self.init_preprocess_tab()

    def init_run_tab(self):
        self.inputs = {}

        def add_input(label_text, key):
            frame = tk.Frame(self.run_tab)
            frame.pack(fill="x", padx=10, pady=2)
            label = tk.Label(frame, text=label_text, width=40, anchor="w")
            label.pack(side="left")
            entry = tk.Entry(frame, width=50)
            entry.pack(side="left", padx=5)
            self.inputs[key] = entry
            tk.Button(frame, text="Browse", command=lambda: self.browse_file(entry, self.root)).pack(side="left")

        add_input("Protein-Protein Interaction Network (-p):", "ppi")
        add_input("Co-expression Network (-c):", "coexpr")
        add_input("Seed Genes File (-s):", "seed")
        add_input("Differentially Expressed Genes (-de):", "deg")
        add_input("Gene-Ontology Mapping File (-a):", "anno")
        add_input("Disease-Specific Ontologies (-do):", "disease_onto")

        self.run_button = tk.Button(self.run_tab, text="▶ Run PageRank", command=self.run_pagerank, bg="#0078D7", fg="white")
        self.run_button.pack(pady=10)

        self.status = tk.Label(self.run_tab, text="", fg="green")
        self.status.pack()

        self.download_button = tk.Button(self.run_tab, text="💾 Save Result As...", command=self.save_as)
        self.download_button.pack(pady=5)
        self.download_button.pack_forget()

    def run_pagerank(self):
        try:
            args = {
                "ppi_file_path": self.inputs["ppi"].get(),
                "co_expression_file_path": self.inputs["coexpr"].get(),
                "seed_file_path": self.inputs["seed"].get(),
                "secondary_seed_file_path": self.inputs["deg"].get(),
                "map__gene__ontologies_file_path": self.inputs["anno"].get(),
                "disease_ontology_file_path": self.inputs["disease_onto"].get(),
                "matrix_aggregation_policy": "convex_combination",
                "personalization_vector_creation_policies": ["topological", "biological"],
                "personalization_vector_aggregation_policy": "Sum",
                "restart_prob": 0.9,
                "alpha": 0.5,
                "beta": 0.5,
                "network_weight_flag": True
            }
            os.makedirs("output", exist_ok=True)
            output_path = "output/LATEST_RESULT.csv"
            args["output_file_path"] = output_path
            self.last_output_path = output_path

            for k, v in args.items():
                if k.endswith("_file_path") and (not v or not os.path.exists(v)):
                    raise ValueError(f"File not found: {v}")

            self.status.config(text="⏳ Running PageRank... Please wait.", fg="blue")
            self.download_button.pack_forget()
            self.root.update()

            start = time.perf_counter()
            ImprovedPageRankCancerGeneRanking(**args)
            runtime = time.perf_counter() - start

            self.status.config(text=f"✅ Completed in {runtime:.2f} seconds", fg="green")
            self.download_button.pack(pady=5)

        except Exception as e:
            self.status.config(text=f"❌ Error: {e}", fg="red")
            messagebox.showerror("Error", str(e))

    def init_preprocess_tab(self):
        tk.Label(self.preprocess_tab, text="Choose a preprocessing function:", font=("Arial", 12, "bold")).pack(pady=10)
        actions = [
            ("Compute Ontology Graph", self.run_ontology_graph),
            ("Compute Disease-Specific Ontologies", self.run_disease_ontologies),
            ("Compute DE Genes + Co-expression", self.run_de_genes_and_coexpr),
            ("Create Tumor-Control Table", self.run_tcga_table)
        ]
        for text, command in actions:
            tk.Button(self.preprocess_tab, text=text, width=40, command=command).pack(pady=5)

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

                tk.Button(window, text="💾 Save Result(s)", command=save).pack(pady=5)
                messagebox.showinfo("Done", f"✅ {title} completed.", parent=window)
            else:
                messagebox.showerror("Missing File", "Please select all required files.", parent=window)

        tk.Button(window, text="Run", command=run, bg="#0078D7", fg="white").pack(pady=10)
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
