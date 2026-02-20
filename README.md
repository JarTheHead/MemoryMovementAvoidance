# Movement Avoidance Project

This project demonstrates how memory compression can expand system capacity by avoiding movement of data to slow storage devices.

## Project Overview

The goal is to prove that compressing data in memory allows the system to hold more data without using the slow hard drive. We call this expanding capacity to avoid movement.

## Components

1. **Setup Script** (`setup.sh`) - Configures Zswap with LZ4 compression and creates a memory-constrained cgroup
2. **Controller** (`controller.py`) - Monitors system pressure and dynamically adjusts compression
3. **Workload** (`workload.py`) - Generates memory pressure to test the system
4. **Logger** (`logger.py`) - Records test results to a CSV file

## Prerequisites

- Linux system with Zswap support
- Python 3.x with psutil library (`pip install psutil`)
- cgroup tools (`sudo apt install cgroup-tools` on Ubuntu/Debian)
- For visualization: matplotlib (`pip install matplotlib pandas`)

## Installation

1. Install required packages:
   ```bash
   sudo apt update
   sudo apt install cgroup-tools python3-pip
   pip3 install psutil
   ```

2. Clone or download this project

## Running the Project

### Step 1: Run Setup Script
```bash
sudo ./setup.sh
```

This script:
- Enables Zswap with LZ4 compression
- Sets compression pool to 20% of RAM
- Reduces swappiness to minimize disk swapping
- Creates a cgroup with 512MB memory limit

### Step 2: Start the Controller
In one terminal:
```bash
python3 controller.py
```

The controller will:
- Monitor memory pressure via PSI (Pressure Stall Information)
- Monitor CPU usage
- Dynamically adjust compression levels
- Log metrics to `movement_avoidance_results.csv`

### Step 3: Run the Workload
In another terminal:
```bash
sudo cgexec -g memory:movement_avoidance_test python3 workload.py
```

The workload will:
- Allocate large chunks of memory
- Continuously modify data to create memory pressure
- Operate within the constrained cgroup

### Step 4: Monitor Results
Results are logged to `movement_avoidance_results.csv` with columns:
- Time: Timestamp of measurement
- Memory_Pressure: Memory pressure percentage
- CPU_Pressure: CPU usage percentage
- Swap_Activity: Whether swapping to disk occurred
- Compression_Ratio: Current compression effectiveness

### Step 5: Visualize Results (Optional)
To visualize the results with graphs:
```bash
python3 visualize.py
```

This will create charts showing:
- System pressure over time
- Compression ratio trends
- Swap activity patterns
- Correlation between compression and swapping

## Expected Results

You should observe:
1. High compression ratios lead to reduced swap activity
2. When CPU is free, compression increases to accommodate more data
3. When CPU is busy, compression decreases to reduce processing overhead
4. Less frequent swapping to disk compared to systems without compression

## Interpreting the Data

Look for patterns in the CSV log file:
- When `Compression_Ratio` is high and `Swap_Activity` is `False`, movement avoidance is successful
- When `Swap_Activity` becomes `True`, movement avoidance has failed
- Higher `Compression_Ratio` values indicate more effective memory utilization

## Troubleshooting

1. **Permission errors**: Ensure you run setup.sh with sudo
2. **cgroup errors**: Verify cgroup-tools is installed
3. **PSI not available**: Some older kernels don't support Pressure Stall Information
4. **Zswap not supported**: Check kernel version (4.8+ required)

## Cleaning Up

To disable Zswap after testing:
```bash
echo 0 | sudo tee /sys/module/zswap/parameters/enabled
```

To remove the cgroup:
```bash
sudo rmdir /sys/fs/cgroup/memory/movement_avoidance_test
```