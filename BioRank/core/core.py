import sys
import numpy as np
import networkx as nx
from sklearn.preprocessing import normalize

# convergence criterion - when vector L1 norm drops below 10^(-6)
# (this is the same as the original RWR paper)
CONV_THRESHOLD = 0.000001

class RandomWalkWithRestartCore:
    """Sparse BRWR/RWR core using p(t+1) = (1-r) W p(t) + r p0."""

    def __init__(self, 

        personalization_vector,
        G,
        restart_prob = 0.25,
        convergence_threshold=CONV_THRESHOLD,
        max_iter=None,
        cancellation_event=None):

        self.restart_prob = restart_prob
        self.personalization_vector = personalization_vector
        self.G = G
        self.convergence_threshold = convergence_threshold
        self.max_iter = max_iter
        self.cancellation_event = cancellation_event
        self.nodes = list(self.G.nodes())
        self.node_index = {node: index for index, node in enumerate(self.nodes)}

        self._build_matrix()        

    
    def run(self):

        p_0 = self._set_up_p0()

        diff_norm = 1
        iteration = 0
        
        p_t = np.copy(p_0)

        while diff_norm > self.convergence_threshold:
            if self.max_iter is not None and iteration >= self.max_iter:
                break
            self._check_cancelled()

            # first, calculate p^(t + 1) from p^(t)
            p_t_1 = self._calculate_next_p(p_t, p_0)

            # calculate L1 norm of difference between p^(t + 1) and p^(t),
            # for checking the convergence condition
            diff_norm = np.linalg.norm(np.subtract(p_t_1, p_t), 1)

            # then, set p^(t) = p^(t + 1), and loop again if necessary
            # no deep copy necessary here, we're just renaming p
            p_t = p_t_1
            iteration += 1

        # now, generate and print a rank list from the final prob vector
        ranked_list = self._generate_rank_list(p_t)

        return ranked_list

    def _check_cancelled(self):
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise RuntimeError("Operation cancelled.")

    def _generate_prob_list(self, p_t, node_list):
        gene_probs = dict(zip(self.nodes, p_t.tolist()))
        for node in node_list:
            yield node, gene_probs[node]

    def _generate_rank_list(self, p_t):
        gene_probs = zip(self.nodes, p_t.tolist())

        for s in sorted(gene_probs, key=lambda x: x[1], reverse=True):
            yield s[0], s[1]


    def _calculate_next_p(self, p_t, p_0):

        epsilon = np.squeeze(np.asarray(self.normalized_adjacency_matrix.dot(p_t)))
        no_restart = epsilon * (1 - self.restart_prob)
        
        restart = p_0 * self.restart_prob

        return np.add(no_restart, restart)


    def _set_up_p0(self,):
        
        """ Set up and return the 0th probability vector. """
        p_0 = [0] * self.G.number_of_nodes()
        
        for source_id,score in self.personalization_vector.items():
            try:
                # matrix columns are in the same order as nodes in original nx
                # graph, so we can get the index of the source node from the OG
                source_index = self.node_index[source_id]
                p_0[source_index] = score
            except KeyError:
                sys.exit("Source node {} is not in original graph. Exiting.".format(
                          source_id))
        return np.array(p_0)


    def _build_matrix(self):
        """ Build column-normalized adjacency matrix for each graph.
        NOTE: these are column-normalized adjacency matrices (not nx
              graphs), used to compute each p-vector
        """
        adjacency_matrix_not_normalized = nx.adjacency_matrix(self.G, nodelist=self.nodes)
        
        self.normalized_adjacency_matrix = self._normalize_cols(adjacency_matrix_not_normalized)



    def _normalize_cols(self, matrix):
        """ Normalize the columns of the adjacency matrix """
        return normalize(matrix, norm='l1', axis=0)


class RandomWalkWithRestartOriginal:
    """Dense legacy BRWR/RWR core; same formula as the sparse core."""

    def __init__(
        self,
        personalization_vector,
        G,
        restart_prob=0.25,
        convergence_threshold=CONV_THRESHOLD,
        max_iter=None,
        cancellation_event=None,
    ):
        self.restart_prob = restart_prob
        self.personalization_vector = personalization_vector
        self.G = G
        self.convergence_threshold = convergence_threshold
        self.max_iter = max_iter
        self.cancellation_event = cancellation_event

        adjacency_matrix_not_normalized = nx.adjacency_matrix(self.G,)
        self.normalized_adjacency_matrix = normalize(
            adjacency_matrix_not_normalized,
            norm='l1',
            axis=0,
        ).todense()

    def run(self):
        p_0 = self._set_up_p0()
        diff_norm = 1
        iteration = 0
        p_t = np.copy(p_0)

        while diff_norm > self.convergence_threshold:
            if self.max_iter is not None and iteration >= self.max_iter:
                break
            self._check_cancelled()

            p_t_1 = self._calculate_next_p(p_t, p_0)
            diff_norm = np.linalg.norm(np.subtract(p_t_1, p_t), 1)
            p_t = p_t_1
            iteration += 1

        return sorted(zip(self.G.nodes(), p_t.tolist()), key=lambda x: x[1], reverse=True)

    def _check_cancelled(self):
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise RuntimeError("Operation cancelled.")

    def _calculate_next_p(self, p_t, p_0):
        epsilon = np.squeeze(np.asarray(np.dot(self.normalized_adjacency_matrix, p_t)))
        no_restart = epsilon * (1 - self.restart_prob)
        restart = p_0 * self.restart_prob
        return np.add(no_restart, restart)

    def _set_up_p0(self):
        p_0 = [0] * self.G.number_of_nodes()

        for source_id, score in self.personalization_vector.items():
            try:
                source_index = list(self.G.nodes()).index(source_id)
                p_0[source_index] = score
            except ValueError:
                sys.exit("Source node {} is not in original graph. Exiting.".format(source_id))
        return np.array(p_0)
