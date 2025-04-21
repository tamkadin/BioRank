import networkx as nx

CONV_THRESHOLD = 0.000001  # Ngưỡng hội tụ

class PageRankCore:
    def __init__(self, 
                 personalization_vector,  # Vector cá nhân hóa p_0
                 G,                        # Đồ thị đầu vào
                 restart_prob=0.85):       # Hệ số giảm chấn (damping factor)
        self.restart_prob = restart_prob
        self.G = G  # Đồ thị đầu vào, không chuẩn hóa
        self.personalization_vector = personalization_vector  # Vector cá nhân hóa p_0
    
    def __compute_next_page_rank__(self, p_t):
        """
        Cập nhật giá trị PageRank dựa trên công thức cải tiến.
        """
        next_p_t = {}
        damping_factor = self.restart_prob

        for v in self.G.nodes():
            # Thành phần ngẫu nhiên (restart probability)
            rank_sum = (1 - damping_factor) * self.personalization_vector.get(v, 0)

            # Thành phần lan truyền
            for u in self.G.predecessors(v):  # Các nút có cạnh hướng tới v
                weight_uv = self.G[u][v].get('weight', 0)  # Trọng số w(u, v)
                total_weight_u = sum(self.G[u][k].get('weight', 0) for k in self.G.successors(u))  # Tổng trọng số w(u, k)
                
                if total_weight_u > 0:
                    rank_sum += damping_factor * (p_t[u] * weight_uv / total_weight_u)

            next_p_t[v] = rank_sum  # Cập nhật giá trị PageRank mới cho nút v

        return next_p_t

    def __generate_ranked_list__(self, page_rank_vector):
        """
        Sắp xếp các nút dựa trên giá trị PageRank đã tính.
        """
        ranked_list = sorted(page_rank_vector.items(), key=lambda x: x[1], reverse=True)
        return ranked_list

    def __norm_l1__(self, p_t_1, p_t):
        """
        Tính độ khác biệt L1 giữa hai vector PageRank liên tiếp.
        """
        return sum(abs(p_t_1[gene] - p_t[gene]) for gene in p_t)

    def run(self):
        """
        Thực thi thuật toán PageRank cho đến khi hội tụ.
        """
        p_v = self.personalization_vector.copy()  # Sử dụng p_0 làm điểm khởi tạo
        diff_norm = 1

        while diff_norm > CONV_THRESHOLD:  # Kiểm tra điều kiện hội tụ
            p_t_1 = self.__compute_next_page_rank__(p_v)  # Tính giá trị PageRank mới
            diff_norm = self.__norm_l1__(p_t_1, p_v)  # Tính độ khác biệt giữa hai vòng lặp
            p_v = p_t_1  # Cập nhật vector PageRank

        return self.__generate_ranked_list__(p_v)  # Trả về danh sách xếp hạng

#CODE PAGERANK CẢI TIẾN 1 ---------------------------------------------------------------------------------
# import networkx as nx

# CONV_THRESHOLD = 0.000001

# class PageRankCore:
#     def __init__(self, 
#                  personalization_vector,  
#                  G,                       
#                  restart_prob=0.85):       

#         self.restart_prob = restart_prob
#         self.G = G 
#         self.personalization_vector = personalization_vector 
    
#     def normalize_weights_by_min(self):
#         """
#         Chuẩn hóa trọng số của các gene dựa trên gene có trọng số thấp nhất (từ vector cá nhân hóa p).
#         """
#         for node in self.G.nodes():
#             if node in self.personalization_vector:
#                 self.G.nodes[node]['weight'] = self.personalization_vector[node]
#             else:
#                 self.G.nodes[node]['weight'] = 1 

#         weights = nx.get_node_attributes(self.G, 'weight')
#         min_weight = min(weights.values())
#         print(f"Trọng số thấp nhất: {min_weight}")
        
#         for node in self.G.nodes():
#             current_weight = self.G.nodes[node].get('weight', 1) 
#             normalized_weight = current_weight / min_weight  
#             self.G.nodes[node]['normalized_weight'] = normalized_weight 

#     def __compute_next_page_rank__(self, p_t):
#         next_p_t = {}
#         damping_factor = self.restart_prob
#         n = len(p_t) 

#         for i in p_t.keys():
#             rank_sum = (1 - damping_factor) / n
       
#             for j in self.G.predecessors(i):
                
#                 normalized_weight_j = self.G.nodes[j].get('normalized_weight', 1) 

#                 if normalized_weight_j > 0:
#                     rank_sum += damping_factor * (p_t[j] / normalized_weight_j)

#             next_p_t[i] = rank_sum 

#         return next_p_t

#     def __generate_ranked_list__(self, page_rank_vector):
#         """
#         Sắp xếp các nút dựa trên điểm PageRank.
#         """
#         generate_probabilities = []
#         for k, v in page_rank_vector.items():
#             generate_probabilities.append([k, v])
#         sorted_list = sorted(generate_probabilities, key=lambda x: x[1], reverse=True)
#         return sorted_list

#     def __norm_l1__(self, p_t_1, p_t):
#         """
#         Tính độ khác biệt giữa hai vector PageRank liên tiếp.
#         """
#         return sum(abs(p_t_1[gene] - p_t[gene]) for gene in p_t_1)

#     def run(self):
#         """
#         Thực thi thuật toán PageRank cho đến khi hội tụ.
#         """
#         n = len(self.G.nodes())
#         p_v = {node: 1 / n for node in self.G.nodes()}  
#         diff_norm = 1

#         self.normalize_weights_by_min() 

#         while diff_norm > CONV_THRESHOLD:
#             p_t_1 = self.__compute_next_page_rank__(p_v)
#             diff_norm = self.__norm_l1__(p_t_1, p_v)
#             p_v = p_t_1

#         return self.__generate_ranked_list__(p_v)

# CODE PAGERANK GỐC------------------------------------------------------------------------------
# import networkx as nx

# CONV_THRESHOLD = 0.000001

# class PageRankCore:
#     def __init__(self, 
#                  personalization_vector,  # Vẫn giữ đầu vào nhưng không sử dụng
#                  G,                        # Đồ thị
#                  restart_prob=0.85):       # Hệ số giảm chấn (damping factor)

#         self.restart_prob = restart_prob
#         self.G = self.__normalize_graph__(G)  # Chuẩn hóa đồ thị
    
#     def __compute_next_page_rank__(self, p_t):
#         next_p_t = {}
#         damping_factor = self.restart_prob
#         n = len(p_t)  # Số lượng nút trong đồ thị

#         for i in p_t.keys():
#             # Giá trị khởi tạo (1 - d)/n
#             rank_sum = (1 - damping_factor) / n
            
#             for j in self.G.predecessors(i):  # Các nút có cạnh hướng tới i
#                 out_degree_j = self.G.out_degree(j)  # Chỉ lấy bậc đi ra
#                 if out_degree_j > 0:
#                     rank_sum += damping_factor * (p_t[j] / out_degree_j)

#             next_p_t[i] = rank_sum  # Lưu giá trị PageRank mới của nút i

#         return next_p_t

#     def __generate_ranked_list__(self, page_rank_vector):
#         """
#         Sắp xếp các nút dựa trên điểm PageRank.
#         """
#         generate_probabilities = []
#         for k, v in page_rank_vector.items():
#             generate_probabilities.append([k, v])
#         sorted_list = sorted(generate_probabilities, key=lambda x: x[1], reverse=True)
#         return sorted_list

#     def __norm_l1__(self, p_t_1, p_t):
#         """
#         Tính độ khác biệt giữa hai vector PageRank liên tiếp.
#         """
#         return sum(abs(p_t_1[gene] - p_t[gene]) for gene in p_t_1)

#     def __normalize_graph__(self, G):
#         """
#         Chuẩn hóa trọng số của đồ thị để tổng trọng số từ một nút bất kỳ bằng 1.
#         """
#         G_normalized = nx.DiGraph()

#         for node_1 in G:
#             total_weight = sum(G[node_1][node_2].get('weight', 1) for node_2 in G[node_1])

#             for node_2 in G[node_1]:
#                 if total_weight != 0.0:
#                     normalized_weight = G[node_1][node_2].get('weight', 1) / total_weight
#                 else:
#                     normalized_weight = 0.0
#                 G_normalized.add_edge(node_1, node_2, weight=normalized_weight)

#         return G_normalized
#     def run(self):
#         """
#         Thực thi thuật toán PageRank cho đến khi hội tụ.
#         """
#         n = len(self.G.nodes())
#         p_v = {node: 1 / n for node in self.G.nodes()} 
#         diff_norm = 1
#         while diff_norm > CONV_THRESHOLD:
#             p_t_1 = self.__compute_next_page_rank__(p_v)
#             diff_norm = self.__norm_l1__(p_t_1, p_v)
#             p_v = p_t_1
#         out_degrees = [self.G.out_degree(node) for node in self.G.nodes()]

#         print(f"Bậc đi ra thấp nhất: {min(out_degrees)}")
#         print(f"Bậc đi ra cao nhất: {max(out_degrees)}")
#         return self.__generate_ranked_list__(p_v)