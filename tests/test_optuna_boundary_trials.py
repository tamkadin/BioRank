import unittest

from BioRank.optimization.biorank_alpha_beta_optimizer import BioRankAlphaBetaOptimizer
from BioRank.optimization.ablation_config import (
    ABLATION_MODE_FULL,
    ABLATION_MODE_WITHOUT_ANNOTATION,
    ABLATION_MODE_WITHOUT_COEXPRESSION,
    ABLATION_MODE_WITHOUT_DE_GENES,
)


class OptunaBoundaryTrialsTest(unittest.TestCase):
    def _optimizer(
        self,
        alpha_range=(0.0, 1.0),
        beta_range=(0.0, 1.0),
        n_trials=4,
        ablation_mode=ABLATION_MODE_FULL,
    ):
        return BioRankAlphaBetaOptimizer(
            cancer_type="TEST",
            input_paths={},
            validation_file_path="",
            validation_gene_column="Gene",
            gene_mapping_file_path="",
            alpha_range=alpha_range,
            beta_range=beta_range,
            n_trials=n_trials,
            metric_config={"recall_k": 100, "ndcg_k": 100, "precision_k": 15},
            output_dir="",
            ablation_mode=ablation_mode,
        )

    def test_full_range_queues_exact_zero_and_one_boundary_combinations(self):
        optimizer = self._optimizer()

        self.assertEqual(
            optimizer._boundary_param_sets(),
            [
                {"alpha": 0.0, "beta": 0.0},
                {"alpha": 0.0, "beta": 1.0},
                {"alpha": 1.0, "beta": 0.0},
                {"alpha": 1.0, "beta": 1.0},
            ],
        )

    def test_boundary_trials_are_limited_by_requested_trial_count(self):
        optimizer = self._optimizer(n_trials=2)

        self.assertEqual(
            optimizer._boundary_param_sets()[: optimizer.n_trials],
            [
                {"alpha": 0.0, "beta": 0.0},
                {"alpha": 0.0, "beta": 1.0},
            ],
        )

    def test_without_de_only_queues_beta_boundaries(self):
        optimizer = self._optimizer(ablation_mode=ABLATION_MODE_WITHOUT_DE_GENES)

        self.assertEqual(optimizer._boundary_param_sets(), [{"beta": 0.0}, {"beta": 1.0}])

    def test_without_coexpression_only_queues_alpha_boundaries(self):
        optimizer = self._optimizer(ablation_mode=ABLATION_MODE_WITHOUT_COEXPRESSION)

        self.assertEqual(optimizer._boundary_param_sets(), [{"alpha": 0.0}, {"alpha": 1.0}])

    def test_without_annotation_only_queues_beta_boundaries(self):
        optimizer = self._optimizer(ablation_mode=ABLATION_MODE_WITHOUT_ANNOTATION)

        self.assertEqual(optimizer._boundary_param_sets(), [{"beta": 0.0}, {"beta": 1.0}])

    def test_trial_parameters_only_suggest_active_dimensions(self):
        class Trial:
            def __init__(self):
                self.suggested = []

            def suggest_float(self, name, low, high):
                self.suggested.append(name)
                return (low + high) / 2

        cases = (
            (ABLATION_MODE_FULL, ["alpha", "beta"], (0.5, 0.5)),
            (ABLATION_MODE_WITHOUT_DE_GENES, ["beta"], (1.0, 0.5)),
            (ABLATION_MODE_WITHOUT_COEXPRESSION, ["alpha"], (0.5, 1.0)),
            (ABLATION_MODE_WITHOUT_ANNOTATION, ["beta"], (0.0, 0.5)),
        )
        for mode, expected_dimensions, expected_values in cases:
            with self.subTest(mode=mode):
                optimizer = self._optimizer(ablation_mode=mode)
                trial = Trial()

                self.assertEqual(optimizer._trial_parameters(trial), expected_values)
                self.assertEqual(trial.suggested, expected_dimensions)

    def test_inactive_parameters_are_missing_from_reported_results(self):
        without_de = self._optimizer(ablation_mode=ABLATION_MODE_WITHOUT_DE_GENES)
        without_coexpression = self._optimizer(ablation_mode=ABLATION_MODE_WITHOUT_COEXPRESSION)

        self.assertIsNone(without_de._reported_parameter("alpha", 1.0))
        self.assertEqual(without_de._reported_parameter("beta", 0.4), 0.4)
        self.assertEqual(without_de._parameter_filename(None, 0.4), "aNA_b0.4000")
        self.assertEqual(without_coexpression._reported_parameter("alpha", 0.6), 0.6)
        self.assertIsNone(without_coexpression._reported_parameter("beta", 1.0))
        self.assertEqual(without_coexpression._parameter_filename(0.6, None), "a0.6000_bNA")


if __name__ == "__main__":
    unittest.main()
