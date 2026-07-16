import threading

from PySide6.QtCore import QObject, Signal, Slot

from BioRank.optimization.biorank_alpha_beta_optimizer import (
    BioRankAlphaBetaOptimizer,
    OptimizationCancelled,
)


class OptimizerWorker(QObject):
    progress = Signal(dict)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.cancellation_event = threading.Event()

    @Slot()
    def run(self):
        try:
            optimizer = BioRankAlphaBetaOptimizer(
                cancer_type=self.config["cancer_type"],
                input_paths=self.config["input_paths"],
                validation_file_path=self.config["validation_file_path"],
                validation_gene_column=self.config["validation_gene_column"],
                gene_mapping_file_path=self.config["gene_mapping_file_path"],
                alpha_range=self.config["alpha_range"],
                beta_range=self.config["beta_range"],
                n_trials=self.config["n_trials"],
                metric_config=self.config["metric_config"],
                output_dir=self.config["output_dir"],
                prefer_balanced_top5=self.config["prefer_balanced_top5"],
                random_seed=self.config["random_seed"],
                candidate_selection_mode=self.config["candidate_selection_mode"],
                max_selected_candidates=self.config["max_selected_candidates"],
                cancellation_event=self.cancellation_event,
                progress_callback=self.progress.emit,
            )
            self.completed.emit(optimizer.run())
        except OptimizationCancelled as exc:
            self.cancelled.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))

    def cancel(self):
        self.cancellation_event.set()
