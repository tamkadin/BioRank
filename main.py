import glob
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "BioRank - Cancer Gene Prioritization"
DATASET_DIR = "data_set"
OUTPUT_DIR = "output"
PREVIEW_NODE_LIMIT = 1000
PREVIEW_EDGE_LIMIT = 2000

COLORS = {
    "bg": "#eaf2ff",
    "panel": "#ffffff",
    "text": "#111827",
    "muted": "#5b677a",
    "border": "#bfdbfe",
    "accent": "#2563eb",
    "accent_dark": "#0f4c81",
    "accent_soft": "#dbeafe",
    "secondary": "#eff6ff",
    "secondary_hover": "#dbeafe",
    "success": "#15803d",
    "warning": "#b45309",
    "danger": "#b91c1c",
}

DISEASES = ("BLCA", "BRCA", "COAD", "LUAD", "PRAD", "STAD", "THCA")
ALGORITHM_ORIGINAL_PAGERANK = "pagerank"
ALGORITHM_BIORANK = "biorank"

ALGORITHM_LABELS = {
    ALGORITHM_ORIGINAL_PAGERANK: "Original PageRank",
    ALGORITHM_BIORANK: "BioRank",
}

ALGORITHM_SLUGS = {
    ALGORITHM_ORIGINAL_PAGERANK: "original_pagerank",
    ALGORITHM_BIORANK: "biorank",
}

BIORANK_INPUTS = [
    ("PPI Network (-p)", "ppi_file_path", False),
    ("Co-expression Network (-c)", "co_expression_file_path", False),
    ("Seed Genes File (-s)", "seed_file_path", False),
    ("Differentially Expressed Genes (-de)", "secondary_seed_file_path", False),
    ("Gene-Ontology Mapping File (-a)", "map__gene__ontologies_file_path", False),
    ("Disease-Specific Ontologies (-do)", "disease_ontology_file_path", False),
]


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def find_first(patterns):
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
    return ""


def detect_disease_from_text(text):
    normalized = text.upper()
    for disease in DISEASES:
        if disease in normalized:
            return disease
    return ""


def disease_output_dir(disease):
    if disease in DISEASES:
        return ensure_dir(os.path.join(OUTPUT_DIR, disease))
    return ensure_dir(os.path.join(OUTPUT_DIR, "common"))


def build_output_paths(disease, algorithm):
    disease_dir = disease_output_dir(disease)
    algorithm_slug = ALGORITHM_SLUGS.get(algorithm, algorithm or "ranking")
    return {
        "ranking": os.path.join(disease_dir, f"{disease}_{algorithm_slug}_ranking.tsv"),
        "network": os.path.join(disease_dir, f"{disease}_integrated_network.tsv"),
    }


def build_default_biorank_inputs(disease):
    tcga = f"TCGA-{disease}"
    return {
        "ppi_file_path": find_first([os.path.join(DATASET_DIR, "ppi_network", "HIPPIE.tsv")]),
        "co_expression_file_path": find_first(
            [os.path.join(DATASET_DIR, "co-expression_networks", f"{tcga}*co_expression*.tsv")]
        ),
        "seed_file_path": find_first(
            [
                os.path.join(DATASET_DIR, "seed_set", f"{tcga}*_seed.txt"),
                os.path.join(DATASET_DIR, "seed_set", f"{tcga}*_seed.tsv"),
                os.path.join(DATASET_DIR, "seed_set", f"{tcga}*_seed.*"),
                os.path.join(DATASET_DIR, "seed_set", f"{tcga}*_seed"),
            ]
        ),
        "secondary_seed_file_path": find_first(
            [os.path.join(DATASET_DIR, "differentially_expressed_genes", f"{tcga}*de_genes.tsv")]
        ),
        "map__gene__ontologies_file_path": find_first(
            [os.path.join(DATASET_DIR, "ontology_network", "ontology_network.tsv")]
        ),
        "disease_ontology_file_path": find_first(
            [os.path.join(DATASET_DIR, "disease_specific_ontologies", f"{tcga}*disease_ontologies.txt")]
        ),
    }


class BioRankGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1160x660")
        self.root.minsize(980, 580)

        self.status_var = tk.StringVar(value="Ready")
        self.current_result_path = None
        self.current_network_path = None

        self._configure_window_icon()
        self._configure_style()
        self._build_layout()

    def _configure_window_icon(self):
        if sys.platform != "win32":
            return
        try:
            icon_path = os.path.join(getattr(sys, "_MEIPASS", os.getcwd()), "icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(default=icon_path)
        except Exception as exc:
            print(f"[Warning] Could not set window icon: {exc}")

    def _configure_style(self):
        self.root.configure(bg=COLORS["bg"])
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["panel"])
        style.configure("Panel.TLabelframe", background=COLORS["panel"], padding=14)
        style.configure("Panel.TLabelframe.Label", font=("Segoe UI", 12, "bold"))
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground="#ffffff", background=COLORS["accent_dark"])
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#dbeafe", background=COLORS["accent_dark"])
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"), foreground=COLORS["text"], background=COLORS["panel"])
        style.configure("Hint.TLabel", font=("Segoe UI", 9), foreground=COLORS["muted"], background=COLORS["panel"])
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground="#ffffff",
            background=COLORS["accent"],
            bordercolor=COLORS["accent"],
            lightcolor=COLORS["accent"],
            darkcolor=COLORS["accent"],
            padding=(14, 9),
        )
        style.map(
            "Primary.TButton",
            foreground=[("disabled", "#f1f5f9"), ("active", "#ffffff")],
            background=[("disabled", "#94a3b8"), ("active", COLORS["accent_dark"])],
        )
        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10),
            foreground=COLORS["text"],
            background=COLORS["secondary"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["secondary"],
            darkcolor=COLORS["secondary"],
            padding=(12, 8),
        )
        style.map("Secondary.TButton", background=[("active", COLORS["secondary_hover"])])
        style.configure("Status.TLabel", font=("Segoe UI", 9), foreground=COLORS["muted"], background="#e8edf5")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Treeview", rowheight=24)

    def _build_layout(self):
        header = tk.Frame(self.root, bg=COLORS["accent_dark"])
        header.pack(fill="x")
        header_inner = ttk.Frame(header, padding=(28, 20, 28, 18))
        header_inner.configure(style="Header.TFrame")
        header_inner.pack(fill="x")
        ttk.Style(self.root).configure("Header.TFrame", background=COLORS["accent_dark"])
        ttk.Label(header_inner, text="BioRank", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header_inner,
            text="Select a cancer type, auto-load available datasets, review the integrated network, then run ranking.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        main_frame = ttk.Frame(self.root, padding=(24, 10, 24, 18))
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=7)
        main_frame.columnconfigure(1, weight=5)
        main_frame.rowconfigure(0, weight=1)

        self.selected_disease_var = tk.StringVar(value="COAD")
        self.dataset_summary_var = tk.StringVar()

        self.left_panel, self.left_frame = self._create_panel(main_frame, "Ranking Workflow")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.right_panel, self.right_frame = self._create_panel(main_frame, "Data Preprocessing")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self._init_run_buttons()
        self._init_preprocess_buttons()
        self._build_status_bar()
        self._refresh_dataset_status()

    def _create_panel(self, parent, title):
        outer = tk.Frame(
            parent,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            bd=0,
        )
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        tk.Label(
            outer,
            text=title,
            bg=COLORS["panel"],
            fg=COLORS["accent_dark"],
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 6))

        tk.Frame(outer, bg=COLORS["accent"], height=3).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 10),
        )

        body = ttk.Frame(outer, style="Card.TFrame", padding=(18, 4, 18, 18))
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        return outer, body

    def _build_status_bar(self):
        ttk.Label(
            self.root,
            textvariable=self.status_var,
            style="Status.TLabel",
            anchor="w",
            padding=(16, 6),
        ).pack(fill="x", side="bottom")

    def _init_run_buttons(self):
        selector = ttk.Frame(self.left_frame, style="Card.TFrame")
        selector.pack(fill="x", pady=(0, 14))
        selector.columnconfigure(1, weight=1)

        ttk.Label(selector, text="Cancer type", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12))
        disease_box = ttk.Combobox(
            selector,
            textvariable=self.selected_disease_var,
            values=DISEASES,
            state="readonly",
            width=12,
        )
        disease_box.grid(row=0, column=1, sticky="w")
        disease_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_dataset_status())

        ttk.Label(
            self.left_frame,
            textvariable=self.dataset_summary_var,
            style="Hint.TLabel",
            wraplength=500,
        ).pack(anchor="w", pady=(0, 10))

        self.dataset_tree = ttk.Treeview(
            self.left_frame,
            columns=("input", "status", "file"),
            show="headings",
            height=6,
        )
        self.dataset_tree.heading("input", text="Input")
        self.dataset_tree.heading("status", text="Status")
        self.dataset_tree.heading("file", text="Detected file")
        self.dataset_tree.column("input", width=190, anchor="w")
        self.dataset_tree.column("status", width=80, anchor="center")
        self.dataset_tree.column("file", width=300, anchor="w")
        self.dataset_tree.tag_configure("ready", foreground=COLORS["success"])
        self.dataset_tree.tag_configure("missing", foreground=COLORS["warning"])
        self.dataset_tree.pack(fill="x", pady=(0, 14))

        ttk.Button(
            self.left_frame,
            text="Build Network + Original PageRank",
            style="Primary.TButton",
            command=lambda: self.open_biorank_window(ALGORITHM_ORIGINAL_PAGERANK),
        ).pack(fill="x", pady=6)

        ttk.Button(
            self.left_frame,
            text="Build Network + BioRank",
            style="Primary.TButton",
            command=lambda: self.open_biorank_window(ALGORITHM_BIORANK),
        ).pack(fill="x", pady=6)

        ttk.Label(
            self.left_frame,
            text="Outputs are saved automatically under output/<DISEASE>/ with explicit filenames.",
            style="Hint.TLabel",
            wraplength=500,
        ).pack(anchor="w", pady=(18, 0))

    def _refresh_dataset_status(self):
        if not hasattr(self, "dataset_tree"):
            return

        disease = self.selected_disease_var.get()
        defaults = build_default_biorank_inputs(disease)
        available = sum(1 for value in defaults.values() if value)
        total = len(defaults)
        output_paths = build_output_paths(disease, ALGORITHM_BIORANK)
        self.dataset_summary_var.set(
            f"{available}/{total} standard inputs detected for {disease}. "
            f"Default output: {output_paths['ranking']}"
        )

        for item in self.dataset_tree.get_children():
            self.dataset_tree.delete(item)

        labels = {key: label for label, key, _ in BIORANK_INPUTS}
        for key, value in defaults.items():
            status = "Ready" if value else "Missing"
            file_name = value if value else "Browse manually in the run window"
            tag = "ready" if value else "missing"
            self.dataset_tree.insert("", "end", values=(labels[key], status, file_name), tags=(tag,))

    def open_biorank_window(self, algorithm):
        title = ALGORITHM_LABELS[algorithm]
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("940x620")
        window.configure(bg=COLORS["bg"])
        window.transient(self.root)

        container = ttk.Frame(window, padding=18)
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)

        disease_var = tk.StringVar(value=self.selected_disease_var.get())
        ttk.Label(container, text="Cancer type").grid(row=0, column=0, sticky="w", pady=6)
        disease_box = ttk.Combobox(
            container,
            textvariable=disease_var,
            values=DISEASES,
            state="readonly",
            width=12,
        )
        disease_box.grid(row=0, column=1, sticky="w", padx=8, pady=6)

        auto_status_var = tk.StringVar(value="")
        ttk.Label(container, textvariable=auto_status_var, style="Hint.TLabel").grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(0, 8),
        )

        entries = {}
        start_row = 2
        for row_offset, (label, key, is_folder) in enumerate(BIORANK_INPUTS):
            row = start_row + row_offset
            ttk.Label(container, text=label).grid(row=row, column=0, sticky="w", pady=6)
            entry = ttk.Entry(container)
            entry.grid(row=row, column=1, sticky="ew", padx=8, pady=6)
            entries[key] = entry
            browse = self.browse_folder if is_folder else self.browse_file
            ttk.Button(
                container,
                text="Browse",
                command=lambda e=entry, b=browse: self._browse_and_detect_disease(
                    e,
                    b,
                    window,
                    disease_var,
                    refresh_output_hint,
                ),
            ).grid(row=row, column=2, sticky="ew", pady=6)

        settings_row = start_row + len(BIORANK_INPUTS)
        settings = ttk.LabelFrame(container, text="Parameters", padding=10)
        settings.grid(row=settings_row, column=0, columnspan=3, sticky="ew", pady=(14, 8))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        alpha_var = tk.StringVar(value="0.2")
        beta_var = tk.StringVar(value="0.2")
        ttk.Label(settings, text="Alpha").grid(row=0, column=0, padx=(0, 8))
        ttk.Entry(settings, textvariable=alpha_var, width=10).grid(row=0, column=1, sticky="w")
        ttk.Label(settings, text="Beta").grid(row=0, column=2, padx=(24, 8))
        ttk.Entry(settings, textvariable=beta_var, width=10).grid(row=0, column=3, sticky="w")

        output_var = tk.StringVar()
        ttk.Label(container, textvariable=output_var, style="Hint.TLabel").grid(
            row=settings_row + 1,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(4, 10),
        )

        actions = ttk.Frame(container)
        actions.grid(row=settings_row + 2, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)

        build_button = ttk.Button(actions, text="Build Network", style="Primary.TButton")
        build_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="Auto-fill Inputs", command=lambda: auto_fill()).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=6,
        )
        ttk.Button(actions, text="Close", command=window.destroy).grid(
            row=0,
            column=2,
            sticky="ew",
            padx=(6, 0),
        )

        def refresh_output_hint():
            paths = build_output_paths(disease_var.get(), algorithm)
            output_var.set(f"Output: {paths['ranking']} | {paths['network']}")

        def auto_fill():
            defaults = build_default_biorank_inputs(disease_var.get())
            missing = []
            for label, key, _ in BIORANK_INPUTS:
                entries[key].delete(0, tk.END)
                if defaults[key]:
                    entries[key].insert(0, defaults[key])
                else:
                    missing.append(label)

            if missing:
                auto_status_var.set("Auto-fill missing: " + ", ".join(missing))
            else:
                auto_status_var.set("All standard inputs were auto-filled from data_set/.")
            refresh_output_hint()

        def on_disease_change(_event=None):
            self.selected_disease_var.set(disease_var.get())
            self._refresh_dataset_status()
            auto_fill()

        def build_network():
            args = self._collect_biorank_args(entries, alpha_var, beta_var, disease_var.get(), algorithm)
            if args is None:
                return

            output_paths = build_output_paths(disease_var.get(), algorithm)
            build_button.config(state="disabled", text="Building network...")
            self.status_var.set(f"Building integrated network for {disease_var.get()}...")

            threading.Thread(
                target=self._prepare_network_task,
                args=(window, title, disease_var.get(), output_paths, args, build_button),
                daemon=True,
            ).start()

        disease_box.bind("<<ComboboxSelected>>", on_disease_change)
        build_button.config(command=build_network)
        auto_fill()

    def _browse_and_detect_disease(self, entry, browse_func, parent, disease_var, on_change=None):
        browse_func(entry, parent)
        detected = detect_disease_from_text(entry.get())
        if detected:
            disease_var.set(detected)
        if on_change is not None:
            on_change()

    def _collect_biorank_args(self, entries, alpha_var, beta_var, disease, algorithm):
        missing = []
        invalid = []
        args = {}

        for label, key, _ in BIORANK_INPUTS:
            value = entries[key].get().strip()
            if not value:
                missing.append(label)
            elif not os.path.exists(value):
                invalid.append(value)
            args[key] = value

        if missing:
            messagebox.showerror("Missing input", "Please select:\n" + "\n".join(missing))
            return None
        if invalid:
            messagebox.showerror("Invalid path", "These files do not exist:\n" + "\n".join(invalid[:8]))
            return None

        try:
            alpha = float(alpha_var.get())
            beta = float(beta_var.get())
        except ValueError:
            messagebox.showerror("Invalid parameters", "Alpha and Beta must be numeric values.")
            return None

        if not 0 <= alpha <= 1 or not 0 <= beta <= 1:
            messagebox.showerror("Invalid parameters", "Alpha and Beta must be between 0 and 1.")
            return None

        output_paths = build_output_paths(disease, algorithm)
        args.update(
            {
                "matrix_aggregation_policy": "convex_combination",
                "personalization_vector_creation_policies": ["topological", "biological"],
                "personalization_vector_aggregation_policy": "Sum",
                "alpha": alpha,
                "beta": beta,
                "network_weight_flag": True,
                "algorithm": algorithm,
                "output_file_path": output_paths["ranking"],
                "auto_run": False,
            }
        )
        return args

    def _prepare_network_task(self, parent_window, title, disease, output_paths, args, build_button):
        try:
            from BioRank.BioRank import BioRankCancerGeneRanking

            runner = BioRankCancerGeneRanking(**args)
            runner.prepare_network()
            runner.save_network(output_paths["network"])
        except Exception as exc:
            error_message = str(exc)
            self.root.after(
                0,
                lambda: self._finish_with_error(build_button, "Build Network", error_message),
            )
            return

        self.root.after(
            0,
            lambda: self._show_network_preview(parent_window, title, disease, output_paths, runner, build_button),
        )

    def _show_network_preview(self, parent_window, title, disease, output_paths, runner, build_button):
        summary = runner.get_network_summary()
        self.current_network_path = output_paths["network"]
        self.status_var.set(
            f"{disease} network built: {summary['nodes']} nodes, {summary['edges']} edges."
        )

        preview = tk.Toplevel(parent_window)
        preview.title(f"{title} - {disease} Built Network Preview")
        preview.geometry("980x620")
        preview.transient(parent_window)

        container = ttk.Frame(preview, padding=14)
        container.pack(fill="both", expand=True)
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        info_text = (
            f"{disease} integrated network: {summary['nodes']} vertices and "
            f"{summary['edges']} weighted directed edges."
        )
        ttk.Label(container, text=info_text, style="Section.TLabel").grid(row=0, column=0, sticky="w")

        notebook = ttk.Notebook(container)
        notebook.grid(row=1, column=0, sticky="nsew", pady=12)

        nodes_frame = ttk.Frame(notebook, padding=8)
        edges_frame = ttk.Frame(notebook, padding=8)
        notebook.add(nodes_frame, text=f"Vertices (first {PREVIEW_NODE_LIMIT})")
        notebook.add(edges_frame, text=f"Edges (first {PREVIEW_EDGE_LIMIT})")

        self._populate_nodes_table(nodes_frame, runner)
        self._populate_edges_table(edges_frame, runner)

        actions = ttk.Frame(container)
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)

        run_button = ttk.Button(actions, text="Run Algorithm", style="Primary.TButton")
        run_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            actions,
            text="Close Preview",
            command=lambda: self._cancel_preview(preview, build_button),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        def run_algorithm():
            run_button.config(state="disabled", text="Running algorithm...")
            self.status_var.set(f"Running {title} for {disease}...")
            threading.Thread(
                target=self._execute_algorithm_task,
                args=(preview, title, disease, output_paths, runner, build_button),
                daemon=True,
            ).start()

        run_button.config(command=run_algorithm)

    def _populate_nodes_table(self, frame, runner):
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        table = ttk.Treeview(frame, columns=("node",), show="headings", height=18)
        table.heading("node", text="Vertex")
        table.column("node", width=260, anchor="w")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for node in runner.iter_network_nodes(limit=PREVIEW_NODE_LIMIT):
            table.insert("", "end", values=(node,))

    def _populate_edges_table(self, frame, runner):
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        columns = ("source", "target", "weight")
        table = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        table.heading("source", text="Source")
        table.heading("target", text="Target")
        table.heading("weight", text="Weight")
        table.column("source", width=220, anchor="w")
        table.column("target", width=220, anchor="w")
        table.column("weight", width=120, anchor="e")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for source, target, weight in runner.iter_network_edges(limit=PREVIEW_EDGE_LIMIT):
            table.insert("", "end", values=(source, target, f"{weight:.8g}"))

    def _execute_algorithm_task(self, preview_window, title, disease, output_paths, runner, build_button):
        try:
            runner.execute_ranking()
        except Exception as exc:
            error_message = str(exc)
            self.root.after(
                0,
                lambda: self._finish_with_error(build_button, "Build Network", error_message),
            )
            return

        self.root.after(
            0,
            lambda: self._finish_algorithm_success(preview_window, title, disease, output_paths, runner, build_button),
        )

    def _finish_algorithm_success(self, preview_window, title, disease, output_paths, runner, build_button):
        self.current_result_path = output_paths["ranking"]
        self.current_network_path = output_paths["network"]
        build_button.config(state="normal", text="Build Network")
        runtime = runner.total_runtime_seconds or 0
        self.status_var.set(f"{title} for {disease} completed in {runtime:.2f} seconds.")
        messagebox.showinfo(
            "Done",
            f"{title} for {disease} completed.\nResult: {output_paths['ranking']}\nNetwork: {output_paths['network']}",
            parent=preview_window,
        )

    def _finish_with_error(self, build_button, button_text, error_message):
        build_button.config(state="normal", text=button_text)
        self.status_var.set("Error")
        messagebox.showerror("Error", error_message)

    def _cancel_preview(self, preview_window, build_button):
        preview_window.destroy()
        build_button.config(state="normal", text="Build Network")
        self.status_var.set("Network preview closed. Algorithm was not run.")

    def _init_preprocess_buttons(self):
        ttk.Label(
            self.right_frame,
            text="Preprocessing outputs are written to output/common/ or output/<DISEASE>/.",
            style="Hint.TLabel",
            wraplength=500,
        ).pack(anchor="w", pady=(0, 16))

        actions = [
            ("Compute Ontology Graph", self.run_ontology_graph),
            ("Compute Disease-Specific Ontologies", self.run_disease_ontologies),
            ("Create Tumor-Control Table", self.run_tcga_table),
            ("Compute DE Genes + Co-expression", self.run_de_genes_and_coexpr),
        ]
        for text, command in actions:
            ttk.Button(
                self.right_frame,
                text=text,
                style="Primary.TButton",
                command=command,
            ).pack(fill="x", pady=6)

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

    def create_input_window(self, title, inputs, process_func, output_files, disease_scoped=True):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("880x500")
        window.configure(bg=COLORS["bg"])
        window.transient(self.root)

        container = ttk.Frame(window, padding=18)
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)
        entries = {}

        disease_var = tk.StringVar(value="COAD")
        row_offset = 0
        if disease_scoped:
            ttk.Label(container, text="Cancer type").grid(row=0, column=0, sticky="w", pady=6)
            ttk.Combobox(
                container,
                textvariable=disease_var,
                values=DISEASES,
                state="readonly",
                width=12,
            ).grid(row=0, column=1, sticky="w", padx=8, pady=6)
            row_offset = 1

        for row, (label, key, is_folder) in enumerate(inputs, start=row_offset):
            ttk.Label(container, text=label).grid(row=row, column=0, sticky="w", pady=6)
            entry = ttk.Entry(container)
            entry.grid(row=row, column=1, sticky="ew", padx=8, pady=6)
            entries[key] = entry
            browse = self.browse_folder if is_folder else self.browse_file
            ttk.Button(
                container,
                text="Browse",
                command=lambda e=entry, b=browse: self._browse_and_detect_disease(e, b, window, disease_var),
            ).grid(row=row, column=2, sticky="ew", pady=6)

        hint_row = row_offset + len(inputs)
        output_hint = tk.StringVar(value="")
        ttk.Label(container, textvariable=output_hint, style="Hint.TLabel").grid(
            row=hint_row,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(8, 12),
        )

        actions = ttk.Frame(container)
        actions.grid(row=hint_row + 1, column=0, columnspan=3, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        run_button = ttk.Button(actions, text="Run", style="Primary.TButton")
        run_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="Close", command=window.destroy).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        def build_paths():
            if not output_files:
                return {}
            disease = disease_var.get() if disease_scoped else "common"
            folder = disease_output_dir(disease)
            return {key: os.path.join(folder, name.format(disease=disease)) for key, name in output_files.items()}

        def refresh_output_hint(_event=None):
            paths = build_paths()
            if paths:
                output_hint.set("Output: " + " | ".join(paths.values()))
            else:
                output_hint.set("Output folder is selected by the user in this step.")

        def run():
            files = {key: entry.get().strip() for key, entry in entries.items()}
            missing = [key for key, value in files.items() if not value]
            if missing:
                messagebox.showerror("Missing input", "Please select all required files.", parent=window)
                return

            paths = build_paths()
            run_button.config(state="disabled", text="Running...")
            self.status_var.set(f"{title} is running...")
            threading.Thread(
                target=self._run_preprocess_task,
                args=(window, title, process_func, files, paths, run_button),
                daemon=True,
            ).start()

        if disease_scoped:
            for child in container.winfo_children():
                if isinstance(child, ttk.Combobox):
                    child.bind("<<ComboboxSelected>>", refresh_output_hint)

        run_button.config(command=run)
        refresh_output_hint()

    def _run_preprocess_task(self, window, title, process_func, files, paths, run_button):
        try:
            process_func(files, paths)
        except Exception as exc:
            error_message = str(exc)
            self.root.after(
                0,
                lambda: self._finish_preprocess_error(window, run_button, error_message),
            )
            return

        self.root.after(
            0,
            lambda: self._finish_preprocess_success(window, title, paths, run_button),
        )

    def _finish_preprocess_success(self, window, title, paths, run_button):
        run_button.config(state="normal", text="Run")
        self.status_var.set(f"{title} completed.")

        saved_paths = "\n".join(paths.values()) if paths else "Output directory selected in this step."
        messagebox.showinfo("Done", f"{title} completed.\n\nSaved automatically:\n{saved_paths}", parent=window)

    def _finish_preprocess_error(self, window, run_button, error_message):
        run_button.config(state="normal", text="Run")
        self.status_var.set("Error")
        messagebox.showerror("Error", error_message, parent=window)

    def run_ontology_graph(self):
        from data_preprocessing.compute_ontology_graph import OntologyGraph

        self.create_input_window(
            "Compute Ontology Graph",
            [
                ("GO .gaf File", "go", False),
                ("KEGG File", "kegg", False),
                ("Reactome File", "reactome", False),
                ("Uniprot-Ensembl Mapping File", "uniprot", False),
                ("KEGG-Uniprot Mapping File", "keggmap", False),
            ],
            lambda f, p: OntologyGraph(
                GO_file_path=f["go"],
                KEGG_file_path=f["kegg"],
                Reactome_file_path=f["reactome"],
                output_file_path=p["ontology"],
                uniprot_mapping_path=f["uniprot"],
                kegg_mapping_path=f["keggmap"],
            ).run(),
            {"ontology": "ontology_network.tsv"},
            disease_scoped=False,
        )

    def run_disease_ontologies(self):
        from data_preprocessing.compute_disease_specific_ontologies import DiseaseOntologies

        self.create_input_window(
            "Compute Disease-Specific Ontologies",
            [
                ("Ontology Graph File", "onto", False),
                ("Seed Genes File", "seed", False),
            ],
            lambda f, p: DiseaseOntologies(
                ontology_graph_file_path=f["onto"],
                disease_seed_file_path=f["seed"],
                output_file_path=p["disease"],
            ).run(),
            {"disease": "{disease}_disease_ontologies.txt"},
        )

    def run_de_genes_and_coexpr(self):
        from data_preprocessing.compute_co_expression_and_de_genes import (
            create_de_genes,
            get_top_correlations,
        )

        self.create_input_window(
            "Compute DE Genes + Co-expression",
            [
                ("Tumor Expression Table", "tumor", False),
                ("Control Expression Table", "control", False),
                ("Identifier File", "identifier", False),
            ],
            lambda f, p: (
                create_de_genes(
                    tumor_file_path=f["tumor"],
                    control_file_path=f["control"],
                    output_file_path=p["de"],
                    threshold=2.5,
                    identifier_file_path=f["identifier"],
                ),
                get_top_correlations(
                    expression_file_path=f["tumor"],
                    output_file_path=p["coexpr"],
                    identifier_file_path=f["identifier"],
                    threshold=0.7,
                ),
            ),
            {
                "de": "{disease}_de_genes.tsv",
                "coexpr": "{disease}_co_expression_t_70.tsv",
            },
        )

    def run_tcga_table(self):
        from data_preprocessing.TCGA_analyzer import TCGAAnalyzer

        self.create_input_window(
            "Create Tumor-Control Table",
            [
                ("GDC Sample Sheet", "gdc", False),
                ("Manifest File", "manifest", False),
                ("RNA-seq Directory", "rna_dir", True),
                ("Output Directory", "output_dir", True),
            ],
            lambda f, p: TCGAAnalyzer(
                sample_sheet_file_path=f["gdc"],
                manifest_file_path=f["manifest"],
                TCGA_directory_path=f["rna_dir"],
                output_dir_path=f["output_dir"],
            ).create_tumor_control_table(),
            {},
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = BioRankGUI(root)
    root.mainloop()
