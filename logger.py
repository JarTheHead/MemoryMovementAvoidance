#!/usr/bin/env python3
"""
Extended Logger - CSV logging with NUMA support.

Adds columns:
- Node0_Free, Node1_Free: Per-node memory available
- NUMA_Miss_Rate: Cross-node memory access rate
- Algorithm: Current compression algorithm
- Compression_Ratio_Node0, Compression_Ratio_Node1: Per-node compression ratios
"""

import sys
import os
from datetime import datetime

LOG_FILE = "movement_avoidance_results.csv"


def initialize_log():
    """Initialize the log file with headers if it doesn't exist"""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("Time,Memory_Pressure,CPU_Pressure,Swap_Activity,Compression_Ratio,"
                    "Node0_Free,Node1_Free,NUMA_Miss_Rate,Algorithm,"
                    "Compression_Ratio_Node0,Compression_Ratio_Node1\n")
        print(f"Initialized log file: {LOG_FILE}")


def log_metrics(timestamp, mem_pressure, cpu_pressure, swap_activity, compression_ratio,
                node0_free=0, node1_free=0, numa_miss_rate=0, algorithm="lz4",
                cr_node0=1.0, cr_node1=1.0):
    """Log metrics to CSV file"""
    # Convert timestamp to readable format
    if timestamp.startswith('20'):
        # Already a datetime string
        time_str = timestamp
    else:
        # Assume it's a datetime object
        time_str = str(timestamp)

    # Format swap activity as boolean string
    swap_str = "True" if str(swap_activity).lower() in ['true', '1', 'yes'] else "False"

    # Prepare log entry
    log_entry = f"{time_str},{mem_pressure},{cpu_pressure},{swap_str},{compression_ratio},"
    log_entry += f"{node0_free},{node1_free},{numa_miss_rate},{algorithm},"
    log_entry += f"{cr_node0},{cr_node1}\n"

    # Append to log file
    with open(LOG_FILE, "a") as f:
        f.write(log_entry)

    print(f"Logged: {log_entry.strip()}")


def log_from_stats(timestamp, metrics, numa_stats=None, algorithm="lz4"):
    """
    Log metrics from comprehensive stats dictionaries.

    Args:
        timestamp: Timestamp string
        metrics: Dict with Memory_Pressure, CPU_Pressure, Swap_Activity, Compression_Ratio
        numa_stats: Optional NUMA stats dict from NUMAMonitor
        algorithm: Current compression algorithm
    """
    mem_pressure = metrics.get("Memory_Pressure", metrics.get("mem_pressure", 0))
    cpu_pressure = metrics.get("CPU_Pressure", metrics.get("cpu_pressure", 0))
    swap_activity = metrics.get("Swap_Activity", metrics.get("swap_activity", False))
    compression_ratio = metrics.get("Compression_Ratio", metrics.get("compression_ratio", 1.0))

    # Extract node stats
    node0_free = 0
    node1_free = 0
    cr_node0 = 1.0
    cr_node1 = 1.0

    if numa_stats:
        node_memory = numa_stats.get("node_memory_stats", {})

        # Get free memory for each node (in MB)
        for node_name, stats in node_memory.items():
            free_kb = stats.get("MemFree", 0) / 1024  # Convert to MB
            if node_name == "Node0":
                node0_free = free_kb
            elif node_name == "Node1":
                node1_free = free_kb

        # Get NUMA miss rate
        numa_miss_rate = numa_stats.get("numa_miss_rate", 0)

        # Get per-node compression ratios
        per_node_cr = numa_stats.get("per_node_compression", {})
        cr_node0 = per_node_cr.get("Node0", 1.0)
        cr_node1 = per_node_cr.get("Node1", 1.0)

    else:
        numa_miss_rate = 0

    log_metrics(
        timestamp, mem_pressure, cpu_pressure, swap_activity, compression_ratio,
        node0_free, node1_free, numa_miss_rate, algorithm,
        cr_node0, cr_node1
    )


def main():
    """Main function to log metrics from command line arguments"""
    # Check if we have enough arguments for extended logging
    if len(sys.argv) >= 12:
        # Full format with NUMA stats
        timestamp = sys.argv[1]
        mem_pressure = sys.argv[2]
        cpu_pressure = sys.argv[3]
        swap_activity = sys.argv[4]
        compression_ratio = sys.argv[5]
        node0_free = sys.argv[6]
        node1_free = sys.argv[7]
        numa_miss_rate = sys.argv[8]
        algorithm = sys.argv[9]
        cr_node0 = sys.argv[10]
        cr_node1 = sys.argv[11]

        log_metrics(timestamp, mem_pressure, cpu_pressure, swap_activity, compression_ratio,
                   node0_free, node1_free, numa_miss_rate, algorithm, cr_node0, cr_node1)
    elif len(sys.argv) == 6:
        # Original format
        timestamp = sys.argv[1]
        mem_pressure = sys.argv[2]
        cpu_pressure = sys.argv[3]
        swap_activity = sys.argv[4]
        compression_ratio = sys.argv[5]

        log_metrics(timestamp, mem_pressure, cpu_pressure, swap_activity, compression_ratio,
                   node0_free=0, node1_free=0, numa_miss_rate=0, algorithm="lz4",
                   cr_node0=1.0, cr_node1=1.0)
    else:
        print("Usage: python3 logger.py <timestamp> <memory_pressure> <cpu_pressure> <swap_activity> <compression_ratio>")
        print("With NUMA: python3 logger.py <timestamp> <mem> <cpu> <swap> <ratio> <node0_free> <node1_free> <numa_miss_rate> <algorithm> <cr_node0> <cr_node1>")
        print("Example: python3 logger.py '2023-01-01 12:00:00' 45.2 23.1 True 2.5")
        print("Example with NUMA: python3 logger.py '2023-01-01 12:00:00' 45.2 23.1 True 2.5 1024 2048 5.0 lz4 2.5 2.3")
        sys.exit(1)


if __name__ == "__main__":
    # If called directly without arguments, just initialize the log
    if len(sys.argv) == 1:
        initialize_log()
        print(f"Logger initialized. Ready to log to {LOG_FILE}")
    else:
        main()
