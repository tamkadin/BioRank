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

BioRank v2 expects the input dataset under `data_set/`.

The dataset is large, so it is not uploaded directly to git. Download it from:

```text
https://drive.google.com/drive/folders/1LU25AoEO8PNBLvk0TU5PAyL1kwb7B_mr?usp=sharing
```

After downloading or extracting the dataset, rename the folder to exactly:

```text
data_set
```

Then place it at the repository root, next to `main.py`:

```text
BioRank/
  main.py
  data_set/
```

The name must be `data_set` because the app auto-detects inputs from that folder.

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
```

Dataset New uses:

```text
data_set/seed_set/New/TCGA-<DISEASE>_seed.txt
data_set/disease_specific_ontologies/TCGA-<DISEASE>_disease_ontologies_new_22_6.txt
```

Supported disease codes:

```text
BLCA, BRCA, COAD, LUAD, PRAD, STAD, THCA
```

Current behavior:

- Evaluation mode is `OncoKB`.
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
1. Input Data Configuration
2. Data Preprocessing
3. Priority Gene Ranking
4. Parameter Optimization
```

## 8. Run a Ranking Experiment

1. Open `Input Data Configuration`.
2. Select the disease code in the header.
3. Select dataset profile:
   - `Dataset`: default seed and disease ontology.
   - `Dataset New`: new seed and new disease ontology.
4. Confirm all six BioRank inputs are `Ready`.
5. Open `Priority Gene Ranking`.
6. Select algorithm:
   - `Original PageRank`
   - `BRWR Lite`
   - `BRWR`
   - `BioRank Lite`
   - `BioRank`
7. Set `Alpha` and `Beta`.
8. Click `Build Network`.
9. Inspect the network preview if needed.
10. Click `Run Algorithm`.
11. Review ranking rows and OncoKB metrics in the Results tab.

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

1. Open `Priority Gene Ranking`.
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

Batch outputs:

```text
output/<DISEASE>/batch_ranking/<YYYYMMDD_HHMMSS>/
```

Each batch folder includes ranking TSV files, integrated network TSV files, and `batch_summary.tsv`.

## 10. Run Optuna Alpha/Beta Optimization

From the main app:

1. Select disease and dataset profile in the header.
2. Open `Parameter Optimization`.
3. Choose `Single Disease` or `Batch Queue`.
4. Set:
   - number of trials;
   - random seed.
5. Click `Start Optuna Engine`.

Default settings:

```text
n_trials = 200
random_seed = 42
alpha range = 0.0..1.0
beta range = 0.0..1.0
objectives = nDCG@100, Recall@100, Common@100
```

The optimization compares:

- Original PageRank baseline.
- BRWR Lite baseline.
- BioRank Lite baseline.
- Selected optimized BioRank Lite candidates.

Optuna outputs:

```text
output/<DISEASE>/optuna_biorank_compare/<YYYYMMDD_HHMMSS>/
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
- dataset profile;
- six input paths;
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

Check that `data_set/` exists under the repository root and that filenames match the expected disease code.

For `Dataset New`, only diseases with both new seed and new disease ontology files will be ready.

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

- Keep code paths relative to the repository root.
- Do not hard-code user-specific absolute paths.
- Do not change input/output schemas unless the pipeline documentation is updated.
- Follow `docs/AGENT_RULES.md` before changing code.
