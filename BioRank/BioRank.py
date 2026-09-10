import csv
import itertools
import time

from BioRank.core.BioRank import BioRank, BioRankLite
from BioRank.core.core import RandomWalkWithRestartCore, RandomWalkWithRestartOriginal
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
ALGORITHM_BIORANK_LITE = "biorank_lite"
ALGORITHM_BRWR = "brwr"
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
        cancellation_event=None,
        progress_callback=None,
        prepared_input_cache=None,
        matrix_aggregation_cache=None,
        personalization_vector_cache=None,
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
        self.cancellation_event = cancellation_event
        self.progress_callback = progress_callback
        self.prepared_input_cache = prepared_input_cache
        self.matrix_aggregation_cache = matrix_aggregation_cache
        self.personalization_vector_cache = personalization_vector_cache

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

    def _check_cancelled(self):
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise RuntimeError("Operation cancelled.")

    def _emit_progress(self, status, **payload):
        if self.progress_callback is not None:
            self.progress_callback({"status": status, **payload})

    def run(self):
        self._pipeline_start_time = time.perf_counter()
        self.prepare_network()
        self.execute_ranking()
        return self.ranked_list

    def prepare_network(self):
        """Load input data, compute PPI weights, and build the final graph."""
        self._pipeline_start_time = self._pipeline_start_time or time.perf_counter()

        # Pipeline phase 1: load all biological inputs from user-selected files.
        self._check_cancelled()
        input_cache_key = self._prepared_input_cache_key()
        cached_inputs = (
            self.prepared_input_cache.get(input_cache_key)
            if self.prepared_input_cache is not None
            else None
        )
        if cached_inputs is not None:
            (
                self.PPI,
                self.CO_expression,
                self.seed_set,
                self.secondary_seed_set,
                self.map__gene__ontologies,
                self.disease_ontology,
            ) = cached_inputs
            self._emit_progress("Reusing loaded and weighted inputs.", phase="load_inputs")
            print("Reusing loaded and weighted inputs.")
        else:
            t0 = time.perf_counter()
            self._emit_progress("Loading networks...", phase="load_inputs")
            print("Loading networks...")
            self.file_loader_step = Loader(
                self.ppi_file_path,
                self.co_expression_file_path,
                self.seed_file_path,
                secondary_seed_file_path=self.secondary_seed_file_path,
                disease_ontology_file_path=self.disease_ontology_file_path,
                map_gene_ontologies_file_path=self.map__gene__ontologies_file_path,
                cancellation_event=self.cancellation_event,
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
        ppi_nodes = self.PPI.number_of_nodes() if self.PPI is not None else 0
        co_expression_nodes = self.CO_expression.number_of_nodes() if self.CO_expression is not None else 0
        self._emit_progress(
            f"Loaded inputs: PPI nodes={ppi_nodes}, co-expression nodes={co_expression_nodes}",
            phase="load_inputs",
        )
        self._check_cancelled()

        # Pipeline phase 2: enrich PPI edges using disease ontology evidence.
        if cached_inputs is None and self.network_weight_flag:
            self._check_cancelled()
            t0 = time.perf_counter()
            self._emit_progress("Weighting PPI edges with disease ontology evidence...", phase="weight_ppi")
            print("Weighting networks...")
            self.compute_ppi_weight = ComputePPIGraphWeight(
                self.PPI,
                map__gene__ontologies=self.map__gene__ontologies,
                disease_ontology=self.disease_ontology,
                cancellation_event=self.cancellation_event,
            )
            self.PPI = self.compute_ppi_weight.compute_weight_on_graph()
            print("Weighting networks computation time:", time.perf_counter() - t0)
            print()
            self._emit_progress("PPI edge weighting completed.", phase="weight_ppi")
            self._check_cancelled()

        if cached_inputs is None and self.prepared_input_cache is not None:
            self.prepared_input_cache[input_cache_key] = (
                self.PPI,
                self.CO_expression,
                self.seed_set,
                self.secondary_seed_set,
                self.map__gene__ontologies,
                self.disease_ontology,
            )

        # Pipeline phase 3: aggregate PPI and co-expression into the graph used by ranking.
        self._check_cancelled()
        t0 = time.perf_counter()
        self._emit_progress(
            f"Aggregating PPI and co-expression with beta={self.beta}...",
            phase="aggregate_network",
        )
        print("Computing aggregation with policy:", self.matrix_aggregation_policy, "...")
        self.G, self.V = self.compute_matrix_aggregation(
            self.PPI,
            self.CO_expression,
            self.matrix_aggregation_policy,
        )
        print(f"Graph has {self.G.number_of_nodes()} nodes and {self.G.number_of_edges()} edges")
        print("Time for computing aggregation matrix:", time.perf_counter() - t0)
        print()
        self._emit_progress(
            f"Integrated graph ready: nodes={self.G.number_of_nodes()}, edges={self.G.number_of_edges()}",
            phase="aggregate_network",
        )
        self._check_cancelled()

        return self.G, self.V

    def execute_ranking(self):
        """Compute personalization vectors and execute the selected ranking core."""
        if self.G is None or self.V is None:
            self.prepare_network()

        self._check_cancelled()
        # Original PageRank uses a uniform prior, so it does not need the
        # biological/topological personalization-vector stages.
        if self.algorithm == ALGORITHM_ORIGINAL_PAGERANK:
            t0 = time.perf_counter()
            self._emit_progress("Executing original PageRank core...", phase="ranking_core")
            print("Executing original PageRank...")
            self.ranked_list = list(
                PageRankOri(self.G, cancellation_event=self.cancellation_event).run()
            )
            print("Time for executing original PageRank:", time.perf_counter() - t0)

            if self.output_file_path is not None:
                self.save_ranked_list(self.output_file_path)

            if self._pipeline_start_time is not None:
                self.total_runtime_seconds = time.perf_counter() - self._pipeline_start_time
                print(f"Done! Total execution time: {self.total_runtime_seconds:.2f} seconds.")

            return self.ranked_list

        # Pipeline phase 4: build the personalization vector from topology and biology.
        t0 = time.perf_counter()
        self._emit_progress(
            "Computing personalization vectors with biological and topological evidence...",
            phase="personalization",
        )
        print(
            "Computing personalization vectors with policies:",
            ", ".join(self.personalization_vector_creation_policies),
            "...",
        )
        self._check_cancelled()
        personalization_cache_key = self._personalization_vector_cache_key()
        personalization_vectors = (
            self.personalization_vector_cache.get(personalization_cache_key)
            if self.personalization_vector_cache is not None and personalization_cache_key is not None
            else None
        )
        if personalization_vectors is not None:
            self._emit_progress("Reusing personalization vectors.", phase="personalization")
            print("Reusing personalization vectors.")
        else:
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
            if self.personalization_vector_cache is not None and personalization_cache_key is not None:
                self.personalization_vector_cache[personalization_cache_key] = personalization_vectors
            print("Time for computing personalization vectors:", time.perf_counter() - t0)
            print()
            self._emit_progress("Personalization vectors completed.", phase="personalization")
        self._check_cancelled()

        t0 = time.perf_counter()
        self._emit_progress(f"Aggregating personalization vectors with alpha={self.alpha}...", phase="personalization")
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
        self._check_cancelled()

        # Pipeline phase 5: run the selected graph-ranking algorithm.
        t0 = time.perf_counter()
        self._emit_progress(f"Executing ranking algorithm: {self.algorithm}", phase="ranking_core")
        print("Executing ranking algorithm...")
        if self.algorithm in {ALGORITHM_RANDOM_WALK, ALGORITHM_BRWR}:
            self._emit_progress(
                "Preparing BRWR transition matrix...",
                phase="ranking_core",
            )
        core = self._create_ranking_core(p_0)
        if self.algorithm in {ALGORITHM_RANDOM_WALK, ALGORITHM_BRWR}:
            self._emit_progress(
                "Running BRWR iterations until convergence...",
                phase="ranking_core",
            )
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
            return BioRank(personalization_vector, self.G, cancellation_event=self.cancellation_event)
        if self.algorithm == ALGORITHM_BIORANK_LITE:
            return BioRankLite(personalization_vector, self.G, cancellation_event=self.cancellation_event)
        if self.algorithm == ALGORITHM_BRWR:
            return RandomWalkWithRestartOriginal(personalization_vector, self.G, cancellation_event=self.cancellation_event)
        return RandomWalkWithRestartCore(personalization_vector, self.G, cancellation_event=self.cancellation_event)

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
                cancellation_event=self.cancellation_event,
                normalized_cache=self.matrix_aggregation_cache,
            )
            return matrix_creation_step.run(chosen_policy="PPI_network")

        if matrix_aggregation_policy == "only_ppi_network":
            return PPI_network, set(PPI_network.nodes())

        if matrix_aggregation_policy == "only_co_expression_network":
            return CO_expression_network, set(CO_expression_network.nodes())

        raise ValueError(f"Unsupported matrix aggregation policy: {matrix_aggregation_policy}")

    def _prepared_input_cache_key(self):
        return (
            self.ppi_file_path,
            self.co_expression_file_path,
            self.seed_file_path,
            self.secondary_seed_file_path,
            self.disease_ontology_file_path,
            self.map__gene__ontologies_file_path,
            self.network_weight_flag,
        )

    def _personalization_vector_cache_key(self):
        if self.V is None:
            return None
        return (
            tuple(self.personalization_vector_creation_policies),
            self.matrix_aggregation_policy,
            self._graph_topology_cache_bucket(),
            id(self.seed_set),
            id(self.secondary_seed_set),
            id(self.map__gene__ontologies),
            id(self.disease_ontology),
            len(self.V),
        )

    def _graph_topology_cache_bucket(self):
        if self.matrix_aggregation_policy == "convex_combination":
            return "beta_zero" if float(self.beta) <= 0.0 else "beta_positive"
        return self.matrix_aggregation_policy

    def get_network_summary(self):
        if self.G is None:
            return {"nodes": 0, "edges": 0}
        return {
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges(),
        }

    def iter_network_nodes(self, limit=None):
        nodes = self.G.nodes() if self.G is not None else []
        if limit is not None:
            nodes = itertools.islice(nodes, limit)
        return list(nodes)

    def iter_network_edges(self, limit=None):
        if self.G is None:
            return []

        edges = (
            (
                source,
                target,
                data.get("weight", 0.0),
            )
            for source, target, data in self.G.edges(data=True)
        )
        if limit is not None:
            edges = itertools.islice(edges, limit)
        return list(edges)

    def save_network(self, file_path):
        self._check_cancelled()
        with open(file_path, "w", newline="", encoding="utf-8") as fp:
            csv_writer = csv.writer(fp, delimiter="\t")
            csv_writer.writerow(["Source", "Target", "Weight"])
            for source, target, weight in self.iter_network_edges():
                self._check_cancelled()
                csv_writer.writerow([source, target, weight])

    def save_ranked_list(self, file_path):
        self._check_cancelled()
        ranked_list = [[item[0], item[1]] for item in self.ranked_list]
        with open(file_path, "w", newline="", encoding="utf-8") as fp:
            csv_writer = csv.writer(fp, delimiter="\t")
            csv_writer.writerow(["GeneNames", "Score"])
            csv_writer.writerows(ranked_list)
