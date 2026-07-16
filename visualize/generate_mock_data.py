#!/usr/bin/env python3
"""
Generates mock trial history data for testing the visualization script.
"""

import numpy as np
import pandas as pd
from pathlib import Path


def generate_mock_tsv(output_path: Path, include_selection_score: bool = True) -> None:
    np.random.seed(42)
    num_trials = 80
    
    data = []
    for i in range(num_trials):
        # Determine state
        state_rand = np.random.rand()
        if state_rand < 0.85:
            state = "COMPLETE"
        elif state_rand < 0.95:
            state = "PRUNED"
        else:
            state = "FAILED"
            
        # Generate alpha and beta
        alpha = np.random.uniform(0.0, 1.0)
        beta = np.random.uniform(0.0, 1.0)
        
        # Add some boundary cases and out-of-bounds cases to verify warnings
        if i == 0:
            alpha, beta = 0.0, 0.0
        elif i == 1:
            alpha, beta = 1.0, 1.0
        elif i == 2:
            alpha, beta = 1.2, 0.5 # Out of bounds warning test
            
        # Generate performance metrics (with a high-alpha, high-beta correlation trend)
        # Let's say ndcg and recall are higher when alpha and beta are higher
        base_performance = 0.4 + 0.3 * alpha + 0.2 * beta
        ndcg = np.clip(base_performance + np.random.normal(0, 0.05), 0.1, 0.95)
        recall = np.clip((base_performance * 0.1) + np.random.normal(0, 0.01), 0.01, 0.15)
        
        # Intermediate metrics
        ndcg_15 = ndcg * 0.8
        recall_15 = recall * 0.6
        
        common_genes = int(recall * 1000)
        all_hits = 1040
        mapped = 12147
        
        selection_score = 0.8 * ndcg + 0.2 * recall + np.random.normal(0, 0.02)
        duration = np.random.uniform(10.0, 25.0)
        error_msg = "" if state == "COMPLETE" else "OptunaPruningException()"
        
        # If trial failed, metrics should be NaN
        if state != "COMPLETE":
            ndcg, recall, ndcg_15, recall_15, selection_score, common_genes = (
                np.nan, np.nan, np.nan, np.nan, np.nan, np.nan
            )
            
        row = {
            "trial_number": i,
            "alpha": alpha,
            "beta": beta,
            "ndcg_at_15": ndcg_15,
            "recall_at_15": recall_15,
            "ndcg_at_100": ndcg,
            "recall_at_100": recall,
            "common_genes_top_100": common_genes,
            "all_hits": all_hits,
            "mapped_genes": mapped,
            "state": state,
            "duration_seconds": duration,
            "error_message": error_msg
        }
        
        if include_selection_score and state == "COMPLETE":
            row["selection_score"] = selection_score
            
        data.append(row)
        
    df = pd.DataFrame(data)
    df.to_csv(output_path, sep='\t', index=False)
    print(f"Generated mock trial history: {output_path} (include_selection_score={include_selection_score})")


if __name__ == "__main__":
    generate_mock_tsv(Path("visualize/mock_trial_history_with_selection.tsv"), include_selection_score=True)
    generate_mock_tsv(Path("visualize/mock_trial_history_no_selection.tsv"), include_selection_score=False)
