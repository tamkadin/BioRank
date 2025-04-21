import pandas as pd

# Đọc dữ liệu từ file TSV (tách cột bằng tab) và bỏ qua các dòng bị lỗi
file_path = r"C:\Users\ASUS\OneDrive - Hanoi University of Science and Technology\Documents\2024.1\Research Bio\Compare result Pagerank\cancerGeneList.tsv"

try:
    # Đọc file với dấu tab là phân tách, bỏ qua các dòng có lỗi
    df = pd.read_csv(file_path, sep='\t', on_bad_lines='skip')  # Bỏ qua các dòng bị lỗi
except pd.errors.ParserError as e:
    print(f"Lỗi khi đọc file: {e}")
    exit()
print(df.columns)
# Giữ lại cột 'Gene' và loại bỏ các giá trị trùng lặp
df_filtered = df[['Hugo Symbol']].drop_duplicates()

# Xuất kết quả ra file CSV mới
output_path = r"C:\Users\ASUS\OneDrive - Hanoi University of Science and Technology\Documents\2024.1\Research Bio\Compare result Pagerank\Onco_KB.csv"
df_filtered.to_csv(output_path, index=False)

print(f"✅ Đã lưu kết quả vào file: {output_path}")
