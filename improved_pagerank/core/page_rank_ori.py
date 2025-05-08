import networkx as nx

CONV_THRESHOLD = 0.000001

class PageRankOri:
    def __init__(self,
                 G,                        # Đồ thị
                 restart_prob=0.85):       # Hệ số giảm chấn (damping factor)

        self.restart_prob = restart_prob
        self.G = self.__normalize_graph__(G)  # Chuẩn hóa đồ thị
    
    def __compute_next_page_rank__(self, p_t):
        next_p_t = {}
        damping_factor = self.restart_prob
        n = len(p_t)  # Số lượng nút trong đồ thị

        for i in p_t.keys():
            # Giá trị khởi tạo (1 - d)/n
            rank_sum = (1 - damping_factor) / n
            
            for j in self.G.predecessors(i):  # Các nút có cạnh hướng tới i
                out_degree_j = self.G.out_degree(j)  # Chỉ lấy bậc đi ra
                if out_degree_j > 0:
                    rank_sum += damping_factor * (p_t[j] / out_degree_j)

            next_p_t[i] = rank_sum  # Lưu giá trị PageRank mới của nút i

        return next_p_t

    def __generate_ranked_list__(self, page_rank_vector):
        """
        Sắp xếp các nút dựa trên điểm PageRank.
        """
        generate_probabilities = []
        for k, v in page_rank_vector.items():
            generate_probabilities.append([k, v])
        sorted_list = sorted(generate_probabilities, key=lambda x: x[1], reverse=True)
        return sorted_list

    def __norm_l1__(self, p_t_1, p_t):
        """
        Tính độ khác biệt giữa hai vector PageRank liên tiếp.
        """
        return sum(abs(p_t_1[gene] - p_t[gene]) for gene in p_t_1)

    def __normalize_graph__(self, G):
        """
        Chuẩn hóa trọng số của đồ thị để tổng trọng số từ một nút bất kỳ bằng 1.
        """
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
        """
        Thực thi thuật toán PageRank cho đến khi hội tụ.
        """
        n = len(self.G.nodes())
        p_v = {node: 1 / n for node in self.G.nodes()} 
        diff_norm = 1
        while diff_norm > CONV_THRESHOLD:
            p_t_1 = self.__compute_next_page_rank__(p_v)
            diff_norm = self.__norm_l1__(p_t_1, p_v)
            p_v = p_t_1
        out_degrees = [self.G.out_degree(node) for node in self.G.nodes()]

        print(f"Bậc đi ra thấp nhất: {min(out_degrees)}")
        print(f"Bậc đi ra cao nhất: {max(out_degrees)}")
        return self.__generate_ranked_list__(p_v)