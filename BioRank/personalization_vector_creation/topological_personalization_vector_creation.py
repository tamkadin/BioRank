from BioRank.personalization_vector_creation.pv_creation import PersonalizationVectorCreation


class TopologicalPersonalizationVectorCreation(PersonalizationVectorCreation):
    def __init__(self, source, universe, G, secondary_seed_set):
        self.universe = universe
        self.G = G
        self.selected_seed_set = self.universe.intersection(source)
        self.source_not_in_G = source.difference(self.selected_seed_set)
        self.secondary_seed_set = secondary_seed_set

    def run(self):
        return self._set_up_topological_personalization_vector()

    def _get_radius_2_neighbors(self, node):
        neighbors = set(self.G[node])
        radius_2_neighbors = set()

        for neighbor in neighbors:
            radius_2_neighbors.update(self.G[neighbor])

        radius_2_neighbors = radius_2_neighbors.difference({node})
        return radius_2_neighbors.difference(neighbors)

    def _compute_topological_node_probability(self, node, phi):
        del phi  # Kept in the signature for compatibility with the original formula inputs.

        neighbors = set(self.G[node])
        radius_2_neighbors = self._get_radius_2_neighbors(node)

        radius_1_score = self._safe_ratio(
            len(neighbors.intersection(self.selected_seed_set)),
            len(neighbors),
        )
        radius_2_score = self._safe_ratio(
            len(radius_2_neighbors.intersection(self.selected_seed_set)),
            len(radius_2_neighbors),
        )

        return radius_1_score + radius_2_score

    def _set_up_topological_personalization_vector(self):
        assert isinstance(
            self.secondary_seed_set,
            dict,
        ), "Secondary seed set is not a dictionary with key (string) and value (float)"
        assert (
            self.G is not None and self.secondary_seed_set is not None
        ), "Not enough input parameters to compute topological personalization vector"

        # Build the expression/topology-based part of the personalization vector.
        personalization_vector = {}
        for node in self.universe:
            if node in self.secondary_seed_set:
                phi = self.secondary_seed_set[node]
                personalization_vector[node] = self._compute_topological_node_probability(node, phi)
            else:
                personalization_vector[node] = 0.0

        l_1_personalization_vector = sum(personalization_vector.values())
        assert l_1_personalization_vector > 0.0, "topological personalization vector is the null vector"

        return {
            node: score / l_1_personalization_vector
            for node, score in personalization_vector.items()
        }

    def _safe_ratio(self, numerator, denominator):
        if denominator == 0:
            return 0.0
        return numerator / denominator
