import networkx as nx

from BioRank.matrix_creation.matrix_aggregation import MatrixAggregation


class ConvexCombinationMatrixAggregationCreation(MatrixAggregation):
    def __init__(self, PPI_network, CO_expression_network, beta):
        self.PPI = PPI_network
        self.CO_expression_network = CO_expression_network
        self.beta = beta

        assert (
            self.PPI is not None and self.CO_expression_network is not None
        ), "PPI or CO-Expression network are None."

    def choose_policy(self, ppi_nodes, co_expression_nodes, chosen_policy="PPI_network"):
        if chosen_policy == "Intersection":
            return ppi_nodes.intersection(co_expression_nodes)
        if chosen_policy == "PPI_network":
            return ppi_nodes
        raise ValueError(f"Unsupported aggregation node policy: {chosen_policy}")

    def run(self, chosen_policy):
        ppi_nodes = set(self.PPI.nodes())
        co_expression_nodes = set(self.CO_expression_network.nodes())
        selected_nodes = self.choose_policy(
            ppi_nodes,
            co_expression_nodes,
            chosen_policy=chosen_policy,
        )

        ppi_sub_network = self.PPI.subgraph(selected_nodes)
        co_expression_sub_network = self.CO_expression_network.subgraph(selected_nodes)

        normalized_ppi = self._normalize_graph(ppi_sub_network)
        normalized_co_expression = self._normalize_graph(co_expression_sub_network)
        aggregated_graph = self._aggregate_adjacency_matrix(
            normalized_ppi,
            normalized_co_expression,
            selected_nodes,
        )

        return aggregated_graph, set(aggregated_graph.nodes())

    def _aggregate_adjacency_matrix(self, PPI_network, CO_expression_network, selected_nodes):
        final_graph = nx.DiGraph()

        # PPI contributes beta * normalized PPI weight.
        for source, target in PPI_network.edges():
            ppi_weight = PPI_network[source][target]["weight"]
            if ppi_weight > 0.0:
                final_graph.add_edge(source, target, weight=self.beta * ppi_weight)

        # Co-expression contributes (1 - beta) * normalized co-expression weight.
        for source, target in CO_expression_network.edges():
            co_expression_weight = CO_expression_network[source][target]["weight"]
            weighted_score = (1 - self.beta) * co_expression_weight

            if final_graph.has_edge(source, target):
                final_graph[source][target]["weight"] += weighted_score
            elif source in selected_nodes and target in selected_nodes and co_expression_weight > 0.0:
                final_graph.add_edge(source, target, weight=weighted_score)

        return final_graph

    def _normalize_graph(self, graph):
        normalized_graph = nx.DiGraph()

        for source in graph:
            total_weight = sum(graph[source][target]["weight"] for target in graph[source])
            for target in graph[source]:
                normalized_weight = 0.0
                if total_weight != 0.0:
                    normalized_weight = graph[source][target]["weight"] / total_weight
                normalized_graph.add_edge(source, target, weight=normalized_weight)

        return normalized_graph
