import csv
import numpy as np
import math

def __load_df__(file_path, Identifiers):
    map__ensembl_id__gene_expression = {}
    with open(file_path, "r") as f:
        csv_reader = csv.reader(f, delimiter="\t")
        for index, row in enumerate(csv_reader):
            if index == 0:
                continue
            ensembl_id = row[0].split(".")[0]
            if ensembl_id in map__ensembl_id__gene_expression:
                continue
            if ensembl_id not in Identifiers:
                continue
            values = [float(v) for v in row[1:]]
            map__ensembl_id__gene_expression[ensembl_id] = np.array(values)
    return map__ensembl_id__gene_expression

def __load_identifier__(file_path):
    with open(file_path, "r") as f:
        return {row[0] for row in csv.reader(f, delimiter="\t")}

def create_de_genes(
    tumor_file_path,
    control_file_path,
    output_file_path,
    threshold=2.5,
    identifier_file_path=None
):
    if identifier_file_path is None:
        raise ValueError("Identifier file path must be provided.")

    identifiers = __load_identifier__(identifier_file_path)
    tumor_df = __load_df__(tumor_file_path, identifiers)
    control_df = __load_df__(control_file_path, identifiers)

    intersection = list(set(tumor_df) & set(control_df))
    table = []
    sum_vector = []

    for gene in intersection:
        tumor_vals = tumor_df[gene]
        control_vals = control_df[gene]
        mean = np.mean(control_vals)
        std = np.std(control_vals)

        if std != 0.0:
            log_z_scores = np.log(np.abs((tumor_vals - mean) / std))
            flag = np.where(log_z_scores > threshold, 1, 0)
            count = np.sum(flag)
            if count > 0:
                sum_vector.append(count)
                table.append([gene, count])

    table.sort(key=lambda x: x[1], reverse=True)
    mean_count = np.mean(sum_vector)
    filtered_table = [record for record in table if record[1] > mean_count]

    with open(output_file_path, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerows(filtered_table)

def __np_pearson_cor__(x, y):
    xv = x - x.mean(axis=0)
    yv = y - y.mean(axis=0)
    xvss = (xv * xv).sum(axis=0)
    yvss = (yv * yv).sum(axis=0)
    result = np.matmul(xv.transpose(), yv) / np.sqrt(np.outer(xvss, yvss))
    return np.clip(result[0][0], -1.0, 1.0)

def get_top_correlations(
    expression_file_path,
    output_file_path,
    identifier_file_path,
    threshold=0.7
):
    identifiers = __load_identifier__(identifier_file_path)
    df = __load_df__(expression_file_path, identifiers)
    gene_list = list(df.keys())

    co_expr_list = []
    print("🔍 Computing Pearson correlation...")

    for i in range(len(gene_list)):
        for j in range(i + 1, len(gene_list)):
            v1 = df[gene_list[i]]
            v2 = df[gene_list[j]]
            pcc = __np_pearson_cor__(v1, v2)
            if not math.isnan(pcc) and pcc > threshold:
                co_expr_list.append([gene_list[i], gene_list[j], abs(pcc)])

    with open(output_file_path, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["u", "v", "score"])
        writer.writerows(co_expr_list)
    print(f"✅ Co-expression network saved: {output_file_path}")
