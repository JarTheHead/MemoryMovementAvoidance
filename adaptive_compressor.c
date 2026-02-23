/*
 * Adaptive Compressor - C Implementation
 *
 * Dynamically cycles through compression algorithms (lzo, lz4, zstd)
 * based on system metrics. Configurable cycle interval.
 *
 * Compile with:
 *   gcc -O3 -o adaptive_compressor adaptive_compressor.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <getopt.h>
#include <time.h>

#define COMPRESSOR_PATH "/sys/module/zswap/parameters/compressor"
#define MAX_ALGOS 16
#define MAX_LINE_LEN 4096
#define DEFAULT_CYCLE_INTERVAL 300  /* 5 minutes */

/* Configuration */
static int config_cycle_interval = DEFAULT_CYCLE_INTERVAL;
static int config_dry_run = 0;

/* Available algorithms */
static const char *algorithms[] = {"lzo", "lz4", "zstd"};
static const int num_algorithms = 3;
static const char *current_algorithm = NULL;
static time_t algorithm_start_time = 0;

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

/* Read a single integer from a file */
static int read_int_file(const char *path, long *value) {
    char buf[64];
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;

    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);

    if (n <= 0) return -1;
    buf[n] = '\0';

    char *endptr;
    *value = strtol(buf, &endptr, 10);
    return 0;
}

/* Get available compression algorithms */
static char* get_available_algorithms(void) {
    static char buf[256];
    int fd = open(COMPRESSOR_PATH, O_RDONLY);
    if (fd < 0) return NULL;

    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);

    if (n <= 0) return NULL;
    buf[n] = '\0';

    /* Remove brackets around current algorithm */
    for (int i = 0; buf[i]; i++) {
        if (buf[i] == '[' || buf[i] == ']') {
            memmove(&buf[i], &buf[i + 1], strlen(&buf[i]));
            i--;
        }
    }
    return buf;
}

/* Check if algorithm is available */
static int is_algorithm_available(const char *algo) {
    char *available = get_available_algorithms();
    if (!available) return 0;

    char *token = strtok(available, " ");
    while (token) {
        if (strcmp(token, algo) == 0) return 1;
        token = strtok(NULL, " ");
    }
    return 0;
}

/* Set compression algorithm */
static int set_compression_algorithm(const char *algo) {
    if (config_dry_run) {
        printf("[DRY RUN] Would set algorithm to: %s\n", algo);
        current_algorithm = algo;
        algorithm_start_time = time(NULL);
        return 1;
    }

    int fd = open(COMPRESSOR_PATH, O_WRONLY);
    if (fd < 0) {
        fprintf(stderr, "Error: Cannot write to %s (need root?)\n", COMPRESSOR_PATH);
        return 0;
    }

    ssize_t n = write(fd, algo, strlen(algo));
    close(fd);

    if (n <= 0) {
        fprintf(stderr, "Error: Failed to set algorithm to %s\n", algo);
        return 0;
    }

    current_algorithm = algo;
    algorithm_start_time = time(NULL);

    /* Print timestamped message */
    time_t now = time(NULL);
    char *timestr = ctime(&now);
    timestr[19] = '\0'; /* Remove newline */
    printf("[%s] Set compression algorithm to: %s\n", timestr, algo);

    return 1;
}

/* Get current compression algorithm */
static const char* get_current_algorithm(void) {
    char *available = get_available_algorithms();
    if (!available) return "unknown";

    /* Find the current algorithm (it's in brackets in the original) */
    int fd = open(COMPRESSOR_PATH, O_RDONLY);
    if (fd < 0) return "unknown";

    char buf[256];
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);

    if (n <= 0) return "unknown";

    /* Extract algorithm with brackets */
    for (int i = 0; i < n - 1; i++) {
        if (buf[i] == '[') {
            int start = i + 1;
            int end = start;
            while (end < n && buf[end] != ']' && buf[end] != ' ') end++;
            buf[end] = '\0';
            return buf + start;
        }
    }
    return "unknown";
}

/* Get compression ratio from zswap stats */
static double get_compression_ratio(void) {
    char pool_path[] = "/sys/kernel/debug/zswap/pool_total_size";
    char pages_path[] = "/sys/kernel/debug/zswap/stored_pages";

    long pool_size, stored_pages;

    if (read_int_file(pool_path, &pool_size) < 0) return 1.0;
    if (read_int_file(pages_path, &stored_pages) < 0) return 1.0;

    if (stored_pages > 0 && pool_size > 0) {
        unsigned long long uncompressed = (unsigned long long)stored_pages * 4096ULL;
        return (double)uncompressed / (double)pool_size;
    }
    return 1.0;
}

/* Get swap count from vmstat */
static long get_swap_count(void) {
    char vmstat_path[] = "/proc/vmstat";
    char buf[MAX_LINE_LEN];
    ssize_t n = read_file(vmstat_path, buf, sizeof(buf));

    if (n < 0) return 0;

    char *line = strtok(buf, "\n");
    while (line) {
        unsigned long val;
        if (sscanf(line, "pswpout %lu", &val) == 1) return (long)val;
        line = strtok(NULL, "\n");
    }
    return 0;
}

/* Get available compressors from /sys */
static int get_available_compressors(char *buf, size_t bufsize) {
    int fd = open(COMPRESSOR_PATH, O_RDONLY);
    if (fd < 0) return -1;

    ssize_t n = read(fd, buf, bufsize - 1);
    close(fd);

    if (n <= 0) return -1;
    buf[n] = '\0';
    return 0;
}

/* Cycle to next algorithm */
static int cycle_algorithm(void) {
    if (!current_algorithm) {
        /* Start with first algorithm */
        if (is_algorithm_available(algorithms[0])) {
            return set_compression_algorithm(algorithms[0]);
        }
        return 0;
    }

    /* Find current algorithm index */
    int current_idx = -1;
    for (int i = 0; i < num_algorithms; i++) {
        if (strcmp(current_algorithm, algorithms[i]) == 0) {
            current_idx = i;
            break;
        }
    }

    if (current_idx < 0) {
        /* Current algorithm not in list, start from first available */
        for (int i = 0; i < num_algorithms; i++) {
            if (is_algorithm_available(algorithms[i])) {
                return set_compression_algorithm(algorithms[i]);
            }
        }
        return 0;
    }

    /* Cycle to next algorithm */
    int next_idx = (current_idx + 1) % num_algorithms;
    if (!is_algorithm_available(algorithms[next_idx])) {
        /* Skip unavailable algorithms */
        for (int i = 1; i < num_algorithms; i++) {
            int try_idx = (current_idx + i) % num_algorithms;
            if (is_algorithm_available(algorithms[try_idx])) {
                return set_compression_algorithm(algorithms[try_idx]);
            }
        }
        return 0;
    }

    return set_compression_algorithm(algorithms[next_idx]);
}

/* Get optimal algorithm based on system metrics */
static const char* get_optimal_algorithm(double cpu_usage, double mem_pressure) {
    if (cpu_usage > 70) {
        /* High CPU usage - use fastest algorithm */
        if (is_algorithm_available("lzo")) return "lzo";
        if (is_algorithm_available("lz4")) return "lz4";
        return "zstd";
    } else if (mem_pressure > 50 && cpu_usage < 50) {
        /* High memory pressure, CPU headroom - use best ratio */
        if (is_algorithm_available("zstd")) return "zstd";
        if (is_algorithm_available("lz4")) return "lz4";
        return "lzo";
    } else {
        /* Balanced - use default */
        if (is_algorithm_available("lz4")) return "lz4";
        if (is_algorithm_available("lzo")) return "lzo";
        return "zstd";
    }
}

/* Check if it's time to cycle */
static int should_cycle(void) {
    time_t now = time(NULL);
    return (now - algorithm_start_time) >= config_cycle_interval;
}

/* Print usage */
static void print_usage(const char *prog) {
    printf("Usage: %s [OPTIONS]\n", prog);
    printf("\nAdaptive Compressor - High Performance Compression Algorithm Manager\n");
    printf("\nOptions:\n");
    printf("  -c, --cycle SECONDS   Cycle interval (default: %d)\n", DEFAULT_CYCLE_INTERVAL);
    printf("  -a, --algo ALGO       Set specific algorithm (lzo, lz4, zstd)\n");
    printf("  -d, --dry-run         Show what would be done without changes\n");
    printf("  -h, --help            Show this help\n");
    printf("\nAlgorithms (fastest to best ratio):\n");
    printf("  lzo   - Fastest, lowest compression ratio\n");
    printf("  lz4   - Balanced speed and ratio\n");
    printf("  zstd  - Best ratio, slower compression\n");
    printf("\nExample:\n");
    printf("  %s -c 300\n", prog);
}

/* Print current state */
static void print_state(double cpu_usage, double mem_pressure) {
    time_t now = time(NULL);
    char *timestr = ctime(&now);
    timestr[19] = '\0';

    double ratio = get_compression_ratio();

    printf("[%s] Algorithm: %s Ratio: %.2fx CPU: %.1f%% Mem: %.1f%%",
           timestr, current_algorithm ? current_algorithm : "unknown",
           ratio, cpu_usage, mem_pressure);

    if (algorithm_start_time > 0) {
        time_t elapsed = now - algorithm_start_time;
        int minutes = elapsed / 60;
        printf(" (elapsed: %dm)", minutes);
    }
    printf("\n");
}

/* Main entry point */
int main(int argc, char *argv[]) {
    int opt;
    int long_index = 0;
    const char *specific_algo = NULL;

    static struct option long_options[] = {
        {"cycle",    required_argument, 0, 'c'},
        {"algo",     required_argument, 0, 'a'},
        {"dry-run",  no_argument,       0, 'd'},
        {"help",     no_argument,       0, 'h'},
        {0, 0, 0, 0}
    };

    while ((opt = getopt_long(argc, argv, "c:a:dh", long_options, &long_index)) != -1) {
        switch (opt) {
            case 'c':
                config_cycle_interval = atoi(optarg);
                break;
            case 'a':
                specific_algo = optarg;
                break;
            case 'd':
                config_dry_run = 1;
                break;
            case 'h':
                print_usage(argv[0]);
                return 0;
            default:
                print_usage(argv[0]);
                return 1;
        }
    }

    printf("=== Adaptive Compressor ===\n");
    printf("Cycle interval: %ds\n", config_cycle_interval);
    printf("Dry run: %s\n", config_dry_run ? "yes" : "no");

    /* Check if compressor path exists */
    if (access(COMPRESSOR_PATH, F_OK) != 0) {
        fprintf(stderr, "Error: Zswap compressor not available. Check kernel and debugfs.\n");
        return 1;
    }

    /* Get available compressors */
    char available[256];
    if (get_available_compressors(available, sizeof(available)) == 0) {
        printf("Available: %s\n", available);
    }

    /* Set specific algorithm if requested */
    if (specific_algo) {
        if (is_algorithm_available(specific_algo)) {
            set_compression_algorithm(specific_algo);
            printf("\n=== Running in manual mode ===\n");
            while (1) {
                sleep(5);
                double cpu = 0.0; /* CPU not measured in manual mode */
                double mem = 0.0;
                print_state(cpu, mem);
            }
        } else {
            fprintf(stderr, "Error: Algorithm '%s' not available\n", specific_algo);
            return 1;
        }
    }

    /* Initialize with first available algorithm */
    for (int i = 0; i < num_algorithms; i++) {
        if (is_algorithm_available(algorithms[i])) {
            set_compression_algorithm(algorithms[i]);
            break;
        }
    }

    printf("\n=== Starting Adaptive Cycle ===\n\n");

    /* Main loop */
    while (1) {
        /* Read system metrics (CPU and memory pressure) */
        double cpu_usage = 0.0, mem_pressure = 0.0;

        /* Read CPU usage from /proc/stat */
        char buf[256];
        int fd = open("/proc/stat", O_RDONLY);
        if (fd >= 0) {
            ssize_t n = read(fd, buf, sizeof(buf) - 1);
            close(fd);
            if (n > 0) {
                /* Simple CPU estimation - use idle percentage */
                unsigned long long user, nice, system, idle, iowait, irq, softirq, steal;
                if (sscanf(buf, "cpu %llu %llu %llu %llu %llu %llu %llu %llu",
                           &user, &nice, &system, &idle, &iowait, &irq, &softirq, &steal) == 8) {
                    unsigned long long total = user + nice + system + idle + iowait + irq + softirq + steal;
                    if (total > 0) {
                        cpu_usage = ((double)(total - idle) / total) * 100.0;
                    }
                }
            }
        }

        /* Read memory pressure from PSI */
        fd = open("/proc/pressure/memory", O_RDONLY);
        if (fd >= 0) {
            ssize_t n = read(fd, buf, sizeof(buf) - 1);
            close(fd);
            if (n > 0) {
                char *line = strtok(buf, "\n");
                while (line) {
                    if (strncmp(line, "some", 4) == 0) {
                        char *token = strtok(line, " =");
                        while (token) {
                            if (strcmp(token, "avg10") == 0) {
                                token = strtok(NULL, " =");
                                if (token) mem_pressure = strtod(token, NULL);
                            }
                            token = strtok(NULL, " =");
                        }
                    }
                    line = strtok(NULL, "\n");
                }
            }
        }

        /* Check if it's time to cycle */
        if (should_cycle()) {
            printf("\n[%s] Cycle interval reached (elapsed: %ds)\n",
                   ctime(&time(NULL)) + 11, config_cycle_interval);
            cycle_algorithm();
        }

        /* Get optimal algorithm based on current load */
        const char *optimal = get_optimal_algorithm(cpu_usage, mem_pressure);
        if (current_algorithm && strcmp(current_algorithm, optimal) != 0) {
            if (is_algorithm_available(optimal)) {
                printf("[%s] Optimal for current load: %s (currently: %s)\n",
                       ctime(&time(NULL)) + 11, optimal, current_algorithm);
                set_compression_algorithm(optimal);
            }
        }

        print_state(cpu_usage, mem_pressure);

        sleep(5);
    }

    return 0;
}
