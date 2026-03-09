#!/usr/bin/env python3

import os
import time
import subprocess
import psutil
from datetime import datetime

import logger  # Add the logger module

class MovementAvoidanceController:
    def __init__(self):
        self.zswap_enabled_path = "/sys/module/zswap/parameters/enabled"
        self.zswap_compressor_path = "/sys/module/zswap/parameters/compressor"
        self.zswap_max_pool_path = "/sys/module/zswap/parameters/max_pool_percent"

        # Check if Zswap is available
        if not os.path.exists(self.zswap_enabled_path):
            print("Error: Zswap not available on this system")
            exit(1)

        # Initialize the log file and write headers
        logger.initialize_log()

        # Initialize compression ratio tracking
        self.last_compression_ratio = 1.0
        
        # Initialize algorithm tracking
        self.current_algorithm = "lz4"
        try:
            with open(self.zswap_compressor_path, "r") as f:
                content = f.read().strip()
                self.current_algorithm = content.replace("[", "").replace("]", "")
        except Exception:
            pass

        # Initialize swap counters for delta tracking
        self.last_pswpin, self.last_pswpout = self._get_raw_swap_stats()

        # NUMA-aware decision thresholds
        self.numa_pressure_threshold = 30  # NUMA miss rate threshold (%)
        self.high_pressure_threshold = 50  # Memory pressure threshold (%)
        self.high_cpu_threshold = 70       # CPU usage threshold (%)

        # Check for NUMA topology
        self.numa_nodes = self._detect_numa_nodes()
        self.is_numa_system = len(self.numa_nodes) > 1

    def _get_raw_swap_stats(self):
        """Read raw pswpin/pswpout values from /proc/vmstat"""
        pswpin, pswpout = 0, 0
        try:
            with open("/proc/vmstat", "r") as f:
                for line in f:
                    if line.startswith("pswpin"):
                        pswpin = int(line.strip().split()[1])
                    elif line.startswith("pswpout"):
                        pswpout = int(line.strip().split()[1])
        except Exception as e:
            print(f"Error reading swap stats: {e}")
        return pswpin, pswpout

    def _detect_numa_nodes(self):
        """Detect NUMA nodes by scanning /sys/devices/system/node"""
        import glob
        node_paths = glob.glob("/sys/devices/system/node/node*")
        return sorted(node_paths)

    def read_psi_memory(self):
        """Read memory pressure from PSI (Pressure Stall Information)"""
        try:
            with open("/proc/pressure/memory", "r") as f:
                lines = f.readlines()

                # Parse the "some" line which indicates memory pressure
                for line in lines:
                    if line.startswith("some"):
                        # Format: some avg10=0.00 avg60=0.00 avg300=0.00 total=12345
                        parts = line.strip().split()
                        for part in parts:
                            if part.startswith("avg10="):
                                pressure = float(part.split("=")[1])
                                return pressure

            print("Failed to retrieve memory pressure")
            return 0.0

        except FileNotFoundError:
            print("Warning: /proc/pressure/memory not found. Using alternative metrics.")
            return self.get_alternative_memory_pressure()
        except Exception as e:
            print(f"Error reading PSI: {e}")
            return 0.0

    def get_alternative_memory_pressure(self):
        """Alternative method to estimate memory pressure"""
        # Use memory percentage as proxy for pressure
        mem = psutil.virtual_memory()
        return mem.percent  # Higher percentage = higher pressure

    def get_cpu_usage(self):
        """Get current CPU usage percentage"""
        usage = psutil.cpu_percent(interval=1)
        # Fix for -0.0 and very small values
        return max(0.0, usage)

    def get_swap_activity(self):
        """Check if system is swapping to disk since last check"""
        curr_in, curr_out = self._get_raw_swap_stats()
        
        # Check if values increased
        is_swapping = (curr_in > self.last_pswpin) or (curr_out > self.last_pswpout)
        
        # Update markers
        self.last_pswpin, self.last_pswpout = curr_in, curr_out
        
        return is_swapping

    def adjust_compression(self, increase=True):
        """Adjust compression settings based on system load"""
        try:
            current_pool = int(open(self.zswap_max_pool_path).read().strip())

            if increase and current_pool < 50:  # Max 50%
                new_pool = min(current_pool + 5, 50)
                with open(self.zswap_max_pool_path, "w") as f:
                    f.write(str(new_pool))
                print(f"Increased compression pool to {new_pool}%")
                return new_pool
            elif not increase and current_pool > 5:  # Min 5%
                new_pool = max(current_pool - 5, 5)
                with open(self.zswap_max_pool_path, "w") as f:
                    f.write(str(new_pool))
                print(f"Decreased compression pool to {new_pool}%")
                return new_pool

        except Exception as e:
            print(f"Error adjusting compression: {e}")

        return current_pool

    def get_compression_ratio(self):
        """Calculate current compression ratio"""
        try:
            with open("/sys/kernel/debug/zswap/pool_total_size", "r") as f:
                pool_size = int(f.read().strip())
            with open("/sys/kernel/debug/zswap/stored_pages", "r") as f:
                stored_pages = int(f.read().strip())

            if stored_pages > 0:
                # Each page is typically 4KB
                uncompressed_size = stored_pages * 4096
                if pool_size > 0:
                    ratio = uncompressed_size / pool_size
                    self.last_compression_ratio = ratio
                    return ratio
        except FileNotFoundError:
            # Debugfs not mounted or zswap debug info not available
            pass
        except Exception as e:
            print(f"Error calculating compression ratio: {e}")

        return self.last_compression_ratio

    def get_numa_miss_rate(self):
        """Get NUMA miss rate from node statistics"""
        total_hits = 0
        total_misses = 0

        for node_path in self.numa_nodes:
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
                                    total_hits += value
                                elif key == "numa_miss":
                                    total_misses += value
            except Exception:
                pass

        total = total_hits + total_misses
        if total == 0:
            return 0.0
        return (total_misses / total) * 100

    def get_node_memory_stats(self, node_id):
        """Get memory statistics for a specific node"""
        node_path = f"/sys/devices/system/node/node{node_id}"
        stats = {
            "MemTotal": 0,
            "MemFree": 0,
            "MemAvailable": 0,
            "Buffers": 0,
            "Cached": 0,
        }

        try:
            meminfo_path = f"{node_path}/meminfo"
            if os.path.exists(meminfo_path):
                with open(meminfo_path, "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            key = parts[0].rstrip(":")
                            value = int(parts[1])
                            if key in stats:
                                stats[key] = value
        except Exception:
            pass

        return stats

    def get_per_node_pressure(self):
        """Get memory pressure for each node"""
        pressures = {}
        for node_path in self.numa_nodes:
            node_id = int(node_path.split("node")[-1])
            stats = self.get_node_memory_stats(node_id)
            total = stats.get("MemTotal", 1)
            free = stats.get("MemFree", 0)
            pressures[f"Node{node_id}"] = ((total - free) / total) * 100 if total > 0 else 0
        return pressures

    def get_available_compressors(self):
        """Get list of available compression algorithms"""
        try:
            with open(self.zswap_compressor_path, "r") as f:
                content = f.read().strip()
                # Format: [lzo] lz4 zstd or similar with current in brackets
                algorithms = content.replace("[", " ").replace("]", " ").split()
                return algorithms
        except Exception:
            return []

    def set_compression_algorithm(self, algorithm):
        """Set the compression algorithm"""
        available = self.get_available_compressors()
        if algorithm not in available:
            return False

        try:
            with open(self.zswap_compressor_path, "w") as f:
                f.write(algorithm)
            self.current_algorithm = algorithm
            return True
        except PermissionError:
            print("Error: Permission denied. Run as root to change compressor.")
            return False
        except Exception as e:
            print(f"Error setting algorithm: {e}")
            return False

    def get_optimal_algorithm(self, cpu_usage, mem_pressure):
        """
        Determine optimal algorithm based on system metrics.

        - High CPU, low pressure -> lzo (fastest, low overhead)
        - Moderate CPU/pressure -> lz4 (balanced)
        - Low CPU, high pressure -> zstd (best ratio)
        """
        if cpu_usage > 70:
            return "lzo"
        elif mem_pressure > 50 and cpu_usage < 50:
            return "zstd"
        else:
            return "lz4"

    def log_status(self, metrics):
        """Log current status using pre-calculated metrics"""
        try:
            # Extract Node0 and Node1 free memory in MB
            node0_free = 0
            node1_free = 0
            
            if self.is_numa_system:
                node0_stats = self.get_node_memory_stats(0)
                node1_stats = self.get_node_memory_stats(1)
                node0_free = node0_stats.get("MemFree", 0) / 1024
                node1_free = node1_stats.get("MemFree", 0) / 1024

            # Call the logger module directly
            logger.log_metrics(
                timestamp=str(datetime.now()),
                mem_pressure=metrics['mem_pressure'],
                cpu_pressure=metrics['cpu_usage'],
                swap_activity=metrics['swap_active'],
                compression_ratio=metrics['compression_ratio'],
                node0_free=node0_free,
                node1_free=node1_free,
                numa_miss_rate=metrics.get('numa_miss_rate', 0.0),
                algorithm=self.current_algorithm,
                cr_node0=1.0,  # Compression ratio node 0 (placeholder)
                cr_node1=1.0   # Compression ratio node 1 (placeholder)
            )
        except Exception as e:
            print(f"Error logging status: {e}")

    def get_numa_aware_recommendation(self, mem_pressure, cpu_usage, numa_miss_rate=0):
        """
        Get NUMA-aware recommendation for compression settings.

        Returns tuple of (increase_pool: bool, optimal_algorithm: str)
        """
        increase_pool = True
        optimal_algorithm = "lz4"

        # Check NUMA miss rate
        if self.is_numa_system and numa_miss_rate > self.numa_pressure_threshold:
            print(f"High NUMA miss rate ({numa_miss_rate:.1f}%) - may benefit from more compression")
            increase_pool = True

        # Base decision on CPU and memory pressure
        if mem_pressure > self.high_pressure_threshold and cpu_usage < self.high_cpu_threshold:
            # High memory pressure, low CPU usage -> increase compression
            increase_pool = True
            optimal_algorithm = "zstd"  # Best ratio when CPU is free
        elif cpu_usage > self.high_cpu_threshold:
            # High CPU usage -> decrease compression to reduce load
            increase_pool = False
            optimal_algorithm = "lzo"  # Fastest when CPU is constrained
        else:
            # Balanced - use default
            increase_pool = False  # Keep current setting
            optimal_algorithm = "lz4"  # Balanced

        return increase_pool, optimal_algorithm

    def run_iteration(self):
        """Run one iteration of the controller loop"""
        # Read system metrics
        mem_pressure = self.read_psi_memory()
        cpu_usage = self.get_cpu_usage()
        swap_active = self.get_swap_activity()
        compression_ratio = self.get_compression_ratio()

        # Get NUMA stats if available
        numa_miss_rate = 0
        if self.is_numa_system:
            numa_miss_rate = self.get_numa_miss_rate()

        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"Mem Pressure: {mem_pressure:.2f}%, "
              f"CPU: {cpu_usage:.1f}%, "
              f"Swap Active: {swap_active}, "
              f"Compression: {compression_ratio:.2f}x")

        if self.is_numa_system:
            print(f"  NUMA Miss Rate: {numa_miss_rate:.2f}%")

        # Get NUMA-aware recommendation
        if self.is_numa_system:
            increase_pool, optimal_algorithm = self.get_numa_aware_recommendation(
                mem_pressure, cpu_usage, numa_miss_rate
            )
        else:
            increase_pool, optimal_algorithm = True, "lz4"

        # Decision logic
        if mem_pressure > 50 and cpu_usage < 70:
            # High memory pressure, low CPU usage -> increase compression
            print("High memory pressure with low CPU - increasing compression")
            self.adjust_compression(increase=True)
        elif cpu_usage > 80:
            # High CPU usage -> decrease compression to reduce load
            print("High CPU usage - decreasing compression to reduce load")
            self.adjust_compression(increase=False)
        
        if swap_active:
            # Swapping detected - log warning
            print("WARNING: System is swapping to disk - movement avoidance failed!")

        # Try to set optimal algorithm if available
        if optimal_algorithm != self.current_algorithm:
            available = self.get_available_compressors()
            if optimal_algorithm in available:
                self.set_compression_algorithm(optimal_algorithm)

        # Gather metrics for logging
        metrics = {
            "mem_pressure": mem_pressure,
            "cpu_usage": cpu_usage,
            "swap_active": swap_active,
            "compression_ratio": compression_ratio,
            "numa_miss_rate": numa_miss_rate
        }

        # Log current status
        self.log_status(metrics)

        return metrics

    def run_loop(self, iterations=None):
        """Run the main controller loop"""
        print("=== Movement Avoidance Controller Started ===")
        print(f"NUMA Support: {'Enabled' if self.is_numa_system else 'Disabled'}")
        print()

        iteration_count = 0

        try:
            while True:
                self.run_iteration()

                iteration_count += 1
                if iterations and iteration_count >= iterations:
                    break

                # Wait before next check
                time.sleep(5)

        except KeyboardInterrupt:
            print("\nController stopped by user")
        except Exception as e:
            print(f"Controller error: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Movement Avoidance Controller")
    parser.add_argument("--iterations", "-n", type=int, default=None,
                        help="Number of iterations to run (default: infinite)")
    parser.add_argument("--dry-run", "-d", action="store_true",
                        help="Show recommendations without applying changes")

    args = parser.parse_args()

    controller = MovementAvoidanceController()

    if args.dry_run:
        # Just show metrics without making changes
        print("=== Dry Run - Showing Metrics Only ===")
        for _ in range(10):
            controller.run_iteration()
            time.sleep(2)
    else:
        controller.run_loop(iterations=args.iterations)


if __name__ == "__main__":
    main()
