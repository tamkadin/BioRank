#!/usr/bin/env python3
"""
Optuna Multi-Objective Tuning Visualization Tool for BioRank
Author: Senior Python / Data Visualization Engineer
Description: Visualizes alpha-beta parameter landscape and Pareto frontier.
"""

import argparse
import sys
import warnings
from pathlib import Path
from typing import Tuple, List, Optional, Union

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Force headless backend for robust execution in WSL
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Optional dependency for interactive plotting
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def load_trial_history(path: Path) -> pd.DataFrame:
    """
    Loads trial history from a TSV file and filters complete trials.
    
    Args:
        path: Path to the TSV file.
        
    Returns:
        DataFrame containing complete trials.
    """
    if not path.exists():
        raise FileNotFoundError(f"Input file not found at: {path}")
        
    try:
        # Load TSV (handling standard Delimiter=Tab)
        df = pd.read_csv(path, sep='\t')
    except Exception as e:
        raise ValueError(f"Failed to read TSV file: {e}")
        
    if df.empty:
        raise ValueError("The input TSV file is empty.")
        
    # Check if 'state' column exists and filter COMPLETE trials
    if 'state' in df.columns:
        complete_df = df[df['state'].str.upper() == 'COMPLETE'].copy()
    else:
        # Fallback if no state column is present, assume all are complete
        warnings.warn("No 'state' column found in TSV file. Proceeding with all rows.")
        complete_df = df.copy()
        
    if complete_df.empty:
        raise ValueError("No trials with state == 'COMPLETE' found in the trial history.")
        
    return complete_df


def validate_columns(df: pd.DataFrame) -> None:
    """
    Validates that the input DataFrame contains the necessary columns.
    Cleans up any rows containing NaN in key visualization columns.
    
    Args:
        df: DataFrame to validate and clean.
    """
    required_cols = ['alpha', 'beta', 'ndcg_at_100', 'recall_at_100']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Input TSV is missing required columns: {missing}")
        
    # Drop rows with NaN in key fields
    initial_len = len(df)
    df.dropna(subset=required_cols, inplace=True)
    dropped = initial_len - len(df)
    if dropped > 0:
        print(f"Warning: Dropped {dropped} rows with NaN values in required parameters/metrics.")
        
    if df.empty:
        raise ValueError("No valid trials left after dropping NaN values in required columns.")

    # Warn if alpha or beta fall outside [0, 1] range
    out_of_bounds = df[
        (df['alpha'] < 0.0) | (df['alpha'] > 1.0) | 
        (df['beta'] < 0.0) | (df['beta'] > 1.0)
    ]
    if not out_of_bounds.empty:
        warnings.warn(
            f"Found {len(out_of_bounds)} trials with alpha/beta values outside [0, 1] bounds. "
            "Plotting will proceed, but check if parameters are correctly scaled."
        )


def compute_balanced_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes normalized metrics, balanced score, and distance to ideal.
    
    balanced_score = 0.5 * normalized_ndcg + 0.5 * normalized_recall
    distance_to_ideal = sqrt((1 - normalized_ndcg)^2 + (1 - normalized_recall)^2)
    
    Args:
        df: The input trial DataFrame.
        
    Returns:
        DataFrame with added normalized and balanced score columns.
    """
    ndcg_col = 'ndcg_at_100'
    recall_col = 'recall_at_100'
    
    # Extract min/max values
    ndcg_min, ndcg_max = df[ndcg_col].min(), df[ndcg_col].max()
    recall_min, recall_max = df[recall_col].min(), df[recall_col].max()
    
    # Normalize metrics to [0, 1]
    if ndcg_max > ndcg_min:
        df['normalized_ndcg_at_100'] = (df[ndcg_col] - ndcg_min) / (ndcg_max - ndcg_min)
    else:
        df['normalized_ndcg_at_100'] = 1.0
        
    if recall_max > recall_min:
        df['normalized_recall_at_100'] = (df[recall_col] - recall_min) / (recall_max - recall_min)
    else:
        df['normalized_recall_at_100'] = 1.0
        
    # Compute balanced score
    df['balanced_score'] = 0.5 * df['normalized_ndcg_at_100'] + 0.5 * df['normalized_recall_at_100']
    
    # Compute distance to ideal (1, 1) in the normalized space
    df['distance_to_ideal'] = np.sqrt(
        (1.0 - df['normalized_ndcg_at_100'])**2 + 
        (1.0 - df['normalized_recall_at_100'])**2
    )
    
    return df


def mark_pareto_frontier(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifies the Pareto frontier for maximizing both ndcg_at_100 and recall_at_100.
    A trial is dominated if another trial has higher or equal values for both objectives
    and is strictly higher in at least one of them.
    
    Args:
        df: Input DataFrame.
        
    Returns:
        DataFrame with an added boolean column 'is_pareto'.
    """
    ndcg = df['ndcg_at_100'].values
    recall = df['recall_at_100'].values
    n = len(df)
    
    is_pareto = []
    for i in range(n):
        dominated = False
        for j in range(n):
            if i == j:
                continue
            # Check if trial j dominates trial i
            if (ndcg[j] >= ndcg[i] and recall[j] >= recall[i]) and (ndcg[j] > ndcg[i] or recall[j] > recall[i]):
                dominated = True
                break
        is_pareto.append(not dominated)
        
    df['is_pareto'] = is_pareto
    return df


def infer_best_region(df: pd.DataFrame) -> str:
    """
    Analyzes the top 10% trials based on selection_score (or balanced_score as fallback)
    and generates a localized parameter consensus warning/note.
    
    Args:
        df: Input DataFrame with calculated scores.
        
    Returns:
        String representing inferred best region.
    """
    # Decide which rank score to use
    rank_col = 'selection_score' if 'selection_score' in df.columns else 'balanced_score'
    
    # Sort descending and take top 10% (at least 1 trial)
    df_sorted = df.sort_values(by=rank_col, ascending=False)
    top_count = max(1, int(np.ceil(len(df_sorted) * 0.1)))
    top_trials = df_sorted.head(top_count)
    
    # Compute medians
    median_alpha = top_trials['alpha'].median()
    median_beta = top_trials['beta'].median()
    
    # Determine the status and message using the requested logic
    # (using cautious language to represent "observed best region")
    if median_alpha > 0.7 and median_beta > 0.7:
        return "Observed best region appears concentrated at high alpha and high beta."
    elif median_alpha < 0.3 and median_beta < 0.3:
        return "Observed best region appears concentrated at low alpha and low beta."
    elif median_alpha > 0.7 and median_beta < 0.3:
        return "Observed best region appears concentrated at high alpha and low beta."
    elif median_alpha < 0.3 and median_beta > 0.7:
        return "Observed best region appears concentrated at low alpha and high beta."
    elif median_alpha < 0.3:
        return "Observed best region appears concentrated at low alpha."
    elif median_alpha > 0.7:
        return "Observed best region appears concentrated at high alpha."
    elif median_beta < 0.3:
        return "Observed best region appears concentrated at low beta."
    elif median_beta > 0.7:
        return "Observed best region appears concentrated at high beta."
    else:
        return "No single dominant alpha-beta region; inspect Pareto trials and stability."


def plot_alpha_beta_landscape(
    df: pd.DataFrame,
    metric_col: str,
    title: str,
    ax: Optional[plt.Axes] = None,
    colorbar_label: str = ""
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Plots the alpha-beta landscape colored by a given metric.
    Highlights key optimal trials.
    
    Args:
        df: Input DataFrame.
        metric_col: Column name to use for coloring points.
        title: Title of the panel.
        ax: Optional matplotlib axes.
        colorbar_label: Label to display next to the colorbar.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6), facecolor='white')
    else:
        fig = ax.get_figure()
        
    # Plot scatter points colored by metric_col
    sc = ax.scatter(
        df['alpha'],
        df['beta'],
        c=df[metric_col],
        cmap='viridis',
        s=50,
        alpha=0.8,
        edgecolors='none',
        vmin=df[metric_col].min(),
        vmax=df[metric_col].max()
    )
    
    # Highlight top trial for the specific coloring metric
    idx_max_metric = df[metric_col].idxmax()
    top_metric_trial = df.loc[idx_max_metric]
    h1 = ax.scatter(
        top_metric_trial['alpha'],
        top_metric_trial['beta'],
        marker='*',
        s=220,
        facecolor='none',
        edgecolors='#ef4444',
        linewidths=2.0,
        zorder=5,
        label=f'Top {metric_col} (T{int(top_metric_trial["trial_number"])})'
    )
    
    # Highlight top trial by selection_score if available
    h2 = None
    if 'selection_score' in df.columns:
        idx_max_sel = df['selection_score'].idxmax()
        if idx_max_sel != idx_max_metric:
            top_sel_trial = df.loc[idx_max_sel]
            h2 = ax.scatter(
                top_sel_trial['alpha'],
                top_sel_trial['beta'],
                marker='D',
                s=120,
                facecolor='none',
                edgecolors='#3b82f6',
                linewidths=2.0,
                zorder=4,
                label=f'Top selection_score (T{int(top_sel_trial["trial_number"])})'
            )

    # Styling
    ax.set_title(title, fontsize=12, fontweight='bold', color='#0f172a', pad=10)
    ax.set_xlabel('Alpha (α)', fontsize=10, color='#334155')
    ax.set_ylabel('Beta (β)', fontsize=10, color='#334155')
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.grid(True, color='#e2e8f0', linestyle='-', linewidth=0.5, zorder=0)
    
    # Set tick styling
    ax.tick_params(colors='#475569', labelsize=9)
    for spine in ax.spines.values():
        spine.set_color('#cbd5e1')
        
    # Colorbar
    cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=8, colors='#475569')
    cbar.outline.set_edgecolor('#cbd5e1')
    if colorbar_label:
        cbar.set_label(colorbar_label, fontsize=9, color='#475569')
        
    # Legend
    ax.legend(loc='lower left', frameon=True, facecolor='white', edgecolor='#e2e8f0', fontsize=8)
    
    return fig, ax


def plot_pareto_view(
    df: pd.DataFrame,
    top_k_labels: int = 5,
    ax: Optional[plt.Axes] = None
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Plots the Pareto view showing Recall vs nDCG, drawing the frontier and labeling top trials.
    
    Args:
        df: Input DataFrame.
        top_k_labels: Number of top trials (by selection/balanced score) to annotate.
        ax: Optional matplotlib axes.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6), facecolor='white')
    else:
        fig = ax.get_figure()
        
    # Separate Pareto frontier and dominated points
    pareto_mask = df['is_pareto']
    pareto_df = df[pareto_mask].copy()
    dominated_df = df[~pareto_mask].copy()
    
    # Plot dominated trials in muted color
    ax.scatter(
        dominated_df['recall_at_100'],
        dominated_df['ndcg_at_100'],
        color='#94a3b8',
        s=40,
        alpha=0.5,
        edgecolors='none',
        label='Other Trials',
        zorder=2
    )
    
    # Plot Pareto trials in distinct bright color
    ax.scatter(
        pareto_df['recall_at_100'],
        pareto_df['ndcg_at_100'],
        color='#f43f5e',
        s=70,
        alpha=0.9,
        edgecolors='#be123c',
        linewidths=1.0,
        label='Pareto Frontier',
        zorder=3
    )
    
    # Connect Pareto frontier with a thin dashed line
    if len(pareto_df) > 1:
        # Sort by recall ascending to draw the line correctly
        pareto_sorted = pareto_df.sort_values(by='recall_at_100')
        ax.plot(
            pareto_sorted['recall_at_100'],
            pareto_sorted['ndcg_at_100'],
            color='#f43f5e',
            linestyle='--',
            linewidth=1.2,
            alpha=0.7,
            zorder=2
        )
        
    # Determine the ranking column for labeling
    rank_col = 'selection_score' if 'selection_score' in df.columns else 'balanced_score'
    
    # Find top K trials to annotate
    top_k_trials = df.sort_values(by=rank_col, ascending=False).head(top_k_labels)
    
    # Annotate top trials with smart offsetting to prevent overlap
    # We will use alternating offsets: (x_offset, y_offset)
    offsets = [
        (10, 10),    # Top-right
        (-30, 15),   # Top-left
        (10, -25),   # Bottom-right
        (-35, -20),  # Bottom-left
        (15, -5),    # Right-ish
        (-15, 15),
    ]
    
    for i, (_, row) in enumerate(top_k_trials.iterrows()):
        trial_num = int(row['trial_number'])
        alpha_val = row['alpha']
        beta_val = row['beta']
        ndcg_val = row['ndcg_at_100']
        recall_val = row['recall_at_100']
        
        label_text = (
            f"T{trial_num}\n"
            f"α={alpha_val:.2f}, β={beta_val:.2f}\n"
            f"nDCG={ndcg_val:.3f}, Recall={recall_val:.3f}"
        )
        
        # Pick offset based on index to distribute label positions
        dx, dy = offsets[i % len(offsets)]
        
        # Draw marker ring for annotated trials
        ax.scatter(
            recall_val,
            ndcg_val,
            s=120,
            facecolors='none',
            edgecolors='#1e293b',
            linewidths=1.5,
            zorder=4
        )
        
        ax.annotate(
            label_text,
            xy=(recall_val, ndcg_val),
            xytext=(dx, dy),
            textcoords='offset points',
            fontsize=8,
            fontweight='bold',
            color='#1e293b',
            arrowprops=dict(
                arrowstyle='->',
                color='#475569',
                lw=0.8,
                alpha=0.7
            ),
            bbox=dict(
                boxstyle='round,pad=0.2',
                facecolor='#ffffff',
                edgecolor='#e2e8f0',
                alpha=0.9,
                lw=0.8
            ),
            zorder=6
        )
        
    # Styling
    ax.set_title("C. Pareto view: Recall@100 vs nDCG@100", fontsize=12, fontweight='bold', color='#0f172a', pad=10)
    ax.set_xlabel("Recall@100", fontsize=10, color='#334155')
    ax.set_ylabel("nDCG@100", fontsize=10, color='#334155')
    
    # Adjust axes limits with padding
    r_min, r_max = df['recall_at_100'].min(), df['recall_at_100'].max()
    n_min, n_max = df['ndcg_at_100'].min(), df['ndcg_at_100'].max()
    
    r_pad = (r_max - r_min) * 0.08 if r_max > r_min else 0.05
    n_pad = (n_max - n_min) * 0.08 if n_max > n_min else 0.05
    
    ax.set_xlim(max(0, r_min - r_pad), r_max + r_pad * 1.5) # extra room for labels on right
    ax.set_ylim(max(0, n_min - n_pad), n_max + n_pad)
    
    ax.grid(True, color='#e2e8f0', linestyle='-', linewidth=0.5, zorder=0)
    ax.tick_params(colors='#475569', labelsize=9)
    for spine in ax.spines.values():
        spine.set_color('#cbd5e1')
        
    ax.legend(loc='lower left', frameon=True, facecolor='white', edgecolor='#e2e8f0', fontsize=9)
    
    return fig, ax


def create_dashboard(
    df: pd.DataFrame,
    disease: str,
    best_region_note: str,
    top_k_labels: int = 5
) -> plt.Figure:
    """
    Creates the combined 16x13 dashboard incorporating panels A, B, C and the summary note.
    
    Args:
        df: Input DataFrame.
        disease: Disease name.
        best_region_note: Generated consensus note string.
        top_k_labels: Number of top labels to plot in Pareto panel.
    """
    # 16x13 layout to give enough breathing room for labels and notes
    fig = plt.figure(figsize=(16, 13), facecolor='white')
    
    # 3-row grid layout: row 0 is Alpha-Beta plots, row 1 is Pareto plot, row 2 is note space
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 0.08], hspace=0.3, wspace=0.2)
    
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, :])
    
    # Plot panels
    plot_alpha_beta_landscape(df, 'ndcg_at_100', 'A. Alpha-Beta colored by nDCG@100', ax=ax_a, colorbar_label='nDCG@100')
    plot_alpha_beta_landscape(df, 'recall_at_100', 'B. Alpha-Beta colored by Recall@100', ax=ax_b, colorbar_label='Recall@100')
    plot_pareto_view(df, top_k_labels=top_k_labels, ax=ax_c)
    
    # Dashboard overall title
    fig.suptitle(
        f"{disease} - Optuna Tuning Visualization",
        fontsize=18,
        fontweight='bold',
        color='#1e3a8a',  # Navy
        y=0.96
    )
    
    # Subtitle
    fig.text(
        0.5, 0.93,
        "Metrics shown: nDCG@100 and Recall@100",
        fontsize=12,
        color='#475569',
        ha='center'
    )
    
    # Add note box at the bottom (within row 2)
    ax_note = fig.add_subplot(gs[2, :])
    ax_note.axis('off')
    
    # Draw note text inside a beautiful styled box
    ax_note.text(
        0.5, 0.5,
        f"Consensus Observation Note: {best_region_note}",
        ha='center',
        va='center',
        fontsize=11,
        fontweight='bold',
        color='#1e293b',
        bbox=dict(
            boxstyle='round,pad=0.6',
            facecolor='#f8fafc',
            edgecolor='#cbd5e1',
            alpha=0.9,
            lw=1.0
        )
    )
    
    # Adjust layout
    plt.subplots_adjust(top=0.90, bottom=0.05)
    
    return fig


def export_summary_tables(df: pd.DataFrame, disease: str, output_dir: Path) -> None:
    """
    Exports summary tables (top 20 and Pareto frontier trials) to CSV.
    
    Args:
        df: Input DataFrame.
        disease: Disease name.
        output_dir: Directory to export to.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Columns requested for output CSV
    requested_cols = [
        'trial_number', 'alpha', 'beta', 'ndcg_at_100', 'recall_at_100',
        'selection_score', 'balanced_score', 'is_pareto',
        'common_genes_top_100', 'duration_seconds'
    ]
    
    # Filter to only existing columns to avoid crash
    actual_cols = [col for col in requested_cols if col in df.columns]
    
    # 1. Export top 20 trials based on selection_score (or balanced_score)
    rank_col = 'selection_score' if 'selection_score' in df.columns else 'balanced_score'
    top_20 = df.sort_values(by=rank_col, ascending=False).head(20)[actual_cols]
    
    top_csv_path = output_dir / f"{disease}_top_trials_summary.csv"
    top_20.to_csv(top_csv_path, index=False)
    print(f"Exported top 20 summary to: {top_csv_path}")
    
    # 2. Export Pareto trials
    pareto_trials = df[df['is_pareto']].sort_values(by=rank_col, ascending=False)[actual_cols]
    pareto_csv_path = output_dir / f"{disease}_pareto_trials.csv"
    pareto_trials.to_csv(pareto_csv_path, index=False)
    print(f"Exported Pareto trials summary to: {pareto_csv_path}")


def create_interactive_plotly(df: pd.DataFrame, disease: str, output_path: Path) -> None:
    """
    Creates an interactive HTML dashboard using Plotly.
    
    Args:
        df: DataFrame.
        disease: Disease name.
        output_path: Path to write the output HTML.
    """
    if not PLOTLY_AVAILABLE:
        print("Warning: Plotly is not installed. Skipping interactive HTML export.")
        return
        
    print(f"Generating interactive Plotly dashboard for {disease}...")
    
    # Create subplots layout: 1st row has Landscape A & B, 2nd row has Pareto Plot
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            f"Alpha-Beta colored by nDCG@100",
            f"Alpha-Beta colored by Recall@100",
            f"Pareto View: Recall@100 vs nDCG@100"
        ),
        specs=[
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy", "colspan": 2}, None]
        ],
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )
    
    # Add rank score helper
    rank_col = 'selection_score' if 'selection_score' in df.columns else 'balanced_score'
    
    # Prepare custom data for hover tooltip
    customdata = np.stack((
        df['trial_number'],
        df['ndcg_at_100'],
        df['recall_at_100'],
        df[rank_col],
        df['is_pareto'].astype(str)
    ), axis=-1)
    
    hover_template = (
        "<b>Trial #%{customdata[0]}</b><br>"
        "Alpha: %{x:.4f}<br>"
        "Beta: %{y:.4f}<br>"
        "nDCG@100: %{customdata[1]:.4f}<br>"
        "Recall@100: %{customdata[2]:.4f}<br>"
        f"Score ({rank_col}): %{{customdata[3]:.4f}}<br>"
        "Is Pareto: %{customdata[4]}<extra></extra>"
    )
    
    # Plot Panel A: nDCG Landscape
    fig.add_trace(
        go.Scatter(
            x=df['alpha'],
            y=df['beta'],
            mode='markers',
            marker=dict(
                size=10,
                color=df['ndcg_at_100'],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="nDCG@100", x=0.45, y=0.78, len=0.45),
            ),
            customdata=customdata,
            hovertemplate=hover_template,
            name="nDCG Landscape"
        ),
        row=1, col=1
    )
    
    # Plot Panel B: Recall Landscape
    fig.add_trace(
        go.Scatter(
            x=df['alpha'],
            y=df['beta'],
            mode='markers',
            marker=dict(
                size=10,
                color=df['recall_at_100'],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Recall@100", x=1.02, y=0.78, len=0.45),
            ),
            customdata=customdata,
            hovertemplate=hover_template,
            name="Recall Landscape"
        ),
        row=1, col=2
    )
    
    # Plot Panel C: Pareto (Recall vs nDCG)
    # Separated into Dominated and Pareto for distinct hover/colors
    pareto_df = df[df['is_pareto']].copy()
    dominated_df = df[~df['is_pareto']].copy()
    
    p_customdata = np.stack((
        pareto_df['trial_number'],
        pareto_df['ndcg_at_100'],
        pareto_df['recall_at_100'],
        pareto_df[rank_col],
        pareto_df['is_pareto'].astype(str)
    ), axis=-1) if not pareto_df.empty else np.empty((0, 5))
    
    d_customdata = np.stack((
        dominated_df['trial_number'],
        dominated_df['ndcg_at_100'],
        dominated_df['recall_at_100'],
        dominated_df[rank_col],
        dominated_df['is_pareto'].astype(str)
    ), axis=-1) if not dominated_df.empty else np.empty((0, 5))
    
    # Dominated points (gray)
    fig.add_trace(
        go.Scatter(
            x=dominated_df['recall_at_100'],
            y=dominated_df['ndcg_at_100'],
            mode='markers',
            marker=dict(size=8, color='#94a3b8', opacity=0.6),
            customdata=d_customdata,
            hovertemplate=hover_template,
            name="Other Trials"
        ),
        row=2, col=1
    )
    
    # Pareto frontier points (crimson)
    fig.add_trace(
        go.Scatter(
            x=pareto_df['recall_at_100'],
            y=pareto_df['ndcg_at_100'],
            mode='markers',
            marker=dict(size=12, color='#f43f5e', line=dict(color='#be123c', width=1.5)),
            customdata=p_customdata,
            hovertemplate=hover_template,
            name="Pareto Frontier"
        ),
        row=2, col=1
    )
    
    # Pareto line connection
    if len(pareto_df) > 1:
        pareto_sorted = pareto_df.sort_values(by='recall_at_100')
        fig.add_trace(
            go.Scatter(
                x=pareto_sorted['recall_at_100'],
                y=pareto_sorted['ndcg_at_100'],
                mode='lines',
                line=dict(color='#f43f5e', width=1.5, dash='dash'),
                hoverinfo='skip',
                showlegend=False
            ),
            row=2, col=1
        )
        
    # Formatting axes and layout
    fig.update_layout(
        title=dict(
            text=f"Interactive Optuna Tuning Visualization: {disease}",
            font=dict(size=20, color='#1e3a8a'),
            x=0.5, y=0.95
        ),
        template='plotly_white',
        height=850,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Axes titles
    fig.update_xaxes(title_text="Alpha (α)", row=1, col=1)
    fig.update_yaxes(title_text="Beta (β)", row=1, col=1)
    fig.update_xaxes(title_text="Alpha (α)", row=1, col=2)
    fig.update_yaxes(title_text="Beta (β)", row=1, col=2)
    fig.update_xaxes(title_text="Recall@100", row=2, col=1)
    fig.update_yaxes(title_text="nDCG@100", row=2, col=1)
    
    # Write to file
    try:
        fig.write_html(str(output_path))
        print(f"Saved interactive dashboard: {output_path}")
    except Exception as e:
        print(f"Warning: Could not save interactive HTML dashboard: {e}")


def save_figure(fig: plt.Figure, base_path: Path, format_choice: str, dpi: int) -> None:
    """
    Saves a matplotlib figure in the specified format choice(s).
    
    Args:
        fig: Matplotlib Figure.
        base_path: Output file path (without extension).
        format_choice: 'png', 'pdf', 'svg', or 'all'.
        dpi: DPI for image rendering.
    """
    formats = []
    if format_choice == 'all':
        formats = ['png', 'pdf', 'svg']
    elif format_choice in ['png', 'pdf', 'svg']:
        formats = [format_choice]
    else:
        print(f"Warning: Unknown format choice '{format_choice}'. Defaulting to PNG.")
        formats = ['png']
        
    for fmt in formats:
        out_file = base_path.with_suffix(f".{fmt}")
        try:
            fig.savefig(out_file, dpi=dpi, bbox_inches='tight')
            print(f"Saved: {out_file}")
        except Exception as e:
            print(f"Warning: Failed to save figure as {fmt}: {e}. Skipping format.")


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Visualize Optuna multi-objective tuning parameters for BioRank."
    )
    
    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help="Path to the trial_history.tsv file."
    )
    
    parser.add_argument(
        '--disease',
        type=str,
        default=None,
        help="Disease abbreviation (e.g. BRCA). If not supplied, inferred from input path."
    )
    
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help="Directory to save generated figures. Defaults to <input_parent>/visualizations"
    )
    
    parser.add_argument(
        '--top-k-labels',
        type=int,
        default=5,
        help="Number of top trials to label on the Pareto plot (default: 5)."
    )
    
    parser.add_argument(
        '--dpi',
        type=int,
        default=300,
        help="DPI for saved PNG images (default: 300)."
    )
    
    parser.add_argument(
        '--show',
        action='store_true',
        help="If set, display the figures using plt.show()."
    )
    
    parser.add_argument(
        '--format',
        type=str,
        choices=['png', 'pdf', 'svg', 'all'],
        default='all',
        help="File format for saving figures (default: all)."
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help="If set, export interactive HTML plot via Plotly (requires plotly library)."
    )
    
    return parser.parse_args()


def main() -> None:
    """Main execution flow."""
    args = parse_args()
    
    try:
        # Load and clean history
        print(f"Loading trials from: {args.input}")
        df = load_trial_history(args.input)
        validate_columns(df)
        
        # Calculate balanced metrics & identify Pareto frontier
        print("Computing balanced metrics and identifying Pareto frontier...")
        df = compute_balanced_metrics(df)
        df = mark_pareto_frontier(df)
        
        # Infer disease name if not specified
        disease = args.disease
        if not disease:
            # Look at path parts to guess disease name
            known_diseases = ["BRCA", "COAD", "LUAD", "THCA", "BLCA", "PRAD", "STAD"]
            inferred = "UNKNOWN"
            for part in list(args.input.parts) + [args.input.name]:
                for d in known_diseases:
                    if d.lower() in part.lower():
                        inferred = d
                        break
                if inferred != "UNKNOWN":
                    break
            disease = inferred
            print(f"Inferred disease name: {disease}")
            
        # Set up output directory
        out_dir = args.output_dir
        if not out_dir:
            out_dir = args.input.parent / "visualizations"
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"Saving output files to directory: {out_dir}")
        
        # Compute consensus comment
        best_region_note = infer_best_region(df)
        print(f"Consensus comment: {best_region_note}")
        
        # --- 1. Draw and Save Dashboard ---
        print("Generating and saving primary dashboard...")
        dashboard_fig = create_dashboard(df, disease, best_region_note, top_k_labels=args.top_k_labels)
        dashboard_base = out_dir / f"{disease}_optuna_dashboard"
        save_figure(dashboard_fig, dashboard_base, args.format, args.dpi)
        
        # --- 2. Draw and Save Individual Plots ---
        print("Generating and saving individual panels...")
        
        # Panel A Individual
        fig_a, ax_a = plt.subplots(figsize=(8, 6), facecolor='white')
        plot_alpha_beta_landscape(df, 'ndcg_at_100', 'Alpha-Beta Landscape: nDCG@100', ax=ax_a, colorbar_label='nDCG@100')
        save_figure(fig_a, out_dir / f"{disease}_alpha_beta_ndcg100", args.format, args.dpi)
        plt.close(fig_a)
        
        # Panel B Individual
        fig_b, ax_b = plt.subplots(figsize=(8, 6), facecolor='white')
        plot_alpha_beta_landscape(df, 'recall_at_100', 'Alpha-Beta Landscape: Recall@100', ax=ax_b, colorbar_label='Recall@100')
        save_figure(fig_b, out_dir / f"{disease}_alpha_beta_recall100", args.format, args.dpi)
        plt.close(fig_b)
        
        # Panel C Individual
        fig_c, ax_c = plt.subplots(figsize=(10, 6), facecolor='white')
        plot_pareto_view(df, top_k_labels=args.top_k_labels, ax=ax_c)
        save_figure(fig_c, out_dir / f"{disease}_pareto_recall100_ndcg100", args.format, args.dpi)
        plt.close(fig_c)
        
        # --- 3. Export Summary CSVs ---
        export_summary_tables(df, disease, out_dir)
        
        # --- 4. Export Interactive plotly HTML if requested ---
        if args.interactive:
            plotly_html_path = out_dir / f"{disease}_optuna_interactive.html"
            create_interactive_plotly(df, disease, plotly_html_path)
            
        # Display figures if show flag is set
        if args.show:
            plt.show()
            
        # Explicitly close all remaining matplotlib figures
        plt.close('all')
        print("Visualization generation completed successfully.")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
