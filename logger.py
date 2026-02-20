#!/usr/bin/env python3

import sys
import os
from datetime import datetime

LOG_FILE = "movement_avoidance_results.csv"

def initialize_log():
    """Initialize the log file with headers if it doesn't exist"""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("Time,Memory_Pressure,CPU_Pressure,Swap_Activity,Compression_Ratio\n")
        print(f"Initialized log file: {LOG_FILE}")

def log_metrics(timestamp, mem_pressure, cpu_pressure, swap_activity, compression_ratio):
    """Log metrics to CSV file"""
    # Convert timestamp to readable format
    if timestamp.startswith('20'):
        # Already a datetime string
        time_str = timestamp
    else:
        # Assume it's a datetime object
        time_str = str(timestamp)

    # Format swap activity as boolean string
    swap_str = "True" if str(swap_activity).lower() in ['true', '1', 'yes'] else "False"

    # Prepare log entry
    log_entry = f"{time_str},{mem_pressure},{cpu_pressure},{swap_str},{compression_ratio}\n"

    # Append to log file
    with open(LOG_FILE, "a") as f:
        f.write(log_entry)

    print(f"Logged: {log_entry.strip()}")

def main():
    """Main function to log metrics from command line arguments"""
    if len(sys.argv) != 6:
        print("Usage: python3 logger.py <timestamp> <memory_pressure> <cpu_pressure> <swap_activity> <compression_ratio>")
        print("Example: python3 logger.py '2023-01-01 12:00:00' 45.2 23.1 True 2.5")
        sys.exit(1)

    timestamp = sys.argv[1]
    mem_pressure = sys.argv[2]
    cpu_pressure = sys.argv[3]
    swap_activity = sys.argv[4]
    compression_ratio = sys.argv[5]

    # Initialize log file if needed
    initialize_log()

    # Log the metrics
    log_metrics(timestamp, mem_pressure, cpu_pressure, swap_activity, compression_ratio)

if __name__ == "__main__":
    # If called directly without arguments, just initialize the log
    if len(sys.argv) == 1:
        initialize_log()
        print(f"Logger initialized. Ready to log to {LOG_FILE}")
    else:
        main()