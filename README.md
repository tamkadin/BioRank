# Prioritizing Cancer Therapeutic Genes Using BioRank

BioRank is a GUI-based tool for integrating multi-omics biological data and prioritizing cancer-related genes with biologically informed PageRank and random-walk methods.

The current implementation is **BioRank v2**, a desktop workspace that runs from `main.py`. It resolves runtime paths from the repository root, so the project can be copied to another machine as long as the expected `data_set/` layout is kept.

For a step-by-step installation and run guide, see [docs/setup_and_run_biorank_v2.md](docs/setup_and_run_biorank_v2.md).

---

## Author

**Nguyen Huu Tam**, **Pham Duc Tinh**, **Pham Van Hai**

Project: BioRank, 2025

---

## Citation

BioRank was developed based on and extends concepts from:

Gentili M., Martini L., Sponziello M., Becchetti L. "Biological Random Walks: Multi-Omics Integration for Disease Gene Prioritization." Bioinformatics, 2022. DOI: https://doi.org/10.1093/bioinformatics/btac446

Original BiologicalRandomWalks repository:

```text
https://github.com/LeoM93/BiologicalRandomWalks
```

If you use BioRank or its underlying methods in research, cite the original paper and this project.

---

## Introduction

PageRank-based approaches can identify disease-related genes from biological networks, but classical graph methods mainly use network topology. BioRank extends this idea by integrating additional biological evidence:

- Protein-protein interaction network, or PPI.
- Co-expression network.
- Disease seed genes.
- Differentially expressed genes.
- Gene ontology annotations from GO, KEGG, and Reactome.
- Disease-specific ontology terms.

The system builds an integrated weighted gene graph, creates biological and topological personalization vectors, then ranks candidate genes with Original PageRank, BRWR, BioRank Lite, or BioRank.

<p align="center">
  <img src="imgs/Ảnh2.jpg" alt="BioRank Overview" width="600"/>
</p>

---

## Application Overview

BioRank is a Python desktop application for biomedical researchers who need to:

- Prepare biological input data through preprocessing tools.
- Auto-detect required BioRank input files.
- Build and preview an integrated biological network.
- Run cancer gene prioritization algorithms.
- Review ranked genes with gene symbol mapping and OncoKB hits.
- Tune BioRank Lite alpha/beta parameters with Optuna.

Main entry point:

```powershell
python main.py
```

---

## Features

| Function | Description |
|---|---|
| BioRank gene prioritization | Rank candidate cancer genes from integrated biological networks. |
| Original PageRank | Run topology-only PageRank baseline on the integrated graph. |
| BRWR Lite / BRWR | Run biological random walk with restart variants. |
| BioRank Lite / BioRank | Run BioRank variants using biological and topological personalization. |
| Network preview | Build the integrated graph and inspect first nodes/edges before ranking. |
| Batch ranking | Run multiple disease and alpha/beta configurations sequentially. |
| Ranking review | Export mapped TSV ranking with `GeneSymbol` and `OncoKBHit`. |
| Optuna optimization | Multi-objective alpha/beta tuning for BioRank Lite. |
| Data preprocessing | Build ontology graph, disease ontology, TCGA tumor/control tables, DE genes, and co-expression network. |

---

## BioRank v2 UI and Optuna Optimization

BioRank v2 reorganizes the application as a workspace with four main screens:

1. **Input Data Configuration**
   - Select disease, dataset profile, and evaluation mode.
   - Inspect six required input files.
   - Browse and override input files manually.

2. **Data Preprocessing**
   - Build ontology graph.
   - Compute disease-specific ontology enrichment.
   - Create TCGA tumor/control expression tables.
   - Compute DE genes and co-expression network.

3. **Priority Gene Ranking**
   - Run single-disease ranking.
   - Build and preview the integrated network.
   - Run batch ranking for multiple diseases and alpha/beta pairs.
   - View ranking output and OncoKB-based metrics.

4. **Parameter Optimization**
   - Run Optuna alpha/beta optimization for BioRank Lite.
   - Compare PageRank, BRWR Lite, BioRank Lite baseline, and selected optimized BioRank Lite candidates.
   - Support single-disease and sequential multi-disease optimization.

Optuna defaults:

```text
n_trials = 200
random_seed = 42
alpha range = 0.0..1.0
beta range = 0.0..1.0
objectives = nDCG@100, Recall@100, Common@100
```

Optimizer outputs are isolated under:

```text
output/<DISEASE>/optuna_biorank_compare/<YYYYMMDD_HHMMSS>/
```

The output folder includes:

```text
comparison_summary.tsv
biorank_trial_history.tsv
selected_biorank_candidates.tsv
biorank_pareto_trials.tsv
optimization_summary.json
logs.txt
rankings/
```

---

## Repository Structure

```text
BioRank/
  main.py                         # Main CustomTkinter GUI
  main_qt_optimizer.py            # Standalone Qt optimizer entry point
  BioRank/                        # Ranking pipeline, cores, metrics, optimizer
  biorank_ui/                     # Main GUI state, config, views, service layer
  biorank_qt/                     # Standalone Qt optimizer UI
  data_preprocessing/             # Preprocessing modules
  data_set/                       # Input datasets and references
  output/                         # Generated outputs, ignored by git
  tests/                          # Unit tests
  docs/                           # Architecture, setup guide, workflow notes
  requirements.txt
```

Important docs:

- [docs/setup_and_run_biorank_v2.md](docs/setup_and_run_biorank_v2.md): detailed setup, run, and troubleshooting guide.
- [docs/BioRank_pipeline_and_architecture.md](docs/BioRank_pipeline_and_architecture.md): current pipeline and architecture.
- [docs/USER_WORKFLOW_AND_SPECIFICATION.md](docs/USER_WORKFLOW_AND_SPECIFICATION.md): UI workflow notes.
- [docs/AGENT_RULES.md](docs/AGENT_RULES.md): maintainer rules for code changes.

---

## Requirements

Use Python 3.10+ if possible. Python 3.9+ should work for most workflows.

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For complete setup instructions on Windows, macOS, or Linux, read:

```text
docs/setup_and_run_biorank_v2.md
```

---

## Required Data Layout

The GUI auto-detects default ranking inputs under `data_set/`:

The full dataset is large, so it is not uploaded directly to git. Download it from Google Drive:

```text
https://drive.google.com/drive/folders/1LU25AoEO8PNBLvk0TU5PAyL1kwb7B_mr?usp=sharing
```

After downloading or extracting the folder, rename the dataset folder to exactly:

```text
data_set
```

Place it at the repository root, next to `main.py`, so the final path is:

```text
BioRank/data_set/
```

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

For `Dataset New`, BioRank v2 overrides seed and disease ontology with:

```text
data_set/seed_set/New/TCGA-<DISEASE>_seed.txt
data_set/disease_specific_ontologies/TCGA-<DISEASE>_disease_ontologies_new_22_6.txt
```

Supported disease codes:

```text
BLCA, BRCA, COAD, LUAD, PRAD, STAD, THCA
```

The app does not split seed genes into train/test sets. Evaluation currently uses:

```text
data_set/Onco_KB.csv
```

---

## Quick Start

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
python -m pip install -r requirements.txt
```

3. Run the main GUI.

```powershell
python main.py
```

4. In the app:

```text
Input Data Configuration -> confirm inputs are Ready
Priority Gene Ranking -> Build Network -> Run Algorithm
Parameter Optimization -> Start Optuna Engine
```

---

## Main Ranking Outputs

Single-run ranking and integrated network outputs:

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

Batch ranking outputs:

```text
output/<DISEASE>/batch_ranking/<YYYYMMDD_HHMMSS>/
```

---

## Reproduce an Experiment

To reproduce a ranking run, record:

- Repo version or Git commit.
- Disease code.
- Dataset profile: `Dataset` or `Dataset New`.
- Evaluation mode: `OncoKB`.
- Algorithm.
- Alpha and beta.
- The six input paths shown in the GUI.

Then restore the same `data_set/` files, run `python main.py`, select the same parameters, build the network, and run the algorithm.

To reproduce Optuna optimization, additionally record:

- Number of trials.
- Random seed.
- Alpha and beta ranges.
- Candidate selection settings if changed.

For the same input files, search space, random seed, and trial count, Optuna uses the same suggestion sequence.

---

## Tests

Focused checks:

```powershell
python -m unittest tests.test_ui_config_wiring
python -m unittest tests.test_service_ranking_output
```

Full test suite:

```powershell
python -m unittest discover tests
```

---

## Notes for Maintainers

- Keep runtime paths relative to the repository root.
- Do not hard-code user-specific absolute paths.
- Keep generated outputs under `output/`.
- Keep large or generated runtime files out of source control.
- Follow [docs/AGENT_RULES.md](docs/AGENT_RULES.md) before changing code or docs.
