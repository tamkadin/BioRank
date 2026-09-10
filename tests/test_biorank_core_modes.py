import unittest

import networkx as nx

from BioRank.core.BioRank import BioRank, BioRankLite


class BioRankCoreModesTest(unittest.TestCase):
    def test_lite_and_original_match_on_small_weighted_graph(self):
        graph = nx.DiGraph()
        for source, target, weight in (
            ("A", "B", 2.0),
            ("A", "C", 1.0),
            ("B", "C", 3.0),
            ("C", "A", 4.0),
            ("C", "D", 2.0),
            ("D", "A", 1.0),
            ("D", "B", 0.5),
        ):
            graph.add_edge(source, target, weight=weight)

        personalization = {"A": 2.0, "B": 1.0, "C": 0.5, "D": 0.25}
        original = dict(BioRank(personalization, graph, max_iter=1000).run())
        lite = dict(BioRankLite(personalization, graph, max_iter=1000).run())

        self.assertEqual(set(original), set(lite))
        for node, original_score in original.items():
            self.assertAlmostEqual(lite[node], original_score, places=12)


if __name__ == "__main__":
    unittest.main()
