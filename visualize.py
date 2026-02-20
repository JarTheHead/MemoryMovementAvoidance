#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt
import sys
import os

def visualize_results(csv_file="movement_avoidance_results.csv"):
    """Create visualization of the test results"""

    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found. Run tests first.")
        return

    # Read the CSV data
    df = pd.read_csv(csv_file)

    # Convert Time column to datetime
    df['Time'] = pd.to_datetime(df['Time'])

    # Convert boolean string to numeric for plotting
    df['Swap_Activity'] = df['Swap_Activity'].map({'True': 1, 'False': 0})

    # Create plots
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Movement Avoidance Test Results')

    # Plot 1: Memory Pressure and CPU Pressure over time
    axes[0, 0].plot(df['Time'], df['Memory_Pressure'], label='Memory Pressure (%)')
    axes[0, 0].plot(df['Time'], df['CPU_Pressure'], label='CPU Pressure (%)')
    axes[0, 0].set_title('System Pressure Over Time')
    axes[0, 0].legend()
    axes[0, 0].tick_params(axis='x', rotation=45)

    # Plot 2: Compression Ratio over time
    axes[0, 1].plot(df['Time'], df['Compression_Ratio'], 'g-', label='Compression Ratio')
    axes[0, 1].set_title('Compression Ratio Over Time')
    axes[0, 1].legend()
    axes[0, 1].tick_params(axis='x', rotation=45)

    # Plot 3: Swap Activity over time
    axes[1, 0].plot(df['Time'], df['Swap_Activity'], 'r-', label='Swap Activity')
    axes[1, 0].set_title('Swap Activity Over Time')
    axes[1, 0].legend()
    axes[1, 0].tick_params(axis='x', rotation=45)

    # Plot 4: Correlation between Compression Ratio and Swap Activity
    axes[1, 1].scatter(df['Compression_Ratio'], df['Swap_Activity'], alpha=0.5)
    axes[1, 1].set_xlabel('Compression Ratio')
    axes[1, 1].set_ylabel('Swap Activity (Boolean)')
    axes[1, 1].set_title('Compression Ratio vs Swap Activity')

    # Rotate x-axis labels for better readability
    for ax in axes.flat:
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    plt.tight_layout()
    plt.show()

    # Print summary statistics
    print("\n=== Summary Statistics ===")
    print(f"Total measurements: {len(df)}")
    print(f"Average Memory Pressure: {df['Memory_Pressure'].mean():.2f}%")
    print(f"Average CPU Pressure: {df['CPU_Pressure'].mean():.2f}%")
    print(f"Average Compression Ratio: {df['Compression_Ratio'].mean():.2f}x")
    print(f"Swap Activity Occurred: {df['Swap_Activity'].sum()} times")
    print(f"Times without Swap Activity: {len(df) - df['Swap_Activity'].sum()}")

def main():
    csv_file = "movement_avoidance_results.csv"
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]

    try:
        visualize_results(csv_file)
    except ImportError:
        print("matplotlib not installed. Install with: pip install matplotlib")
        print("Alternatively, examine the CSV file directly:")
        print(f"head {csv_file}")

if __name__ == "__main__":
    main()