#!/usr/bin/env python3
"""
Adaptive Compressor - Dynamically cycles through compression algorithms.

Algorithms (in order of speed vs ratio):
- lzo: Fastest, lowest compression ratio
- lz4: Balanced, good speed and ratio
- zstd: Best ratio, slower compression

Cycle interval is configurable (default 5 minutes).
Algorithm selection is based on system metrics.
"""

import os
import time
import subprocess
from datetime import datetime


class AdaptiveCompressor:
    """Manages Zswap compression algorithm selection"""

    # Available algorithms ordered by speed (fastest first)
    ALGORITHMS = ["lzo", "lz4", "zstd"]
    DEFAULT_CYCLE_INTERVAL = 300  # 5 minutes in seconds

    def __init__(self, cycle_interval=None):
        self.compressor_path = "/sys/module/zswap/parameters/compressor"
        self.cycle_interval = cycle_interval or self.DEFAULT_CYCLE_INTERVAL
        self.current_algorithm = None
        self.algorithm_start_time = None
        self.algorithm_stats = {alg: {"swaps": 0, "compression_ratio": 1.0} for alg in self.ALGORITHMS}

        # Verify compressor path exists
        if not os.path.exists(self.compressor_path):
            print("Error: Zswap compressor path not found")
            exit(1)

    def get_available_algorithms(self):
        """Get list of available compression algorithms"""
        try:
            with open(self.compressor_path, "r") as f:
                content = f.read().strip()
                # Format: [lzo] lz4 zstd or similar with current in brackets
                algorithms = content.replace("[", " ").replace("]", " ").split()
                return algorithms
        except Exception as e:
            print(f"Error reading available algorithms: {e}")
            return []

    def set_algorithm(self, algorithm):
        """Set the compression algorithm"""
        if algorithm not in self.ALGORITHMS:
            print(f"Warning: Algorithm '{algorithm}' not in supported list: {self.ALGORITHMS}")
            return False

        available = self.get_available_algorithms()
        if algorithm not in available:
            print(f"Warning: Algorithm '{algorithm}' not available on this system")
            print(f"Available: {available}")
            return False

        try:
            with open(self.compressor_path, "w") as f:
                f.write(algorithm)
            self.current_algorithm = algorithm
            self.algorithm_start_time = time.time()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Set compression algorithm to: {algorithm}")
            return True
        except PermissionError:
            print("Error: Permission denied. Run as root to change compressor.")
            return False
        except Exception as e:
            print(f"Error setting algorithm: {e}")
            return False

    def get_current_algorithm(self):
        """Get the current compression algorithm"""
        try:
            with open(self.compressor_path, "r") as f:
                content = f.read().strip()
                # Remove brackets around current algorithm
                return content.replace("[", "").replace("]", "")
        except Exception as e:
            print(f"Error getting current algorithm: {e}")
            return None

    def cycle_algorithm(self):
        """Cycle to the next algorithm in the sequence"""
        current_idx = 0
        if self.current_algorithm in self.ALGORITHMS:
            current_idx = self.ALGORITHMS.index(self.current_algorithm)

        next_idx = (current_idx + 1) % len(self.ALGORITHMS)
        next_algorithm = self.ALGORITHMS[next_idx]
        return self.set_algorithm(next_algorithm)

    def get_compression_ratio(self):
        """Get current compression ratio from zswap stats"""
        try:
            with open("/sys/kernel/debug/zswap/pool_total_size", "r") as f:
                pool_size = int(f.read().strip())
            with open("/sys/kernel/debug/zswap/stored_pages", "r") as f:
                stored_pages = int(f.read().strip())

            if stored_pages > 0:
                uncompressed_size = stored_pages * 4096
                if pool_size > 0:
                    return uncompressed_size / pool_size
        except Exception:
            pass
        return 1.0

    def get_swap_count(self):
        """Get total swap count from vmstat"""
        try:
            with open("/proc/vmstat", "r") as f:
                for line in f:
                    if line.startswith("pgswapout"):
                        return int(line.split()[1])
        except Exception:
            pass
        return 0

    def update_algorithm_stats(self):
        """Update statistics for current algorithm"""
        if self.current_algorithm:
            ratio = self.get_compression_ratio()
            swaps = self.get_swap_count()

            # Only update if values have changed significantly
            if ratio > 1.0:
                self.algorithm_stats[self.current_algorithm]["compression_ratio"] = ratio
            if swaps > 0:
                self.algorithm_stats[self.current_algorithm]["swaps"] = swaps

    def should_cycle(self):
        """Check if it's time to cycle to the next algorithm"""
        if self.algorithm_start_time is None:
            return True

        elapsed = time.time() - self.algorithm_start_time
        return elapsed >= self.cycle_interval

    def get_best_algorithm_for_load(self, cpu_usage, mem_pressure):
        """
        Determine optimal algorithm based on system metrics.

        - High CPU, low pressure -> lzo (fastest, low overhead)
        - Moderate CPU/pressure -> lz4 (balanced)
        - Low CPU, high pressure -> zstd (best ratio)
        """
        # Base decision on CPU and memory pressure
        if cpu_usage > 70:
            # High CPU usage - use fastest algorithm
            return "lzo"
        elif mem_pressure > 50 and cpu_usage < 50:
            # High memory pressure, some CPU headroom - use best ratio
            return "zstd"
        else:
            # Balanced - use default
            return "lz4"

    def adaptive_cycle(self, cpu_usage=None, mem_pressure=None):
        """
        Cycle algorithm adaptively based on system metrics.
        If metrics not provided, just cycle to next algorithm.
        """
        if cpu_usage is None or mem_pressure is None:
            return self.cycle_algorithm()

        optimal = self.get_best_algorithm_for_load(cpu_usage, mem_pressure)
        if self.current_algorithm != optimal:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Optimal algorithm for current load: {optimal} (currently: {self.current_algorithm})")
            return self.set_algorithm(optimal)

        return True

    def run_auto_cycle(self, controller=None):
        """Run automatic algorithm cycling with metrics-based selection"""
        print("=== Adaptive Compressor Started ===")
        print(f"Cycle interval: {self.cycle_interval}s")
        print(f"Algorithms: {self.ALGORITHMS}")
        print()

        # Initialize with first algorithm
        self.set_algorithm(self.ALGORITHMS[0])

        try:
            while True:
                # Update stats for current algorithm
                self.update_algorithm_stats()

                # Get system metrics if controller provided
                cpu_usage = 0.0
                mem_pressure = 0.0
                if controller:
                    try:
                        cpu_usage = controller.get_cpu_usage()
                        mem_pressure = controller.read_psi_memory()
                    except Exception:
                        pass

                # Check if it's time to cycle
                if self.should_cycle():
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Cycle time reached (elapsed: {time.time() - self.algorithm_start_time:.0f}s)")
                    self.adaptive_cycle(cpu_usage, mem_pressure)
                else:
                    # Still cycle adaptively based on current load
                    self.adaptive_cycle(cpu_usage, mem_pressure)

                # Print status
                ratio = self.get_compression_ratio()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Algorithm: {self.current_algorithm}, "
                      f"Ratio: {ratio:.2f}x, "
                      f"CPU: {cpu_usage:.1f}%, "
                      f"Mem Pressure: {mem_pressure:.1f}%")

                # Wait
                time.sleep(5)

        except KeyboardInterrupt:
            print("\nAdaptive compressor stopped by user")
        except Exception as e:
            print(f"Adaptive compressor error: {e}")

    def print_algorithm_stats(self):
        """Print collected statistics for all algorithms"""
        print("\n=== Algorithm Statistics ===")
        for algo, stats in self.algorithm_stats.items():
            print(f"  {algo.upper()}:")
            print(f"    Compression Ratio: {stats['compression_ratio']:.2f}x")
            print(f"    Swap Operations: {stats['swaps']}")


def main():
    import sys

    cycle_interval = None
    if len(sys.argv) > 1:
        try:
            cycle_interval = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [cycle_interval_seconds]")
            sys.exit(1)

    compressor = AdaptiveCompressor(cycle_interval=cycle_interval)
    compressor.run_auto_cycle()


if __name__ == "__main__":
    main()
