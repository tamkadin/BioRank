import unittest

from BioRank.personalization_vector_aggregation.p_v_aggregation import (
    PersonalizationVectorAggregation,
)


class PersonalizationVectorAggregationTest(unittest.TestCase):
    def test_single_vector_does_not_depend_on_alpha(self):
        vector = {"A": 2.0, "B": 1.0}

        for alpha in (0.0, 0.25, 1.0):
            with self.subTest(alpha=alpha):
                result = PersonalizationVectorAggregation(
                    [vector],
                    universe={"A", "B"},
                    alpha=alpha,
                ).run()

                self.assertAlmostEqual(result["A"], 2.0 / 3.0)
                self.assertAlmostEqual(result["B"], 1.0 / 3.0)

    def test_two_vectors_keep_alpha_convex_combination(self):
        result = PersonalizationVectorAggregation(
            [{"A": 1.0, "B": 0.0}, {"A": 0.0, "B": 1.0}],
            universe={"A", "B"},
            alpha=0.75,
        ).run()

        self.assertAlmostEqual(result["A"], 0.75)
        self.assertAlmostEqual(result["B"], 0.25)


if __name__ == "__main__":
    unittest.main()
