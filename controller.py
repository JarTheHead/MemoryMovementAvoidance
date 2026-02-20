#!/usr/bin/env python3

import os
import time
import subprocess
import psutil
from datetime import datetime

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
        """Call logger to record current status"""
        try:
            mem_pressure = self.read_psi_memory()
            cpu_usage = self.get_cpu_usage()
            swap_active = self.get_swap_activity()
            compression_ratio = self.get_compression_ratio()

            # Call logger script with current metrics
            subprocess.run([
                "python3", logger_script,
                str(datetime.now()),
                str(mem_pressure),
                str(cpu_usage),
                str(swap_active),
                str(compression_ratio)
            ])
        except Exception as e:
            print(f"Error logging status: {e}")

def main():
    print("=== Movement Avoidance Controller Started ===")
    controller = MovementAvoidanceController()

    try:
        while True:
            # Read system metrics
            mem_pressure = controller.read_psi_memory()
            cpu_usage = controller.get_cpu_usage()
            swap_active = controller.get_swap_activity()
            compression_ratio = controller.get_compression_ratio()

            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Mem Pressure: {mem_pressure:.2f}%, "
                  f"CPU: {cpu_usage:.1f}%, "
                  f"Swap Active: {swap_active}, "
                  f"Compression: {compression_ratio:.2f}x")

            # Decision logic
            if mem_pressure > 50 and cpu_usage < 70:
                # High memory pressure, low CPU usage -> increase compression
                print("High memory pressure with low CPU - increasing compression")
                controller.adjust_compression(increase=True)
            elif cpu_usage > 80:
                # High CPU usage -> decrease compression to reduce load
                print("High CPU usage - decreasing compression to reduce load")
                controller.adjust_compression(increase=False)
            elif swap_active:
                # Swapping detected - log warning
                print("WARNING: System is swapping to disk - movement avoidance failed!")

            # Log current status
            controller.log_status()

            # Wait before next check
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nController stopped by user")
    except Exception as e:
        print(f"Controller error: {e}")

if __name__ == "__main__":
    main()