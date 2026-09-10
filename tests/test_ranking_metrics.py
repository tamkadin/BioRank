import unittest

from BioRank.metrics.ranking_metrics import (
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    source_balance,
)


class RankingMetricsTest(unittest.TestCase):
    def test_recall_precision_and_ndcg(self):
        ranked = ["A", "B", "C", "D"]
        truth = {"B", "D"}

        self.assertEqual(recall_at_k(ranked, truth, 2), 0.5)
        self.assertEqual(precision_at_k(ranked, truth, 2), 0.5)
        self.assertGreaterEqual(ndcg_at_k(ranked, truth, 4), 0.0)
        self.assertLessEqual(ndcg_at_k(ranked, truth, 4), 1.0)

    def test_source_balance(self):
        self.assertAlmostEqual(source_balance(0.5, 0.5), 1.0)
        self.assertAlmostEqual(source_balance(1.0, 1.0), 0.0)


if __name__ == "__main__":
    unittest.main()
