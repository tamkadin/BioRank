import csv
import math


def normalize_gene_symbol(value):
    return str(value or "").strip().upper()


def load_gene_mapping(mapping_file_path):
    mapping = {}
    if not mapping_file_path:
        return mapping

    with open(mapping_file_path, newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp, delimiter="\t")
        for row in reader:
            ensembl_id = (row.get("Gene stable ID") or "").strip()
            gene_name = (row.get("Gene name") or "").strip()
            if ensembl_id and gene_name:
                mapping[ensembl_id.split(".")[0]] = gene_name
    return mapping


def load_truth_genes(validation_file_path, gene_column="Gene"):
    truth_genes = set()
    with open(validation_file_path, newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        if gene_column not in (reader.fieldnames or []):
            raise ValueError(f"Validation file does not contain column {gene_column}.")
        for row in reader:
            gene = normalize_gene_symbol(row.get(gene_column))
            if gene:
                truth_genes.add(gene)
    return truth_genes


def load_ranked_genes_from_tsv(ranking_path):
    ranked = []
    with open(ranking_path, newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp, delimiter="\t")
        for row in reader:
            gene = (row.get("GeneNames") or row.get("name") or "").strip()
            if gene:
                ranked.append(gene)
    return ranked


def map_ranked_genes_to_symbols(ranked_genes, gene_mapping):
    mapped = []
    mapped_count = 0
    for gene in ranked_genes:
        base_gene = gene.split(".")[0]
        gene_name = gene_mapping.get(base_gene, base_gene)
        if gene_name != base_gene:
            mapped_count += 1
        mapped.append(gene_name)
    return mapped, mapped_count


def recall_at_k(ranked_genes, truth_genes, k):
    truth = {normalize_gene_symbol(gene) for gene in truth_genes if gene}
    if not truth:
        return 0.0
    top = {normalize_gene_symbol(gene) for gene in ranked_genes[:k]}
    return len(top.intersection(truth)) / len(truth)


def precision_at_k(ranked_genes, truth_genes, k):
    if k <= 0:
        return 0.0
    truth = {normalize_gene_symbol(gene) for gene in truth_genes if gene}
    top = [normalize_gene_symbol(gene) for gene in ranked_genes[:k]]
    return sum(1 for gene in top if gene in truth) / k


def ndcg_at_k(ranked_genes, truth_genes, k):
    truth = {normalize_gene_symbol(gene) for gene in truth_genes if gene}
    if not truth or k <= 0:
        return 0.0

    dcg = 0.0
    for index, gene in enumerate(ranked_genes[:k]):
        relevance = 1.0 if normalize_gene_symbol(gene) in truth else 0.0
        dcg += relevance / math.log2(index + 2)

    ideal_hits = min(len(truth), k)
    idcg = sum(1.0 / math.log2(index + 2) for index in range(ideal_hits))
    return dcg / idcg if idcg > 0.0 else 0.0


def source_balance(alpha, beta):
    alpha_balance = 1.0 - abs(alpha - 0.5) / 0.5
    beta_balance = 1.0 - abs(beta - 0.5) / 0.5
    return max(0.0, (alpha_balance + beta_balance) / 2.0)


def selection_score(recall, ndcg, precision, balance, prefer_balanced=False):
    if prefer_balanced:
        return 0.40 * recall + 0.40 * ndcg + 0.10 * precision + 0.10 * balance
    return 0.45 * recall + 0.45 * ndcg + 0.10 * precision


def optuna_display_score(recall_at_15, ndcg_at_15, recall_at_100, ndcg_at_100):
    return 0.25 * recall_at_15 + 0.25 * ndcg_at_15 + 0.25 * recall_at_100 + 0.25 * ndcg_at_100


def evaluate_ranking_against_oncokb(
    ranked_genes,
    truth_genes,
    gene_mapping=None,
    recall_k=100,
    ndcg_k=100,
    precision_k=15,
):
    mapped_genes, mapped_count = map_ranked_genes_to_symbols(ranked_genes, gene_mapping or {})
    truth = {normalize_gene_symbol(gene) for gene in truth_genes if gene}
    common_top = sum(1 for gene in mapped_genes[:recall_k] if normalize_gene_symbol(gene) in truth)
    all_hits = sum(1 for gene in mapped_genes if normalize_gene_symbol(gene) in truth)

    return {
        "recall": recall_at_k(mapped_genes, truth, recall_k),
        "ndcg": ndcg_at_k(mapped_genes, truth, ndcg_k),
        "precision": precision_at_k(mapped_genes, truth, precision_k),
        "common_genes": common_top,
        "all_hits": all_hits,
        "mapped_genes": mapped_count,
    }
