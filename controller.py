#!/usr/bin/env python3

import os
import time
import subprocess
import psutil
from datetime import datetime

# Import new modules
try:
    from numa_monitor import NUMAMonitor
    from adaptive_compressor import AdaptiveCompressor
except ImportError:
    NUMAMonitor = None
    AdaptiveCompressor = None


class MovementAvoidanceController:
    def __init__(self):
        self.zswap_enabled_path = "/sys/module/zswap/parameters/enabled"
        self.zswap_compressor_path = "/sys/module/zswap/parameters/compressor"
        self.zswap_max_pool_path = "/sys/module/zswap/parameters/max_pool_percent"

        # Check if Zswap is available
        if not os.path.exists(self.zswap_enabled_path):
            print("Error: Zswap not available on this system")
            exit(1)

        # Initialize compression ratio tracking
        self.last_compression_ratio = 1.0

        # Initialize NUMA monitor if available
        self.numa_monitor = NUMAMonitor() if NUMAMonitor else None

        # Initialize adaptive compressor
        self.compressor = AdaptiveCompressor() if AdaptiveCompressor else None

        # NUMA-aware decision thresholds
        self.numa_pressure_threshold = 30  # NUMA miss rate threshold (%)
        self.high_pressure_threshold = 50  # Memory pressure threshold (%)
        self.high_cpu_threshold = 70       # CPU usage threshold (%)

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
        except FileNotFoundError:
            print("Warning: /proc/pressure/memory not found. Using alternative metrics.")
            return self.get_alternative_memory_pressure()
        except Exception as e:
            print(f"Error reading PSI: {e}")
            return 0.0

        return 0.0

    def get_alternative_memory_pressure(self):
        """Alternative method to estimate memory pressure"""
        # Use memory percentage as proxy for pressure
        mem = psutil.virtual_memory()
        return mem.percent  # Higher percentage = higher pressure

    def get_cpu_usage(self):
        """Get current CPU usage percentage"""
        return psutil.cpu_percent(interval=1)

    def get_swap_activity(self):
        """Check if system is swapping to disk"""
        try:
            with open("/proc/vmstat", "r") as f:
                lines = f.readlines()

            for line in lines:
                if line.startswith("pswpin") or line.startswith("pswpout"):
                    # These counters increment when swapping occurs
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        value = int(parts[1])
                        if value > 0:
                            return True
        except Exception as e:
            print(f"Error checking swap activity: {e}")

        return False

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

    def log_status(self, logger_script="./logger.py"):
        """Call logger to record current status with NUMA and algorithm info"""
        try:
            mem_pressure = self.read_psi_memory()
            cpu_usage = self.get_cpu_usage()
            swap_active = self.get_swap_activity()
            compression_ratio = self.get_compression_ratio()

            # Get NUMA stats if available
            numa_stats = None
            if self.numa_monitor:
                numa_stats = self.numa_monitor.get_system_summary()

            # Get current algorithm if adaptive compressor is available
            algorithm = "lz4"  # Default
            if self.compressor and self.compressor.current_algorithm:
                algorithm = self.compressor.current_algorithm

            # Call logger with extended metrics
            subprocess.run([
                "python3", logger_script,
                str(datetime.now()),
                str(mem_pressure),
                str(cpu_usage),
                str(swap_active),
                str(compression_ratio),
                str(numa_stats.get("node_memory_stats", {}).get("Node0", {}).get("MemFree", 0) if numa_stats else 0),
                str(numa_stats.get("node_memory_stats", {}).get("Node1", {}).get("MemFree", 0) if numa_stats else 0),
                str(numa_stats.get("numa_miss_rate", 0) if numa_stats else 0),
                algorithm,
                str(1.0),  # Compression ratio node 0 (placeholder)
                str(1.0),  # Compression ratio node 1 (placeholder)
            ])
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
        if self.numa_monitor and self.numa_monitor.is_numa_system():
            if numa_miss_rate > self.numa_pressure_threshold:
                # High NUMA miss rate - consider more aggressive compression
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
        if self.numa_monitor:
            numa_summary = self.numa_monitor.get_system_summary()
            numa_miss_rate = numa_summary.get("numa_miss_rate", 0)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"Mem Pressure: {mem_pressure:.2f}%, "
              f"CPU: {cpu_usage:.1f}%, "
              f"Swap Active: {swap_active}, "
              f"Compression: {compression_ratio:.2f}x")

        if self.numa_monitor and self.numa_monitor.is_numa_system():
            print(f"  NUMA Miss Rate: {numa_miss_rate:.2f}%")

        # Get NUMA-aware recommendation
        if self.numa_monitor:
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
        elif swap_active:
            # Swapping detected - log warning
            print("WARNING: System is swapping to disk - movement avoidance failed!")

        # Update adaptive compressor if available
        if self.compressor:
            self.compressor.adaptive_cycle(cpu_usage, mem_pressure)

        # Log current status
        self.log_status()

        return {
            "mem_pressure": mem_pressure,
            "cpu_usage": cpu_usage,
            "swap_active": swap_active,
            "compression_ratio": compression_ratio,
            "numa_miss_rate": numa_miss_rate,
            "algorithm": self.compressor.current_algorithm if self.compressor else "lz4"
        }

    def run_loop(self, iterations=None):
        """Run the main controller loop"""
        print("=== Movement Avoidance Controller Started ===")
        print("NUMA Support:", "Enabled" if self.numa_monitor else "Disabled")
        print("Adaptive Compression:", "Enabled" if self.compressor else "Disabled")
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
