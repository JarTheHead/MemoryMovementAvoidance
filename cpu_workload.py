#!/usr/bin/env python3
"""
CPU Workload Generator - Controls CPU contention independently.

CPU contention levels:
- 0%: No CPU workload (idle)
- 25%: Light CPU load
- 50%: Moderate CPU load
- 75%: Heavy CPU load
- 100%: Full CPU saturation

Usage:
    python3 cpu_workload.py --contention 50 --duration 60
    python3 cpu_workload.py --contention 0 --duration 30  # No CPU load
"""

import os
import sys
import time
import argparse
import multiprocessing
import subprocess
import psutil
from datetime import datetime


class CPUWorkloadGenerator:
    """Generates controlled CPU workload with configurable contention percentage"""

    def __init__(self, cpu_count=None):
        self.cpu_count = cpu_count or multiprocessing.cpu_count()
        self.workers = []
        self.running = False
        self.target_contention = 0
        self.current_contention = 0

    def calculate_workers_and_duty(self, contention_pct):
        """
        Calculate number of workers and duty cycle for given contention.

        Returns (worker_count, duty_cycle_ms, sleep_cycle_ms)
        - worker_count: Number of concurrent workers
        - duty_cycle_ms: How long each worker runs
        - sleep_cycle_ms: How long each worker sleeps
        """
        if contention_pct <= 0:
            return 0, 0, 0

        if contention_pct >= 100:
            # Full saturation - one worker per CPU, no sleep
            return self.cpu_count, 0, 0

        # Calculate workers needed for target contention
        worker_count = max(1, int(self.cpu_count * contention_pct / 100))

        # Calculate duty cycle to achieve precise contention
        # Each worker runs for duty_cycle, then sleeps for sleep_cycle
        # Duty cycle = (contention / 100) * total_cycle
        # For simplicity, use 100ms total cycle
        total_cycle_ms = 100
        duty_cycle_ms = int((contention_pct / 100.0) * total_cycle_ms)
        sleep_cycle_ms = total_cycle_ms - duty_cycle_ms

        return worker_count, duty_cycle_ms, sleep_cycle_ms

    def cpu_worker(self, duty_cycle_ms, sleep_cycle_ms, stop_event):
        """Worker function that runs CPU work with duty cycling"""
        while not stop_event.is_set():
            if duty_cycle_ms > 0:
                # Busy work - compute something
                end_time = time.time() + (duty_cycle_ms / 1000.0)
                while time.time() < end_time:
                    # Simple CPU-intensive computation
                    _ = sum(i * i for i in range(1000))
            if sleep_cycle_ms > 0:
                stop_event.wait(sleep_cycle_ms / 1000.0)

    def start_workers(self, contention_pct):
        """Start CPU workers for given contention level"""
        worker_count, duty_cycle_ms, sleep_cycle_ms = self.calculate_workers_and_duty(contention_pct)

        # Stop any existing workers
        self.stop_workers()

        if worker_count == 0:
            self.current_contention = 0
            return

        # Create stop event for workers
        stop_event = multiprocessing.Event()

        # Start workers
        for i in range(worker_count):
            p = multiprocessing.Process(
                target=self.cpu_worker,
                args=(duty_cycle_ms, sleep_cycle_ms, stop_event)
            )
            p.start()
            self.workers.append((p, stop_event))

        self.target_contention = contention_pct
        self.current_contention = contention_pct

    def stop_workers(self):
        """Stop all CPU workers"""
        for p, event in self.workers:
            event.set()
            if p.is_alive():
                p.terminate()
                p.join(timeout=1)
        self.workers = []
        self.current_contention = 0

    def update_contention(self, new_contention_pct):
        """Update contention level while running"""
        self.start_workers(new_contention_pct)


    def run_contention_sweep(self, contentions, duration_per_test=10):
        """
        Run CPU contention sweep.

        Args:
            contentions: List of contention percentages to test
            duration_per_test: How long to run each test
        """
        print("=== CPU Contention Sweep ===")
        print(f"CPU count: {self.cpu_count}")
        print()

        for contention in contentions:
            print(f"Setting CPU contention to {contention}%...")

            # Start workers
            self.start_workers(contention)

            # Monitor for duration
            start_time = time.time()
            while time.time() - start_time < duration_per_test:
                actual = psutil.cpu_percent(interval=0.5)
                print(f"  Current: {actual:.1f}% (target: {contention}%)")
                time.sleep(1)

            # Stop workers
            self.stop_workers()
            print()

        print("CPU contention sweep complete")


class CPUStressWorkload:
    """Alternative: Use stress-ng for CPU workload if available"""

    def __init__(self):
        self.process = None
        self.stressng_path = self._find_stressng()

    def _find_stressng(self):
        """Find stress-ng binary"""
        for path in ["/usr/bin/stress-ng", "/usr/local/bin/stress-ng"]:
            if os.path.exists(path):
                return path
        return None

    def check_available(self):
        """Check if stress-ng is available"""
        if not self.stressng_path:
            return False
        try:
            result = subprocess.run([self.stressng_path, "--version"],
                                   capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def run_stress(self, cpu_count, duration=None):
        """Run stress-ng CPU stressor"""
        if not self.stressng_path:
            return {"error": "stress-ng not found"}

        cmd = [
            self.stressng_path,
            "--cpu", str(cpu_count),
            "--timeout", str(duration) if duration else "60s",
            "--metrics",
        ]

        try:
            process = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=duration + 60 if duration else 120)
            return {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "returncode": process.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": "Timeout"}
        except Exception as e:
            return {"error": str(e)}

    def run_burnin(self, duration=60):
        """Run continuous CPU burn-in (no stress-ng required)"""
        print(f"Running CPU burn-in for {duration} seconds...")
        print("This will fully utilize all CPU cores.")

        start_time = time.time()
        try:
            while time.time() - start_time < duration:
                # Full CPU utilization - busy loop
                end_time = time.time() + 0.1
                while time.time() < end_time:
                    _ = sum(i * i for i in range(10000))
        except KeyboardInterrupt:
            print("\nCPU burn-in stopped by user")


def main():
    parser = argparse.ArgumentParser(description="CPU Workload Generator")
    parser.add_argument("--contention", "-c", type=int, default=0,
                        help="CPU contention percentage (0-100, default: 0)")
    parser.add_argument("--duration", "-d", type=int, default=0,
                        help="Duration in seconds (0 = forever)")
    parser.add_argument("--sweep", "-s", nargs="+", type=int, default=None,
                        help="Run contention sweep (list of percentages)")
    parser.add_argument("--burnin", "-b", action="store_true",
                        help="Run continuous CPU burn-in (100% utilization)")

    args = parser.parse_args()

    # Check for stress-ng availability
    stress = CPUStressWorkload()
    if stress.check_available():
        print(f"stress-ng available at {stress.stressng_path}")
    else:
        print("Using Python-based CPU workload (no stress-ng)")

    if args.sweep:
        # Run contention sweep
        generator = CPUWorkloadGenerator()
        generator.run_contention_sweep(args.sweep, duration_per_test=args.duration or 10)

    elif args.burnin:
        # Run burn-in
        stress.run_burnin(duration=args.duration or 60)

    elif args.contention > 0:
        # Run with specific contention
        generator = CPUWorkloadGenerator()
        print(f"Starting CPU workload with {args.contention}% contention")
        print("Press Ctrl+C to stop")
        generator.start_workers(args.contention)

        if args.duration > 0:
            time.sleep(args.duration)
            generator.stop_workers()
            print(f"Ran for {args.duration} seconds")
        else:
            try:
                while True:
                    time.sleep(1)
                    actual = psutil.cpu_percent(interval=0.5)
                    print(f"Current CPU: {actual:.1f}% (target: {args.contention}%)")
            except KeyboardInterrupt:
                print("\nCPU workload stopped by user")

        generator.stop_workers()

    else:
        # No CPU load (idle)
        print("CPU workload: IDLE (0% contention)")


if __name__ == "__main__":
    main()
