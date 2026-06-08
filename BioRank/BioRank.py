import csv
import time

from BioRank.core.BioRank import BioRank
from BioRank.core.core import RandomWalkWithRestartCore
from BioRank.core.page_rank_ori import PageRankOri
from BioRank.graph_weight_computation.PPI_graph_weight_computation import ComputePPIGraphWeight
from BioRank.loader.loader import Loader
from BioRank.matrix_creation.convex_combination_aggregation_matrix_creation import (
    ConvexCombinationMatrixAggregationCreation,
)
from BioRank.personalization_vector_aggregation.p_v_aggregation import (
    PersonalizationVectorAggregation,
)
from BioRank.personalization_vector_creation.biological_personalization_vector_creation import (
    BiologicalPersonalizationVectorCreation,
)
from BioRank.personalization_vector_creation.default_personalization_vector_creation import (
    DefaultPersonalizationVectorCreation,
)
from BioRank.personalization_vector_creation.topological_personalization_vector_creation import (
    TopologicalPersonalizationVectorCreation,
)


ALGORITHM_BIORANK = "biorank"
ALGORITHM_ORIGINAL_PAGERANK = "pagerank"
ALGORITHM_RANDOM_WALK = "random_walk"


class BioRankCancerGeneRanking:
    """Run the BioRank gene-prioritization pipeline.

    The default constructor behavior is kept backward-compatible: creating the
    object runs the full pipeline. The GUI can pass auto_run=False to stop after
    network construction, show the graph preview, then call execute_ranking().
    """

    def __init__(
        self,
        seed_file_path,
        ppi_file_path=None,
        co_expression_file_path=None,
        disease_ontology_file_path=None,
        map__gene__ontologies_file_path=None,
        secondary_seed_file_path=None,
        matrix_aggregation_policy="convex_combination",
        personalization_vector_creation_policies=None,
        personalization_vector_aggregation_policy="Sum",
        alpha=0.2,
        beta=0.2,
        network_weight_flag=True,
        output_file_path=None,
        algorithm=None,
        auto_run=True,
    ):
        self.seed_file_path = seed_file_path
        self.ppi_file_path = ppi_file_path
        self.co_expression_file_path = co_expression_file_path
        self.disease_ontology_file_path = disease_ontology_file_path
        self.map__gene__ontologies_file_path = map__gene__ontologies_file_path
        self.secondary_seed_file_path = secondary_seed_file_path
        self.matrix_aggregation_policy = matrix_aggregation_policy
        self.personalization_vector_creation_policies = (
            personalization_vector_creation_policies or ["biological", "topological"]
        )
        self.personalization_vector_aggregation_policy = personalization_vector_aggregation_policy
        self.alpha = alpha
        self.beta = beta
        self.network_weight_flag = network_weight_flag
        self.output_file_path = output_file_path
        self.algorithm = algorithm or ALGORITHM_RANDOM_WALK

        self.file_loader_step = None
        self.compute_ppi_weight = None
        self.personalization_vector_aggregation_step = None

        self.PPI = None
        self.CO_expression = None
        self.seed_set = None
        self.secondary_seed_set = None
        self.map__gene__ontologies = None
        self.disease_ontology = None
        self.G = None
        self.V = None
        self.ranked_list = []
        self.total_runtime_seconds = None
        self._pipeline_start_time = None

        if auto_run:
            self.run()

    def run(self):
        self._pipeline_start_time = time.perf_counter()
        self.prepare_network()
        self.execute_ranking()
        return self.ranked_list

    def prepare_network(self):
        """Load input data, compute PPI weights, and build the final graph."""
        self._pipeline_start_time = self._pipeline_start_time or time.perf_counter()

        # Pipeline phase 1: load all biological inputs from user-selected files.
        t0 = time.perf_counter()
        print("Loading networks...")
        self.file_loader_step = Loader(
            self.ppi_file_path,
            self.co_expression_file_path,
            self.seed_file_path,
            secondary_seed_file_path=self.secondary_seed_file_path,
            disease_ontology_file_path=self.disease_ontology_file_path,
            map_gene_ontologies_file_path=self.map__gene__ontologies_file_path,
        )
        (
            self.PPI,
            self.CO_expression,
            self.seed_set,
            self.secondary_seed_set,
            self.map__gene__ontologies,
            self.disease_ontology,
        ) = self.file_loader_step.run()
        print("Loading time:", time.perf_counter() - t0)
        print()

        # Pipeline phase 2: enrich PPI edges using disease ontology evidence.
        if self.network_weight_flag:
            t0 = time.perf_counter()
            print("Weighting networks...")
            self.compute_ppi_weight = ComputePPIGraphWeight(
                self.PPI,
                map__gene__ontologies=self.map__gene__ontologies,
                disease_ontology=self.disease_ontology,
            )
            self.PPI = self.compute_ppi_weight.compute_weight_on_graph()
            print("Weighting networks computation time:", time.perf_counter() - t0)
            print()

        # Pipeline phase 3: aggregate PPI and co-expression into the graph used by ranking.
        t0 = time.perf_counter()
        print("Computing aggregation with policy:", self.matrix_aggregation_policy, "...")
        self.G, self.V = self.compute_matrix_aggregation(
            self.PPI,
            self.CO_expression,
            self.matrix_aggregation_policy,
        )
        print(f"Graph has {self.G.number_of_nodes()} nodes and {self.G.number_of_edges()} edges")
        print("Time for computing aggregation matrix:", time.perf_counter() - t0)
        print()

        return self.G, self.V

    def execute_ranking(self):
        """Compute personalization vectors and execute the selected ranking core."""
        if self.G is None or self.V is None:
            self.prepare_network()

        # Original PageRank uses a uniform prior, so it does not need the
        # biological/topological personalization-vector stages.
        if self.algorithm == ALGORITHM_ORIGINAL_PAGERANK:
            t0 = time.perf_counter()
            print("Executing original PageRank...")
            self.ranked_list = list(PageRankOri(self.G).run())
            print("Time for executing original PageRank:", time.perf_counter() - t0)

            if self.output_file_path is not None:
                self.save_ranked_list(self.output_file_path)

            if self._pipeline_start_time is not None:
                self.total_runtime_seconds = time.perf_counter() - self._pipeline_start_time
                print(f"Done! Total execution time: {self.total_runtime_seconds:.2f} seconds.")

            return self.ranked_list

        # Pipeline phase 4: build the personalization vector from topology and biology.
        t0 = time.perf_counter()
        print(
            "Computing personalization vectors with policies:",
            ", ".join(self.personalization_vector_creation_policies),
            "...",
        )
        personalization_vectors = self.compute_personalization_vectors(
            seed_set=self.seed_set,
            V=self.V,
            disease_ontology=self.disease_ontology,
            map__gene_name__ontologies=self.map__gene__ontologies,
            universe_ontologies=None,
            G=self.G,
            secondary_seed_set=self.secondary_seed_set,
            chosen_policies=self.personalization_vector_creation_policies,
        )
        print("Time for computing personalization vectors:", time.perf_counter() - t0)
        print()

        t0 = time.perf_counter()
        print(
            "Aggregating personalization vectors with policy:",
            self.personalization_vector_aggregation_policy,
            "...",
        )
        self.personalization_vector_aggregation_step = PersonalizationVectorAggregation(
            personalization_vectors,
            universe=self.V,
            alpha=self.alpha,
        )
        p_0 = self.personalization_vector_aggregation_step.run(
            chosen_policy=self.personalization_vector_aggregation_policy
        )

        # Pipeline phase 5: run the selected graph-ranking algorithm.
        t0 = time.perf_counter()
        print("Executing ranking algorithm...")
        core = self._create_ranking_core(p_0)
        self.ranked_list = list(core.run())
        print("Time for executing ranking algorithm:", time.perf_counter() - t0)

        if self.output_file_path is not None:
            self.save_ranked_list(self.output_file_path)

        if self._pipeline_start_time is not None:
            self.total_runtime_seconds = time.perf_counter() - self._pipeline_start_time
            print(f"Done! Total execution time: {self.total_runtime_seconds:.2f} seconds.")

        return self.ranked_list

    def _create_ranking_core(self, personalization_vector):
        if self.algorithm == ALGORITHM_BIORANK:
            return BioRank(personalization_vector, self.G)
        return RandomWalkWithRestartCore(personalization_vector, self.G)

    def compute_personalization_vectors(
        self,
        seed_set,
        V,
        disease_ontology=None,
        map__gene_name__ontologies=None,
        universe_ontologies=None,
        G=None,
        secondary_seed_set=None,
        chosen_policies=None,
    ):
        chosen_policies = chosen_policies or ["biological"]
        personalization_vectors = []

        if "default" in chosen_policies:
            personalization_vector_creation_step = DefaultPersonalizationVectorCreation(seed_set, V)
            personalization_vectors.append(personalization_vector_creation_step.run())

        if "biological" in chosen_policies:
            personalization_vector_creation_step = BiologicalPersonalizationVectorCreation(
                source=seed_set,
                universe=V,
                disease_ontology=disease_ontology,
                map__gene_name__ontologies=map__gene_name__ontologies,
            )
            personalization_vectors.append(personalization_vector_creation_step.run())

        if "topological" in chosen_policies:
            personalization_vector_creation_step = TopologicalPersonalizationVectorCreation(
                seed_set,
                V,
                G=G,
                secondary_seed_set=secondary_seed_set,
            )
            personalization_vectors.append(personalization_vector_creation_step.run())

        return personalization_vectors

    def compute_matrix_aggregation(
        self,
        PPI_network,
        CO_expression_network,
        matrix_aggregation_policy="convex_combination",
    ):
        if matrix_aggregation_policy == "convex_combination":
            matrix_creation_step = ConvexCombinationMatrixAggregationCreation(
                PPI_network,
                CO_expression_network,
                self.beta,
            )
            return matrix_creation_step.run(chosen_policy="PPI_network")

        if matrix_aggregation_policy == "only_ppi_network":
            return PPI_network, set(PPI_network.nodes())

        if matrix_aggregation_policy == "only_co_expression_network":
            return CO_expression_network, set(CO_expression_network.nodes())

        raise ValueError(f"Unsupported matrix aggregation policy: {matrix_aggregation_policy}")

    def get_network_summary(self):
        if self.G is None:
            return {"nodes": 0, "edges": 0}
        return {
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges(),
        }

    def iter_network_nodes(self, limit=None):
        nodes = sorted(self.G.nodes()) if self.G is not None else []
        if limit is not None:
            nodes = nodes[:limit]
        return nodes

    def iter_network_edges(self, limit=None):
        if self.G is None:
            return []

        edges = sorted(
            (
                source,
                target,
                data.get("weight", 0.0),
            )
            for source, target, data in self.G.edges(data=True)
        )
        if limit is not None:
            edges = edges[:limit]
        return edges

    def save_network(self, file_path):
        with open(file_path, "w", newline="", encoding="utf-8") as fp:
            csv_writer = csv.writer(fp, delimiter="\t")
            csv_writer.writerow(["Source", "Target", "Weight"])
            for source, target, weight in self.iter_network_edges():
                csv_writer.writerow([source, target, weight])

    def save_ranked_list(self, file_path):
        ranked_list = [[item[0], item[1]] for item in self.ranked_list]
        with open(file_path, "w", newline="", encoding="utf-8") as fp:
            csv_writer = csv.writer(fp, delimiter="\t")
            csv_writer.writerow(["GeneNames", "Score"])
            csv_writer.writerows(ranked_list)
