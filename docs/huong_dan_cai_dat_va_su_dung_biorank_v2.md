# User Manual

BioRank v2: Cancer Gene Prioritization Workspace

Huu-Tam Nguyen, Duc-Tinh Pham, Van-Hai Pham

## Table of Contents

1. [Overview](#1-overview)
2. [Installation and Launch](#2-installation-and-launch)
3. [Dataset Information](#3-dataset-information)
4. [Interface](#4-interface)
5. [Data Preprocessing Workflow](#5-data-preprocessing-workflow)
6. [Running Gene Ranking](#6-running-gene-ranking)
7. [Parameter Optimization](#7-parameter-optimization)
8. [Output and Export](#8-output-and-export)
9. [Troubleshooting](#9-troubleshooting)

## 1. Overview

BioRank v2 là ứng dụng desktop hỗ trợ ưu tiên gen liên quan ung thư bằng cách tích hợp nhiều nguồn dữ liệu sinh học, gồm PPI network, co-expression network, seed genes, DE genes, ontology annotations và disease-specific ontologies.

Người dùng làm việc trực tiếp trên giao diện `BioRank: Cancer Gene Prioritization Workspace`. Trong một workflow thông thường, người dùng sẽ:

1. Chuẩn bị thư mục `data_set/`.
2. Mở BioRank v2.
3. Chọn cancer type và seed profile.
4. Kiểm tra các input đang `Ready`.
5. Build integrated network.
6. Chạy thuật toán ranking hoặc Optuna optimization.
7. Xem và lấy file kết quả trong `output/`.

BioRank v2 hỗ trợ các disease code:

```text
BLCA, BRCA, COAD, LUAD, PRAD, STAD, THCA
```

Các thuật toán ranking trong BioRank v2:

- `Original PageRank`
- `BRWR Lite`
- `BRWR`
- `BioRank Lite`
- `BioRank`

## 2. Installation and Launch

BioRank v2 có 2 cách chạy. Người dùng chọn một trong hai cách tùy vào việc có muốn cài Python hay chỉ muốn mở bản đã đóng gói.

### Option 1. Run from `main.py`

Cách này dùng khi người dùng có source code và có thể cài Python dependencies.

#### Step 1. Mở thư mục project

Nếu clone từ GitHub:

```powershell
cd "C:\path\to\workspace"
git clone https://github.com/tamkadin/BioRank.git
cd BioRank
```

Nếu đã có sẵn source code, mở terminal tại thư mục chứa `main.py`:

```text
BioRank/
  main.py
  requirements.txt
  BioRank/
  biorank_ui/
  data_preprocessing/
  docs/
```

#### Step 2. Tạo Python environment

Khuyến nghị dùng Python 3.10 trở lên.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Nếu PowerShell không cho activate environment:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

#### Step 3. Cài dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

#### Step 4. Đặt dataset

Đặt thư mục `data_set/` cạnh file `main.py`:

```text
BioRank/
  main.py
  data_set/
```

Kiểm tra nhanh:

```powershell
Test-Path .\data_set
Test-Path .\data_set\ppi_network\HIPPIE.tsv
```

Nếu cả hai lệnh trả về `True`, dataset đã ở đúng vị trí cơ bản.

#### Step 5. Launch BioRank v2

```powershell
python main.py
```

Sau khi chạy, cửa sổ `BioRank: Cancer Gene Prioritization Workspace` sẽ mở lên.

> **[PLACEHOLDER HÌNH 01]** Chèn ảnh màn hình chính BioRank v2 sau khi launch thành công.

### Option 2. Run Packaged Version

Cách này dùng khi người dùng nhận sẵn bản đóng gói, không cần cài Python hoặc dependencies.

#### Step 1. Giải nén ứng dụng

Nếu nhận file `.zip`, giải nén toàn bộ trước khi chạy. Không mở trực tiếp trong file zip.

Cấu trúc thường gặp:

```text
BioRank/
  BioRank.exe
  _internal/
```

Người dùng cần giữ nguyên cả thư mục `BioRank/`. Không copy riêng file `BioRank.exe` ra nơi khác.

#### Step 2. Đặt ứng dụng ở thư mục có quyền ghi

Khuyến nghị:

```text
C:\BioRank_v2\
```

Không nên đặt trong:

```text
C:\Program Files\
C:\Windows\
```

BioRank cần quyền ghi để tạo thư mục `output/`.

#### Step 3. Đặt dataset cho bản đóng gói

Với bản PyInstaller `--onedir` hiện tại, dataset thường được auto-detect tại:

```text
BioRank/
  BioRank.exe
  _internal/
    data_set/
```

Nếu bản đóng gói được cấu hình để đọc dataset cạnh file `.exe`, cấu trúc có thể là:

```text
BioRank/
  BioRank.exe
  data_set/
  _internal/
```

Nếu không chắc vị trí nào đúng, người dùng mở app, vào `Input Data Readiness`, chọn cancer type và kiểm tra các input. Nếu các input hiện `Ready`, thư mục dữ liệu đã được nhận diện. Nếu hiện `Missing`, dùng nút browse để chọn file thủ công.

#### Step 4. Launch BioRank v2

Double-click:

```text
BioRank.exe
```

Nếu Windows SmartScreen hiện cảnh báo, chỉ chọn `More info` -> `Run anyway` khi chắc chắn file đến từ nguồn đáng tin cậy.

## 3. Dataset Information

BioRank v2 cần thư mục `data_set/`. Full dataset có thể tải tại:

```text
https://drive.google.com/drive/folders/11TY1KGRpxG2VzStKO1rb5NjBtcNClysP?usp=sharing
```

Sau khi tải và giải nén, tên thư mục được khuyến nghị là:

```text
data_set
```

App ưu tiên thư mục `data_set/` cạnh `main.py`. Nếu thư mục này đã đổi tên,
app có thể tự nhận diện một thư mục con duy nhất có cấu trúc BioRank, chẳng hạn
có `ppi_network/`, `seed_set/` và `ontology_network/`. Với dữ liệu nằm ở vị trí
khác, đặt biến môi trường `BIORANK_DATA_DIR` thành đường dẫn tuyệt đối hoặc
đường dẫn tương đối từ thư mục repo trước khi mở app.

### Required Files

BioRank v2 auto-detect các input chính theo disease code:

```text
data_set/ppi_network/HIPPIE.tsv
data_set/co-expression_networks/TCGA-<DISEASE>*co_expression*.tsv
data_set/seed_set/TCGA-<DISEASE>*_seed.txt
data_set/seed_set/TCGA-<DISEASE>*_seed.tsv
data_set/differentially_expressed_genes/TCGA-<DISEASE>*de_genes.tsv
data_set/ontology_network/ontology_network.tsv
data_set/disease_specific_ontologies/TCGA-<DISEASE>*disease_ontologies.txt
data_set/mart_biotool.txt
data_set/Onco_KB.csv
data_set/Onco_KB_<DISEASE>.csv
data_set/Onco_KB <DISEASE>.csv
```

### Seed Profiles

BioRank v2 có 2 seed profile trong thanh trên cùng:

- `Original`: dùng seed genes và disease ontology gốc.
- `Enriched`: dùng bộ seed đã làm giàu và disease ontology tương ứng.

Với profile `Enriched`, cần thêm:

```text
data_set/seed_set/New/TCGA-<DISEASE>_seed.txt
data_set/disease_specific_ontologies/TCGA-<DISEASE>_disease_ontologies_new_22_6.txt
```

> **[PLACEHOLDER HÌNH 02]** Chèn ảnh dropdown `Seed profile` trong header, hiển thị hai lựa chọn `Original` và `Enriched`.

### Evaluation Data

BioRank v2 có 2 lựa chọn validation set:

- `Pan-cancer OncoKB`: dùng file chung cho tất cả disease.
- `Cancer-specific OncoKB`: dùng file đánh giá riêng theo disease đang chọn.

File chung:

```text
data_set/Onco_KB.csv
```

File riêng theo disease được auto-detect theo thứ tự:

```text
data_set/Onco_KB_<DISEASE>.csv
data_set/Onco_KB <DISEASE>.csv
data_set/seed_set/New/Onco_KB_<DISEASE>.csv
data_set/seed_set/New/Onco_KB <DISEASE>.csv
```

Nếu chọn `Cancer-specific OncoKB`, khi đổi disease hoặc chạy batch nhiều disease, BioRank sẽ dùng file validation riêng tương ứng với từng disease.

## 4. Interface

BioRank v2 không dùng layout cũ kiểu một panel chạy PageRank và một panel preprocessing. Giao diện hiện tại là workspace gồm sidebar và vùng làm việc chính.

### Header Bar

Thanh trên cùng có các lựa chọn:

- `Cancer type`: chọn disease code, ví dụ `BRCA`.
- `Seed profile`: chọn `Original` hoặc `Enriched`.
- `Validation set`: chọn `Pan-cancer OncoKB` hoặc `Cancer-specific OncoKB`.
- `Status`: hiển thị trạng thái hiện tại của app.

> **[PLACEHOLDER HÌNH 03]** Chèn ảnh header bar của BioRank v2, trong đó thấy `Cancer type`, `Seed profile`, `Validation set` và trạng thái app.

### 1. Input Data Readiness

Đây là màn hình người dùng nên mở đầu tiên. Màn hình này hiển thị trạng thái các input BioRank:

- PPI network.
- Co-expression network.
- Seed genes.
- Differentially expressed genes.
- Gene-ontology mapping.
- Disease-specific ontologies.
- Validation reference.

Nếu tất cả input sinh học và `Validation Reference` hiện `Ready`, người dùng có thể chuyển sang ranking hoặc optimization. Nếu input hiện `Missing`, chọn file thủ công bằng nút browse tương ứng.

> **[PLACEHOLDER HÌNH 04]** Chèn ảnh màn hình `Input Data Readiness` khi các input đã hiện `Ready`.

> **[PLACEHOLDER HÌNH 05]** Chèn ảnh ví dụ một input hiện `Missing` và vị trí nút browse để chọn file thủ công.

### 2. Data Preprocessing

Màn hình này dùng để tạo hoặc tái tạo các file dữ liệu cần thiết:

- Ontology graph.
- Disease-specific ontology.
- Tumor/control expression tables.
- DE genes.
- Co-expression network.

Người dùng chỉ cần dùng màn hình này khi chưa có đủ dữ liệu đầu vào hoặc muốn tạo lại dữ liệu từ raw data.

> **[PLACEHOLDER HÌNH 06]** Chèn ảnh màn hình `Data Preprocessing` với các chức năng preprocessing hiện có.

### 3. Cancer Gene Ranking

Màn hình này dùng để chạy ranking:

- Chọn thuật toán.
- Đặt `Alpha`.
- Đặt `Beta`.
- Build network.
- Run algorithm.
- Xem kết quả và metric.
- Chạy batch ranking.

> **[PLACEHOLDER HÌNH 07]** Chèn ảnh màn hình `Cancer Gene Ranking`, trong đó thấy khu vực chọn thuật toán, alpha/beta, `Build Integrated Network` và `Run Gene Ranking`.

### 4. Parameter Optimization

Màn hình này dùng để tối ưu alpha/beta cho `BioRank Lite` bằng Optuna:

- Chạy một disease.
- Chạy queue nhiều disease.
- Chọn ablation case.
- Theo dõi progress, logs và bảng comparison.

> **[PLACEHOLDER HÌNH 08]** Chèn ảnh màn hình `Parameter Optimization`, trong đó thấy số trials, random seed, mode chạy và nút `Start Optimization`.

## 5. Data Preprocessing Workflow

Người dùng có thể bỏ qua phần này nếu đã có full dataset đúng cấu trúc. Chỉ dùng preprocessing khi cần tạo lại input từ dữ liệu gốc.

### 5.1. Compute Ontology Graph

Mục tiêu: tạo file gene-ontology mapping dùng cho BioRank.

Các bước:

1. Mở `Data Preprocessing`.
2. Chọn chức năng `Compute Ontology Graph`.
3. Chọn các file đầu vào theo hộp thoại:
   - GO `.gaf` file.
   - KEGG file.
   - Reactome file.
   - UniProt-Ensembl mapping.
   - KEGG-UniProt mapping.
4. Chọn output path.
5. Bấm `Run`.

> **[PLACEHOLDER HÌNH 09]** Chèn ảnh hộp thoại `Compute Ontology Graph` sau khi đã chọn các input cần thiết.

Output khuyến nghị:

```text
data_set/ontology_network/ontology_network.tsv
```

### 5.2. Compute Disease-Specific Ontologies

Mục tiêu: tạo ontology đặc hiệu cho disease đang chọn.

Các bước:

1. Mở `Data Preprocessing`.
2. Chọn `Compute Disease-Specific Ontologies`.
3. Chọn ontology graph từ bước 5.1.
4. Chọn seed gene file của disease tương ứng.
5. Chọn output path.
6. Bấm `Run`.

> **[PLACEHOLDER HÌNH 10]** Chèn ảnh hộp thoại `Compute Disease-Specific Ontologies` sau khi chọn ontology graph và seed gene file.

Output khuyến nghị:

```text
data_set/disease_specific_ontologies/TCGA-<DISEASE>_disease_ontologies.txt
```

### 5.3. Create TCGA Tumor-Control Tables

Mục tiêu: tạo bảng expression cho tumor và control từ raw RNA-seq data.

Các bước:

1. Mở `Data Preprocessing`.
2. Chọn `Create Tumor-Control table`.
3. Chọn:
   - GDC sample sheet.
   - GDC manifest file.
   - RNA-seq data folder.
   - Output directory.
4. Bấm `Run`.

Sau bước này, người dùng sẽ có tumor expression table và control expression table để dùng ở bước 5.4.

> **[PLACEHOLDER HÌNH 11]** Chèn ảnh hộp thoại `Create Tumor-Control table` với sample sheet, manifest, RNA-seq folder và output directory.

### 5.4. Compute DE Genes and Co-expression Network

Mục tiêu: tạo DE genes và co-expression network cho disease.

Các bước:

1. Mở `Data Preprocessing`.
2. Chọn `Compute DE Genes + Co-expression`.
3. Chọn:
   - Tumor expression table.
   - Control expression table.
   - Identifier list, ví dụ `HIPPIE_node_list.txt`.
4. Chọn output paths.
5. Bấm `Run`.

> **[PLACEHOLDER HÌNH 12]** Chèn ảnh hộp thoại `Compute DE Genes + Co-expression` với tumor table, control table và identifier list.

Output khuyến nghị:

```text
data_set/differentially_expressed_genes/TCGA-<DISEASE>_de_genes.tsv
data_set/co-expression_networks/TCGA-<DISEASE>_co_expression_t_70.tsv
```

## 6. Running Gene Ranking

Người dùng chạy ranking trong màn hình `Cancer Gene Ranking`.

### 6.1. Chuẩn bị trước khi ranking

1. Mở `Input Data Readiness`.
2. Chọn `Cancer type`.
3. Chọn `Seed profile`.
4. Chọn `Validation set`.
5. Kiểm tra 6 input sinh học và `Validation Reference` đều `Ready`.
6. Nếu cần dùng dữ liệu enrichment, chọn profile `Enriched` và kiểm tra lại trạng thái input.

### 6.2. Single Ranking Run

Các bước:

1. Mở `Cancer Gene Ranking`.
2. Chọn thuật toán:
   - `Original PageRank`
   - `BRWR Lite`
   - `BRWR`
   - `BioRank Lite`
   - `BioRank`
3. Đặt `Alpha`.
4. Đặt `Beta`.
5. Bấm `Build Network`.
6. Xem network preview nếu cần.
7. Bấm `Run Algorithm`.
8. Xem kết quả ranking trong tab results.

> **[PLACEHOLDER HÌNH 13]** Chèn ảnh chọn thuật toán và nhập alpha/beta trong `Cancer Gene Ranking`.

> **[PLACEHOLDER HÌNH 14]** Chèn ảnh sau khi bấm `Build Network`, có log hoặc trạng thái network đã được build.

> **[PLACEHOLDER HÌNH 15]** Chèn ảnh cửa sổ network preview, nếu có dùng preview trong hướng dẫn Word.

> **[PLACEHOLDER HÌNH 16]** Chèn ảnh tab results sau khi `Run Algorithm` hoàn tất, trong đó thấy bảng ranking và metric.

Gợi ý:

- `Original PageRank` là baseline topology-based.
- `BRWR Lite` và `BRWR` là các biến thể random walk.
- `BioRank Lite` là lựa chọn phù hợp khi muốn chạy nhanh.
- `BioRank` dùng pipeline đầy đủ hơn.

### 6.3. Batch Ranking

Batch ranking dùng khi người dùng muốn chạy nhiều cấu hình alpha/beta hoặc nhiều disease liên tiếp.

Các bước:

1. Mở `Cancer Gene Ranking`.
2. Chọn disease cho batch job.
3. Nhập alpha,beta, mỗi dòng một cặp:

```text
0.20,0.20
0.50,0.50
1.00,0.00
```

4. Thêm disease vào queue.
5. Lặp lại với disease khác nếu cần.
6. Start batch ranking.

BioRank chạy batch tuần tự để tránh quá tải bộ nhớ và CPU.
Nếu đang chọn `Cancer-specific OncoKB`, mỗi disease trong batch sẽ dùng file validation riêng của disease đó.

> **[PLACEHOLDER HÌNH 17]** Chèn ảnh khu vực batch ranking sau khi đã nhập nhiều cặp alpha,beta và thêm disease vào queue.

## 7. Parameter Optimization

Người dùng chạy tối ưu trong màn hình `Parameter Optimization`. Chức năng này dùng Optuna để tìm alpha/beta tốt cho `BioRank Lite`.

### 7.1. Single Disease Optimization

Các bước:

1. Chọn disease ở header.
2. Chọn seed profile.
3. Chọn validation set.
4. Mở `Parameter Optimization`.
5. Chọn chế độ `Single Disease`.
6. Nhập số trials.
7. Nhập random seed.
8. Chọn ablation case nếu cần.
9. Bấm `Start Optimization`.

> **[PLACEHOLDER HÌNH 18]** Chèn ảnh cấu hình `Single Disease` trong màn hình `Parameter Optimization`.

Giá trị mặc định:

```text
n_trials = 200
random_seed = 42
alpha range = 0.0..1.0
beta range = 0.0..1.0
objectives = nDCG@100, Recall@100, Common@100
```

### 7.2. Batch Optimization

Các bước:

1. Mở `Parameter Optimization`.
2. Chọn `Batch Queue`.
3. Thêm từng disease vào queue.
4. Chọn ablation case nếu cần.
5. Bấm `Start Optimization`.

BioRank sẽ chạy từng disease/case theo thứ tự trong queue.
Nếu đang chọn `Cancer-specific OncoKB`, mỗi disease trong queue sẽ dùng file validation riêng của disease đó.

> **[PLACEHOLDER HÌNH 19]** Chèn ảnh `Batch Queue` trong `Parameter Optimization` sau khi đã thêm nhiều disease/case.

### 7.3. Ablation Cases

BioRank v2 hỗ trợ các case:

- `BioRank v2 full`: dùng đầy đủ biological personalization, topological/DE personalization, PPI annotation weighting và PPI + co-expression aggregation.
- `BioRank v2 without DE genes`: bỏ topological/DE personalization; alpha được hiển thị là `N/A`.
- `BioRank v2 without co-expression`: chỉ dùng PPI network; beta được hiển thị là `N/A`.
- `BioRank v2 without annotation`: bỏ biological/ontology personalization và tắt annotation weighting; alpha được hiển thị là `N/A`.

> **[PLACEHOLDER HÌNH 20]** Chèn ảnh phần chọn ablation cases trong màn hình optimization.

### 7.4. Pause, Resume, Cancel

Trong lúc optimization đang chạy:

- `Pause`: tạm dừng tại checkpoint an toàn tiếp theo.
- `Resume`: tiếp tục run trong cùng phiên app.
- `Cancel Run`: hủy queue đang chạy.

Lưu ý: không đóng app khi đang pause nếu muốn resume, vì resume chỉ áp dụng cho phiên app hiện tại.

> **[PLACEHOLDER HÌNH 21]** Chèn ảnh optimization đang chạy, trong đó thấy progress, log, và các nút `Pause` / `Cancel Run`.

## 8. Output and Export

BioRank ghi kết quả vào thư mục `output/`.

### 8.1. Single Ranking Output

```text
output/<DISEASE>/<DISEASE>_integrated_network.tsv
output/<DISEASE>/<DISEASE>_original_pagerank_ranking.tsv
output/<DISEASE>/<DISEASE>_biorank_ranking.tsv
output/<DISEASE>/<DISEASE>_biorank_lite_ranking.tsv
output/<DISEASE>/<DISEASE>_brwr_ranking.tsv
output/<DISEASE>/<DISEASE>_brwr_lite_ranking.tsv
```

Ranking TSV schema:

```text
Rank<TAB>GeneNames<TAB>GeneSymbol<TAB>Score<TAB>OncoKBHit
```

### 8.2. Batch Ranking Output

```text
output/<DISEASE>/batch_ranking/<YYYYMMDD_HHMMSS>/
```

Thư mục batch có ranking TSV, integrated network TSV và `batch_summary.tsv`.

### 8.3. Optuna Output

Output mặc định:

```text
output/<DISEASE>/optuna_biorank_compare/<YYYYMMDD_HHMMSS>/
```

Output khi chạy ablation:

```text
output/<DISEASE>/optuna_biorank_compare/<ABLATION_CASE>/<YYYYMMDD_HHMMSS>/
```

Các file quan trọng:

```text
comparison_summary.tsv
biorank_trial_history.tsv
selected_biorank_candidates.tsv
biorank_pareto_trials.tsv
optimization_summary.json
logs.txt
rankings/
```

### 8.4. Output Location in Packaged Version

Với bản đóng gói, nếu không thấy `output/` cạnh `BioRank.exe`, kiểm tra thêm:

```text
BioRank/_internal/output/
BioRank/output/
```

## 9. Troubleshooting

### 9.1. App mở được nhưng input hiện `Missing`

Người dùng kiểm tra:

1. Thư mục dữ liệu có cấu trúc BioRank hợp lệ không.
2. Nếu thư mục không tên `data_set`, app có nhận diện duy nhất một thư mục phù hợp hoặc biến `BIORANK_DATA_DIR` đã được đặt chưa.
3. File có đúng disease code không, ví dụ `TCGA-BRCA`.
4. Với profile `Enriched`, có đủ enriched seed và disease ontology tương ứng không.

Nếu vẫn `Missing`, chọn file thủ công trong `Input Data Readiness`.

### 9.2. Không kích hoạt được virtual environment

Trên Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 9.3. Ranking lỗi do format file

Kiểm tra các file TSV:

- PPI có ít nhất 2 cột tab-separated.
- Co-expression có ít nhất 3 cột tab-separated.
- Seed có ít nhất 1 cột.
- DE genes có ít nhất 2 cột tab-separated.
- Ontology mapping có ít nhất 3 cột tab-separated.
- Disease ontology có ít nhất 2 cột tab-separated.

### 9.4. Không thấy output sau khi chạy bản đóng gói

Tìm trong:

```text
BioRank/_internal/output/
BioRank/output/
```

Hoặc tìm theo tên file:

```text
*_ranking.tsv
comparison_summary.tsv
selected_biorank_candidates.tsv
```

### 9.5. Output quá lớn

Sau nhiều lần ranking hoặc Optuna, thư mục `output/` có thể lớn. Người dùng có thể nén các run quan trọng và xóa các run cũ nếu không cần dùng nữa.
