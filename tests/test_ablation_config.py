import unittest

from BioRank.optimization.ablation_config import (
    ABLATION_MODE_FULL,
    ABLATION_MODE_WITHOUT_ANNOTATION,
    ABLATION_MODE_WITHOUT_COEXPRESSION,
    ABLATION_MODE_WITHOUT_DE_GENES,
    ablation_pipeline_config,
    required_input_keys,
)


class AblationConfigTest(unittest.TestCase):
    def test_full_biorank_v2_uses_all_evidence_sources(self):
        config = ablation_pipeline_config(ABLATION_MODE_FULL)

        self.assertEqual(config["matrix_aggregation_policy"], "convex_combination")
        self.assertEqual(
            config["personalization_vector_creation_policies"],
            ["biological", "topological"],
        )
        self.assertTrue(config["network_weight_flag"])
        self.assertTrue(config["alpha_used"])
        self.assertTrue(config["beta_used"])
        self.assertIsNone(config["fixed_alpha"])
        self.assertIsNone(config["fixed_beta"])
        self.assertIn("co_expression_file_path", required_input_keys(ABLATION_MODE_FULL))
        self.assertIn("secondary_seed_file_path", required_input_keys(ABLATION_MODE_FULL))
        self.assertIn("disease_ontology_file_path", required_input_keys(ABLATION_MODE_FULL))

    def test_without_de_genes_removes_topological_personalization(self):
        config = ablation_pipeline_config(ABLATION_MODE_WITHOUT_DE_GENES)

        self.assertEqual(config["personalization_vector_creation_policies"], ["biological"])
        self.assertFalse(config["alpha_used"])
        self.assertTrue(config["beta_used"])
        self.assertEqual(config["fixed_alpha"], 1.0)
        self.assertNotIn(
            "secondary_seed_file_path",
            required_input_keys(ABLATION_MODE_WITHOUT_DE_GENES),
        )

    def test_without_coexpression_uses_ppi_only_network(self):
        config = ablation_pipeline_config(ABLATION_MODE_WITHOUT_COEXPRESSION)

        self.assertEqual(config["matrix_aggregation_policy"], "only_ppi_network")
        self.assertTrue(config["alpha_used"])
        self.assertFalse(config["beta_used"])
        self.assertEqual(config["fixed_beta"], 1.0)
        self.assertNotIn(
            "co_expression_file_path",
            required_input_keys(ABLATION_MODE_WITHOUT_COEXPRESSION),
        )

    def test_without_annotation_removes_biological_personalization_and_ppi_weighting(self):
        config = ablation_pipeline_config(ABLATION_MODE_WITHOUT_ANNOTATION)

        self.assertEqual(config["personalization_vector_creation_policies"], ["topological"])
        self.assertFalse(config["network_weight_flag"])
        self.assertFalse(config["alpha_used"])
        self.assertTrue(config["beta_used"])
        self.assertEqual(config["fixed_alpha"], 0.0)
        self.assertNotIn(
            "map__gene__ontologies_file_path",
            required_input_keys(ABLATION_MODE_WITHOUT_ANNOTATION),
        )
        self.assertNotIn(
            "disease_ontology_file_path",
            required_input_keys(ABLATION_MODE_WITHOUT_ANNOTATION),
        )


if __name__ == "__main__":
    unittest.main()
