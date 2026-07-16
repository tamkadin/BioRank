import numpy as np
from scipy import sparse


CONV_THRESHOLD = 0.000001


class BioRankLite:
    def __init__(
        self,
        personalization_vector,
        G,
        damping_factor=0.85,
        convergence_threshold=CONV_THRESHOLD,
        max_iter=1000,
        cancellation_event=None,
    ):
        self.damping_factor = damping_factor
        self.G = G
        self.personalization_vector = personalization_vector
        self.convergence_threshold = convergence_threshold
        self.max_iter = max_iter
        self.cancellation_event = cancellation_event
        self.nodes = list(self.G.nodes())
        self.node_index = {node: index for index, node in enumerate(self.nodes)}
        self.transition_matrix = self.__build_transition_matrix__()
        self.teleport_vector = self.__build_personalization_array__()

    def __check_cancelled__(self):
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise RuntimeError("Operation cancelled.")

    def __build_personalization_array__(self):
        p_0 = np.zeros(len(self.nodes), dtype=float)
        for node, score in self.personalization_vector.items():
            index = self.node_index.get(node)
            if index is not None:
                p_0[index] = score
        total = p_0.sum()
        if total > 0.0:
            p_0 /= total
        return p_0

    def __build_transition_matrix__(self):
        rows = []
        cols = []
        data = []

        for source in self.nodes:
            source_index = self.node_index[source]
            outgoing_edges = list(self.G.out_edges(source, data=True))
            total_weight = sum(edge_data.get("weight", 0.0) for _, _, edge_data in outgoing_edges)
            if total_weight <= 0.0:
                continue

            for _, target, edge_data in outgoing_edges:
                weight = edge_data.get("weight", 0.0)
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

    def __compute_next_page_rank__(self, p_t):
        return (
            (1 - self.damping_factor) * self.teleport_vector
            + self.damping_factor * self.transition_matrix.dot(p_t)
        )

    def __generate_ranked_list__(self, page_rank_vector):
        ranked_list = sorted(
            zip(self.nodes, page_rank_vector.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked_list

    def __norm_l1__(self, p_t_1, p_t):
        return np.linalg.norm(p_t_1 - p_t, 1)

    def run(self):
        p_v = self.teleport_vector.copy()
        diff_norm = 1
        iteration = 0

        while diff_norm > self.convergence_threshold and iteration < self.max_iter:
            self.__check_cancelled__()
            p_t_1 = self.__compute_next_page_rank__(p_v)
            diff_norm = self.__norm_l1__(p_t_1, p_v)
            p_v = p_t_1
            iteration += 1

        return self.__generate_ranked_list__(p_v)


class BioRank:
    def __init__(
        self,
        personalization_vector,
        G,
        damping_factor=0.85,
        convergence_threshold=CONV_THRESHOLD,
        max_iter=None,
        cancellation_event=None,
    ):
        self.damping_factor = damping_factor
        self.G = G
        self.personalization_vector = personalization_vector
        self.convergence_threshold = convergence_threshold
        self.max_iter = max_iter
        self.cancellation_event = cancellation_event
        self.nodes = list(self.G.nodes())
        self.node_index = {node: index for index, node in enumerate(self.nodes)}
        self.out_weight_totals = self.__build_out_weight_totals__()
        self.teleport_vector = self.__build_personalization_array__()

    def __check_cancelled__(self):
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise RuntimeError("Operation cancelled.")

    def __build_personalization_array__(self):
        p_0 = np.zeros(len(self.nodes), dtype=float)
        for node, score in self.personalization_vector.items():
            index = self.node_index.get(node)
            if index is not None:
                p_0[index] = score
        total = p_0.sum()
        if total > 0.0:
            p_0 /= total
        return p_0

    def __build_out_weight_totals__(self):
        totals = {}
        for source in self.nodes:
            total_weight = 0.0
            for _source, _target, edge_data in self.G.out_edges(source, data=True):
                weight = edge_data.get("weight", 0.0)
                if weight > 0.0:
                    total_weight += weight
            totals[source] = total_weight
        return totals

    def __compute_next_page_rank__(self, p_t):
        p_t_1 = (1 - self.damping_factor) * self.teleport_vector.copy()
        for target in self.nodes:
            target_index = self.node_index[target]
            contribution = 0.0
            for source, _target, edge_data in self.G.in_edges(target, data=True):
                total_weight = self.out_weight_totals.get(source, 0.0)
                if total_weight <= 0.0:
                    continue
                weight = edge_data.get("weight", 0.0)
                if weight <= 0.0:
                    continue
                contribution += p_t[self.node_index[source]] * weight / total_weight
            p_t_1[target_index] += self.damping_factor * contribution
        return p_t_1

    def __generate_ranked_list__(self, page_rank_vector):
        return sorted(
            zip(self.nodes, page_rank_vector.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )

    def __norm_l1__(self, p_t_1, p_t):
        return np.linalg.norm(p_t_1 - p_t, 1)

    def run(self):
        p_v = self.teleport_vector.copy()
        diff_norm = 1
        iteration = 0

        while diff_norm > self.convergence_threshold:
            if self.max_iter is not None and iteration >= self.max_iter:
                break
            self.__check_cancelled__()
            p_t_1 = self.__compute_next_page_rank__(p_v)
            diff_norm = self.__norm_l1__(p_t_1, p_v)
            p_v = p_t_1
            iteration += 1

        return self.__generate_ranked_list__(p_v)
