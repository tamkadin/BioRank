import glob
import os
from pathlib import Path

from biorank_ui import theme


APP_TITLE = "BioRank - Cancer Gene Prioritization"
REPO_ROOT = Path(__file__).resolve().parents[1]


def repo_path(*parts):
    return str(REPO_ROOT.joinpath(*parts))


def dataset_path(*parts):
    return repo_path("data_set", *parts)


def output_path(*parts):
    return repo_path("output", *parts)


DATASET_DIR = dataset_path()
OUTPUT_DIR = output_path()
PREVIEW_NODE_LIMIT = 1000
PREVIEW_EDGE_LIMIT = 2000
RANKING_REVIEW_LIMIT = 500
METRIC_TOP_N = 100
GENE_MAPPING_PATH = dataset_path("mart_biotool.txt")
ONCOKB_PATH = dataset_path("Onco_KB.csv")
DEFAULT_ALPHA_MIN = 0.0
DEFAULT_ALPHA_MAX = 1.0
DEFAULT_BETA_MIN = 0.0
DEFAULT_BETA_MAX = 1.0
DEFAULT_OPTUNA_TRIALS = 200
DEFAULT_OPTUNA_RANDOM_SEED = 42
DEFAULT_RECALL_K = 100
DEFAULT_NDCG_K = 100
DEFAULT_PRECISION_K = 15
DEFAULT_CANDIDATE_SELECTION_MODE = "pareto"
DEFAULT_MAX_SELECTED_CANDIDATES = 5

COLORS = {
    "bg": theme.BACKGROUND,
    "panel": theme.CARD_BG,
    "text": theme.TEXT,
    "muted": theme.MUTED,
    "border": theme.BORDER,
    "accent": theme.PRIMARY,
    "accent_dark": theme.PRIMARY_DARK,
    "accent_soft": theme.PRIMARY_SOFT,
    "secondary": theme.SECONDARY,
    "secondary_hover": theme.SECONDARY_HOVER,
    "success": theme.SUCCESS,
    "warning": theme.WARNING,
    "danger": theme.DANGER,
}

DISEASES = ("BLCA", "BRCA", "COAD", "LUAD", "PRAD", "STAD", "THCA")
DATASET_PROFILE_DEFAULT = "Dataset"
DATASET_PROFILE_NEW = "Dataset New"
DATASET_PROFILES = (DATASET_PROFILE_DEFAULT, DATASET_PROFILE_NEW)
EVALUATION_MODE_ONCOKB = "OncoKB"
EVALUATION_MODES = (EVALUATION_MODE_ONCOKB,)

ALGORITHM_ORIGINAL_PAGERANK = "pagerank"
ALGORITHM_BIORANK = "biorank"
ALGORITHM_BIORANK_LITE = "biorank_lite"
ALGORITHM_BRWR = "brwr"
ALGORITHM_BRWR_LITE = "random_walk"

ALGORITHM_LABELS = {
    ALGORITHM_ORIGINAL_PAGERANK: "Original PageRank",
    ALGORITHM_BRWR_LITE: "BRWR Lite",
    ALGORITHM_BRWR: "BRWR",
    ALGORITHM_BIORANK_LITE: "BioRank Lite",
    ALGORITHM_BIORANK: "BioRank",
}

ALGORITHM_BY_LABEL = {label: algorithm for algorithm, label in ALGORITHM_LABELS.items()}

ALGORITHM_SLUGS = {
    ALGORITHM_ORIGINAL_PAGERANK: "original_pagerank",
    ALGORITHM_BIORANK: "biorank",
    ALGORITHM_BIORANK_LITE: "biorank_lite",
    ALGORITHM_BRWR: "brwr",
    ALGORITHM_BRWR_LITE: "brwr_lite",
}

RANKING_ALGORITHMS = (
    ALGORITHM_ORIGINAL_PAGERANK,
    ALGORITHM_BRWR_LITE,
    ALGORITHM_BRWR,
    ALGORITHM_BIORANK_LITE,
    ALGORITHM_BIORANK,
)

STATE_TO_BACKEND_INPUT_KEYS = {
    "ppi": "ppi_file_path",
    "coexpression": "co_expression_file_path",
    "seed": "seed_file_path",
    "de_genes": "secondary_seed_file_path",
    "ontology_map": "map__gene__ontologies_file_path",
    "disease_ontology": "disease_ontology_file_path",
}

BACKEND_TO_STATE_INPUT_KEYS = {value: key for key, value in STATE_TO_BACKEND_INPUT_KEYS.items()}

BIORANK_INPUTS = [
    ("PPI Network (-p)", "ppi_file_path", False),
    ("Co-expression Network (-c)", "co_expression_file_path", False),
    ("Seed Genes File (-s)", "seed_file_path", False),
    ("Differentially Expressed Genes (-de)", "secondary_seed_file_path", False),
    ("Gene-Ontology Mapping File (-a)", "map__gene__ontologies_file_path", False),
    ("Disease-Specific Ontologies (-do)", "disease_ontology_file_path", False),
]


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def find_first(patterns):
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
    return ""


def detect_disease_from_text(text):
    normalized = text.upper()
    for disease in DISEASES:
        if disease in normalized:
            return disease
    return ""


def disease_output_dir(disease):
    if disease in DISEASES:
        return ensure_dir(output_path(disease))
    return ensure_dir(output_path("common"))


def get_optuna_biorank_compare_output_base(disease_code):
    return Path(output_path(disease_code, "optuna_biorank_compare"))


def build_output_paths(disease, algorithm):
    disease_dir = disease_output_dir(disease)
    algorithm_slug = ALGORITHM_SLUGS.get(get_algorithm_slug(algorithm), algorithm or "ranking")
    return {
        "ranking": os.path.join(disease_dir, f"{disease}_{algorithm_slug}_ranking.tsv"),
        "network": os.path.join(disease_dir, f"{disease}_integrated_network.tsv"),
    }


def build_batch_output_paths(disease, algorithm, alpha, beta, batch_id):
    disease_dir = disease_output_dir(disease)
    algorithm_slug = ALGORITHM_SLUGS.get(get_algorithm_slug(algorithm), algorithm or "ranking")
    batch_dir = ensure_dir(os.path.join(disease_dir, "batch_ranking", str(batch_id)))
    alpha_slug = f"{float(alpha):.4f}".rstrip("0").rstrip(".")
    beta_slug = f"{float(beta):.4f}".rstrip("0").rstrip(".")
    return {
        "ranking": os.path.join(batch_dir, f"{disease}_{algorithm_slug}_a{alpha_slug}_b{beta_slug}_ranking.tsv"),
        "network": os.path.join(batch_dir, f"{disease}_a{alpha_slug}_b{beta_slug}_integrated_network.tsv"),
    }


def get_algorithm_slug(value):
    if value in RANKING_ALGORITHMS:
        return value
    return ALGORITHM_BY_LABEL.get(value, value)


def state_file_paths_to_backend(file_paths):
    return {
        backend_key: file_paths.get(state_key, "")
        for state_key, backend_key in STATE_TO_BACKEND_INPUT_KEYS.items()
    }


def backend_file_paths_to_state(input_paths):
    return {
        state_key: input_paths.get(backend_key, "")
        for backend_key, state_key in BACKEND_TO_STATE_INPUT_KEYS.items()
    }


def build_default_state_file_paths(
    disease,
    dataset_profile=DATASET_PROFILE_DEFAULT,
    evaluation_mode=EVALUATION_MODE_ONCOKB,
):
    return backend_file_paths_to_state(
        build_default_biorank_inputs(disease, dataset_profile, evaluation_mode)
    )


def build_default_biorank_inputs(
    disease,
    dataset_profile=DATASET_PROFILE_DEFAULT,
    evaluation_mode=EVALUATION_MODE_ONCOKB,
):
    if dataset_profile not in DATASET_PROFILES:
        raise ValueError(f"Unknown dataset profile: {dataset_profile}")
    if evaluation_mode not in EVALUATION_MODES:
        raise ValueError(f"Unknown evaluation mode: {evaluation_mode}")
    tcga = f"TCGA-{disease}"
    inputs = {
        "ppi_file_path": find_first([dataset_path("ppi_network", "HIPPIE.tsv")]),
        "co_expression_file_path": find_first(
            [dataset_path("co-expression_networks", f"{tcga}*co_expression*.tsv")]
        ),
        "seed_file_path": find_first(
            [
                dataset_path("seed_set", f"{tcga}*_seed.txt"),
                dataset_path("seed_set", f"{tcga}*_seed.tsv"),
                dataset_path("seed_set", f"{tcga}*_seed.*"),
                dataset_path("seed_set", f"{tcga}*_seed"),
            ]
        ),
        "secondary_seed_file_path": find_first(
            [dataset_path("differentially_expressed_genes", f"{tcga}*de_genes.tsv")]
        ),
        "map__gene__ontologies_file_path": find_first(
            [dataset_path("ontology_network", "ontology_network.tsv")]
        ),
        "disease_ontology_file_path": find_first(
            [
                dataset_path("disease_specific_ontologies", f"{tcga}_disease_ontologies.txt"),
                dataset_path("disease_specific_ontologies", f"{tcga}*disease_ontologies.txt"),
            ]
        ),
    }
    if dataset_profile == DATASET_PROFILE_NEW:
        inputs["seed_file_path"] = find_first(
            [dataset_path("seed_set", "New", f"{tcga}_seed.txt")]
        )
        inputs["disease_ontology_file_path"] = find_first(
            [
                dataset_path(
                    "disease_specific_ontologies",
                    f"{tcga}_disease_ontologies_new_22_6.txt",
                )
            ]
        )
    return inputs


def get_validation_reference_path(disease, dataset_profile, evaluation_mode):
    if dataset_profile not in DATASET_PROFILES:
        raise ValueError(f"Unknown dataset profile: {dataset_profile}")
    if evaluation_mode not in EVALUATION_MODES:
        raise ValueError(f"Unknown evaluation mode: {evaluation_mode}")
    return ONCOKB_PATH
