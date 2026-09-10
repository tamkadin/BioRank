class PersonalizationVectorAggregation:
    def __init__(self, personalization_vectors, universe, alpha):
        self.alpha = alpha
        self.universe = universe
        self.personalization_vectors = list(personalization_vectors)

    def run(self, chosen_policy="Sum"):
        if not self.personalization_vectors:
            raise ValueError("At least one personalization vector is required.")

        if len(self.personalization_vectors) == 1:
            return self._normalize(self.personalization_vectors[0])

        aggregated = {node: 0.0 for node in self.universe}
        for node in self.universe:
            for index, vector in enumerate(self.personalization_vectors):
                if index == 0:
                    aggregated[node] += self.alpha * vector[node]
                elif chosen_policy == "Sum":
                    aggregated[node] += (1 - self.alpha) * vector[node]
                elif chosen_policy == "Product":
                    aggregated[node] *= vector[node]
                else:
                    raise ValueError(f"Unsupported personalization aggregation policy: {chosen_policy}")

        return self._normalize(aggregated)

    def _normalize(self, vector):
        values = {node: float(vector[node]) for node in self.universe}
        l_1 = sum(values.values())
        if l_1 <= 0.0:
            raise ValueError("Personalization vector must have a positive L1 norm.")
        return {node: value / l_1 for node, value in values.items()}
