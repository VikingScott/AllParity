import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# Import your modules
from src.data_loader import get_merged_market_state
from src.macro_regime_signal_generator import run_signal_pipeline

def verify_and_visualize():
    print("1. Loading Data...")
    # Update paths if your data folder structure is different
    df = get_merged_market_state('data/Macro_Daily_Final.csv', 'data/asset_prices.csv')
    
    print(f"   Loaded {len(df)} rows. Date range: {df.index.min().date()} to {df.index.max().date()}")

    print("2. Running Signal Pipeline...")
    signal_df = run_signal_pipeline(df)
    
    # Drop NaNs from the start (warm-up period) for cleaner plotting
    plot_df = signal_df.dropna(subset=['Regime', 'Trend_Growth']).copy()
    
    print("3. Generating Visualization...")
    sns.set_theme(style="whitegrid")
    
    # Create a 3-panel plot
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, 
                             gridspec_kw={'height_ratios': [1, 2, 1.5]})

    # --- Panel 1: Regime Strip ---
    # 1=Green, 2=Blue, 3=Orange, 4=Red
    cmap = {1: 'green', 2: 'cornflowerblue', 3: 'orange', 4: 'firebrick'}
    colors = plot_df['Regime'].map(cmap)
    
    axes[0].scatter(plot_df.index, [1]*len(plot_df), c=colors, marker='|', s=500, alpha=1.0)
    axes[0].set_yticks([])
    axes[0].set_title("Regime History (Green=1, Blue=2, Orange=3, Red=4)", fontsize=14, fontweight='bold')
    
    # --- Panel 2: Macro Trends ---
    axes[1].plot(plot_df.index, plot_df['Trend_Growth'], label='Growth Trend', color='green', linewidth=1.5)
    axes[1].plot(plot_df.index, plot_df['Trend_Inflation_Blended'], label='Inflation Trend', color='orange', linewidth=1.5)
    axes[1].axhline(0, color='black', linestyle='--', alpha=0.5)
    axes[1].set_ylabel("Trend Strength")
    axes[1].legend(loc='upper left')
    axes[1].set_title("Underlying Macro Signals", fontsize=12)
    
    # --- Panel 3: Market Veto ---
    # Plot Score on left axis, VIX on right axis
    ax3 = axes[2]
    ax3_right = ax3.twinx()
    
    # VIX (Area chart)
    if 'Signal_Vol_VIX' in plot_df.columns:
        ax3_right.fill_between(plot_df.index, plot_df['Signal_Vol_VIX'], 0, color='gray', alpha=0.2, label='VIX (Right)')
        ax3_right.set_ylabel("VIX Level")
        ax3_right.set_ylim(0, 80)
    
    # Stress Score (Line)
    ax3.plot(plot_df.index, plot_df['Market_Stress_Score'], color='purple', linewidth=2, label='Stress Score')
    ax3.axhline(-2, color='red', linestyle='--', label='Panic Threshold (-2)')
    ax3.set_ylabel("Score (0 to -3)")
    ax3.set_ylim(-3.5, 0.5)
    
    # Combine legends
    lines, labels = ax3.get_legend_handles_labels()
    lines2, labels2 = ax3_right.get_legend_handles_labels()
    ax3.legend(lines + lines2, labels + labels2, loc='upper left')
    ax3.set_title("Market Veto Triggers", fontsize=12)

    plt.tight_layout()
    output_file = "regime_verification_full.png"
    plt.savefig(output_file)
    print(f"✅ Visualization saved to: {output_file}")
    print("   Open this image to inspect the stability of your signals.")

if __name__ == "__main__":
    verify_and_visualize()