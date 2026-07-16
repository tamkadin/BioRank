import numpy as np
from scipy import sparse


CONV_THRESHOLD = 0.000001


class PageRankOri:
    def __init__(
        self,
        G,
        restart_prob=0.85,
        convergence_threshold=CONV_THRESHOLD,
        max_iter=1000,
        cancellation_event=None,
    ):
        self.restart_prob = restart_prob
        self.G = G
        self.convergence_threshold = convergence_threshold
        self.max_iter = max_iter
        self.cancellation_event = cancellation_event
        self.nodes = list(self.G.nodes())
        self.node_index = {node: index for index, node in enumerate(self.nodes)}
        self.transition_matrix = self.__build_transition_matrix__()

    def __check_cancelled__(self):
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise RuntimeError("Operation cancelled.")

    def __build_transition_matrix__(self):
        rows = []
        cols = []
        data = []

        for source in self.nodes:
            source_index = self.node_index[source]
            out_degree = self.G.out_degree(source)
            if out_degree <= 0:
                continue

            probability = 1.0 / out_degree
            for target in self.G.successors(source):
                rows.append(self.node_index[target])
                cols.append(source_index)
                data.append(probability)

        return sparse.csr_matrix(
            (data, (rows, cols)),
            shape=(len(self.nodes), len(self.nodes)),
            dtype=float,
        )

    def __compute_next_page_rank__(self, p_t):
        n = len(self.nodes)
        return ((1 - self.restart_prob) / n) + self.restart_prob * self.transition_matrix.dot(p_t)

    def __generate_ranked_list__(self, page_rank_vector):
        return sorted(
            zip(self.nodes, page_rank_vector.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )

    def __norm_l1__(self, p_t_1, p_t):
        return np.linalg.norm(p_t_1 - p_t, 1)

    def run(self):
        n = len(self.nodes)
        if n == 0:
            return []

        p_v = np.full(n, 1.0 / n, dtype=float)
        diff_norm = 1
        iteration = 0

        while diff_norm > self.convergence_threshold and iteration < self.max_iter:
            self.__check_cancelled__()
            p_t_1 = self.__compute_next_page_rank__(p_v)
            diff_norm = self.__norm_l1__(p_t_1, p_v)
            p_v = p_t_1
            iteration += 1

        return self.__generate_ranked_list__(p_v)
