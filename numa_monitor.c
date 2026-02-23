/*
 * NUMA Monitor - C Implementation
 *
 * High-performance monitoring of per-node memory, PSI, and NUMA statistics.
 * Parses /sys/devices/system/node/node*/ for per-node stats.
 *
 * Compile with:
 *   gcc -O3 -o numa_monitor numa_monitor.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <glob.h>

#define NODE_DIR "/sys/devices/system/node"
#define NODE_COUNT_MAX 8
#define MAX_PATH_LEN 512
#define MAX_LINE_LEN 4096

/* NUMA node statistics */
typedef struct {
    int node_id;
    unsigned long mem_total_kb;
    unsigned long mem_free_kb;
    unsigned long mem_available_kb;
    unsigned long buffers_kb;
    unsigned long cached_kb;
    unsigned long swap_cached_kb;
    unsigned long active_kb;
    unsigned long inactive_kb;
    unsigned long active_anon_kb;
    unsigned long inactive_anon_kb;
    unsigned long active_file_kb;
    unsigned long inactive_file_kb;
    unsigned long numa_hits;
    unsigned long numa_misses;
} numa_node_stats_t;

/* Global state */
static numa_node_stats_t nodes[NODE_COUNT_MAX];
static int num_nodes = 0;
static int is_numa_system = 0;

/* Read entire file into buffer */
static ssize_t read_file(const char *path, char *buf, size_t bufsize) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;

    ssize_t n = read(fd, buf, bufsize - 1);
    close(fd);

    if (n <= 0) return -1;
    buf[n] = '\0';
    return n;
}

/* Get free memory for a node from its meminfo */
static unsigned long get_node_meminfo_kb(const char *node_path, const char *key) {
    char path[MAX_PATH_LEN];
    snprintf(path, sizeof(path), "%s/meminfo", node_path);

    char buf[MAX_LINE_LEN];
    ssize_t n = read_file(path, buf, sizeof(buf));
    if (n < 0) return 0;

    char *line = strtok(buf, "\n");
    while (line) {
        unsigned long value;
        if (strncmp(line, key, strlen(key)) == 0 &&
            sscanf(line, "%*s %lu", &value) == 1) {
            return value;
        }
        line = strtok(NULL, "\n");
    }
    return 0;
}

/* Scan all NUMA nodes */
static void scan_numa_nodes(void) {
    num_nodes = 0;
    is_numa_system = 0;

    char pattern[MAX_PATH_LEN];
    snprintf(pattern, sizeof(pattern), "%s/node*", NODE_DIR);

    glob_t glob_result;
    if (glob(pattern, 0, NULL, &glob_result) != 0) {
        return;
    }

    for (size_t i = 0; i < glob_result.gl_pathc && num_nodes < NODE_COUNT_MAX; i++) {
        const char *node_path = glob_result.gl_pathv[i];

        /* Extract node ID from path */
        int node_id = -1;
        if (sscanf(node_path, "%*s/node%d", &node_id) != 1) continue;

        numa_node_stats_t *node = &nodes[num_nodes];
        node->node_id = node_id;

        /* Read meminfo stats */
        node->mem_total_kb = get_node_meminfo_kb(node_path, "MemTotal:");
        node->mem_free_kb = get_node_meminfo_kb(node_path, "MemFree:");
        node->mem_available_kb = get_node_meminfo_kb(node_path, "MemAvailable:");
        node->buffers_kb = get_node_meminfo_kb(node_path, "Buffers:");
        node->cached_kb = get_node_meminfo_kb(node_path, "Cached:");
        node->swap_cached_kb = get_node_meminfo_kb(node_path, "SwapCached:");
        node->active_kb = get_node_meminfo_kb(node_path, "Active:");
        node->inactive_kb = get_node_meminfo_kb(node_path, "Inactive:");
        node->active_anon_kb = get_node_meminfo_kb(node_path, "Active(anon):");
        node->inactive_anon_kb = get_node_meminfo_kb(node_path, "Inactive(anon):");
        node->active_file_kb = get_node_meminfo_kb(node_path, "Active(file):");
        node->inactive_file_kb = get_node_meminfo_kb(node_path, "Inactive(file):");

        /* Read NUMA hit/miss stats */
        char numastat_path[MAX_PATH_LEN];
        snprintf(numastat_path, sizeof(numastat_path), "%s/numastat", node_path);

        char buf[MAX_LINE_LEN];
        ssize_t n = read_file(numastat_path, buf, sizeof(buf));
        if (n > 0) {
            char *line = strtok(buf, "\n");
            while (line) {
                unsigned long val;
                char key[64];
                if (sscanf(line, "%63s %lu", key, &val) == 2) {
                    if (strcmp(key, "numa_hit") == 0) {
                        node->numa_hits = val;
                    } else if (strcmp(key, "numa_miss") == 0) {
                        node->numa_misses = val;
                    }
                }
                line = strtok(NULL, "\n");
            }
        }

        num_nodes++;
    }

    globfree(&glob_result);

    /* Check if this is a NUMA system */
    if (num_nodes > 1) {
        is_numa_system = 1;
    }
}

/* Check if system has NUMA topology */
int numa_is_numa_system(void) {
    if (num_nodes == 0) scan_numa_nodes();
    return is_numa_system;
}

/* Get number of NUMA nodes */
int numa_get_num_nodes(void) {
    if (num_nodes == 0) scan_numa_nodes();
    return num_nodes;
}

/* Get node stats for a specific node */
const numa_node_stats_t* numa_get_node_stats(int node_id) {
    if (num_nodes == 0) scan_numa_nodes();

    for (int i = 0; i < num_nodes; i++) {
        if (nodes[i].node_id == node_id) {
            return &nodes[i];
        }
    }
    return NULL;
}

/* Get all node stats */
const numa_node_stats_t* numa_get_all_nodes(int *count) {
    if (num_nodes == 0) scan_numa_nodes();
    if (count) *count = num_nodes;
    return nodes;
}

/* Get total NUMA hits and misses */
void numa_get_total_counts(unsigned long *hits, unsigned long *misses) {
    if (num_nodes == 0) scan_numa_nodes();

    unsigned long total_hits = 0, total_misses = 0;

    for (int i = 0; i < num_nodes; i++) {
        total_hits += nodes[i].numa_hits;
        total_misses += nodes[i].numa_misses;
    }

    if (hits) *hits = total_hits;
    if (misses) *misses = total_misses;
}

/* Get NUMA miss rate (percentage) */
double numa_get_miss_rate(void) {
    unsigned long hits, misses;
    numa_get_total_counts(&hits, &misses);

    unsigned long total = hits + misses;
    if (total == 0) return 0.0;

    return ((double)misses / total) * 100.0;
}

/* Get node pressure (percentage of memory used) */
double numa_get_node_pressure(int node_id) {
    const numa_node_stats_t *node = numa_get_node_stats(node_id);
    if (!node || node->mem_total_kb == 0) return 0.0;

    double used = (double)(node->mem_total_kb - node->mem_free_kb);
    return (used / node->mem_total_kb) * 100.0;
}

/* Print node memory info in MB */
void numa_print_node_memory(int node_id) {
    const numa_node_stats_t *node = numa_get_node_stats(node_id);
    if (!node) {
        printf("Node %d not found\n", node_id);
        return;
    }

    printf("Node %d:\n", node_id);
    printf("  Total:     %8lu MB\n", node->mem_total_kb / 1024);
    printf("  Free:      %8lu MB\n", node->mem_free_kb / 1024);
    printf("  Available: %8lu MB\n", node->mem_available_kb / 1024);
    printf("  Used:      %8lu MB (%.1f%%)\n",
           (node->mem_total_kb - node->mem_free_kb) / 1024,
           100.0 - ((double)node->mem_free_kb / node->mem_total_kb * 100.0));
}

/* Print NUMA migration stats */
void numa_print_numa_stats(void) {
    unsigned long hits, misses;
    numa_get_total_counts(&hits, &misses);

    printf("NUMA Stats:\n");
    printf("  Hits:   %lu\n", hits);
    printf("  Misses: %lu\n", misses);
    printf("  Miss Rate: %.2f%%\n", numa_get_miss_rate());
}

/* Print full node summary */
void numa_print_node_summary(void) {
    if (num_nodes == 0) scan_numa_nodes();

    printf("=== NUMA Node Summary ===\n");
    printf("System: %s\n", is_numa_system ? "NUMA" : "UMA");

    for (int i = 0; i < num_nodes; i++) {
        numa_print_node_memory(i);
    }

    if (is_numa_system) {
        printf("\n");
        numa_print_numa_stats();
    }
}

/* Print per-node pressure */
void numa_print_node_pressure(void) {
    if (num_nodes == 0) scan_numa_nodes();

    printf("=== Node Memory Pressure ===\n");
    for (int i = 0; i < num_nodes; i++) {
        double pressure = numa_get_node_pressure(i);
        printf("  Node%d: %.1f%%\n", i, pressure);
    }
}

/* Print JSON summary for easy parsing */
void numa_print_json_summary(void) {
    if (num_nodes == 0) scan_numa_nodes();

    unsigned long hits, misses;
    numa_get_total_counts(&hits, &misses);
    double miss_rate = numa_get_miss_rate();

    printf("{\n");
    printf("  \"is_numa\": %s,\n", is_numa_system ? "true" : "false");
    printf("  \"num_nodes\": %d,\n", num_nodes);

    printf("  \"nodes\": [\n");
    for (int i = 0; i < num_nodes; i++) {
        const numa_node_stats_t *node = &nodes[i];
        printf("    {\n");
        printf("      \"node_id\": %d,\n", node->node_id);
        printf("      \"mem_total_kb\": %lu,\n", node->mem_total_kb);
        printf("      \"mem_free_kb\": %lu,\n", node->mem_free_kb);
        printf("      \"mem_available_kb\": %lu,\n", node->mem_available_kb);
        printf("      \"numa_hits\": %lu,\n", node->numa_hits);
        printf("      \"numa_misses\": %lu\n", node->numa_misses);
        printf("    }%s\n", i < num_nodes - 1 ? "," : "");
    }
    printf("  ],\n");

    printf("  \"total_hits\": %lu,\n", hits);
    printf("  \"total_misses\": %lu,\n", misses);
    printf("  \"miss_rate\": %.2f\n", miss_rate);
    printf("}\n");
}

/* Main entry point */
int main(int argc, char *argv[]) {
    int opt;
    int json_output = 0;
    int pressure_only = 0;

    /* Parse arguments */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-j") == 0 || strcmp(argv[i], "--json") == 0) {
            json_output = 1;
        } else if (strcmp(argv[i], "-p") == 0 || strcmp(argv[i], "--pressure") == 0) {
            pressure_only = 1;
        } else if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            printf("Usage: %s [OPTIONS]\n", argv[0]);
            printf("\nNUMA Monitor - High Performance Monitoring\n");
            printf("\nOptions:\n");
            printf("  -j, --json       Output in JSON format\n");
            printf("  -p, --pressure   Show only node pressure\n");
            printf("  -h, --help       Show this help\n");
            return 0;
        }
    }

    scan_numa_nodes();

    if (json_output) {
        numa_print_json_summary();
    } else if (pressure_only) {
        numa_print_node_pressure();
    } else {
        numa_print_node_summary();
    }

    return 0;
}
