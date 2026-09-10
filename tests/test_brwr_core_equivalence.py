import unittest

import networkx as nx
import numpy as np
from sklearn.preprocessing import normalize

from BioRank.core.core import CONV_THRESHOLD, RandomWalkWithRestartCore, RandomWalkWithRestartOriginal


class LegacyRandomWalkWithRestartCore:
    def __init__(self, personalization_vector, G, restart_prob=0.25):
        self.restart_prob = restart_prob
        self.personalization_vector = personalization_vector
        self.G = G
        adjacency_matrix_not_normalized = nx.adjacency_matrix(self.G,)
        self.normalized_adjacency_matrix = normalize(
            adjacency_matrix_not_normalized,
            norm="l1",
            axis=0,
        ).todense()

    def run(self):
        p_0 = self._set_up_p0()
        diff_norm = 1
        p_t = np.copy(p_0)
        while diff_norm > CONV_THRESHOLD:
            epsilon = np.squeeze(np.asarray(np.dot(self.normalized_adjacency_matrix, p_t)))
            p_t_1 = epsilon * (1 - self.restart_prob) + p_0 * self.restart_prob
            diff_norm = np.linalg.norm(np.subtract(p_t_1, p_t), 1)
            p_t = p_t_1
        return sorted(zip(self.G.nodes(), p_t.tolist()), key=lambda x: x[1], reverse=True)

    def _set_up_p0(self):
        p_0 = [0] * self.G.number_of_nodes()
        for source_id, score in self.personalization_vector.items():
            source_index = list(self.G.nodes()).index(source_id)
            p_0[source_index] = score
        return np.array(p_0)


class BrwrCoreEquivalenceTest(unittest.TestCase):
    def test_sparse_brwr_matches_legacy_dense_results(self):
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
        legacy = dict(LegacyRandomWalkWithRestartCore(personalization, graph).run())
        current = dict(RandomWalkWithRestartCore(personalization, graph).run())

        self.assertEqual(set(current), set(legacy))
        for node, legacy_score in legacy.items():
            self.assertAlmostEqual(current[node], legacy_score, places=12)

    def test_optional_max_iter_limits_iterations_when_explicitly_requested(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "B", weight=1.0)
        graph.add_edge("B", "A", weight=1.0)
        personalization = {"A": 1.0, "B": 0.0}

        core = RandomWalkWithRestartCore(
            personalization,
            graph,
            convergence_threshold=0.0,
            max_iter=1,
        )
        ranked = list(core.run())

        self.assertEqual(len(ranked), 2)
        self.assertEqual({node for node, _score in ranked}, {"A", "B"})

    def test_original_brwr_mode_matches_legacy_dense_results(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "B", weight=2.0)
        graph.add_edge("B", "A", weight=1.0)
        graph.add_edge("B", "C", weight=3.0)
        graph.add_edge("C", "A", weight=4.0)
        personalization = {"A": 1.0, "B": 0.5, "C": 0.25}

        legacy = dict(LegacyRandomWalkWithRestartCore(personalization, graph).run())
        original = dict(RandomWalkWithRestartOriginal(personalization, graph).run())

        self.assertEqual(set(original), set(legacy))
        for node, legacy_score in legacy.items():
            self.assertAlmostEqual(original[node], legacy_score, places=12)


if __name__ == "__main__":
    unittest.main()
