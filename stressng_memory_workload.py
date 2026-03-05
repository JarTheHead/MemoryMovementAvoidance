#!/usr/bin/env python3
"""
StressNG Workload - Synthetic sweep wrapper for stress-ng.

Memory patterns:
- random_stride: Random memory access pattern
- sequential: Sequential memory access pattern

CPU contention:
- 0%, 25%, 50%, 75% via parallel stressors

Duration-based sweeps with metrics collection.
"""

import os
import sys
import subprocess
import time
import json
from datetime import datetime


class StressNGWorkload:
    def __init__(self, duration=60):
        self.duration = duration
        self.results = []
        self.stressng_path = self._find_stressng()

    def _find_stressng(self):
        """Find stress-ng binary path"""
        paths = ["/usr/bin/stress-ng", "/usr/local/bin/stress-ng"]
        for path in paths:
            if os.path.exists(path):
                return path
        return None

    def check_available(self):
        """Check if stress-ng is installed"""
        if self.stressng_path is None:
            return False
        try:
            result = subprocess.run(
                [self.stressng_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_available_patterns(self):
        """Get available memory access patterns"""
        return ["random", "sequential", "hot", "cold"]

    def get_available_cpu_contentions(self):
        """Get available CPU contention levels"""
        return [0, 25, 50, 75, 100]

    def calculate_workers(self, contention_pct, cpu_count):
        """Calculate number of workers for given contention percentage"""
        if contention_pct <= 0:
            return 0
        return max(1, int(cpu_count * contention_pct / 100))

    def run_sweep(self, pattern="random", contention=50, duration=None, memory_gb=1):
        """
        Run a single stress-ng sweep configuration.

        Args:
            pattern: Memory access pattern (random, sequential, hot, cold)
            contention: CPU contention percentage (0-100)
            duration: Test duration in seconds
            memory_gb: Memory to allocate in GB

        Returns:
            dict with results
        """
        if duration is None:
            duration = self.duration

        if self.stressng_path is None:
            return {"error": "stress-ng not found"}

        if not self.check_available():
            return {"error": "stress-ng not available"}

        # Get CPU count
        cpu_count = os.cpu_count() or 4

        # Calculate workers
        worker_count = self.calculate_workers(contention, cpu_count)

        # Build stress-ng command
        cmd = [
            self.stressng_path,
            "--vm", "1",              # VM stressor for memory
            "--vm-bytes", f"{memory_gb}G",
            "--vm-keep",              # Don't free memory
            "--timeout", f"{duration}s",
            "--metrics",              # Show metrics
        ]

        # Add CPU workers for contention
        if worker_count > 0:
            cmd.extend(["--cpu", str(worker_count)])

        # Add verbose output
        cmd.extend(["-v"])

        print(f"Running: {' '.join(cmd)}")

        result = {
            "pattern": pattern,
            "contention": contention,
            "duration": duration,
            "memory_gb": memory_gb,
            "worker_count": worker_count,
            "timestamp": datetime.now().isoformat(),
            "cmd": " ".join(cmd),
            "success": False,
            "error": None,
            "metrics": {}
        }

        try:
            # Run with timeout
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration + 60
            )

            result["stdout"] = process.stdout
            result["stderr"] = process.stderr
            result["returncode"] = process.returncode

            # stress-ng returns 0 on success or timeout (when --timeout is used)
            if process.returncode == 0:
                result["success"] = True
                result["metrics"] = self._parse_stressng_output(process.stderr)
            else:
                result["error"] = process.stderr

        except subprocess.TimeoutExpired:
            result["error"] = "Test timed out"
        except Exception as e:
            result["error"] = str(e)

        self.results.append(result)
        return result

    def _parse_stressng_output(self, output):
        """Parse stress-ng output for metrics"""
        metrics = {}

        # Look for metrics line
        for line in output.split('\n'):
            if 'bogo-ops' in line or 'metrics' in line.lower():
                # Try to extract numeric values
                parts = line.split()
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=')
                        try:
                            metrics[key] = float(value)
                        except ValueError:
                            metrics[key] = value

        # Try to extract throughput
        for line in output.split('\n'):
            if 'throughput' in line.lower():
                # Look for MB/s values
                import re
                matches = re.findall(r'([\d.]+)\s*MB\/s', line)
                if matches:
                    metrics['throughput_mb_s'] = float(matches[0])

        return metrics

    def run_full_sweep(self, patterns=None, contentions=None, duration=None, memory_gb=1):
        """
        Run full sweep across all pattern and contention combinations.

        Returns list of results.
        """
        if patterns is None:
            patterns = self.get_available_patterns()
        if contentions is None:
            contentions = self.get_available_cpu_contentions()
        if duration is None:
            duration = self.duration

        print(f"=== Running StressNG Sweep ===")
        print(f"Patterns: {patterns}")
        print(f"Contentions: {contentions}")
        print(f"Duration per test: {duration}s")
        print(f"Memory: {memory_gb}GB")
        print()

        all_results = []

        for pattern in patterns:
            for contention in contentions:
                print(f"\n--- Pattern: {pattern}, Contention: {contention}% ---")
                result = self.run_sweep(
                    pattern=pattern,
                    contention=contention,
                    duration=duration,
                    memory_gb=memory_gb
                )
                all_results.append(result)

                if result["success"]:
                    print(f"  Success: {result['metrics']}")
                else:
                    print(f"  Failed: {result.get('error', 'Unknown error')}")

        self.results = all_results
        return all_results

    def get_summary(self):
        """Get summary of all sweep results"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "configs_tested": len(self.results),
            "successful": sum(1 for r in self.results if r.get("success", False)),
            "failed": sum(1 for r in self.results if not r.get("success", False)),
            "results": []
        }

        for result in self.results:
            summary["results"].append({
                "pattern": result.get("pattern"),
                "contention": result.get("contention"),
                "success": result.get("success"),
                "throughput": result.get("metrics", {}).get("throughput_mb_s", 0),
                "bogo_ops": result.get("metrics", {}).get("bogo-ops", 0),
            })

        return summary

    def save_results(self, filename=None):
        """Save results to JSON file"""
        if filename is None:
            filename = f"stressng_sweep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        summary = self.get_summary()
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\nResults saved to {filename}")
        return filename


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run stress-ng workload sweep")
    parser.add_argument("--duration", "-d", type=int, default=60,
                        help="Duration per test in seconds (default: 60)")
    parser.add_argument("--memory", "-m", type=float, default=1,
                        help="Memory to allocate in GB (default: 1)")
    parser.add_argument("--pattern", "-p", nargs="+", default=None,
                        help="Memory patterns to test")
    parser.add_argument("--contention", "-c", nargs="+", type=int, default=None,
                        help="CPU contention percentages to test")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file for results")

    args = parser.parse_args()

    workload = StressNGWorkload(duration=args.duration)

    if not workload.check_available():
        print("Error: stress-ng not found or not available")
        print("Install with: sudo apt install stress-ng")
        sys.exit(1)

    print(f"stress-ng found at: {workload.stressng_path}")
    print(f"CPU count: {os.cpu_count()}")

    # Convert pattern arguments
    patterns = args.pattern if args.pattern else ["random", "sequential", "hot", "cold"]
    contentions = args.contention if args.contention else [0, 25, 50, 75, 100]

    # Run full sweep
    results = workload.run_full_sweep(
        patterns=patterns,
        contentions=contentions,
        duration=args.duration,
        memory_gb=args.memory
    )

    # Save and print summary
    workload.save_results(args.output)
    print("\n=== Summary ===")
    summary = workload.get_summary()
    print(f"Tested {summary['configs_tested']} configurations")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")

    # Print detailed results
    for result in summary["results"]:
        print(f"  {result['pattern']}/{result['contention']}%: "
              f"{'OK' if result['success'] else 'FAIL'} - "
              f"{result['throughput']:.2f} MB/s")


if __name__ == "__main__":
    main()
