# BioRank Pipeline and Architecture

This document describes the current BioRank application flow implemented in
this repository.

## Entry Points

- `main.py`: main CustomTkinter desktop application.
- `main_qt_optimizer.py`: optional standalone PySide6 optimizer.
- `biorank_ui/optuna_compare_window.py`: Tk fallback optimizer window when Qt
  is unavailable.

## Core Pipeline

The ranking pipeline is orchestrated by `BioRank/BioRank.py`.

1. `BioRank/loader/loader.py` loads PPI, co-expression, seed genes, DE genes,
   gene-ontology mappings, and disease-specific ontologies.
2. `BioRank/graph_weight_computation/` optionally applies annotation/ontology
   evidence to PPI edge weights.
3. `BioRank/matrix_creation/` builds the graph used by ranking:
   - `convex_combination`: beta combines normalized PPI and co-expression.
   - `only_ppi_network`: PPI only, used for the without co-expression
     ablation.
4. `BioRank/personalization_vector_creation/` creates biological and/or
   topological personalization vectors.
5. `BioRank/personalization_vector_aggregation/` combines personalization
   vectors by alpha. If only one personalization vector is active, it is
   normalized directly and alpha has no effect.
6. `BioRank/core/` executes PageRank, BRWR, BioRank, or BioRank Lite.

BioRank Lite uses damping factor `0.85`, convergence threshold `1e-6`, and
`max_iter=1000`.

## Optuna Optimization

`BioRank/optimization/biorank_alpha_beta_optimizer.py` runs multi-objective
Optuna optimization with:

```text
objectives = nDCG@100, Recall@100, Common@100
sampler = NSGAIISampler
default random_seed = 42
```

Optuna output is written under:

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

## Ablation Cases

- `full`: biological personalization, topological/DE personalization,
  annotation-weighted PPI, and PPI + co-expression aggregation. Alpha and beta
  are optimized.
- `without_de_genes`: removes topological/DE personalization. Alpha is
  inactive and reported as N/A; beta is optimized.
- `without_co_expression`: uses only PPI for matrix aggregation. Beta is
  inactive and reported as N/A; alpha is optimized.
- `without_annotation`: removes biological/ontology personalization and
  disables annotation PPI weighting. Alpha is inactive and reported as N/A;
  beta is optimized.

## Fast Optuna Path

Repeated BioRank Lite trial evaluation uses
`BioRank/optimization/fast_biorank_lite.py`.

The fast path preserves the BioRank Lite formula and evaluation metrics while
avoiding repeated NetworkX graph construction per trial. Per disease/case run,
it caches:

- loaded input graphs and gene sets;
- ontology-weighted PPI when enabled;
- normalized sparse PPI and co-expression components;
- topology graph for topological personalization;
- active personalization vectors.

For each trial, beta combines the cached sparse components, alpha combines the
cached personalization vectors, and the same BioRank Lite power iteration is
run. If required input files are not present, the optimizer falls back to the
standard `BioRankCancerGeneRanking` path; this keeps tests and legacy call
sites compatible.

## UI Performance

The main app coalesces Optuna progress updates before rendering them in Tk.
The optimization view appends new trial rows instead of rebuilding old rows,
deduplicates consecutive log messages, and renders only the active result tab.
The results view caches each row's search text so filtering large ranking TSVs
does not repeatedly rebuild uppercase strings.

## Main UI Workflow

The main header exposes three experiment dimensions:

- `Cancer type`: the TCGA disease code.
- `Seed profile`: `Original` or `Enriched`.
- `Validation set`: `Pan-cancer OncoKB` or `Cancer-specific OncoKB`.

The display labels map to the existing internal dataset profile values, so
ranking services and saved run metadata keep their established contract.
`Pan-cancer OncoKB` uses `data_set/Onco_KB.csv` for every disease.
`Cancer-specific OncoKB` resolves a per-disease reference file, preferring
`data_set/Onco_KB_<DISEASE>.csv`, `data_set/Onco_KB <DISEASE>.csv`, then the
matching files under `data_set/seed_set/New/`. If the selected validation set
is missing for any disease in a ranking or Optuna batch queue, the run is
blocked before execution. The selected validation reference is used for
OncoKB hit marking, Recall, Common, and nDCG metrics.

Input Data Readiness shows six required biological inputs plus a separate
`Validation Reference` card. Each input card shows both the selected filename
and its parent directory so manually selected files can be distinguished when
names are similar.

## Dataset Discovery

The default dataset directory is `data_set/` under the repository root. The
path can be overridden with `BIORANK_DATA_DIR`. If `data_set/` is absent, the
app can detect one renamed direct child directory when its contents match the
expected BioRank layout, including at least three known input subdirectories
such as `ppi_network`, `seed_set`, and `ontology_network`.

The enriched seed file may be stored in a child directory below `seed_set/`.
Enriched disease ontology files are detected by `new` or `enrich` in the
filename, while the existing `_new_22_6` filename remains the first choice for
backward compatibility.

## Packaging Notes

`requirements.txt` includes the GUI and scientific runtime dependencies needed
by the main app. The dataset folder is intentionally external:

```text
BioRank/
  main.py
  data_set/
```

A PyInstaller build can be started with:

```powershell
python -m PyInstaller --noconfirm --windowed --name BioRank --icon icon.ico --collect-data customtkinter main.py
```
