from improved_pagerank.loader.loader import Loader
from improved_pagerank.graph_weight_computation.PPI_graph_weight_computation import ComputePPIGraphWeight
from improved_pagerank.matrix_creation.convex_combination_aggregation_matrix_creation import ConvexCombinationMatrixAggregationCreation
from improved_pagerank.personalization_vector_creation.default_personalization_vector_creation import DefaultPersonalizationVectorCreation
from improved_pagerank.personalization_vector_creation.biological_personalization_vector_creation import BiologicalPersonalizationVectorCreation
from improved_pagerank.personalization_vector_creation.topological_personalization_vector_creation import TopologicalPersonalizationVectorCreation
from improved_pagerank.personalization_vector_aggregation.p_v_aggregation import PersonalizationVectorAggregation
from improved_pagerank.core.page_rank_core import PageRankCore
from improved_pagerank.core.page_rank_ori import PageRankOri
import time
import csv

class ImprovedPageRankCancerGeneRanking():
    
    def __init__(self,
        seed_file_path,
        ppi_file_path = None, 
        co_expression_file_path = None,
        disease_ontology_file_path= None,
        map__gene__ontologies_file_path = None,
        secondary_seed_file_path = None,
        matrix_aggregation_policy = "convex_combination",
        personalization_vector_creation_policies = ["biological","topological"],
        personalization_vector_aggregation_policy = "Sum",
        alpha = 0.5,
        beta = 0.5,
        network_weight_flag = True,
        output_file_path = None,
        enhanced = True,
        ):

        t0 = time.perf_counter()
        start_time = time.perf_counter()
        self.alpha = alpha
        self.beta = beta
        self.enhanced = enhanced
        
        print("Loading Networks....")
        self.file_loader_step = Loader(ppi_file_path,
            co_expression_file_path,
            seed_file_path,
            secondary_seed_file_path = secondary_seed_file_path,
            disease_ontology_file_path = disease_ontology_file_path,
            map_gene_ontologies_file_path = map__gene__ontologies_file_path)
        
        PPI, CO_expression, seed_set, secondary_seed_set, map__gene__ontologies, disease_ontology = self.file_loader_step.run()
        print("Loading Time:", time.perf_counter() - t0)
        print()

        if network_weight_flag:
            t0 = time.perf_counter()

            print("Weighting Networks....")
            self.compute_ppi_weight = ComputePPIGraphWeight(PPI,map__gene__ontologies = map__gene__ontologies, disease_ontology = disease_ontology)
            PPI = self.compute_ppi_weight.compute_weight_on_graph()
            print("Weighting Networks Computation Time:", time.perf_counter() - t0)
            print()

        
        t0 = time.perf_counter()
        print("Computing aggragation with policy:", matrix_aggregation_policy,"....")
        G, V = self.compute_matrix_aggregation(PPI, CO_expression, matrix_aggregation_policy)
        
        print("Time for computing Aggregation Matrix:", time.perf_counter() - t0)
        print()

        # Print network stats
        #self.__print_aggregated_network_stats__(G)
            
        print()
        t0 = time.perf_counter()

        print("Computing personalization vectors with policies:", ", ".join(personalization_vector_creation_policies),"....")
        personalization_vectors = self.compute_personalization_vectors(
                
            seed_set = seed_set, 
            V = V,
                
            disease_ontology = disease_ontology, 
            map__gene_name__ontologies = map__gene__ontologies, 
            universe_ontologies = None,

            G = G,
            secondary_seed_set = secondary_seed_set,
            chosen_policies = personalization_vector_creation_policies )

        print("Time for computing personalization Vectors:", time.perf_counter() - t0)
        print()

        t0 = time.perf_counter()


        print("Aggregating personalization vectors with policy:", personalization_vector_aggregation_policy ,"....")
        self.personalization_vector_aggregation_step = PersonalizationVectorAggregation(personalization_vectors, universe = V, alpha = self.alpha)
        p_0 = self.personalization_vector_aggregation_step.run(chosen_policy = personalization_vector_aggregation_policy)
  
        # p_1 = self.compute_normalized_degree(G)
        # p = self.aggregate_p0_and_p1(p_0,p_1)

        t0 = time.perf_counter()

        print("Exectuting Pagerank....")

        if self.enhanced:
            core = PageRankCore(p_0, G)
        else:
            core = PageRankOri(G)	

        self.ranked_list = core.run()
        print("Time for Exectuting Page_rank", time.perf_counter() - t0)
                
        if output_file_path != None:
            self.save_ranked_list(output_file_path)

        end_time = time.perf_counter()
        self.total_runtime_seconds=end_time-start_time
        print(f"Done! Total execution time: {self.total_runtime_seconds:.2f} seconds.")

    def compute_personalization_vectors(self,
        seed_set,
        V,

        disease_ontology = None, 
        map__gene_name__ontologies = None, 
        universe_ontologies = None,

        G = None,
        secondary_seed_set = None,

        chosen_policies = ["biological"]):

        default_p_v = None
        overwritten_p_v = None
        biological_p_v = None
        topological_p_v = None

        personalization_vectors = []

        if "default" in chosen_policies:
            personalization_vector_creation_step = DefaultPersonalizationVectorCreation(seed_set, V)
            default_p_v = personalization_vector_creation_step.run()

        if "topological" in chosen_policies:
            personalization_vector_creation_step = TopologicalPersonalizationVectorCreation(seed_set, V,G = G, secondary_seed_set = secondary_seed_set)
            topological_p_v = personalization_vector_creation_step.run()

        if "biological" in chosen_policies:

            personalization_vector_creation_step = BiologicalPersonalizationVectorCreation(
                source = seed_set,
                universe = V,
                disease_ontology = disease_ontology, 
                map__gene_name__ontologies = map__gene_name__ontologies)

            biological_p_v = personalization_vector_creation_step.run()


        if default_p_v != None:
            personalization_vectors.append(default_p_v)

        if biological_p_v != None:
            personalization_vectors.append(biological_p_v)

        if topological_p_v != None:
            personalization_vectors.append(topological_p_v)


        
        return personalization_vectors

    def compute_matrix_aggregation(self, PPI_network, CO_expression_network, matrix_aggregation_policy = "convex_combination"):


        if matrix_aggregation_policy == "convex_combination":
            
            matrix_creation_step = ConvexCombinationMatrixAggregationCreation(PPI_network, CO_expression_network,self.beta) 
            G, V = matrix_creation_step.run(chosen_policy = "PPI_network")

            return G,V

        elif matrix_aggregation_policy == "only_ppi_network":
            
            V = set(PPI_network.nodes())
            return PPI_network, V

        elif matrix_aggregation_policy == "only_co_expression_network":

            V = set(CO_expression_network.nodes())
            return CO_expression_network, V


    def save_ranked_list(self, file_path):

        ranked_list = [[item[0], item[1]] for item in self.ranked_list]

        csv_writer = csv.writer(open(file_path,'w'), delimiter = "\t")
        csv_writer.writerow(["GeneNames","Score"])
        csv_writer.writerows(ranked_list)

    def write_debug(self,file_path,algorithm_output,delimiter = "\t",wm="w"):
    
        with open(file_path,wm) as fp:
            csv_writer = csv.writer(fp,delimiter = delimiter)
            csv_writer.writerows(algorithm_output)


    def __print_aggregated_network_stats__(self, G):
        filename="C:/Users/ASUS/OneDrive - Hanoi University of Science and Technology/Documents/2024.1/Research Bio/BiologicalRandomWalks-master/G1.csv"
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Gene u", "Gene v", "Weight"])
            
            for u, v, data in G.edges(data=True):
                weight = data.get('weight', 0.0) 
                writer.writerow([u, v, weight])
  
    def compute_normalized_degree(self, G):

        degree_dict = {node: len(list(G.neighbors(node))) for node in G.nodes()}
        total_degree = sum(degree_dict.values())

        normalized_degree_dict = {node: degree / total_degree for node, degree in degree_dict.items()}
  
        return normalized_degree_dict
    def aggregate_p0_and_p1(self, p_0, p_1, output_file_path="aggregated_vectors.csv"):
        aggregated_vector = {}

        for node in p_0:
            if node in p_1:
                aggregated_vector[node] = p_0[node] + p_1[node]
            else:
                aggregated_vector[node] = p_0[node]

        print(f"Aggregated vectors saved to {output_file_path}")
        return aggregated_vector
