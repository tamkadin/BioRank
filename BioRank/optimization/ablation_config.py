ABLATION_MODE_FULL = "full"
ABLATION_MODE_WITHOUT_DE_GENES = "without_de_genes"
ABLATION_MODE_WITHOUT_COEXPRESSION = "without_co_expression"
ABLATION_MODE_WITHOUT_ANNOTATION = "without_annotation"

ABLATION_MODE_ORDER = (
    ABLATION_MODE_FULL,
    ABLATION_MODE_WITHOUT_DE_GENES,
    ABLATION_MODE_WITHOUT_COEXPRESSION,
    ABLATION_MODE_WITHOUT_ANNOTATION,
)

ABLATION_MODE_LABELS = {
    ABLATION_MODE_FULL: "BioRank v2 full",
    ABLATION_MODE_WITHOUT_DE_GENES: "BioRank v2 without DE genes",
    ABLATION_MODE_WITHOUT_COEXPRESSION: "BioRank v2 without co-expression",
    ABLATION_MODE_WITHOUT_ANNOTATION: "BioRank v2 without annotation",
}

ABLATION_MODE_SLUGS = {
    ABLATION_MODE_FULL: "full",
    ABLATION_MODE_WITHOUT_DE_GENES: "without_de_genes",
    ABLATION_MODE_WITHOUT_COEXPRESSION: "without_co_expression",
    ABLATION_MODE_WITHOUT_ANNOTATION: "without_annotation",
}

_BASE_REQUIRED_INPUT_KEYS = {
    "ppi_file_path",
    "seed_file_path",
}

_COEXPRESSION_INPUT_KEYS = {"co_expression_file_path"}
_DE_INPUT_KEYS = {"secondary_seed_file_path"}
_ANNOTATION_INPUT_KEYS = {
    "map__gene__ontologies_file_path",
    "disease_ontology_file_path",
}


def normalize_ablation_mode(value):
    if value in ABLATION_MODE_ORDER:
        return value
    raise ValueError(f"Unsupported ablation mode: {value}")


def ablation_label(value):
    return ABLATION_MODE_LABELS[normalize_ablation_mode(value)]


def ablation_slug(value):
    return ABLATION_MODE_SLUGS[normalize_ablation_mode(value)]


def ablation_pipeline_config(value):
    mode = normalize_ablation_mode(value)
    if mode == ABLATION_MODE_FULL:
        return {
            "matrix_aggregation_policy": "convex_combination",
            "personalization_vector_creation_policies": ["biological", "topological"],
            "network_weight_flag": True,
            "alpha_used": True,
            "beta_used": True,
            "fixed_alpha": None,
            "fixed_beta": None,
        }
    if mode == ABLATION_MODE_WITHOUT_DE_GENES:
        return {
            "matrix_aggregation_policy": "convex_combination",
            "personalization_vector_creation_policies": ["biological"],
            "network_weight_flag": True,
            "alpha_used": False,
            "beta_used": True,
            "fixed_alpha": 1.0,
            "fixed_beta": None,
        }
    if mode == ABLATION_MODE_WITHOUT_COEXPRESSION:
        return {
            "matrix_aggregation_policy": "only_ppi_network",
            "personalization_vector_creation_policies": ["biological", "topological"],
            "network_weight_flag": True,
            "alpha_used": True,
            "beta_used": False,
            "fixed_alpha": None,
            "fixed_beta": 1.0,
        }
    if mode == ABLATION_MODE_WITHOUT_ANNOTATION:
        return {
            "matrix_aggregation_policy": "convex_combination",
            "personalization_vector_creation_policies": ["topological"],
            "network_weight_flag": False,
            "alpha_used": False,
            "beta_used": True,
            "fixed_alpha": 0.0,
            "fixed_beta": None,
        }
    raise ValueError(f"Unsupported ablation mode: {value}")


def required_input_keys(value):
    mode = normalize_ablation_mode(value)
    keys = set(_BASE_REQUIRED_INPUT_KEYS)
    if mode != ABLATION_MODE_WITHOUT_COEXPRESSION:
        keys.update(_COEXPRESSION_INPUT_KEYS)
    if mode != ABLATION_MODE_WITHOUT_DE_GENES:
        keys.update(_DE_INPUT_KEYS)
    if mode != ABLATION_MODE_WITHOUT_ANNOTATION:
        keys.update(_ANNOTATION_INPUT_KEYS)
    return keys
