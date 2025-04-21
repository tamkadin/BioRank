# import pandas as pd

# # Đọc dữ liệu từ các file CSV A, A1, A2 và file CSV B
# file_A_path = r"C:\Users\ASUS\OneDrive - Hanoi University of Science and Technology\Documents\2024.1\Research Bio\Compare result Pagerank\THCA_BRWR.csv"
# file_A1_path = r"C:\Users\ASUS\OneDrive - Hanoi University of Science and Technology\Documents\2024.1\Research Bio\Compare result Pagerank\THCA_PR_goc.csv"
# file_A2_path = r"C:\Users\ASUS\OneDrive - Hanoi University of Science and Technology\Documents\2024.1\Research Bio\Compare result Pagerank\THCA_PR_caitien.csv"
# file_B_path = r"C:\Users\ASUS\OneDrive - Hanoi University of Science and Technology\Documents\2024.1\Research Bio\Compare result Pagerank\Onco_KB_THCA.csv"

# # Đọc các file A, A1, A2 và B
# df_A = pd.read_csv(file_A_path)
# df_A1 = pd.read_csv(file_A1_path)
# df_A2 = pd.read_csv(file_A2_path)
# df_B = pd.read_csv(file_B_path)

# # Hàm để tính recall và số lượng gene trùng
# def calculate_recall_and_common(df, df_B, top_n=100):
#     # Lấy top n giá trị của cột 'name' từ file A
#     top_n_names = df['name'].head(top_n)
    
#     # Chuyển cột 'Gene' trong file B thành set để tra cứu nhanh
#     gene_set_B = set(df_B['Gene'])
    
#     # Kiểm tra xem có bao nhiêu name trong top n có mặt trong file B
#     common_genes = top_n_names[top_n_names.isin(gene_set_B)]
    
#     # Tính toán Recall@top_n
#     recall_at_n = len(common_genes) / len(gene_set_B)
    
#     # Trả về kết quả
#     return recall_at_n, len(common_genes)

# # Tính recall và số lượng gene trùng cho 3 file A, A1, A2
# recall_A, common_A = calculate_recall_and_common(df_A, df_B)
# recall_A1, common_A1 = calculate_recall_and_common(df_A1, df_B)
# recall_A2, common_A2 = calculate_recall_and_common(df_A2, df_B)

# # In kết quả
# print(f"Recall@100 for THCA with PR_Goc: {recall_A1:.4f}, Số lượng gene trùng: {common_A1}")
# print(f"Recall@100 for THCA with BRWR: {recall_A:.4f}, Số lượng gene trùng: {common_A}")
# print(f"Recall@100 for THCA with PR_Caitien: {recall_A2:.4f}, Số lượng gene trùng: {common_A2}")
import pandas as pd
import numpy as np

# Đọc dữ liệu từ các file CSV A, A1, A2 và file CSV B
file_A_path = r"C:\Users\ASUS\OneDrive - Hanoi University of Science and Technology\Documents\2024.1\Research Bio\Compare result Pagerank\THCA_BRWR.csv"
file_A1_path = r"C:\Users\ASUS\OneDrive - Hanoi University of Science and Technology\Documents\2024.1\Research Bio\Compare result Pagerank\THCA_PR_goc.csv"
file_A2_path = r"C:\Users\ASUS\OneDrive - Hanoi University of Science and Technology\Documents\2024.1\Research Bio\Compare result Pagerank\THCA_PR_caitien.csv"
file_B_path = r"C:\Users\ASUS\OneDrive - Hanoi University of Science and Technology\Documents\2024.1\Research Bio\Compare result Pagerank\Onco_KB.csv"

# Đọc các file A, A1, A2 và B
df_A = pd.read_csv(file_A_path)
df_A1 = pd.read_csv(file_A1_path)
df_A2 = pd.read_csv(file_A2_path)
df_B = pd.read_csv(file_B_path)

# Hàm để tính recall và số lượng gene trùng
def calculate_recall_and_common(df, df_B, top_n=100):
    # Lấy top n giá trị của cột 'name' từ file A
    top_n_names = df['name'].head(top_n)
    
    # Chuyển cột 'Gene' trong file B thành set để tra cứu nhanh
    gene_set_B = set(df_B['Gene'])
    
    # Kiểm tra xem có bao nhiêu name trong top n có mặt trong file B
    common_genes = top_n_names[top_n_names.isin(gene_set_B)]
    
    # Tính toán Recall@top_n
    recall_at_n = len(common_genes) / len(gene_set_B)
    
    # Trả về kết quả
    return recall_at_n, len(common_genes), top_n_names, gene_set_B

# Hàm tính DCG và nDCG
def calculate_ndcg(top_n_names, gene_set_B, top_n=100):
    # Tạo list rel (1 nếu gen đúng, 0 nếu gen sai)
    rel = [1 if name in gene_set_B else 0 for name in top_n_names]
    
    # Tính DCG
    dcg = sum([rel[i] / np.log2(i + 2) for i in range(top_n)])  # +2 vì log2(1+1) là phần đầu tiên
    # Tính IDCG (đúng ở đầu tiên sẽ có giá trị tối đa là 1)
    idcg = sum([1 / np.log2(i + 2) for i in range(top_n)])
    
    # Tính nDCG
    ndcg = dcg / idcg if idcg > 0 else 0
    
    return ndcg

# Tính recall, số lượng gene trùng và nDCG cho 3 file A, A1, A2
recall_A, common_A, top_n_names_A, gene_set_B = calculate_recall_and_common(df_A, df_B)
recall_A1, common_A1, top_n_names_A1, _ = calculate_recall_and_common(df_A1, df_B)
recall_A2, common_A2, top_n_names_A2, _ = calculate_recall_and_common(df_A2, df_B)

# Tính nDCG cho 3 file A, A1, A2
ndcg_A = calculate_ndcg(top_n_names_A, gene_set_B)
ndcg_A1 = calculate_ndcg(top_n_names_A1, gene_set_B)
ndcg_A2 = calculate_ndcg(top_n_names_A2, gene_set_B)

# In kết quả
print(f"Recall@100 for THCA with PR_Goc: {recall_A1:.4f}, Số lượng gene trùng: {common_A1}, nDCG@100: {ndcg_A1:\ư0863.4f}")
print(f"Recall@100 for THCA with BRWR: {recall_A:.4f}, Số lượng gene trùng: {common_A}, nDCG@100: {ndcg_A:.4f}")
print(f"Recall@100 for THCA with PR_Caitien: {recall_A2:.4f}, Số lượng gene trùng: {common_A2}, nDCG@100: {ndcg_A2:.4f}")
