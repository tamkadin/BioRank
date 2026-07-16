import glob
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from biorank_ui.config import DATASET_DIR
from biorank_ui.theme import (
    APP_BG,
    BORDER,
    CARD_BG,
    DEEP_BLUE,
    FONT_FAMILY_BODY,
    FONT_FAMILY_HEADER,
    PRIMARY,
    SOFT_BLUE,
    STATUS_ERROR,
    TEXT_MAIN,
    TEXT_MUTED,
)


TEXT_FILE_TYPES = [("Tab/text files", ("*.tsv", "*.txt", "*.csv")), ("All files", "*")]


def build_preprocessing_dialog_config(step_index, disease, file_paths, data_dir=DATASET_DIR):
    data_dir = os.path.abspath(data_dir)
    configs = {
        1: {
            "title": "Step 1: Compute Ontology Graph",
            "description": "Select five annotation/mapping inputs and the ontology graph output.",
            "fields": [
                _field("go_file_path", "GO annotation (.gaf)", "input_file", filetypes=[("GO annotation", "*.gaf"), ("All files", "*")]),
                _field("kegg_file_path", "KEGG annotation", "input_file"),
                _field("reactome_file_path", "Reactome mapping", "input_file"),
                _field("uniprot_mapping_path", "UniProt-Ensembl mapping", "input_file"),
                _field("kegg_mapping_path", "KEGG-UniProt mapping", "input_file"),
                _field(
                    "output_file_path",
                    "Ontology graph output",
                    "output_file",
                    os.path.join(data_dir, "ontology_network", "ontology_network.tsv"),
                ),
            ],
        },
        2: {
            "title": f"Step 2: Disease-Specific Ontologies ({disease})",
            "description": "Review the detected ontology and seed files, then choose the enrichment output.",
            "fields": [
                _field("ontology_file_path", "Ontology graph", "input_file", file_paths.get("ontology_map", "")),
                _field("seed_file_path", f"Seed genes ({disease})", "input_file", file_paths.get("seed", "")),
                _field(
                    "output_file_path",
                    "Disease ontology output",
                    "output_file",
                    os.path.join(data_dir, "disease_specific_ontologies", f"TCGA-{disease}_disease_ontologies.txt"),
                    extension=".txt",
                ),
            ],
        },
        3: {
            "title": "Step 3: Create Tumor-Control Tables",
            "description": "Select GDC metadata, the downloaded RNA-seq folder, and an output folder.",
            "fields": [
                _field(
                    "sample_sheet_file_path",
                    "GDC sample sheet",
                    "input_file",
                    _first_match(os.path.join(data_dir, "TCGA", "*sample_sheet*.tsv")),
                ),
                _field(
                    "manifest_file_path",
                    "GDC manifest",
                    "input_file",
                    _first_match(os.path.join(data_dir, "TCGA", "*manifest*.txt")),
                ),
                _field("tcga_directory_path", "Downloaded GDC RNA-seq folder", "input_dir"),
                _field("output_dir_path", "Tumor/control output folder", "output_dir"),
            ],
        },
        4: {
            "title": f"Step 4: DE Genes and Co-expression ({disease})",
            "description": "Select tumor/control matrices and identifier list, then review both output files.",
            "fields": [
                _field("tumor_file_path", "Tumor expression table", "input_file"),
                _field("control_file_path", "Control table (TCGA or GTEx GCT)", "input_file"),
                _field(
                    "identifier_file_path",
                    "Identifier list",
                    "input_file",
                    os.path.join(data_dir, "ppi_network", "HIPPIE_node_list.txt"),
                ),
                _field(
                    "de_output_file_path",
                    "DE genes output",
                    "output_file",
                    os.path.join(data_dir, "differentially_expressed_genes", f"TCGA-{disease}_de_genes.tsv"),
                ),
                _field(
                    "coexpression_output_file_path",
                    "Co-expression output",
                    "output_file",
                    os.path.join(data_dir, "co-expression_networks", f"TCGA-{disease}_co_expression_t_70.tsv"),
                ),
            ],
        },
    }
    if step_index not in configs:
        raise ValueError(f"Unknown preprocessing step: {step_index}")
    return configs[step_index]


def _field(key, label, kind, default="", filetypes=None, extension=".tsv"):
    return {
        "key": key,
        "label": label,
        "kind": kind,
        "default": os.path.abspath(default) if default else "",
        "filetypes": filetypes or TEXT_FILE_TYPES,
        "extension": extension,
    }


def _first_match(pattern):
    matches = sorted(glob.glob(pattern))
    return matches[0] if matches else ""


class PreprocessingInputDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        step_index,
        disease,
        file_paths,
        submit_callback,
        initial_values=None,
        back_callback=None,
    ):
        super().__init__(master)
        self.submit_callback = submit_callback
        self.back_callback = back_callback
        self.initial_values = initial_values or {}
        self.config_data = build_preprocessing_dialog_config(step_index, disease, file_paths)
        self.entries = {}

        self.title(self.config_data["title"])
        self.geometry("900x560")
        self.minsize(760, 460)
        self.configure(fg_color=APP_BG)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._go_back)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_fields()
        self._build_actions()
        self.after(20, self._activate_modal)

    def _activate_modal(self):
        self.grab_set()
        self.focus_force()
        self._center_on_parent()

    def _center_on_parent(self):
        self.update_idletasks()
        parent = self.master
        x = parent.winfo_rootx() + max((parent.winfo_width() - self.winfo_width()) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - self.winfo_height()) // 2, 0)
        self.geometry(f"+{x}+{y}")

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=DEEP_BLUE, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            header,
            text=self.config_data["title"],
            font=(FONT_FAMILY_HEADER, 20, "bold"),
            text_color="#FFFFFF",
            anchor="w",
        ).pack(fill="x", padx=24, pady=(20, 4))
        ctk.CTkLabel(
            header,
            text=self.config_data["description"],
            font=(FONT_FAMILY_BODY, 13),
            text_color="#DCEBFA",
            anchor="w",
        ).pack(fill="x", padx=24, pady=(0, 20))

    def _build_fields(self):
        form = ctk.CTkScrollableFrame(self, fg_color=CARD_BG, corner_radius=8, border_color=BORDER, border_width=1)
        form.grid(row=1, column=0, padx=24, pady=20, sticky="nsew")
        form.grid_columnconfigure(1, weight=1)

        for row, field in enumerate(self.config_data["fields"]):
            ctk.CTkLabel(
                form,
                text=field["label"],
                font=(FONT_FAMILY_HEADER, 13, "bold"),
                text_color=TEXT_MAIN,
                anchor="w",
            ).grid(row=row, column=0, padx=(16, 12), pady=10, sticky="w")

            entry = ctk.CTkEntry(
                form,
                font=(FONT_FAMILY_BODY, 13),
                fg_color=APP_BG,
                text_color=TEXT_MAIN,
                border_color=BORDER,
                height=38,
            )
            entry.grid(row=row, column=1, padx=0, pady=10, sticky="ew")
            initial_value = self.initial_values.get(field["key"], field["default"])
            if initial_value:
                entry.insert(0, initial_value)
            self.entries[field["key"]] = entry

            ctk.CTkButton(
                form,
                text="Browse",
                font=(FONT_FAMILY_HEADER, 12, "bold"),
                fg_color=SOFT_BLUE,
                text_color=PRIMARY,
                hover_color=BORDER,
                width=92,
                height=36,
                command=lambda item=field: self._browse(item),
            ).grid(row=row, column=2, padx=16, pady=10)

    def _build_actions(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, padx=24, pady=(0, 20), sticky="ew")

        self.error_label = ctk.CTkLabel(
            footer,
            text="",
            font=(FONT_FAMILY_BODY, 12),
            text_color=STATUS_ERROR,
            anchor="w",
        )
        self.error_label.pack(side="left", fill="x", expand=True)

        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.pack(side="right")
        ctk.CTkButton(
            actions,
            text="< Back",
            font=(FONT_FAMILY_HEADER, 13, "bold"),
            fg_color=SOFT_BLUE,
            text_color=PRIMARY,
            hover_color=BORDER,
            width=110,
            height=40,
            command=self._go_back,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            actions,
            text="Run Step",
            font=(FONT_FAMILY_HEADER, 13, "bold"),
            fg_color=PRIMARY,
            hover_color=DEEP_BLUE,
            text_color="#FFFFFF",
            width=130,
            height=40,
            command=self._submit,
        ).pack(side="left")

    def _browse(self, field):
        current = self.entries[field["key"]].get().strip()
        initial_dir = self._existing_directory(current)
        kind = field["kind"]
        if kind == "input_file":
            selected = filedialog.askopenfilename(
                parent=self,
                title=f"Select {field['label']}",
                initialdir=initial_dir,
                filetypes=field["filetypes"],
            )
        elif kind == "output_file":
            selected = filedialog.asksaveasfilename(
                parent=self,
                title=f"Save {field['label']}",
                initialdir=initial_dir,
                initialfile=os.path.basename(current) if current else "",
                defaultextension=field["extension"],
                filetypes=field["filetypes"],
                confirmoverwrite=False,
            )
        else:
            selected = filedialog.askdirectory(
                parent=self,
                title=f"Select {field['label']}",
                initialdir=initial_dir,
                mustexist=(kind == "input_dir"),
            )
        if selected:
            entry = self.entries[field["key"]]
            entry.delete(0, "end")
            entry.insert(0, selected)
            self.error_label.configure(text="")

    def _submit(self):
        values = {key: entry.get().strip() for key, entry in self.entries.items()}
        error = self._validate(values)
        if error:
            self.error_label.configure(text=error)
            return

        existing_outputs = [
            values[field["key"]]
            for field in self.config_data["fields"]
            if field["kind"] == "output_file" and os.path.isfile(values[field["key"]])
        ]
        if existing_outputs and not messagebox.askyesno(
            "Replace existing output?",
            "The selected output file already exists and will be replaced. Continue?",
            parent=self,
        ):
            return

        self.grab_release()
        self.destroy()
        self.submit_callback(values)

    def _validate(self, values):
        for field in self.config_data["fields"]:
            path = values[field["key"]]
            if not path:
                return f"Choose a path for: {field['label']}"
            if field["kind"] == "input_file" and not os.path.isfile(path):
                return f"Input file does not exist: {field['label']}"
            if field["kind"] == "input_dir" and not os.path.isdir(path):
                return f"Input folder does not exist: {field['label']}"
        return ""

    @staticmethod
    def _existing_directory(path):
        candidate = path if os.path.isdir(path) else os.path.dirname(path)
        while candidate and not os.path.isdir(candidate):
            parent = os.path.dirname(candidate)
            if parent == candidate:
                break
            candidate = parent
        return candidate if candidate and os.path.isdir(candidate) else os.getcwd()

    def _go_back(self):
        if self.back_callback:
            self.back_callback({key: entry.get().strip() for key, entry in self.entries.items()})
        if self.grab_current() == self:
            self.grab_release()
        self.destroy()
