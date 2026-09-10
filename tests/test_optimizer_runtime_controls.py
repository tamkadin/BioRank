import threading
import time
import unittest
from unittest.mock import patch

from BioRank.optimization.ablation_config import ABLATION_MODE_WITHOUT_COEXPRESSION
from BioRank.optimization.biorank_alpha_beta_optimizer import BioRankAlphaBetaOptimizer


class OptimizerRuntimeControlsTest(unittest.TestCase):
    def _optimizer(self, pause_event=None, progress_callback=None):
        return BioRankAlphaBetaOptimizer(
            cancer_type="TEST",
            input_paths={
                "ppi_file_path": "ppi.tsv",
                "seed_file_path": "seed.tsv",
                "secondary_seed_file_path": "de.tsv",
                "map__gene__ontologies_file_path": "ontology.tsv",
                "disease_ontology_file_path": "disease_ontology.tsv",
            },
            validation_file_path="validation.csv",
            validation_gene_column="Gene",
            gene_mapping_file_path="",
            alpha_range=(0.0, 1.0),
            beta_range=(0.0, 1.0),
            n_trials=2,
            metric_config={"recall_k": 100, "ndcg_k": 100, "precision_k": 15},
            output_dir="",
            ablation_mode=ABLATION_MODE_WITHOUT_COEXPRESSION,
            pause_event=pause_event,
            progress_callback=progress_callback,
        )

    def test_pause_waits_until_resume(self):
        pause_event = threading.Event()
        pause_event.set()
        progress = []
        optimizer = self._optimizer(pause_event=pause_event, progress_callback=progress.append)
        optimizer._log = lambda _message: None

        worker = threading.Thread(target=optimizer._check_cancelled)
        worker.start()
        time.sleep(0.05)
        self.assertTrue(worker.is_alive())

        pause_event.clear()
        worker.join(timeout=1.0)

        self.assertFalse(worker.is_alive())
        self.assertEqual(progress[0]["phase"], "paused")
        self.assertEqual(progress[-1]["status"], "Optimization resumed.")

    def test_ppi_only_trials_reuse_prepared_network(self):
        class FakeRunner:
            instances = 0
            prepare_calls = 0

            def __init__(self, **kwargs):
                type(self).instances += 1
                self.alpha = kwargs["alpha"]
                self.beta = kwargs["beta"]
                self.algorithm = kwargs["algorithm"]
                self.output_file_path = kwargs["output_file_path"]
                self.cancellation_event = kwargs["cancellation_event"]
                self.progress_callback = kwargs["progress_callback"]
                self.ranked_list = []

            def prepare_network(self):
                type(self).prepare_calls += 1

            def execute_ranking(self):
                self.ranked_list = [("TP53", 1.0), ("GENE2", 0.5)]

        optimizer = self._optimizer()
        optimizer.truth_genes = {"TP53"}
        optimizer.gene_mapping = {}
        optimizer._log = lambda _message: None

        with patch(
            "BioRank.optimization.biorank_alpha_beta_optimizer.BioRankCancerGeneRanking",
            FakeRunner,
        ):
            optimizer._run_and_score("biorank_lite", alpha=0.2, beta=1.0)
            optimizer._run_and_score("biorank_lite", alpha=0.8, beta=1.0)

        self.assertEqual(FakeRunner.instances, 1)
        self.assertEqual(FakeRunner.prepare_calls, 1)


if __name__ == "__main__":
    unittest.main()
