# Memory Movement Avoidance Project

This project demonstrates memory compression for expanding system capacity by avoiding data movement to slow storage devices. It uses Zswap (Linux kernel compression) combined with dynamic pressure-based control and NUMA-aware optimizations.

## Project Overview

The goal is to prove that compressing data in memory allows the system to hold more data without using the slow hard drive. We call this expanding capacity to avoid movement.

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ workload.py      │────>│ controller.py    │────>│ setup.sh         │
│ (memory stress)  │     │ (dynamic control)│     │ (Zswap/cgroup)   │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   logger.py      │
                    │ (CSV logging)    │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  visualize.py    │
                    │ (graph generation)│
                    └──────────────────┘
```

## Key Components

| Component | File | Description |
|-----------|------|-------------|
| Zswap Controller | `controller.py` | Monitors PSI/CPU, dynamically adjusts compression pool (5-50%) |
| NUMA Monitor | `numa_monitor.c` | Per-node memory, PSI, migration stats (high performance) |
| Adaptive Compressor | `adaptive_compressor.c` | Cycles through lzo/lz4/zstd based on system metrics |
| Memory Workload | `workload.py` | Generates pressure by allocating blocks, modifying data |
| Memory Workload (C) | `allocate_memory.c` | High-performance memory allocator with configurable size |
| StressNG Workload | `stressng_workload.py` | Synthetic sweep testing with pattern/contention variables |
| Real Workloads | `real_workloads.py` | Redis benchmark and llama.cpp inference managers |
| Logger | `logger.py` | Logs metrics to `movement_avoidance_results.csv` |
| Visualization | `visualize.py` | Creates matplotlib charts from CSV data |
| Setup | `setup.sh` | Enables Zswap, sets cgroup limits, NUMA topology detection |

## Features

- **Dynamic Compression Control**: Automatically adjusts Zswap pool (5-50%) based on system pressure
- **NUMA-Aware Monitoring**: Tracks per-node memory usage and cross-node access rates
- **Adaptive Algorithm Selection**: Cycles through compression algorithms (lzo, lz4, zstd) based on CPU/memory pressure
- **Synthetic Testing**: stress-ng sweep across memory patterns and CPU contention
- **Real Workload Validation**: Redis latency measurements and llama.cpp throughput testing
- **High-Performance C Implementations**: Critical monitoring paths optimized in C

## Prerequisites

- Linux kernel 4.8+ (Zswap requirement)
- Python 3.x with psutil library (`pip install psutil`)
- cgroup tools (`sudo apt install cgroup-tools` on Ubuntu/Debian)
- For visualization: matplotlib and pandas (`pip install matplotlib pandas`)
- stress-ng (optional, for synthetic testing: `sudo apt install stress-ng`)

## Installation

1. Install required packages:
   ```bash
   sudo apt update
   sudo apt install cgroup-tools python3-pip stress-ng
   pip3 install psutil matplotlib pandas
   ```

2. Clone or download this project

## Running the Project

### Step 1: Run Setup Script
```bash
sudo ./setup.sh
```

This script:
- Enables Zswap with automatic compressor selection (zstd > lz4 > lzo)
- Sets compression pool based on system memory (20-30%)
- Detects NUMA topology and creates per-NUMA cgroups
- Reduces swappiness to minimize disk swapping
- Sets memory limits for cgroup testing

### Step 2: Start the Controller

**Using C controller (recommended for production):**
```bash
gcc -O3 -o controller controller.c
sudo ./controller
```

**Using Python controller (for development/debugging):**
```bash
python3 controller.py
```

The controller will:
- Monitor memory pressure via PSI (Pressure Stall Information)
- Monitor CPU usage and NUMA miss rates
- Dynamically adjust compression levels and algorithm
- Log metrics to `movement_avoidance_results.csv`

### Step 3: Run the Workload

**Python workload:**
```bash
sudo cgexec -g memory:movement_avoidance_test python3 workload.py
```

**C workload with 1GB limit, 4KB blocks:**
```bash
gcc -O3 -o allocate_memory allocate_memory.c
sudo cgexec -g memory:movement_avoidance_test ./allocate_memory 1G 4K
```

The workload will:
- Allocate large chunks of memory within cgroup limits
- Continuously modify data to create memory pressure
- Trigger compression via memory pressure

### Step 4: Run Synthetic Testing (Optional)

```bash
# Test different memory patterns and CPU contention
python3 stressng_workload.py --duration 30 --pattern random --contention 50

# Full sweep across all combinations
python3 stressng_workload.py --duration 60
```

### Step 5: Monitor Results
Results are logged to `movement_avoidance_results.csv` with columns:
- Time: Timestamp of measurement
- Memory_Pressure: Memory pressure percentage (PSI)
- CPU_Pressure: CPU usage percentage
- Swap_Activity: Whether swapping to disk occurred
- Compression_Ratio: Current compression effectiveness
- Node0_Free, Node1_Free: Per-node free memory (MB)
- NUMA_Miss_Rate: Cross-node access percentage
- Algorithm: Current compression algorithm (lzo, lz4, zstd)

### Step 6: Visualize Results
```bash
python3 visualize.py
```

This creates charts showing:
- System pressure over time (Memory/CPU)
- Compression ratio trends
- NUMA miss rate over time
- Per-node memory free
- Per-node compression ratios
- Algorithm selection over time
- StressNG sweep heatmap (pattern vs contention vs throughput)

## Running Real Workloads

### Redis Benchmark
```bash
# With sweep across configurations
python3 real_workloads.py --workload redis --action sweep

# Single benchmark
python3 real_workloads.py --workload redis --action bench
```

### Llama.cpp Inference
```bash
# Throughput sweep across token counts
python3 real_workloads.py --workload llama --action sweep --model /path/to/model.gguf
```

## Expected Results

You should observe:
1. **High compression ratios** lead to reduced swap activity
2. When CPU is free, compression **increases** to accommodate more data
3. When CPU is busy, compression **decreases** to reduce processing overhead
4. **Less frequent swapping** to disk compared to systems without compression
5. **NUMA-aware systems** show lower cross-node access rates with optimized settings

## Interpreting the Data

Look for patterns in the CSV log file:
- When `Compression_Ratio` is high and `Swap_Activity` is `False`, movement avoidance is successful
- When `Swap_Activity` becomes `True`, movement avoidance has failed
- Higher `Compression_Ratio` values indicate more effective memory utilization
- Lower `NUMA_Miss_Rate` indicates better memory placement on NUMA systems

## Command Line Options

### Controller
```bash
python3 controller.py -h
# Options:
#   -i, --interval SECONDS   Measurement interval (default: 5)
#   -n, --iterations NUM     Number of iterations (0 = forever)
#   -d, --dry-run            Show recommendations without changes
```

### C Controller
```bash
sudo ./controller -h
# Options:
#   -i, --interval SECONDS   Measurement interval (default: 5)
#   -n, --iterations NUM     Number of iterations (0 = forever)
#   -q, --quiet              Suppress metrics output
#   -d, --dry-run            Show recommendations without changes
```

### StressNG Workload
```bash
python3 stressng_workload.py -h
# Options:
#   -d, --duration SECONDS   Duration per test
#   -m, --memory GB          Memory to allocate
#   -p, --pattern PATTERNS   Memory patterns to test
#   -c, --contention PCT     CPU contention percentages
```

## C Implementation Performance

The C implementations (`numa_monitor.c`, `adaptive_compressor.c`, `controller.c`) provide:
- **3-5x faster** file I/O parsing compared to Python
- **Minimal overhead** for continuous 24/7 monitoring
- **Direct sysfs access** without Python bindings
- **No subprocess overhead** for monitoring

## Troubleshooting

1. **Permission errors**: Run setup.sh and controller with `sudo`
2. **cgroup errors**: Verify cgroup-tools is installed (`sudo apt install cgroup-tools`)
3. **PSI not available**: Kernel 4.17+ required for Pressure Stall Information
4. **Zswap not supported**: Check kernel version (`uname -r`, requires 4.8+)
5. **Debugfs not mounted**: Mount with `sudo mount -t debugfs debugfs /sys/kernel/debug`

## NUMA-Specific Notes

On NUMA systems:
- Per-node cgroups are created at `/sys/fs/cgroup/memory/movement_avoidance_test/node0`
- Run workload on specific node: `sudo cgexec -g memory:movement_avoidance_test/node0 python3 workload.py`
- Monitor NUMA status: `gcc -O3 -o numa_monitor numa_monitor.c && sudo ./numa_monitor`

## Cleaning Up

To disable Zswap after testing:
```bash
echo 0 | sudo tee /sys/module/zswap/parameters/enabled
```

To remove the cgroup:
```bash
sudo rmdir /sys/fs/cgroup/memory/movement_avoidance_test 2>/dev/null || true
sudo rmdir /sys/fs/cgroup/memory/movement_avoidance_test/node0 2>/dev/null || true
sudo rmdir /sys/fs/cgroup/memory/movement_avoidance_test/node1 2>/dev/null || true
```

## License

MIT License - See LICENSE file for details.
