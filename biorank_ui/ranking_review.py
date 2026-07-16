import csv
import math
import os
import tkinter as tk
from tkinter import messagebox, ttk

from biorank_ui.config import (
    COLORS,
    GENE_MAPPING_PATH,
    METRIC_TOP_N,
    ONCOKB_PATH,
    RANKING_REVIEW_LIMIT,
)


def show_ranking_result_review(root, title, disease, output_paths):
    try:
        gene_mapping = _load_gene_mapping()
        oncokb_genes = _load_oncokb_genes()
        results = _load_ranked_results(output_paths["ranking"], gene_mapping, oncokb_genes)
        metrics = _calculate_ranking_metrics(results, oncokb_genes)
    except Exception as exc:
        messagebox.showerror("Result preview error", str(exc), parent=root)
        return

    review = tk.Toplevel(root)
    review.title(f"{title} - {disease} Ranking Review")
    review.geometry("1120x720")
    review.minsize(960, 600)
    review.configure(bg=COLORS["bg"])
    review.transient(root)

    container = ttk.Frame(review, padding=18)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(4, weight=1)

    header = tk.Frame(container, bg=COLORS["accent_dark"])
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)
    tk.Label(
        header,
        text=f"{disease} Ranking Review",
        bg=COLORS["accent_dark"],
        fg="#ffffff",
        font=("Segoe UI", 16, "bold"),
        anchor="w",
        padx=14,
        pady=10,
    ).grid(row=0, column=0, sticky="ew")
    tk.Label(
        header,
        text=f"{title} output: {output_paths['ranking']}",
        bg=COLORS["accent_dark"],
        fg="#dbeafe",
        font=("Segoe UI", 9),
        anchor="w",
        padx=14,
        pady=0,
    ).grid(row=1, column=0, sticky="ew")

    metrics_frame = ttk.Frame(container)
    metrics_frame.grid(row=1, column=0, sticky="ew", pady=(14, 10))
    for column in range(5):
        metrics_frame.columnconfigure(column, weight=1)

    metric_cards = [
        (f"Recall@{metrics['top_n']}", f"{metrics['recall']:.4f}", "OncoKB coverage in top results"),
        (f"nDCG@{metrics['top_n']}", f"{metrics['ndcg']:.4f}", "Position-aware hit quality"),
        ("Common genes", str(metrics["common_count"]), f"Top {metrics['top_n']} overlaps"),
        ("All hits", str(metrics["hit_count_all"]), "Across the full ranking"),
        ("Mapped genes", f"{metrics['mapped_count']}/{metrics['result_count']}", "Ensembl to gene symbol"),
    ]
    for column, (label, value, hint) in enumerate(metric_cards):
        _create_metric_card(metrics_frame, column, label, value, hint)

    controls = ttk.Frame(container)
    controls.grid(row=2, column=0, sticky="ew", pady=(2, 10))
    controls.columnconfigure(1, weight=1)

    search_var = tk.StringVar()
    hits_only_var = tk.BooleanVar(value=False)
    visible_limit_var = tk.StringVar(value=str(RANKING_REVIEW_LIMIT))

    ttk.Label(controls, text="Search gene").grid(row=0, column=0, sticky="w", padx=(0, 8))
    search_entry = ttk.Entry(controls, textvariable=search_var)
    search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))
    ttk.Checkbutton(controls, text="OncoKB hits only", variable=hits_only_var).grid(
        row=0,
        column=2,
        sticky="w",
        padx=(0, 12),
    )
    ttk.Label(controls, text="Rows").grid(row=0, column=3, sticky="e", padx=(0, 8))
    ttk.Combobox(
        controls,
        textvariable=visible_limit_var,
        values=("100", "500", "1000", "All"),
        state="readonly",
        width=8,
    ).grid(row=0, column=4, sticky="e")

    status_var = tk.StringVar()
    ttk.Label(container, textvariable=status_var, style="Hint.TLabel").grid(
        row=3,
        column=0,
        sticky="w",
        pady=(0, 6),
    )

    table_frame = ttk.Frame(container)
    table_frame.grid(row=4, column=0, sticky="nsew")
    table_frame.rowconfigure(0, weight=1)
    table_frame.columnconfigure(0, weight=1)

    columns = ("rank", "ensembl", "gene", "score", "oncokb")
    table = ttk.Treeview(table_frame, columns=columns, show="headings", height=18)
    table.heading("rank", text="#")
    table.heading("ensembl", text="Ensembl ID")
    table.heading("gene", text="Gene Symbol")
    table.heading("score", text="Score")
    table.heading("oncokb", text="OncoKB")
    table.column("rank", width=64, anchor="e", stretch=False)
    table.column("ensembl", width=190, anchor="w")
    table.column("gene", width=150, anchor="w")
    table.column("score", width=150, anchor="e")
    table.column("oncokb", width=90, anchor="center", stretch=False)
    table.tag_configure("hit", background="#dcfce7", foreground="#166534")
    table.tag_configure("plain", background="#ffffff", foreground=COLORS["text"])
    table.grid(row=0, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=0, column=1, sticky="ns")

    actions = ttk.Frame(container)
    actions.grid(row=5, column=0, sticky="ew", pady=(12, 0))
    actions.columnconfigure(0, weight=1)
    ttk.Label(
        actions,
        text=f"Reference: {ONCOKB_PATH} | Mapping: {GENE_MAPPING_PATH}",
        style="Hint.TLabel",
    ).grid(row=0, column=0, sticky="w")
    ttk.Button(actions, text="Close", command=review.destroy).grid(row=0, column=1, sticky="e")

    def parse_limit():
        value = visible_limit_var.get()
        if value == "All":
            return len(results)
        try:
            return max(1, int(value))
        except ValueError:
            return RANKING_REVIEW_LIMIT

    def refresh_table(*_args):
        query = search_var.get().strip().upper()
        hits_only = hits_only_var.get()
        limit = parse_limit()

        for item_id in table.get_children():
            table.delete(item_id)

        shown = 0
        matched_total = 0
        for item in results:
            searchable = f"{item['ensembl_id']} {item['gene_name']}".upper()
            if query and query not in searchable:
                continue
            if hits_only and not item["is_oncokb"]:
                continue

            matched_total += 1
            if shown >= limit:
                continue

            tag = "hit" if item["is_oncokb"] else "plain"
            table.insert(
                "",
                "end",
                values=(
                    item["rank"],
                    item["ensembl_id"],
                    item["gene_name"],
                    f"{item['score']:.8g}",
                    "Hit" if item["is_oncokb"] else "",
                ),
                tags=(tag,),
            )
            shown += 1

        status_var.set(
            f"Showing {shown} of {matched_total} matched rows. "
            f"Green rows are genes found in OncoKB."
        )

    search_var.trace_add("write", refresh_table)
    hits_only_var.trace_add("write", refresh_table)
    visible_limit_var.trace_add("write", refresh_table)
    refresh_table()
    search_entry.focus_set()


def _load_gene_mapping():
    mapping = {}
    if not os.path.exists(GENE_MAPPING_PATH):
        return mapping

    with open(GENE_MAPPING_PATH, newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp, delimiter="\t")
        for row in reader:
            ensembl_id = (row.get("Gene stable ID") or "").strip()
            gene_name = (row.get("Gene name") or "").strip()
            if ensembl_id and gene_name:
                mapping[ensembl_id.split(".")[0]] = gene_name
    return mapping


def _load_oncokb_genes():
    genes = set()
    if not os.path.exists(ONCOKB_PATH):
        return genes

    with open(ONCOKB_PATH, newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            gene = _normalize_gene_symbol(row.get("Gene", ""))
            if gene:
                genes.add(gene)
    return genes


def _load_ranked_results(ranking_path, gene_mapping, oncokb_genes):
    results = []
    with open(ranking_path, newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp, delimiter="\t")
        for rank, row in enumerate(reader, start=1):
            ensembl_id = (row.get("GeneNames") or row.get("name") or "").strip()
            if not ensembl_id:
                continue
            base_ensembl_id = ensembl_id.split(".")[0]
            gene_name = gene_mapping.get(base_ensembl_id, base_ensembl_id)
            normalized_gene = _normalize_gene_symbol(gene_name)
            try:
                score = float(row.get("Score") or row.get("score") or 0.0)
            except ValueError:
                score = 0.0

            results.append(
                {
                    "rank": rank,
                    "ensembl_id": ensembl_id,
                    "gene_name": gene_name,
                    "score": score,
                    "is_oncokb": normalized_gene in oncokb_genes,
                }
            )
    return results


def _calculate_ranking_metrics(results, oncokb_genes, top_n=METRIC_TOP_N):
    top_results = results[:top_n]
    common_count = sum(1 for item in top_results if item["is_oncokb"])
    recall = common_count / len(oncokb_genes) if oncokb_genes else 0.0

    dcg = 0.0
    for index in range(top_n):
        relevance = 1 if index < len(top_results) and top_results[index]["is_oncokb"] else 0
        dcg += relevance / math.log2(index + 2)

    idcg = sum(1 / math.log2(index + 2) for index in range(top_n))
    ndcg = dcg / idcg if idcg > 0 else 0.0

    return {
        "top_n": top_n,
        "common_count": common_count,
        "recall": recall,
        "ndcg": ndcg,
        "oncokb_total": len(oncokb_genes),
        "mapped_count": sum(1 for item in results if item["gene_name"] != item["ensembl_id"].split(".")[0]),
        "result_count": len(results),
        "hit_count_all": sum(1 for item in results if item["is_oncokb"]),
    }


def _normalize_gene_symbol(value):
    return value.strip().upper()


def _create_metric_card(parent, column, label, value, hint):
    card = tk.Frame(
        parent,
        bg=COLORS["panel"],
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        bd=0,
    )
    card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
    tk.Label(
        card,
        text=label,
        bg=COLORS["panel"],
        fg=COLORS["muted"],
        font=("Segoe UI", 9),
        anchor="w",
    ).pack(fill="x", padx=12, pady=(10, 0))
    tk.Label(
        card,
        text=value,
        bg=COLORS["panel"],
        fg=COLORS["accent_dark"],
        font=("Segoe UI", 18, "bold"),
        anchor="w",
    ).pack(fill="x", padx=12)
    tk.Label(
        card,
        text=hint,
        bg=COLORS["panel"],
        fg=COLORS["muted"],
        font=("Segoe UI", 8),
        anchor="w",
    ).pack(fill="x", padx=12, pady=(0, 10))
