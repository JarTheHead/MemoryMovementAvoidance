#!/bin/bash

# Movement Avoidance Setup Script
# Enables Zswap with configurable compression and configures memory constraints
# Supports NUMA topology detection and per-NUMA cgroup configuration

echo "=== Movement Avoidance Setup ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. Please use sudo."
   exit 1
fi

# ============================================
# Phase 1: NUMA Topology Detection
# ============================================
echo ""
echo "=== Phase 1: NUMA Topology Detection ==="

NUMA_NODES=0
if [ -d "/sys/devices/system/node" ]; then
    NUMA_NODES=$(ls -d /sys/devices/system/node/node* 2>/dev/null | wc -l)
fi

echo "Detected $NUMA_NODES NUMA node(s)"

if [ "$NUMA_NODES" -gt 1 ]; then
    echo "NUMA system detected. Per-node cgroups will be configured."
    IS_NUMA=1
else
    echo "Single-node system detected. Using unified cgroup."
    IS_NUMA=0
fi

# ============================================
# Phase 2: Zswap Configuration
# ============================================
echo ""
echo "=== Phase 2: Zswap Configuration ==="

echo "Setting up Zswap..."

# Check if Zswap is available
if [ ! -f "/sys/module/zswap/parameters/enabled" ]; then
    echo "Error: Zswap not available on this system (kernel 4.8+ required)"
    exit 1
fi

# Enable Zswap
echo 1 > /sys/module/zswap/parameters/enabled
echo "Zswap enabled."

# Detect available compressors
AVAILABLE_COMPRESSORS=""
if [ -f "/sys/module/zswap/parameters/compressor" ]; then
    AVAILABLE_COMPRESSORS=$(cat /sys/module/zswap/parameters/compressor)
fi

echo "Available compressors: $AVAILABLE_COMPRESSORS"

# Set compression algorithm (choose best available)
if echo "$AVAILABLE_COMPRESSORS" | grep -q "zstd"; then
    echo zstd > /sys/module/zswap/parameters/compressor
    echo "Compression algorithm set to ZSTD (best ratio)."
    COMPRESSION_ALGO="zstd"
elif echo "$AVAILABLE_COMPRESSORS" | grep -q "lz4"; then
    echo lz4 > /sys/module/zswap/parameters/compressor
    echo "Compression algorithm set to LZ4 (balanced)."
    COMPRESSION_ALGO="lz4"
elif echo "$AVAILABLE_COMPRESSORS" | grep -q "lzo"; then
    echo lzo > /sys/module/zswap/parameters/compressor
    echo "Compression algorithm set to LZO (fastest)."
    COMPRESSION_ALGO="lzo"
else
    echo "Warning: No recommended compressors available"
    COMPRESSION_ALGO="unknown"
fi

# Set maximum pool percentage (5-50% range)
# Default to 20%, adjust based on available memory
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
MAX_POOL_PERCENT=20

# If system has more than 8GB RAM, increase pool limit
if [ "$TOTAL_MEM_KB" -gt 8388608 ]; then
    MAX_POOL_PERCENT=30
    echo "Large system detected - increasing pool limit to 30%"
fi

echo $MAX_POOL_PERCENT > /sys/module/zswap/parameters/max_pool_percent
echo "Zswap pool limit set to ${MAX_POOL_PERCENT}% of RAM."

# Reduce tendency to swap to disk by setting swappiness
# Lower swappiness means less eager to swap to disk
echo 10 > /proc/sys/vm/swappiness
echo "Swappiness set to 10 (low tendency to swap)."

# ============================================
# Phase 3: NUMA-Aware Memory Configuration
# ============================================
echo ""
echo "=== Phase 3: NUMA-Aware Memory Configuration ==="

# Calculate memory limits based on NUMA topology
TOTAL_MEM_MB=$((TOTAL_MEM_KB / 1024))

if [ "$IS_NUMA" -eq 1 ]; then
    # NUMA system - calculate per-node memory
    NODE0_MEM_KB=$(cat /sys/devices/system/node/node0/meminfo | grep MemTotal | awk '{print $2}')
    NODE1_MEM_KB=$(cat /sys/devices/system/node/node1/meminfo | grep MemTotal | awk '{print $2}' 2>/dev/null || echo "0")

    echo "Node 0 memory: $((NODE0_MEM_KB / 1024)) MB"
    if [ -n "$NODE1_MEM_KB" ] && [ "$NODE1_MEM_KB" -gt 0 ]; then
        echo "Node 1 memory: $((NODE1_MEM_KB / 1024)) MB"
    fi

    # Allocate 80% of per-node memory to cgroups
    NODE0_LIMIT_MB=$((NODE0_MEM_KB / 1024 * 80 / 100))
    NODE1_LIMIT_MB=0
    if [ -n "$NODE1_MEM_KB" ] && [ "$NODE1_MEM_KB" -gt 0 ]; then
        NODE1_LIMIT_MB=$((NODE1_MEM_KB / 1024 * 80 / 100))
    fi
else
    # Single node system
    NODE0_LIMIT_MB=$((TOTAL_MEM_MB * 80 / 100))
    NODE1_LIMIT_MB=0
fi

echo "Node 0 cgroup memory limit: ${NODE0_LIMIT_MB}MB"
if [ "$NODE1_LIMIT_MB" -gt 0 ]; then
    echo "Node 1 cgroup memory limit: ${NODE1_LIMIT_MB}MB"
fi

# ============================================
# Phase 4: cgroup Configuration
# ============================================
echo ""
echo "=== Phase 4: cgroup Configuration ==="

# Remove existing cgroup if present
CGROUP_DIR="/sys/fs/cgroup/memory/movement_avoidance_test"
if [ -d "$CGROUP_DIR" ]; then
    cgdelete -g memory:movement_avoidance_test 2>/dev/null
    echo "Removed existing cgroup"
fi

# Create main cgroup
cgcreate -g memory:movement_avoidance_test
echo "Created main cgroup at $CGROUP_DIR"

# Set main memory limit
echo $((NODE0_LIMIT_MB * 1024 * 1024)) > "$CGROUP_DIR/memory.limit_in_bytes"
echo "Main cgroup memory limit set to ${NODE0_LIMIT_MB}MB."

# If NUMA, create per-node sub-cgroups
if [ "$IS_NUMA" -eq 1 ] && [ -d "/sys/devices/system/node/node1" ]; then
    # Create NUMA-aware cgroups
    CGROUP_NODE0="/sys/fs/cgroup/memory/movement_avoidance_test/node0"
    CGROUP_NODE1="/sys/fs/cgroup/memory/movement_avoidance_test/node1"

    cgcreate -g memory:movement_avoidance_test/node0
    cgcreate -g memory:movement_avoidance_test/node1

    echo "Created NUMA cgroups:"
    echo "  $CGROUP_NODE0"
    echo "  $CGROUP_NODE1"

    # Set per-node memory limits
    echo $((NODE0_LIMIT_MB * 1024 * 1024)) > "$CGROUP_NODE0/memory.limit_in_bytes"
    echo "$CGROUP_NODE0 memory limit: ${NODE0_LIMIT_MB}MB"

    echo $((NODE1_LIMIT_MB * 1024 * 1024)) > "$CGROUP_NODE1/memory.limit_in_bytes"
    echo "$CGROUP_NODE1 memory limit: ${NODE1_LIMIT_MB}MB"
fi

# ============================================
# Phase 5: Verification
# ============================================
echo ""
echo "=== Phase 5: Verification ==="
echo "=== Zswap Status ==="
echo "Enabled: $(cat /sys/module/zswap/parameters/enabled)"
echo "Compressor: $(cat /sys/module/zswap/parameters/compressor)"
echo "Max Pool Percent: $(cat /sys/module/zswap/parameters/max_pool_percent)%"
echo "Swappiness: $(cat /proc/sys/vm/swappiness)"

echo ""
echo "=== NUMA Topology ==="
if [ "$IS_NUMA" -eq 1 ]; then
    echo "NUMA nodes detected: $NUMA_NODES"
    for node in /sys/devices/system/node/node*; do
        node_id=$(basename "$node" | sed 's/node//')
        node_mem=$(grep MemTotal "$node/meminfo" | awk '{print $2}')
        echo "  Node $node_id: $((node_mem / 1024)) MB"
    done
else
    echo "Single-node system"
fi

echo ""
echo "=== cgroup Configuration ==="
echo "Main cgroup: $CGROUP_DIR"
echo "Memory limit: $(( $(cat "$CGROUP_DIR/memory.limit_in_bytes") / 1024 / 1024 ))MB"

if [ "$IS_NUMA" -eq 1 ] && [ -d "$CGROUP_NODE0" ]; then
    echo "Node 0 cgroup: $CGROUP_NODE0"
    echo "Memory limit: $(( $(cat "$CGROUP_NODE0/memory.limit_in_bytes") / 1024 / 1024 ))MB"
    echo "Node 1 cgroup: $CGROUP_NODE1"
    echo "Memory limit: $(( $(cat "$CGROUP_NODE1/memory.limit_in_bytes") / 1024 / 1024 ))MB"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Usage examples:"
echo ""
echo "# Memory workload (any system):"
echo "sudo cgexec -g memory:movement_avoidance_test python3 memory_workload.py"
echo ""
echo "# NUMA-aware memory workload (bind to specific node):"
echo "sudo cgexec -g memory:movement_avoidance_test/node0 python3 memory_workload.py"
echo ""
echo "# CPU workload control:"
echo "#   No CPU load (memory only):"
echo "python3 cpu_workload.py --contention 0 --duration 60"
echo "#   50% CPU contention:"
echo "python3 cpu_workload.py --contention 50 --duration 60"
echo "#   Full CPU burn-in:"
echo "python3 cpu_workload.py --burnin --duration 120"
echo ""
echo "# Combined memory + CPU workload:"
echo "python3 cpu_workload.py --contention 50 &"
echo "sudo cgexec -g memory:movement_avoidance_test python3 memory_workload.py"
echo ""
echo "# With stress-ng memory sweep:"
echo "python3 stressng_memory_workload.py --duration 30 --pattern random --contention 50"
echo ""
echo "# With real memory workloads:"
echo "python3 real_memory_workloads.py --workload redis --action sweep"
echo "python3 real_memory_workloads.py --workload llama --action sweep --model /path/to/model"
echo ""
echo "# Visualize results:"
echo "python3 visualize.py"
echo ""
