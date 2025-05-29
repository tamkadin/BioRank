import networkx as nx

CONV_THRESHOLD = 0.000001

class PageRankCore:
    def __init__(self, 
                 personalization_vector,
                 G,
                 damping_factor=0.85):
        self.damping_factor = damping_factor
        self.G = G
        self.personalization_vector = personalization_vector
    
    def __compute_next_page_rank__(self, p_t):
        next_p_t = {}
        damping_factor = self.damping_factor

        for v in self.G.nodes():
            rank_sum = (1 - damping_factor) * self.personalization_vector.get(v, 0)

            for u in self.G.predecessors(v):
                weight_uv = self.G[u][v].get('weight', 0)
                total_weight_u = sum(self.G[u][k].get('weight', 0) for k in self.G.successors(u))
                
                if total_weight_u > 0:
                    rank_sum += damping_factor * (p_t[u] * weight_uv / total_weight_u)

            next_p_t[v] = rank_sum

        return next_p_t

    def __generate_ranked_list__(self, page_rank_vector):
        ranked_list = sorted(page_rank_vector.items(), key=lambda x: x[1], reverse=True)
        return ranked_list

    def __norm_l1__(self, p_t_1, p_t):
        return sum(abs(p_t_1[gene] - p_t[gene]) for gene in p_t)

    def run(self):
        p_v = self.personalization_vector.copy()
        diff_norm = 1

        while diff_norm > CONV_THRESHOLD:
            p_t_1 = self.__compute_next_page_rank__(p_v)
            diff_norm = self.__norm_l1__(p_t_1, p_v) 
            p_v = p_t_1

        return self.__generate_ranked_list__(p_v)