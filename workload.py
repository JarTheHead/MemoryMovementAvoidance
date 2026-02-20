#!/usr/bin/env python3

import os
import sys
import time
import random
import psutil
from datetime import datetime

class MemoryWorkloadGenerator:
    def __init__(self):
        self.data_blocks = []
        self.block_size = 10 * 1024 * 1024  # 10MB blocks
        self.max_blocks = 100  # Up to 1GB of data

    def allocate_memory_block(self):
        """Allocate a block of memory with random data"""
        try:
            # Create random data block
            block = bytearray(random.getrandbits(8) for _ in range(self.block_size))
            self.data_blocks.append(block)
            print(f"Allocated block #{len(self.data_blocks)} ({self.block_size//1024//1024}MB)")
            return True
        except MemoryError:
            print("Memory allocation failed - system limit reached")
            return False

    def modify_existing_blocks(self):
        """Modify existing data blocks to create memory pressure"""
        if not self.data_blocks:
            return

        # Randomly modify some blocks
        for i in range(min(5, len(self.data_blocks))):
            block_idx = random.randint(0, len(self.data_blocks)-1)
            # Modify a portion of the block
            start = random.randint(0, self.block_size - 1000)
            for j in range(start, min(start + 1000, self.block_size)):
                self.data_blocks[block_idx][j] = random.getrandbits(8)

    def release_memory_blocks(self, count=1):
        """Release some memory blocks"""
        for _ in range(min(count, len(self.data_blocks))):
            if self.data_blocks:
                self.data_blocks.pop()
        print(f"Released {count} memory blocks")

    def get_memory_usage(self):
        """Get current process memory usage"""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024  # MB

    def run_workload(self):
        """Run the memory stress workload"""
        print("=== Memory Workload Generator Started ===")
        print("Generating memory pressure...")

        # Start with allocating several blocks
        initial_blocks = 20
        for i in range(initial_blocks):
            if not self.allocate_memory_block():
                break
            time.sleep(0.1)  # Small delay between allocations

        try:
            cycle = 0
            while True:
                cycle += 1
                print(f"\n--- Cycle {cycle} ---")

                # Report current memory usage
                mem_mb = self.get_memory_usage()
                print(f"Current memory usage: {mem_mb:.1f} MB")
                print(f"Allocated blocks: {len(self.data_blocks)}")

                # Every few cycles, try to allocate more memory
                if cycle % 3 == 0 and len(self.data_blocks) < self.max_blocks:
                    print("Trying to allocate more memory...")
                    self.allocate_memory_block()

                # Modify existing data to create memory pressure
                self.modify_existing_blocks()

                # Occasionally release some memory
                if cycle % 7 == 0 and len(self.data_blocks) > 5:
                    print("Releasing some memory...")
                    self.release_memory_blocks(2)

                # Wait before next cycle
                time.sleep(2)

        except KeyboardInterrupt:
            print("\nWorkload stopped by user")
        except Exception as e:
            print(f"Workload error: {e}")

def main():
    # Check if we're running in the correct cgroup
    try:
        with open("/proc/self/cgroup", "r") as f:
            cgroups = f.read()
            if "movement_avoidance_test" not in cgroups:
                print("Warning: Not running in movement_avoidance_test cgroup!")
                print("Run with: cgexec -g memory:movement_avoidance_test python3 workload.py")
    except Exception as e:
        print(f"Could not check cgroup: {e}")

    generator = MemoryWorkloadGenerator()
    generator.run_workload()

if __name__ == "__main__":
    main()