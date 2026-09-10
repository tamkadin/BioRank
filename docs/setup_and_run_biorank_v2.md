# Setup and Run BioRank v2

This guide explains how to set up BioRank v2 on a new machine, verify the expected data layout, run the desktop app, and reproduce ranking or Optuna optimization experiments.

## 1. Requirements

Recommended environment:

- Python 3.10 or newer.
- Git, if cloning from a repository.
- Enough RAM for graph loading and ranking. Large PPI/co-expression networks can require several GB.
- A local copy of the expected `data_set/` folder.

BioRank v2 is a desktop app. The main GUI uses CustomTkinter and starts from:

```powershell
python main.py
```

The standalone Qt optimizer starts from:

```powershell
python main_qt_optimizer.py --disease BRCA
```

The main app does not require running the standalone Qt optimizer.

## 2. Get the Repository

Clone or copy the repository to any local folder.

Example on Windows:

```powershell
cd "C:\path\to\workspace"
git clone <repo-url> BioRank
cd BioRank
```

If the repository is copied manually, open a terminal in the copied `BioRank` folder.

The app resolves default runtime paths from the repository root through `biorank_ui/config.py`, so it should not depend on the old machine-specific path.

## 3. Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

After activation, verify Python points to the virtual environment:

```powershell
python -c "import sys; print(sys.executable)"
```

## 4. Install Dependencies

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install project dependencies:

```powershell
python -m pip install -r requirements.txt
```

If PySide6 installation fails and you only need the main app, first confirm whether `python main.py` can still start after installing the remaining dependencies. PySide6 is mainly used by the standalone Qt optimizer.

## 5. Verify Data Layout

BioRank v2 uses `data_set/` as the recommended input directory name.

The dataset is large, so it is not uploaded directly to git. Download it from:

```text
https://drive.google.com/drive/folders/11TY1KGRpxG2VzStKO1rb5NjBtcNClysP?usp=sharing
```

After downloading or extracting the dataset, the recommended folder name is:

```text
data_set
```

Then place it at the repository root, next to `main.py`:

```text
BioRank/
  main.py
  data_set/
```

The app first checks `data_set/`. If that directory is absent, it can detect one
renamed direct child directory from the expected BioRank subdirectory layout.
For data stored elsewhere, set `BIORANK_DATA_DIR` to an absolute or
repository-relative path before starting the app.

Minimum ranking input layout:

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

The `Enriched` seed profile uses:

```text
data_set/seed_set/New/TCGA-<DISEASE>_seed.txt
data_set/disease_specific_ontologies/TCGA-<DISEASE>_disease_ontologies_new_22_6.txt
```

Supported disease codes:

```text
BLCA, BRCA, COAD, LUAD, PRAD, STAD, THCA
```

Current behavior:

- `Pan-cancer OncoKB` uses `data_set/Onco_KB.csv` for every disease.
- `Cancer-specific OncoKB` uses a per-disease validation file when selected.
  The app detects `data_set/Onco_KB_<DISEASE>.csv`,
  `data_set/Onco_KB <DISEASE>.csv`, and matching files under
  `data_set/seed_set/New/`.
- The app uses full seed files.
- The app does not split seed genes into train/test sets.

## 6. Run a Quick Verification

Run focused tests:

```powershell
python -m unittest tests.test_ui_config_wiring
python -m unittest tests.test_service_ranking_output
```

Run the full test suite:

```powershell
python -m unittest discover tests
```

These tests verify UI path wiring and ranking output enrichment. They do not run a full biological ranking job.

## 7. Start the Main App

From the repository root:

```powershell
python main.py
```

The main window is titled:

```text
BioRank: Cancer Gene Prioritization Workspace
```

Main screens:

```text
1. Input Data Readiness
2. Data Preprocessing
3. Cancer Gene Ranking
4. Parameter Optimization
```

## 8. Run a Ranking Experiment

1. Open `Input Data Readiness`.
2. Select the disease code in the header.
3. Select the seed profile:
   - `Original`: original seed set and disease ontology.
   - `Enriched`: enriched seed set and corresponding disease ontology.
4. Select the validation set:
   - `Pan-cancer OncoKB`: shared reference file for all diseases.
   - `Cancer-specific OncoKB`: disease-specific reference file.
5. Confirm all six BioRank inputs and the `Validation Reference` card are
   `Ready`.
6. Open `Cancer Gene Ranking`.
7. Select algorithm:
   - `Original PageRank`
   - `BRWR Lite`
   - `BRWR`
   - `BioRank Lite`
   - `BioRank`
8. Set `Alpha` and `Beta`.
9. Click `Build Network`.
10. Inspect the network preview if needed.
11. Click `Run Algorithm`.
12. Review ranking rows and validation metrics in the Results tab.

Single-run outputs:

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

## 9. Run Batch Ranking

1. Open `Cancer Gene Ranking`.
2. Use the batch queue section.
3. Select a disease.
4. Enter one alpha,beta pair per line, for example:

```text
0.20,0.20
0.50,0.50
1.00,0.00
```

5. Add the disease to the queue.
6. Repeat for other diseases if needed.
7. Start batch ranking.

Batch ranking runs sequentially to avoid overloading memory and CPU.
When `Cancer-specific OncoKB` is selected, each disease in the batch uses its
own validation reference file.

Batch outputs:

```text
output/<DISEASE>/batch_ranking/<YYYYMMDD_HHMMSS>/
```

Each batch folder includes ranking TSV files, integrated network TSV files, and `batch_summary.tsv`.

## 10. Run Optuna Alpha/Beta Optimization

From the main app:

1. Select the cancer type, seed profile, and validation set in the header.
2. Open `Parameter Optimization`.
3. Choose `Single Disease` or `Batch Queue`.
4. Set:
   - number of trials;
   - random seed.
5. Select ablation cases:
   - `BioRank v2 full`;
   - `BioRank v2 without DE genes`;
   - `BioRank v2 without co-expression`;
   - `BioRank v2 without annotation`.
6. Click `Start Optimization`.

When `Cancer-specific OncoKB` is selected, single-disease optimization uses
the selected disease reference file, and batch optimization resolves a separate
validation file for each disease in the queue.

While optimization is running:

- `Pause` requests a safe pause at the next optimizer checkpoint. Wait until
  the status changes to `paused` before putting the computer to sleep.
- `Resume` continues the same in-memory run and the same SQLite Optuna study
  after the computer wakes up.
- `Cancel Run` stops the queue. Pause/resume does not support closing and
  reopening the application.

The live comparison and disease summary tables use a native row-based table
and render only the active result tab. UI progress events are coalesced, so a
running optimizer does not rebuild hidden tables on every backend update. A
trailing `*` marks a best metric value. No additional result database is
required: Optuna keeps study data in SQLite, while the UI reads its current
run snapshot from application state. This uses only bundled Python/Tk
components and remains compatible with desktop packaging.

Default settings:

```text
n_trials = 200
random_seed = 42
alpha range = 0.0..1.0
beta range = 0.0..1.0
objectives = nDCG@100, Recall@100, Common@100
```

The ablation cases change only the evidence sources used by the BioRank v2
pipeline:

- `BioRank v2 full`: biological personalization, topological/DE personalization, PPI annotation weighting, and PPI + co-expression aggregation.
- `BioRank v2 without DE genes`: removes the topological/DE personalization vector; Optuna optimizes only beta and reports alpha as N/A.
- `BioRank v2 without co-expression`: uses only the PPI network for matrix aggregation; Optuna optimizes only alpha and reports beta as N/A.
- `BioRank v2 without annotation`: removes biological/ontology personalization and disables PPI annotation weighting; Optuna optimizes only beta and reports alpha as N/A.

Inactive parameters are not included in the Optuna search space. Internally,
the limiting values are alpha=1 for `without DE genes`, beta=1 for `without
co-expression`, and alpha=0 for `without annotation`. When an ablation leaves
only one personalization vector, that vector is normalized directly rather
than combined through alpha.

For performance, each Optuna run uses a cached sparse BioRank Lite execution
path for trial evaluation. Within the same disease/case batch it loads inputs,
applies ontology PPI weighting when enabled, normalizes PPI/co-expression
components, and creates personalization vectors once, then each trial only
combines the cached sparse matrices by beta and runs the same BioRank Lite
power iteration. This does not change the alpha/beta formula, convergence
threshold, maximum iteration count, or evaluation metrics; it avoids
recomputing identical NetworkX graph construction steps across trials.
Trial history is appended incrementally, and full ranking lists are generated
only for the selected candidates instead of being retained for every trial.

The optimization compares:

- Original PageRank baseline.
- BRWR Lite baseline.
- BioRank Lite baseline.
- Selected optimized BioRank Lite candidates.

Optuna outputs:

```text
output/<DISEASE>/optuna_biorank_compare/<YYYYMMDD_HHMMSS>/
```

With ablation enabled, each run is grouped by case:

```text
output/<DISEASE>/optuna_biorank_compare/<ABLATION_CASE>/<YYYYMMDD_HHMMSS>/
```

Important files:

```text
comparison_summary.tsv
biorank_trial_history.tsv
selected_biorank_candidates.tsv
biorank_pareto_trials.tsv
optimization_summary.json
logs.txt
rankings/
```

For reproducibility, record:

- disease code;
- seed profile;
- six input paths;
- validation set and validation reference path;
- trial count;
- random seed;
- alpha and beta ranges;
- repository version.

## 11. Optional Standalone Qt Optimizer

The standalone Qt optimizer is separate from the main `main.py` app.

Run:

```powershell
python main_qt_optimizer.py --disease BRCA
```

This path uses:

```text
biorank_qt/app.py
biorank_qt/optimizer_window.py
biorank_qt/workers/optimizer_worker.py
```

If Qt cannot start in the current environment, `biorank_qt/app.py` can fall back to the Tk optimizer window.

## 12. Preprocessing Workflow

Open `Data Preprocessing` in the main app. The available steps are:

1. Compute ontology graph.
2. Compute disease-specific ontology enrichment.
3. Create TCGA tumor/control expression tables.
4. Compute DE genes and co-expression network.

Default output suggestions:

```text
data_set/ontology_network/ontology_network.tsv
data_set/disease_specific_ontologies/TCGA-<DISEASE>_disease_ontologies.txt
data_set/differentially_expressed_genes/TCGA-<DISEASE>_de_genes.tsv
data_set/co-expression_networks/TCGA-<DISEASE>_co_expression_t_70.tsv
```

The dialogs allow manual input and output path selection.

## 13. Troubleshooting

### App opens but inputs are Missing

Check that the detected data directory contains the expected BioRank subdirectories and that filenames match the disease code. Set `BIORANK_DATA_DIR` if auto-detection is ambiguous.

For the `Enriched` seed profile, only diseases with both an enriched seed file and matching enriched disease ontology file will be ready.

### PowerShell cannot activate the virtual environment

Run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate again:

```powershell
.\.venv\Scripts\Activate.ps1
```

### PySide6 or Qt fails

Use the main app first:

```powershell
python main.py
```

The standalone Qt optimizer is optional for the main workflow.

### Build a Desktop App

The repository keeps `data_set/` external so packaged builds stay small and
can reuse the same downloaded dataset folder. From an activated environment:

```powershell
python -m PyInstaller --noconfirm --windowed --name BioRank --icon icon.ico --collect-data customtkinter main.py
```

After building, place or keep `data_set/` next to the executable working
directory, or use the app's browse controls to select the dataset files.

### Ranking fails with missing columns

Most BioRank input files are TSV files. Check that:

- PPI has at least 2 tab-separated columns.
- Co-expression has at least 3 tab-separated columns.
- Seed has at least 1 column.
- DE genes has at least 2 tab-separated columns.
- Ontology mapping has at least 3 tab-separated columns.
- Disease ontology has at least 2 tab-separated columns.

### Output folder becomes large

Generated outputs are written under:

```text
output/
```

This folder is ignored by git. Archive or clean old output folders manually when they are no longer needed.

## 14. Maintainer Notes

- Keep code paths relative to the repository root or resolve them through `BIORANK_DATA_DIR`.
- Do not hard-code user-specific absolute paths.
- Do not change input/output schemas unless the pipeline documentation is updated.
- Follow `docs/AGENT_RULES.md` before changing code.
