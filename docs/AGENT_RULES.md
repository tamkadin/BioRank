# BioRank Agent Rules

Tai lieu nay la bo quy tac lam viec cho AI agent khi doc, sua, tao code trong repo BioRank. Muc tieu la giu code gon, dung ngu canh nghiep vu, va dam bao docs luon phan anh dung nhung gi dang ton tai.

## 1. Doc context truoc khi sua code

- Luon doc `docs/BioRank_pipeline_and_architecture.md` truoc khi sua cac phan lien quan den pipeline, GUI, preprocessing, ranking, loader, output, hoac input dataset.
- Neu task cham vao mot module cu the, doc file code cua module do va cac module lien quan truc tiep truoc khi sua.
- Uu tien hieu luong du lieu tu input file den output ranking truoc khi thay doi logic.
- Khong doan cong thuc thuat toan. Neu sua BioRank, PageRank, personalization vector, graph weighting, hoac matrix aggregation, phai doi chieu voi docs va code hien co.

## 2. Nguyen tac clean code

- Giu thay doi nho, ro pham vi, dung muc tieu task.
- Uu tien pattern dang co trong repo hon tao abstraction moi.
- Dat ten bien, ham, class ro nghia theo domain hien co: disease, gene, seed, ontology, PPI, co-expression, ranking.
- Tach logic khi mot ham qua dai hoac tron nhieu trach nhiem, nhung chi tach khi lam code de doc va de test hon.
- Tranh lap code neu co the dung helper san co hoac tao helper nho co y nghia.
- Khong thay doi format input/output neu task khong yeu cau. Phan lon pipeline dung TSV voi delimiter tab.
- Khong doi cong thuc thuat toan khi chi sua UI, docs, file path, validation, hoac output naming.

## 3. Comments va docstrings

- Han che comments. Chi them comment khi logic kho, co rang buoc nghiep vu, hoac co ly do ky thuat khong hien ro tu code.
- Khong them comment lap lai dieu code da noi ro.
- Neu them comment, viet ngan va gan voi block can giai thich.
- Khong dung comment de giu lai code cu, TODO mo ho, hoac note ve phan da bi xoa.
- Docstring nen mo ta contract cua ham/class neu ham/class la API noi bo quan trong, khong viet lai tung dong xu ly.

## 4. Cap nhat docs sau khi sua code

- Sau khi tao hoac sua code lam thay doi behavior, input, output, tham so, file path, UI workflow, hoac pipeline, phai cap nhat docs lien quan.
- `docs/BioRank_pipeline_and_architecture.md` la tai lieu chinh cho kien truc va luong pipeline. Cap nhat file nay khi thay doi:
  - thu muc/module va vai tro;
  - preprocessing steps;
  - loader input formats;
  - ranking pipeline;
  - output naming;
  - UI workflow;
  - tham so mac dinh;
  - diem ky thuat can luu y.
- Docs chi duoc mo ta nhung gi dang ton tai trong repo sau thay doi.
- Khong ghi docs ve feature chua co, code da xoa, hoac ke hoach tuong lai neu user khong yeu cau.

## 5. Khi xoa code hoac feature

- Khi xoa mot feature, xoa luon cac phan lien quan truc tiep neu khong con duoc dung:
  - imports;
  - helper functions/classes;
  - UI controls;
  - config/constants;
  - tests hoac scripts chi phuc vu feature do;
  - docs va references ve feature do.
- Sau khi xoa, search repo de dam bao khong con reference chet.
- Khong de docs nhac den feature da xoa.
- Khong de comment giai thich "truoc day tung co" neu no khong can cho behavior hien tai.
- Neu co du lieu output cu trong `output/` hoac `data_set/Output/`, khong xoa tru khi user yeu cau ro rang.

## 6. Bao toan pipeline BioRank

- `main.py` la entry point GUI Tkinter. Giu lazy import cho cac thu vien nang va pipeline BioRank de UI mo nhanh.
- `BioRank/loader/loader.py` quy dinh cach doc graph, seed, DE genes, ontology mappings. Sua loader can can than vi anh huong toan pipeline.
- `data_preprocessing/` tao input sinh hoc. Khong tron preprocessing logic vao ranking core neu khong co ly do ro rang.
- `BioRank/graph_weight_computation/` chi nen xu ly trong so sinh hoc cua PPI.
- `BioRank/matrix_creation/` chi nen xu ly aggregate PPI va co-expression graph.
- `BioRank/personalization_vector_creation/` chi nen tao personalization vectors.
- `BioRank/core/` chi nen chua ranking algorithms.
- Output ranking va integrated network hien luu theo disease trong `output/<DISEASE>/`.

## 7. Kiem tra sau thay doi

- Chay test hoac command kiem tra phu hop voi pham vi thay doi.
- Neu khong co test tu dong, chay it nhat syntax check/compile cho file Python da sua khi kha thi.
- Neu sua GUI workflow, kiem tra flow bang code path lien quan va neu co the chay app.
- Neu sua output, kiem tra ten file, delimiter, header, va vi tri ghi file.
- Bao cao ro nhung gi da kiem tra va nhung gi chua kiem tra duoc.

## 8. Lam viec voi du lieu va output

- Khong sua file dataset lon neu task khong yeu cau.
- Khong xoa output cu tru khi user yeu cau ro.
- Khi tao output moi trong code, uu tien dung naming theo docs hien tai:

```text
output/<DISEASE>/<DISEASE>_biorank_ranking.tsv
output/<DISEASE>/<DISEASE>_biorank_lite_ranking.tsv
output/<DISEASE>/<DISEASE>_original_pagerank_ranking.tsv
output/<DISEASE>/<DISEASE>_brwr_ranking.tsv
output/<DISEASE>/<DISEASE>_brwr_lite_ranking.tsv
output/<DISEASE>/<DISEASE>_integrated_network.tsv
```

- Batch ranking tu tab Priority Gene Ranking ghi output rieng, khong ghi de ranking chinh:

```text
output/<DISEASE>/batch_ranking/<YYYYMMDD_HHMMSS>/
```

- Output toi uu Optuna phai nam trong folder rieng, khong ghi de ranking/network chinh:

```text
output/<DISEASE>/optuna_biorank_compare/<YYYYMMDD_HHMMSS>/
```

- UI toi uu Optuna chinh la PySide6 trong `biorank_qt/`, duoc mo tu `main.py` bang `main_qt_optimizer.py` neu PySide6 co san. Tk window trong `biorank_ui/optuna_compare_window.py` chi la fallback khi thieu PySide6.
- UI toi uu Optuna nen giu Simple mode tren man hinh chinh. Cac path dai, search space, metric K, va candidate selection nen nam trong `Advanced Settings` de tranh lam roi workflow chinh.
- Optuna optimizer cho BioRank phai giu multi-objective: dung `create_study(directions=[...])`, objective return tuple metric, va Pareto front lay tu `study.best_trials`. Display score chi duoc dung sau optimization de chon/sort selected candidates, khong duoc dung lam objective duy nhat.
- Output candidates cua optimizer dung `selected_biorank_candidates.tsv` va ranking `biorank_lite_selected<N>_..._ranking.tsv`; khong tao lai output top5 cu neu khong co yeu cau ro.
- Giu TSV la format mac dinh cho graph, seed, DE genes, ontology, ranking, tru khi co yeu cau khac.
- Ranking TSV cua run thuat toan thong thuong nen gom mapping trong cung file: `Rank`, `GeneNames`, `GeneSymbol`, `Score`, `OncoKBHit`. Khong tao metadata JSON rieng cho moi run thong thuong neu user khong yeu cau, de `output/<DISEASE>/` gon.

## 9. Cach tra loi khi hoan tat

- Noi ngan gon file da sua/tao va ly do.
- Neu co chay kiem tra, neu ro command va ket qua.
- Neu khong chay kiem tra, noi ro ly do.
- Khong noi rang thay doi da duoc save neu chua thuc su ghi file.
