#!/usr/bin/env python3
"""
Real Workloads - Redis and llama.cpp workload managers.

Provides classes to:
- RedisWorkload: Start/stop Redis server, run redis-benchmark, capture latency
- LlamaCppWorkload: Start inference, run generation, capture throughput
"""

import os
import subprocess
import time
import json
import signal
from datetime import datetime
from pathlib import Path


class RedisWorkload:
    """Manages Redis server and benchmark workloads"""

    DEFAULT_PORT = 6379
    DEFAULT_MEMORY_MB = 512
    DEFAULT_DURATION = 30

    def __init__(self, port=None, maxmemory_mb=None):
        self.port = port or self.DEFAULT_PORT
        self.maxmemory_mb = maxmemory_mb or self.DEFAULT_MEMORY_MB
        self.server_pid = None
        self.config_path = f"/tmp/redis_{self.port}.conf"
        self.log_path = f"/tmp/redis_{self.port}.log"
        self.results = []

    def _find_redis_binaries(self):
        """Find redis-server and redis-benchmark paths"""
        binaries = {
            "redis-server": None,
            "redis-benchmark": None,
        }

        for name in binaries.keys():
            for path in ["/usr/bin", "/usr/local/bin", "/opt/redis"]:
                full_path = os.path.join(path, name)
                if os.path.exists(full_path):
                    binaries[name] = full_path

        return binaries

    def _write_config(self):
        """Write Redis configuration file"""
        config = f"""# Auto-generated Redis config
port {self.port}
maxmemory {self.maxmemory_mb}mb
maxmemory-policy allkeys-lru
logfile "{self.log_path}"
bind 127.0.0.1
daemonize yes
"""
        with open(self.config_path, 'w') as f:
            f.write(config)

    def start_server(self):
        """Start Redis server"""
        binaries = self._find_redis_binaries()

        if not binaries["redis-server"]:
            raise RuntimeError("redis-server not found. Install Redis.")

        self._write_config()

        cmd = [binaries["redis-server"], self.config_path]

        print(f"Starting Redis server on port {self.port}...")
        process = subprocess.run(cmd, capture_output=True, text=True)

        if process.returncode != 0:
            raise RuntimeError(f"Failed to start Redis: {process.stderr}")

        # Wait for server to be ready
        time.sleep(2)

        # Verify server is running
        if not self.is_running():
            raise RuntimeError("Redis server did not start properly")

        self.server_pid = self._get_pid()
        print(f"Redis server started (PID: {self.server_pid})")

        return True

    def stop_server(self):
        """Stop Redis server"""
        if self.server_pid:
            try:
                os.kill(self.server_pid, signal.SIGTERM)
                time.sleep(1)
            except ProcessLookupError:
                pass
            except Exception as e:
                print(f"Error stopping Redis: {e}")

        # Cleanup
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

        self.server_pid = None
        print("Redis server stopped")

    def is_running(self):
        """Check if Redis server is running"""
        try:
            result = subprocess.run(
                ["redis-cli", "-p", str(self.port), "ping"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() == "PONG"
        except Exception:
            return False

    def _get_pid(self):
        """Get Redis server PID from config file or process"""
        # Try to get from pid file
        pid_file = f"/tmp/redis_{self.port}.pid"
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                return int(f.read().strip())

        # Fallback to process search
        try:
            result = subprocess.run(
                ["pgrep", "-f", f"redis-server.*:{self.port}"],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                return int(result.stdout.strip())
        except Exception:
            pass

        return None

    def run_benchmark(self, clients=10, queries=10000, duration=None):
        """
        Run redis-benchmark with specified parameters.

        Args:
            clients: Number of parallel connections
            queries: Total number of requests
            duration: Duration in seconds (overrides queries)

        Returns:
            dict with benchmark results
        """
        binaries = self._find_redis_binaries()

        if not binaries["redis-benchmark"]:
            raise RuntimeError("redis-benchmark not found. Install Redis.")

        if not self.is_running():
            raise RuntimeError("Redis server is not running")

        cmd = [
            binaries["redis-benchmark"],
            "-h", "127.0.0.1",
            "-p", str(self.port),
            "-t", "set,get",
            "-c", str(clients),
        ]

        if duration:
            cmd.extend(["-d", str(duration), "--latency"])
        else:
            cmd.extend(["-n", str(queries)])

        print(f"Running benchmark: {' '.join(cmd)}")

        result = {
            "timestamp": datetime.now().isoformat(),
            "clients": clients,
            "queries": queries,
            "duration": duration,
            "success": False,
            "stdout": "",
            "stderr": "",
            "metrics": {},
        }

        try:
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 60 if duration else 60)
            result["stdout"] = process.stdout
            result["stderr"] = process.stderr
            result["returncode"] = process.returncode

            if process.returncode == 0:
                result["success"] = True
                result["metrics"] = self._parse_benchmark_output(process.stdout)
            else:
                result["error"] = process.stderr

        except subprocess.TimeoutExpired:
            result["error"] = "Benchmark timed out"

        self.results.append(result)
        return result

    def _parse_benchmark_output(self, output):
        """Parse redis-benchmark output for metrics"""
        metrics = {}

        for line in output.split('\n'):
            if 'requests per second' in line:
                # Extract value
                import re
                match = re.search(r'([\d.]+)\s*requests per second', line)
                if match:
                    metrics["requests_per_second"] = float(match.group(1))

            if 'latency' in line.lower():
                import re
                match = re.search(r'([\d.]+)\s*ms', line)
                if match:
                    metrics["latency_ms"] = float(match.group(1))

        return metrics

    def run_sweep(self, client_counts=None, query_counts=None, duration=None):
        """
        Run Redis benchmark sweep across configurations.

        Args:
            client_counts: List of client counts to test
            query_counts: List of query counts to test
            duration: Duration in seconds for time-based tests

        Returns:
            list of result dicts
        """
        if client_counts is None:
            client_counts = [1, 10, 50, 100]
        if query_counts is None:
            query_counts = [1000, 10000, 100000]

        all_results = []

        print("=== Redis Benchmark Sweep ===")

        for clients in client_counts:
            for queries in query_counts:
                print(f"\nClients: {clients}, Queries: {queries}")
                result = self.run_benchmark(
                    clients=clients,
                    queries=queries,
                    duration=duration
                )

                if result["success"]:
                    rps = result["metrics"].get("requests_per_second", 0)
                    print(f"  RPS: {rps:.2f}")
                else:
                    print(f"  Failed: {result.get('error', 'Unknown')}")

                all_results.append(result)

        self.results = all_results
        return all_results

    def get_summary(self):
        """Get summary of benchmark results"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "tests_run": len(self.results),
            "successful": sum(1 for r in self.results if r.get("success", False)),
            "results": [],
        }

        for result in self.results:
            summary["results"].append({
                "clients": result.get("clients"),
                "queries": result.get("queries"),
                "duration": result.get("duration"),
                "rps": result["metrics"].get("requests_per_second", 0),
                "latency_ms": result["metrics"].get("latency_ms", 0),
            })

        return summary

    def save_results(self, filename=None):
        """Save results to JSON file"""
        if filename is None:
            filename = f"redis_bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        summary = self.get_summary()
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\nResults saved to {filename}")
        return filename


class LlamaCppWorkload:
    """Manages llama.cpp inference workloads"""

    def __init__(self, model_path=None, n_ctx=2048, n_threads=4):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.server_process = None
        self.results = []

    def _find_llama_binary(self):
        """Find llama.cpp binary"""
        binaries = [
            "/usr/local/bin/main",      # Standard build location
            "/usr/bin/llama-main",
            "./main",                    # Local build
            "main",                      # In PATH
        ]

        for path in binaries:
            if os.path.exists(path):
                return path

        return None

    def _find_llama_server(self):
        """Find llama.cpp server binary"""
        binaries = [
            "/usr/local/bin/server",
            "/usr/bin/llama-server",
            "./server",
            "llama-server",
        ]

        for path in binaries:
            if os.path.exists(path):
                return path

        return None

    def run_generation(self, prompt, max_tokens=100, temperature=0.7):
        """
        Run text generation with llama.cpp.

        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            dict with generation results
        """
        main_path = self._find_llama_binary()

        if not main_path:
            raise RuntimeError("llama.cpp main binary not found")

        if not self.model_path:
            raise RuntimeError("No model path specified")

        cmd = [
            main_path,
            "-m", self.model_path,
            "-p", prompt,
            "-n", str(max_tokens),
            "-t", str(self.n_threads),
            "-temp", str(temperature),
            "-cot",  # Output timing info
        ]

        print(f"Running generation with prompt: '{prompt[:50]}...'")

        result = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "success": False,
            "output": "",
            "metrics": {},
        }

        try:
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if process.returncode == 0:
                result["success"] = True
                result["output"] = process.stdout

                # Parse timing metrics
                for line in process.stderr.split('\n'):
                    if 'prompt eval time' in line:
                        import re
                        match = re.search(r'([\d.]+)\s*ms', line)
                        if match:
                            result["metrics"]["prompt_time_ms"] = float(match.group(1))

                    if 'eval time' in line and 'prompt' not in line:
                        import re
                        match = re.search(r'([\d.]+)\s*ms', line)
                        if match:
                            result["metrics"]["generation_time_ms"] = float(match.group(1))

                    if 'tokens per second' in line:
                        import re
                        match = re.search(r'([\d.]+)\s*tokens', line)
                        if match:
                            result["metrics"]["tokens_per_second"] = float(match.group(1))

            else:
                result["error"] = process.stderr

        except subprocess.TimeoutExpired:
            result["error"] = "Generation timed out"
        except Exception as e:
            result["error"] = str(e)

        self.results.append(result)
        return result

    def run_throughput_sweep(self, prompt, token_counts=None):
        """
        Run throughput test across different token generation counts.

        Args:
            prompt: Input prompt
            token_counts: List of token counts to test

        Returns:
            list of result dicts
        """
        if token_counts is None:
            token_counts = [50, 100, 200, 500]

        all_results = []

        print("=== Llama.cpp Throughput Sweep ===")

        for tokens in token_counts:
            print(f"Testing with {tokens} tokens...")
            result = self.run_generation(prompt, max_tokens=tokens)
            all_results.append(result)

            if result["success"]:
                tps = result["metrics"].get("tokens_per_second", 0)
                print(f"  Throughput: {tps:.2f} tokens/s")
            else:
                print(f"  Failed: {result.get('error', 'Unknown')}")

        self.results = all_results
        return all_results

    def run_temperature_sweep(self, prompt, temperatures=None):
        """
        Run test across different temperatures.

        Args:
            prompt: Input prompt
            temperatures: List of temperatures to test

        Returns:
            list of result dicts
        """
        if temperatures is None:
            temperatures = [0.0, 0.5, 0.7, 1.0, 1.5]

        all_results = []

        print("=== Llama.cpp Temperature Sweep ===")

        for temp in temperatures:
            print(f"Testing with temperature: {temp}")
            result = self.run_generation(prompt, max_tokens=100, temperature=temp)
            all_results.append(result)

            if result["success"]:
                tps = result["metrics"].get("tokens_per_second", 0)
                output_len = len(result["output"].split())
                print(f"  Throughput: {tps:.2f} tokens/s, Output length: {output_len} words")
            else:
                print(f"  Failed: {result.get('error', 'Unknown')}")

        self.results = all_results
        return all_results

    def get_summary(self):
        """Get summary of test results"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "tests_run": len(self.results),
            "successful": sum(1 for r in self.results if r.get("success", False)),
            "results": [],
        }

        for result in self.results:
            summary["results"].append({
                "max_tokens": result.get("max_tokens"),
                "temperature": result.get("temperature"),
                "tokens_per_second": result["metrics"].get("tokens_per_second", 0),
                "generation_time_ms": result["metrics"].get("generation_time_ms", 0),
                "prompt_time_ms": result["metrics"].get("prompt_time_ms", 0),
            })

        return summary

    def save_results(self, filename=None):
        """Save results to JSON file"""
        if filename is None:
            filename = f"llama_bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        summary = self.get_summary()
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\nResults saved to {filename}")
        return filename


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run real workloads (Redis/llama.cpp)")
    parser.add_argument("--workload", "-w", choices=["redis", "llama"], required=True,
                        help="Workload type to run")
    parser.add_argument("--model", "-m", help="Model path (for llama.cpp)")
    parser.add_argument("--action", "-a", choices=["gen", "bench", "sweep"],
                        help="Action to perform")

    args = parser.parse_args()

    if args.workload == "redis":
        workload = RedisWorkload()

        if args.action == "bench":
            workload.start_server()
            try:
                result = workload.run_benchmark()
                print(json.dumps(result, indent=2))
            finally:
                workload.stop_server()

        elif args.action == "sweep":
            workload.start_server()
            try:
                results = workload.run_sweep()
                print(json.dumps(workload.get_summary(), indent=2))
                workload.save_results()
            finally:
                workload.stop_server()

    elif args.workload == "llama":
        if not args.model:
            print("Error: --model required for llama.cpp workload")
            sys.exit(1)

        workload = LlamaCppWorkload(model_path=args.model)

        if args.action == "gen":
            result = workload.run_generation("The quick brown fox")
            print(json.dumps(result, indent=2))

        elif args.action == "sweep":
            results = workload.run_throughput_sweep("The quick brown fox")
            print(json.dumps(workload.get_summary(), indent=2))
            workload.save_results()


if __name__ == "__main__":
    main()
