#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <ctype.h>

#define DIV_ROUND_UP(num, den) (num + den - 1) / den
const long k = 1024;

long parse_human_readable(const char *s) {
    char *tail = NULL;
    double coefficient = strtod(s, &tail); // number preceding K/M/G

    long power = 1; // full numerical representation of K/M/G
    if(tail) {
        switch(toupper(*tail)) { // fall through cause its cool
            case 'G': power *= k;
            case 'M': power *= k;
            case 'K': power *= k;
        }
    }

    return coefficient * power;
}



// linked list to keep pointers within memory allocation numbers we are counting, don't need another array
struct node {
    struct node *next;
    // block size should exceed the size of this struct, we will fill this space with random data
};

int main(int argc, char **argv) {
    srand(time(NULL));

    // Parse limit in bytes from user
    double limit = 1 * k*k*k; // Default to 1 GiB
    if(argc > 1) limit = parse_human_readable(argv[1]);


    // Calculate and show configuration to user
    long block_size = 4 * k*k;
    int num_blocks = DIV_ROUND_UP(limit, block_size);
    printf("Limit: %lG, Block size: %lG, Num blocks: %G\n",
            (double)limit, (double)block_size, (double)num_blocks);
    getchar(); // wait for user to press a key
    

    // Allocate the blocks, fill with random numbers
    struct node *head = malloc(sizeof(struct node)), *cur = head;
    clock_t start = clock();
    for(int i = 1; i <= num_blocks; i++) {
        cur->next = malloc(block_size);
        cur = cur->next;

        char *start = (char*)&(cur->next); // Cast to char*(1B) then add block_size to jump just past malloc
        char *unallocated = (char*)(&(cur->next)) + block_size;
        for(char *byte = start; byte < unallocated; byte++)
            *byte = rand() * 256 / RAND_MAX;


        printf("Allocated block %d, Total usage: %lG\n", i, (double)i * block_size);
    }

    
    // Calculate execution time and wait for user input before freeing
    clock_t end = clock();
    printf("Finished in %.2lf minutes\n", (double)(end - start) / CLOCKS_PER_SEC / 60);
    getchar();
    return 0;
}
