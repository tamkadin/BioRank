import networkx as nx

CONV_THRESHOLD = 0.000001

class PageRankOri:
    def __init__(self,
                 G,
                 restart_prob=0.85):

        self.restart_prob = restart_prob
        self.G = self.__normalize_graph__(G)
    
    def __compute_next_page_rank__(self, p_t):
        next_p_t = {}
        damping_factor = self.restart_prob
        n = len(p_t)

        for i in p_t.keys():
            rank_sum = (1 - damping_factor) / n
            
            for j in self.G.predecessors(i):
                out_degree_j = self.G.out_degree(j)
                if out_degree_j > 0:
                    rank_sum += damping_factor * (p_t[j] / out_degree_j)

            next_p_t[i] = rank_sum

        return next_p_t

    def __generate_ranked_list__(self, page_rank_vector):
        generate_probabilities = []
        for k, v in page_rank_vector.items():
            generate_probabilities.append([k, v])
        sorted_list = sorted(generate_probabilities, key=lambda x: x[1], reverse=True)
        return sorted_list

    def __norm_l1__(self, p_t_1, p_t):
        return sum(abs(p_t_1[gene] - p_t[gene]) for gene in p_t_1)

    def __normalize_graph__(self, G):
        G_normalized = nx.DiGraph()

        for node_1 in G:
            total_weight = sum(G[node_1][node_2].get('weight', 1) for node_2 in G[node_1])

            for node_2 in G[node_1]:
                if total_weight != 0.0:
                    normalized_weight = G[node_1][node_2].get('weight', 1) / total_weight
                else:
                    normalized_weight = 0.0
                G_normalized.add_edge(node_1, node_2, weight=normalized_weight)

        return G_normalized
    def run(self):
        n = len(self.G.nodes())
        p_v = {node: 1 / n for node in self.G.nodes()} 
        diff_norm = 1
        while diff_norm > CONV_THRESHOLD:
            p_t_1 = self.__compute_next_page_rank__(p_v)
            diff_norm = self.__norm_l1__(p_t_1, p_v)
            p_v = p_t_1
        return self.__generate_ranked_list__(p_v)