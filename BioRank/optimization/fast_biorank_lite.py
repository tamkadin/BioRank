import numpy as np
import networkx as nx
from scipy import sparse

from BioRank.core.BioRank import CONV_THRESHOLD
from BioRank.graph_weight_computation.PPI_graph_weight_computation import ComputePPIGraphWeight
from BioRank.loader.loader import Loader
from BioRank.personalization_vector_aggregation.p_v_aggregation import PersonalizationVectorAggregation
from BioRank.personalization_vector_creation.biological_personalization_vector_creation import (
    BiologicalPersonalizationVectorCreation,
)
from BioRank.personalization_vector_creation.topological_personalization_vector_creation import (
    TopologicalPersonalizationVectorCreation,
)


class FastBioRankLiteContext:
    """Cached sparse execution path for repeated BioRank Lite Optuna trials."""

    def __init__(
        self,
        input_paths,
        ablation_config,
        cancellation_event=None,
        progress_callback=None,
    ):
        self.input_paths = input_paths
        self.ablation_config = ablation_config
        self.cancellation_event = cancellation_event
        self.progress_callback = progress_callback

        self.PPI = None
        self.CO_expression = None
        self.seed_set = None
        self.secondary_seed_set = None
        self.map__gene__ontologies = None
        self.disease_ontology = None

        self.nodes = []
        self.node_index = {}
        self.universe = set()
        self.ppi_transition = None
        self.co_expression_transition = None
        self.topology_graph = None
        self._personalization_vectors = None

        self._prepare()

    def run(self, alpha, beta):
        self._check_cancelled()
        transition_matrix = self._transition_matrix(beta)
        personalization_vector = self._personalization_vector(alpha)
        teleport_vector = self._personalization_array(personalization_vector)
        page_rank_vector = self._iterate(transition_matrix, teleport_vector)
        return self._rank(page_rank_vector)

    def _prepare(self):
        self._emit("Preparing cached sparse BioRank Lite context...", phase="pipeline")
        self._load_inputs()
        self._prepare_sparse_networks()
        self._prepare_topology_graph()
        self._emit(
            f"Cached sparse context ready: nodes={len(self.nodes)}",
            phase="pipeline",
        )

    def _load_inputs(self):
        self._check_cancelled()
        loader = Loader(
            self.input_paths["ppi_file_path"],
            self.input_paths.get("co_expression_file_path"),
            self.input_paths["seed_file_path"],
            secondary_seed_file_path=self.input_paths.get("secondary_seed_file_path"),
            disease_ontology_file_path=self.input_paths.get("disease_ontology_file_path"),
            map_gene_ontologies_file_path=self.input_paths.get("map__gene__ontologies_file_path"),
            cancellation_event=self.cancellation_event,
        )
        (
            self.PPI,
            self.CO_expression,
            self.seed_set,
            self.secondary_seed_set,
            self.map__gene__ontologies,
            self.disease_ontology,
        ) = loader.run()

        if self.ablation_config["network_weight_flag"]:
            self._check_cancelled()
            self.PPI = ComputePPIGraphWeight(
                self.PPI,
                map__gene__ontologies=self.map__gene__ontologies,
                disease_ontology=self.disease_ontology,
                cancellation_event=self.cancellation_event,
            ).compute_weight_on_graph()

    def _prepare_sparse_networks(self):
        policy = self.ablation_config["matrix_aggregation_policy"]
        if policy == "only_ppi_network":
            self.nodes = list(self.PPI.nodes())
            self.node_index = {node: index for index, node in enumerate(self.nodes)}
            self.universe = set(self.nodes)
            self.ppi_transition = self._normalized_sparse_from_graph(self.PPI, self.universe)
            return

        if policy != "convex_combination":
            raise ValueError(f"Unsupported fast BioRank Lite matrix policy: {policy}")

        self.nodes = list(self.PPI.nodes())
        self.node_index = {node: index for index, node in enumerate(self.nodes)}
        self.universe = set(self.nodes)
        self.ppi_transition = self._normalized_sparse_from_graph(self.PPI, self.universe)
        self.co_expression_transition = self._normalized_sparse_from_graph(
            self.CO_expression,
            self.universe,
        )

    def _prepare_topology_graph(self):
        policy = self.ablation_config["matrix_aggregation_policy"]
        if policy == "only_ppi_network":
            self.topology_graph = self.PPI
            return

        graph = nx.DiGraph()
        graph.add_nodes_from(self.nodes)
        for source, target in self.PPI.edges():
            graph.add_edge(source, target)
        for source, target in self.CO_expression.edges():
            if source in self.universe and target in self.universe:
                graph.add_edge(source, target)
        self.topology_graph = graph

    def _normalized_sparse_from_graph(self, graph, selected_nodes):
        rows = []
        cols = []
        data = []
        for index, source in enumerate(self.nodes):
            if index % 1000 == 0:
                self._check_cancelled()
            if source not in graph:
                continue
            source_index = self.node_index[source]
            targets = [target for target in graph[source] if target in selected_nodes]
            total_weight = sum(graph[source][target].get("weight", 0.0) for target in targets)
            if total_weight <= 0.0:
                continue
            for target in targets:
                weight = graph[source][target].get("weight", 0.0)
                if weight <= 0.0:
                    continue
                rows.append(self.node_index[target])
                cols.append(source_index)
                data.append(weight / total_weight)

        return sparse.csr_matrix(
            (data, (rows, cols)),
            shape=(len(self.nodes), len(self.nodes)),
            dtype=float,
        )

    def _transition_matrix(self, beta):
        policy = self.ablation_config["matrix_aggregation_policy"]
        if policy == "only_ppi_network":
            return self.ppi_transition

        matrix = float(beta) * self.ppi_transition + (1.0 - float(beta)) * self.co_expression_transition
        column_sums = np.asarray(matrix.sum(axis=0)).ravel()
        inverse_sums = np.divide(
            1.0,
            column_sums,
            out=np.zeros_like(column_sums, dtype=float),
            where=column_sums > 0.0,
        )
        return matrix.multiply(inverse_sums).tocsr()

    def _personalization_vector(self, alpha):
        vectors = self._get_personalization_vectors()
        return PersonalizationVectorAggregation(
            vectors,
            universe=self.universe,
            alpha=float(alpha),
        ).run(chosen_policy="Sum")

    def _get_personalization_vectors(self):
        if self._personalization_vectors is not None:
            return self._personalization_vectors

        vectors = []
        policies = self.ablation_config["personalization_vector_creation_policies"]
        for policy in policies:
            if policy == "biological":
                vectors.append(
                    BiologicalPersonalizationVectorCreation(
                        source=self.seed_set,
                        universe=self.universe,
                        disease_ontology=self.disease_ontology,
                        map__gene_name__ontologies=self.map__gene__ontologies,
                    ).run()
                )
            elif policy == "topological":
                vectors.append(
                    TopologicalPersonalizationVectorCreation(
                        self.seed_set,
                        self.universe,
                        G=self.topology_graph,
                        secondary_seed_set=self.secondary_seed_set,
                    ).run()
                )
            else:
                raise ValueError(f"Unsupported personalization policy: {policy}")
        self._personalization_vectors = vectors
        return self._personalization_vectors

    def _personalization_array(self, personalization_vector):
        p_0 = np.zeros(len(self.nodes), dtype=float)
        for node, score in personalization_vector.items():
            index = self.node_index.get(node)
            if index is not None:
                p_0[index] = score
        total = p_0.sum()
        if total > 0.0:
            p_0 /= total
        return p_0

    def _iterate(self, transition_matrix, teleport_vector):
        page_rank = teleport_vector.copy()
        diff_norm = 1.0
        iteration = 0
        while diff_norm > CONV_THRESHOLD and iteration < 1000:
            self._check_cancelled()
            next_page_rank = 0.15 * teleport_vector + 0.85 * transition_matrix.dot(page_rank)
            diff_norm = np.linalg.norm(next_page_rank - page_rank, 1)
            page_rank = next_page_rank
            iteration += 1
        return page_rank

    def _rank(self, page_rank_vector):
        return sorted(
            zip(self.nodes, page_rank_vector.tolist()),
            key=lambda item: item[1],
            reverse=True,
        )

    def _check_cancelled(self):
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise RuntimeError("Operation cancelled.")

    def _emit(self, status, **payload):
        if self.progress_callback is not None:
            self.progress_callback({"status": status, **payload})
