#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
import numpy as np


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

    # Check if we have NUMA columns
    has_numa = 'NUMA_Miss_Rate' in df.columns
    has_algorithm = 'Algorithm' in df.columns
    has_node_stats = 'Node0_Free' in df.columns

    # Create plots based on available data
    if has_numa and has_algorithm:
        # Full NUMA + algorithm visualization (4x2 grid)
        fig, axes = plt.subplots(4, 2, figsize=(16, 14))
        fig.suptitle('Movement Avoidance Test Results - NUMA & Adaptive Compression', fontsize=14)

        # Row 1: Memory Pressure and CPU Pressure over time
        axes[0, 0].plot(df['Time'], df['Memory_Pressure'], label='Memory Pressure (%)', linewidth=2)
        axes[0, 0].plot(df['Time'], df['CPU_Pressure'], label='CPU Pressure (%)', linewidth=2)
        axes[0, 0].set_title('System Pressure Over Time')
        axes[0, 0].legend()
        axes[0, 0].tick_params(axis='x', rotation=45)

        # Row 1: Compression Ratio over time
        axes[0, 1].plot(df['Time'], df['Compression_Ratio'], 'g-', label='Compression Ratio', linewidth=2)
        axes[0, 1].set_title('Compression Ratio Over Time')
        axes[0, 1].legend()
        axes[0, 1].tick_params(axis='x', rotation=45)

        # Row 2: NUMA Miss Rate and Swap Activity
        axes[1, 0].plot(df['Time'], df['NUMA_Miss_Rate'], 'orange', label='NUMA Miss Rate (%)', linewidth=2)
        axes[1, 0].set_title('NUMA Miss Rate Over Time')
        axes[1, 0].legend()
        axes[1, 0].tick_params(axis='x', rotation=45)

        axes[1, 1].plot(df['Time'], df['Swap_Activity'], 'r-', label='Swap Activity', linewidth=2)
        axes[1, 1].set_title('Swap Activity Over Time')
        axes[1, 1].legend()
        axes[1, 1].tick_params(axis='x', rotation=45)

        # Row 3: Per-Node Memory Stats
        if has_node_stats:
            axes[2, 0].plot(df['Time'], df['Node0_Free'], label='Node0 Free (MB)', linewidth=2)
            axes[2, 0].plot(df['Time'], df['Node1_Free'], label='Node1 Free (MB)', linewidth=2)
            axes[2, 0].set_title('Per-Node Free Memory Over Time')
            axes[2, 0].legend()
            axes[2, 0].tick_params(axis='x', rotation=45)

            # Per-node compression ratios
            if 'Compression_Ratio_Node0' in df.columns:
                axes[2, 1].plot(df['Time'], df['Compression_Ratio_Node0'], 'b-', label='Node0 Ratio', linewidth=2)
                axes[2, 1].plot(df['Time'], df['Compression_Ratio_Node1'], 'c-', label='Node1 Ratio', linewidth=2)
                axes[2, 1].set_title('Per-Node Compression Ratios')
                axes[2, 1].legend()
                axes[2, 1].tick_params(axis='x', rotation=45)

        # Row 4: Algorithm selection over time
        if has_algorithm:
            # Convert algorithm names to numeric for plotting
            algo_mapping = {'lzo': 0, 'lz4': 1, 'zstd': 2}
            df['Algorithm_Num'] = df['Algorithm'].map(algo_mapping).fillna(1)
            axes[3, 0].plot(df['Time'], df['Algorithm_Num'], 'purple', label='Algorithm', linewidth=2, marker='o')
            axes[3, 0].set_yticks([0, 1, 2])
            axes[3, 0].set_yticklabels(['LZO', 'LZ4', 'ZSTD'])
            axes[3, 0].set_title('Compression Algorithm Over Time')
            axes[3, 0].legend()
            axes[3, 0].tick_params(axis='x', rotation=45)

            # Algorithm comparison - average metrics per algorithm
            if len(df['Algorithm'].unique()) > 1:
                algo_stats = df.groupby('Algorithm').agg({
                    'Compression_Ratio': 'mean',
                    'NUMA_Miss_Rate': 'mean',
                    'Swap_Activity': 'mean'
                }).reset_index()

                axes[3, 1].bar(algo_stats['Algorithm'], algo_stats['Compression_Ratio'], alpha=0.7)
                axes[3, 1].set_ylabel('Avg Compression Ratio')
                axes[3, 1].set_title('Algorithm Comparison - Compression Ratio')
                axes[3, 1].tick_params(axis='x', rotation=45)
        else:
            # Remove unused axis
            fig.delaxes(axes[3, 1])

    elif has_numa:
        # NUMA visualization (3x2 grid)
        fig, axes = plt.subplots(3, 2, figsize=(16, 12))
        fig.suptitle('Movement Avoidance Test Results - NUMA Support', fontsize=14)

        # Memory Pressure and CPU Pressure
        axes[0, 0].plot(df['Time'], df['Memory_Pressure'], label='Memory Pressure (%)', linewidth=2)
        axes[0, 0].plot(df['Time'], df['CPU_Pressure'], label='CPU Pressure (%)', linewidth=2)
        axes[0, 0].set_title('System Pressure Over Time')
        axes[0, 0].legend()
        axes[0, 0].tick_params(axis='x', rotation=45)

        # Compression Ratio
        axes[0, 1].plot(df['Time'], df['Compression_Ratio'], 'g-', label='Compression Ratio', linewidth=2)
        axes[0, 1].set_title('Compression Ratio Over Time')
        axes[0, 1].legend()
        axes[0, 1].tick_params(axis='x', rotation=45)

        # NUMA Miss Rate
        axes[1, 0].plot(df['Time'], df['NUMA_Miss_Rate'], 'orange', label='NUMA Miss Rate (%)', linewidth=2)
        axes[1, 0].set_title('NUMA Miss Rate Over Time')
        axes[1, 0].legend()
        axes[1, 0].tick_params(axis='x', rotation=45)

        # Swap Activity
        axes[1, 1].plot(df['Time'], df['Swap_Activity'], 'r-', label='Swap Activity', linewidth=2)
        axes[1, 1].set_title('Swap Activity Over Time')
        axes[1, 1].legend()
        axes[1, 1].tick_params(axis='x', rotation=45)

        # Per-Node Memory
        if has_node_stats:
            axes[2, 0].plot(df['Time'], df['Node0_Free'], label='Node0 Free (MB)', linewidth=2)
            axes[2, 0].plot(df['Time'], df['Node1_Free'], label='Node1 Free (MB)', linewidth=2)
            axes[2, 0].set_title('Per-Node Free Memory Over Time')
            axes[2, 0].legend()
            axes[2, 0].tick_params(axis='x', rotation=45)

        # Remove unused axes
        if not has_node_stats:
            fig.delaxes(axes[2, 0])

    elif has_algorithm:
        # Algorithm-only visualization (3x2 grid)
        fig, axes = plt.subplots(3, 2, figsize=(16, 12))
        fig.suptitle('Movement Avoidance Test Results - Algorithm Comparison', fontsize=14)

        # System Pressure
        axes[0, 0].plot(df['Time'], df['Memory_Pressure'], label='Memory Pressure (%)', linewidth=2)
        axes[0, 0].plot(df['Time'], df['CPU_Pressure'], label='CPU Pressure (%)', linewidth=2)
        axes[0, 0].set_title('System Pressure Over Time')
        axes[0, 0].legend()
        axes[0, 0].tick_params(axis='x', rotation=45)

        # Compression Ratio
        axes[0, 1].plot(df['Time'], df['Compression_Ratio'], 'g-', label='Compression Ratio', linewidth=2)
        axes[0, 1].set_title('Compression Ratio Over Time')
        axes[0, 1].legend()
        axes[0, 1].tick_params(axis='x', rotation=45)

        # Algorithm over time
        algo_mapping = {'lzo': 0, 'lz4': 1, 'zstd': 2}
        df['Algorithm_Num'] = df['Algorithm'].map(algo_mapping).fillna(1)
        axes[1, 0].plot(df['Time'], df['Algorithm_Num'], 'purple', label='Algorithm', linewidth=2, marker='o')
        axes[1, 0].set_yticks([0, 1, 2])
        axes[1, 0].set_yticklabels(['LZO', 'LZ4', 'ZSTD'])
        axes[1, 0].set_title('Compression Algorithm Over Time')
        axes[1, 0].legend()
        axes[1, 0].tick_params(axis='x', rotation=45)

        # Algorithm comparison bar chart
        if len(df['Algorithm'].unique()) > 1:
            algo_stats = df.groupby('Algorithm').agg({
                'Compression_Ratio': 'mean',
                'NUMA_Miss_Rate': 'mean',
                'Swap_Activity': 'mean'
            }).reset_index()

            axes[1, 1].bar(algo_stats['Algorithm'], algo_stats['Compression_Ratio'], alpha=0.7)
            axes[1, 1].set_ylabel('Avg Compression Ratio')
            axes[1, 1].set_title('Algorithm Comparison - Compression Ratio')
            axes[1, 1].tick_params(axis='x', rotation=45)

        # Swap Activity
        axes[2, 0].plot(df['Time'], df['Swap_Activity'], 'r-', label='Swap Activity', linewidth=2)
        axes[2, 0].set_title('Swap Activity Over Time')
        axes[2, 0].legend()
        axes[2, 0].tick_params(axis='x', rotation=45)

    else:
        # Original 2x2 grid
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

    # NUMA-specific statistics
    if has_numa:
        print("\n=== NUMA Statistics ===")
        print(f"Average NUMA Miss Rate: {df['NUMA_Miss_Rate'].mean():.2f}%")

        if has_node_stats:
            print(f"Average Node0 Free: {df['Node0_Free'].mean():.2f} MB")
            print(f"Average Node1 Free: {df['Node1_Free'].mean():.2f} MB")

    # Algorithm-specific statistics
    if has_algorithm:
        print("\n=== Algorithm Statistics ===")
        algo_stats = df.groupby('Algorithm').agg({
            'Compression_Ratio': 'mean',
            'NUMA_Miss_Rate': 'mean',
            'Swap_Activity': 'mean'
        })
        print(algo_stats.round(3))


def visualize_stressng_sweep(json_file=None):
    """Create visualization of stress-ng sweep results"""

    if json_file is None:
        # Find the most recent stressng_sweep file
        import glob
        files = glob.glob("stressng_sweep_*.json")
        if files:
            json_file = max(files, key=os.path.getctime)
        else:
            print("Error: No stress-ng sweep JSON file found")
            return

    if not os.path.exists(json_file):
        print(f"Error: {json_file} not found")
        return

    import json

    with open(json_file, 'r') as f:
        data = json.load(f)

    # Create heatmap of results
    results = data.get('results', [])

    if not results:
        print("No results found in JSON file")
        return

    # Extract patterns and contentions
    patterns = list(set(r['pattern'] for r in results))
    contentions = sorted(list(set(r['contention'] for r in results)))

    # Create performance matrix
    perf_matrix = np.zeros((len(contentions), len(patterns)))
    for result in results:
        contention_idx = contentions.index(result['contention'])
        pattern_idx = patterns.index(result['pattern'])
        perf_matrix[contention_idx, pattern_idx] = result.get('throughput', 0)

    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle('StressNG Sweep Results - Performance Heatmap', fontsize=14)

    # Heatmap
    im = axes[0].imshow(perf_matrix, cmap='viridis', aspect='auto')
    axes[0].set_xticks(range(len(patterns)))
    axes[0].set_xticklabels(patterns)
    axes[0].set_yticks(range(len(contentions)))
    axes[0].set_yticklabels(contentions)
    axes[0].set_xlabel('Memory Pattern')
    axes[0].set_ylabel('CPU Contention (%)')
    axes[0].set_title('Throughput (MB/s)')

    # Add colorbar
    plt.colorbar(im, ax=axes[0])

    # Line chart of contentions by pattern
    for i, pattern in enumerate(patterns):
        pattern_results = [r for r in results if r['pattern'] == pattern]
        pattern_results.sort(key=lambda x: x['contention'])
        contentions_for_plot = [r['contention'] for r in pattern_results]
        throughputs = [r.get('throughput', 0) for r in pattern_results]
        axes[1].plot(contentions_for_plot, throughputs, marker='o', label=pattern)

    axes[1].set_xlabel('CPU Contention (%)')
    axes[1].set_ylabel('Throughput (MB/s)')
    axes[1].set_title('Throughput vs CPU Contention by Pattern')
    axes[1].legend()

    plt.tight_layout()
    plt.show()

    # Print summary
    print("\n=== StressNG Sweep Summary ===")
    print(f"Tested {len(results)} configurations")
    successful = sum(1 for r in results if r.get('success', False))
    print(f"Successful: {successful}, Failed: {len(results) - successful}")

    # Find optimal configuration
    if successful > 0:
        best_result = max((r for r in results if r.get('success', False)),
                         key=lambda x: x.get('throughput', 0))
        print(f"Best configuration: {best_result['pattern']} pattern, "
              f"{best_result['contention']}% contention")
        print(f"Best throughput: {best_result.get('throughput', 0):.2f} MB/s")


def main():
    csv_file = "movement_avoidance_results.csv"
    json_file = None

    # Parse arguments
    for i, arg in enumerate(sys.argv[1:]):
        if arg.endswith('.csv'):
            csv_file = arg
        elif arg.endswith('.json'):
            json_file = arg

    try:
        # Check if we have stress-ng JSON file
        if json_file:
            visualize_stressng_sweep(json_file)
        else:
            visualize_results(csv_file)
    except ImportError as e:
        print("Required package not installed:")
        if 'matplotlib' in str(e):
            print("matplotlib not installed. Install with: pip install matplotlib pandas")
        else:
            print(str(e))
        print("\nTo examine the CSV file directly:")
        print(f"head {csv_file}")


if __name__ == "__main__":
    main()
