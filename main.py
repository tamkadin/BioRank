# import tkinter as tk
# from tkinter import filedialog, messagebox, ttk
# import os
# import time
# import shutil
# import pandas as pd

# from improved_pagerank.ImprovedPageRank import ImprovedPageRankCancerGeneRanking

# class PageRankApp:
#     def __init__(self, root):
#         self.root = root
#         self.root.title("Cancer Gene Prioritization using Improved PageRank")
#         self.root.geometry("800x480")
#         self.root.resizable(False, False)
#         self.inputs = {}
#         self.last_output_path = None

#         ttk.Style().configure("TButton", padding=6, relief="flat", font=("Segoe UI", 10))
#         ttk.Style().configure("TLabel", font=("Segoe UI", 10))
#         ttk.Style().configure("TEntry", font=("Segoe UI", 10))

#         self.build_gui()

#     def build_gui(self):
#         frame = ttk.Frame(self.root, padding=15)
#         frame.pack(fill="both", expand=True)

#         label = ttk.Label(frame, text="Input Files", font=("Segoe UI", 14, "bold"))
#         label.grid(row=0, column=0, columnspan=3, pady=(0, 15), sticky="w")

#         self.create_file_input(frame, "Protein-Protein Interaction Network (-p):", "ppi", 1)
#         self.create_file_input(frame, "Co-expression Network (-c):", "coexpr", 2)
#         self.create_file_input(frame, "Seed Genes File (-s):", "seed", 3)
#         self.create_file_input(frame, "Differentially Expressed Genes (-de):", "deg", 4)
#         self.create_file_input(frame, "Gene-Ontology Mapping File (-a):", "anno", 5)
#         self.create_file_input(frame, "Disease-Specific Ontologies (-do):", "disease_onto", 6)

#         # Run button
#         self.run_button = ttk.Button(frame, text="▶ Run PageRank", command=self.run_pagerank)
#         self.run_button.grid(row=7, column=0, pady=(20, 10), sticky="w")

#         # Save button (hidden initially)
#         self.download_button = ttk.Button(frame, text="💾 Save Result As...", command=self.save_as)
#         self.download_button.grid(row=7, column=1, pady=(20, 10), sticky="e")
#         self.download_button.grid_remove()

#         # Status
#         self.status = ttk.Label(frame, text="", foreground="green")
#         self.status.grid(row=8, column=0, columnspan=3, sticky="w")

#     def create_file_input(self, parent, label_text, key, row):
#         label = ttk.Label(parent, text=label_text)
#         label.grid(row=row, column=0, sticky="w", pady=4)

#         entry = ttk.Entry(parent, width=60)
#         entry.grid(row=row, column=1, padx=5)
#         self.inputs[key] = entry

#         def browse():
#             path = filedialog.askopenfilename()
#             if path:
#                 entry.delete(0, tk.END)
#                 entry.insert(0, path)

#         button = ttk.Button(parent, text="Browse", command=browse)
#         button.grid(row=row, column=2, padx=(5, 0))

#     def run_pagerank(self):
#         try:
#             args = {
#                 "ppi_file_path": self.inputs["ppi"].get(),
#                 "co_expression_file_path": self.inputs["coexpr"].get(),
#                 "seed_file_path": self.inputs["seed"].get(),
#                 "secondary_seed_file_path": self.inputs["deg"].get(),
#                 "map__gene__ontologies_file_path": self.inputs["anno"].get(),
#                 "disease_ontology_file_path": self.inputs["disease_onto"].get(),
#                 "matrix_aggregation_policy": "convex_combination",
#                 "personalization_vector_creation_policies": ["topological", "biological"],
#                 "personalization_vector_aggregation_policy": "Sum",
#                 "restart_prob": 0.9,
#                 "alpha": 0.5,
#                 "beta": 0.5,
#                 "network_weight_flag": True
#             }

#             os.makedirs("output", exist_ok=True)
#             output_path = "output/LATEST_RESULT.csv"
#             args["output_file_path"] = output_path
#             self.last_output_path = output_path

#             for key, val in args.items():
#                 if key.endswith("_file_path") and (not val or not os.path.exists(val)):
#                     raise ValueError(f"File not found or missing:\n{val}")

#             self.status.config(text="⏳ Running PageRank...", foreground="blue")
#             self.download_button.grid_remove()
#             self.root.update()

#             start = time.perf_counter()
#             model = ImprovedPageRankCancerGeneRanking(**args)
#             runtime = time.perf_counter() - start

#             self.status.config(text=f"✅ Completed in {runtime:.2f} seconds", foreground="green")
#             self.download_button.grid()
#             self.show_results(output_path)

#         except Exception as e:
#             import traceback
#             traceback.print_exc()
#             self.status.config(text=f"❌ Error: {e}", foreground="red")
#             messagebox.showerror("Error", str(e))

#     def show_results(self, filepath):
#         try:
#             df = pd.read_csv(filepath, sep="\t")
#             result_window = tk.Toplevel(self.root)
#             result_window.title("PageRank Result")

#             text = tk.Text(result_window, wrap="none", height=25, width=80)
#             text.pack(expand=True, fill="both", padx=10, pady=10)
#             text.insert("end", df.to_string(index=False))
#         except Exception as e:
#             messagebox.showerror("Display Error", f"Could not load result: {e}")

#     def save_as(self):
#         if not self.last_output_path or not os.path.exists(self.last_output_path):
#             messagebox.showerror("No result", "No result file found.")
#             return

#         path = filedialog.asksaveasfilename(defaultextension=".csv")
#         if path:
#             try:
#                 shutil.copyfile(self.last_output_path, path)
#                 messagebox.showinfo("Saved", f"✅ File saved to:\n{path}")
#             except Exception as e:
#                 messagebox.showerror("Save Error", f"Could not save file:\n{e}")

# if __name__ == "__main__":
#     root = tk.Tk()
#     app = PageRankApp(root)
#     root.mainloop()