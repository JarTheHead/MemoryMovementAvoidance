#!/usr/bin/env python3
"""
NUMA Monitor - Per-node memory, PSI, and migration statistics.

Monitors:
- Per-node memory stats (MemFree, MemTotal, etc.) from /sys/devices/system/node/node*/memory_*
- NUMA hits/misses for cross-node access rates
- Per-node compression ratio via zswap debugfs (if available)
"""

import os
import glob


class NUMAMonitor:
    def __init__(self):
        self.node_paths = glob.glob("/sys/devices/system/node/node*")
        self.num_nodes = len(self.node_paths)

    def is_numa_system(self):
        """Check if system has NUMA topology"""
        return self.num_nodes > 1

    def get_node_memory_stats(self, node_id):
        """Get memory statistics for a specific node"""
        node_path = f"/sys/devices/system/node/node{node_id}"
        stats = {
            "node_id": node_id,
            "MemTotal": 0,
            "MemFree": 0,
            "MemAvailable": 0,
            "Buffers": 0,
            "Cached": 0,
            "SwapCached": 0,
            "active": 0,
            "inactive": 0,
            "active_anon": 0,
            "inactive_anon": 0,
            "active_file": 0,
            "inactive_file": 0,
        }

        try:
            # Read from node-specific memory info
            memory_info_path = f"{node_path}/memory_stat"
            if os.path.exists(memory_info_path):
                with open(memory_info_path, "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            key, value = parts[0], int(parts[1])
                            if key in stats:
                                stats[key] = value
            else:
                # Fallback to /proc/meminfo for single-node or when node stats unavailable
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            key = parts[0].rstrip(":")
                            value = int(parts[1]) * 1024  # Convert to bytes
                            if key in stats:
                                stats[key] = value
        except Exception as e:
            print(f"Error reading node {node_id} memory stats: {e}")

        return stats

    def get_all_node_memory_stats(self):
        """Get memory statistics for all nodes"""
        stats = {}
        for node_path in self.node_paths:
            node_id = int(node_path.split("node")[-1])
            stats[f"Node{node_id}"] = self.get_node_memory_stats(node_id)
        return stats

    def get_numa_counts(self):
        """Get NUMA hit and miss counts from node stats"""
        numa_hits = 0
        numa_misses = 0

        for node_path in self.node_paths:
            node_id = int(node_path.split("node")[-1])
            node_stat_path = f"{node_path}/numastat"

            try:
                if os.path.exists(node_stat_path):
                    with open(node_stat_path, "r") as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 2:
                                key, value = parts[0], int(parts[1])
                                if key == "numa_hit":
                                    numa_hits += value
                                elif key == "numa_miss":
                                    numa_misses += value
            except Exception as e:
                print(f"Error reading NUMA stats for node {node_id}: {e}")

        return {"hits": numa_hits, "misses": numa_misses}

    def get_numa_miss_rate(self):
        """Calculate NUMA miss rate (cross-node access percentage)"""
        counts = self.get_numa_counts()
        total = counts["hits"] + counts["misses"]
        if total == 0:
            return 0.0
        return (counts["misses"] / total) * 100

    def get_per_node_compression_ratio(self):
        """Get compression ratio per node via zswap debugfs"""
        ratios = {}

        try:
            # Zswap stats are global, not per-node
            # We estimate per-node ratio based on memory allocation distribution
            with open("/sys/kernel/debug/zswap/pool_total_size", "r") as f:
                pool_size = int(f.read().strip())
            with open("/sys/kernel/debug/zswap/stored_pages", "r") as f:
                stored_pages = int(f.read().strip())

            if stored_pages > 0:
                uncompressed_size = stored_pages * 4096
                if pool_size > 0:
                    ratio = uncompressed_size / pool_size

                    # Distribute ratio across nodes based on their memory usage
                    node_stats = self.get_all_node_memory_stats()
                    total_used = 0
                    for node_name, stats in node_stats.items():
                        total = stats.get("MemTotal", 0)
                        free = stats.get("MemFree", 0)
                        used = total - free
                        if used > 0:
                            total_used += used

                    for node_name, stats in node_stats.items():
                        total = stats.get("MemTotal", 0)
                        free = stats.get("MemFree", 0)
                        used = total - free
                        if total_used > 0 and used > 0:
                            node_ratio = ratio * (used / total_used)
                            ratios[node_name] = node_ratio
                        else:
                            ratios[node_name] = ratio
        except FileNotFoundError:
            # Debugfs not mounted or zswap debug info not available
            pass
        except Exception as e:
            print(f"Error calculating per-node compression ratio: {e}")

        return ratios

    def get_node_pressure(self, node_id):
        """Get PSI-like pressure metric for a specific node"""
        try:
            node_path = f"/sys/devices/system/node/node{node_id}/memory_pressure"
            if os.path.exists(node_path):
                with open(node_path, "r") as f:
                    return float(f.read().strip())
        except Exception as e:
            print(f"Error reading node {node_id} pressure: {e}")

        # Fallback to calculating from memory usage
        stats = self.get_node_memory_stats(node_id)
        total = stats.get("MemTotal", 1)
        free = stats.get("MemFree", 0)
        if total > 0:
            return ((total - free) / total) * 100
        return 0.0

    def get_all_node_pressure(self):
        """Get pressure for all nodes"""
        pressures = {}
        for node_path in self.node_paths:
            node_id = int(node_path.split("node")[-1])
            pressures[f"Node{node_id}"] = self.get_node_pressure(node_id)
        return pressures

    def get_system_summary(self):
        """Get comprehensive NUMA system summary"""
        summary = {
            "is_numa": self.is_numa_system(),
            "num_nodes": self.num_nodes,
            "node_memory_stats": self.get_all_node_memory_stats(),
            "numa_counts": self.get_numa_counts(),
            "numa_miss_rate": self.get_numa_miss_rate(),
            "node_pressure": self.get_all_node_pressure(),
        }

        if self.is_numa_system():
            summary["per_node_compression"] = self.get_per_node_compression_ratio()

        return summary


def main():
    monitor = NUMAMonitor()

    print("=== NUMA Monitor ===")
    print(f"NUMA System: {monitor.is_numa_system()}")
    print(f"Number of Nodes: {monitor.num_nodes}")
    print()

    summary = monitor.get_system_summary()

    if summary["is_numa"]:
        print("=== Per-Node Memory Stats ===")
        for node_name, stats in summary["node_memory_stats"].items():
            total_kb = stats.get("MemTotal", 0) / 1024
            free_kb = stats.get("MemFree", 0) / 1024
            used_kb = total_kb - free_kb
            print(f"{node_name}:")
            print(f"  Total: {total_kb:.0f} MB")
            print(f"  Used:  {used_kb:.0f} MB")
            print(f"  Free:  {free_kb:.0f} MB")
        print()

        print("=== NUMA Migration Stats ===")
        counts = summary["numa_counts"]
        print(f"  NUMA Hits:   {counts['hits']}")
        print(f"  NUMA Misses: {counts['misses']}")
        print(f"  Miss Rate:   {summary['numa_miss_rate']:.2f}%")
        print()

        print("=== Per-Node Compression ===")
        for node_name, ratio in summary.get("per_node_compression", {}).items():
            print(f"  {node_name}: {ratio:.2f}x")
        print()

    print("=== Node Pressure ===")
    for node_name, pressure in summary["node_pressure"].items():
        print(f"  {node_name}: {pressure:.1f}%")

    print()
    print("Summary JSON:")
    import json
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
