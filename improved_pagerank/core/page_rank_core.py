import networkx as nx

CONV_THRESHOLD = 0.000001  # Ngưỡng hội tụ

class PageRankCore:
    def __init__(self, 
                 personalization_vector,  # Vector cá nhân hóa p_0
                 G,                        # Đồ thị đầu vào
                 damping_factor=0.85):       # Hệ số giảm chấn (damping factor)
        self.damping_factor = damping_factor
        self.G = G  # Đồ thị đầu vào, không chuẩn hóa
        self.personalization_vector = personalization_vector  # Vector cá nhân hóa p_0
    
    def __compute_next_page_rank__(self, p_t):
        """
        Cập nhật giá trị PageRank dựa trên công thức cải tiến.
        """
        next_p_t = {}
        damping_factor = self.damping_factor

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