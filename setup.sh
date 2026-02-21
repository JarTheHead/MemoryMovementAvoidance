#!/bin/bash

# Movement Avoidance Setup Script
# Enables Zswap with LZ4 compression and configures memory constraints

echo "=== Movement Avoidance Setup ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. Please use sudo."
   exit 1
fi

echo "Setting up Zswap with LZ4 compression..."

# Enable Zswap
echo 1 > /sys/module/zswap/parameters/enabled
echo "Zswap enabled."

# Set compression algorithm to LZ4 (fastest option)
echo lz4 > /sys/module/zswap/parameters/compressor
echo "Compression algorithm set to LZ4."

# Set maximum pool percentage to 20% (avoid excessive swapping to disk)
echo 20 > /sys/module/zswap/parameters/max_pool_percent
echo "Zswap pool limit set to 20% of RAM."

# Reduce tendency to swap to disk by increasing swappiness
# Lower swappiness means less eager to swap to disk
echo 10 > /proc/sys/vm/swappiness
echo "Swappiness set to 10 (low tendency to swap)."



# Create a control group for limiting memory
CGROUP_DIR="/sys/fs/cgroup/memory/movement_avoidance_test"
cgcreate -g memory:movement_avoidance_test
echo "Created cgroup at $CGROUP_DIR"

# Set memory limit to 512MB for testing (adjust as needed)
echo 536870912 > "$CGROUP_DIR/memory.limit_in_bytes"
echo "Memory limit set to 512MB."

# Show current Zswap status
echo ""
echo "=== Zswap Status ==="
echo "Enabled: $(cat /sys/module/zswap/parameters/enabled)"
echo "Compressor: $(cat /sys/module/zswap/parameters/compressor)"
echo "Max Pool Percent: $(cat /sys/module/zswap/parameters/max_pool_percent)%"
echo "Swappiness: $(cat /proc/sys/vm/swappiness)"

echo ""
echo "Setup complete! Run workload with: cgexec -g memory:movement_avoidance_test python3 workload.py"
