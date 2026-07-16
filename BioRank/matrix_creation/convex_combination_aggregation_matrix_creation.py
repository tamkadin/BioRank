import networkx as nx

from BioRank.matrix_creation.matrix_aggregation import MatrixAggregation


class ConvexCombinationMatrixAggregationCreation(MatrixAggregation):
    def __init__(self, PPI_network, CO_expression_network, beta, cancellation_event=None):
        self.PPI = PPI_network
        self.CO_expression_network = CO_expression_network
        self.beta = beta
        self.cancellation_event = cancellation_event

        assert (
            self.PPI is not None and self.CO_expression_network is not None
        ), "PPI or CO-Expression network are None."

    def _check_cancelled(self):
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise RuntimeError("Operation cancelled.")

    def choose_policy(self, ppi_nodes, co_expression_nodes, chosen_policy="PPI_network"):
        if chosen_policy == "Intersection":
            return ppi_nodes.intersection(co_expression_nodes)
        if chosen_policy == "PPI_network":
            return ppi_nodes
        raise ValueError(f"Unsupported aggregation node policy: {chosen_policy}")

    def run(self, chosen_policy):
        self._check_cancelled()
        ppi_nodes = set(self.PPI.nodes())
        co_expression_nodes = set(self.CO_expression_network.nodes())
        selected_nodes = self.choose_policy(
            ppi_nodes,
            co_expression_nodes,
            chosen_policy=chosen_policy,
        )

        ppi_sub_network = self.PPI.subgraph(selected_nodes)
        co_expression_sub_network = self.CO_expression_network.subgraph(selected_nodes)

        self._check_cancelled()
        normalized_ppi = self._normalize_graph(ppi_sub_network)
        self._check_cancelled()
        normalized_co_expression = self._normalize_graph(co_expression_sub_network)
        self._check_cancelled()
        aggregated_graph = self._aggregate_adjacency_matrix(
            normalized_ppi,
            normalized_co_expression,
            selected_nodes,
        )

        return aggregated_graph, set(aggregated_graph.nodes())

    def _aggregate_adjacency_matrix(self, PPI_network, CO_expression_network, selected_nodes):
        final_graph = nx.DiGraph()

        # PPI contributes beta * normalized PPI weight.
        for index, (source, target) in enumerate(PPI_network.edges()):
            if index % 10000 == 0:
                self._check_cancelled()
            ppi_weight = PPI_network[source][target]["weight"]
            if ppi_weight > 0.0:
                final_graph.add_edge(source, target, weight=self.beta * ppi_weight)

        # Co-expression contributes (1 - beta) * normalized co-expression weight.
        for index, (source, target) in enumerate(CO_expression_network.edges()):
            if index % 10000 == 0:
                self._check_cancelled()
            co_expression_weight = CO_expression_network[source][target]["weight"]
            weighted_score = (1 - self.beta) * co_expression_weight

            if final_graph.has_edge(source, target):
                final_graph[source][target]["weight"] += weighted_score
            elif source in selected_nodes and target in selected_nodes and co_expression_weight > 0.0:
                final_graph.add_edge(source, target, weight=weighted_score)

        return final_graph

    def _normalize_graph(self, graph):
        normalized_graph = nx.DiGraph()

        for index, source in enumerate(graph):
            if index % 1000 == 0:
                self._check_cancelled()
            total_weight = sum(graph[source][target]["weight"] for target in graph[source])
            for target in graph[source]:
                normalized_weight = 0.0
                if total_weight != 0.0:
                    normalized_weight = graph[source][target]["weight"] / total_weight
                normalized_graph.add_edge(source, target, weight=normalized_weight)

        return normalized_graph
