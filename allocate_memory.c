#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <ctype.h> // toupper()

#define DIV_ROUND_UP(num, den) (num + den - 1) / den


long parse_human_readable(const char *s) {
    char *tail = NULL;
    double coefficient = strtod(s, &tail); // number preceding K/M/G

    long power = 1; // full numerical representation of K/M/G
    if(tail) {
        switch(toupper(*tail)) { // fall through cause its cool
            case 'G': power <<= 10; // (<<= 10) === (*= 2^10) === (*= 1024)
            case 'M': power <<= 10;
            case 'K': power <<= 10;
        }
    }

    return coefficient * power;
}


// random alloc: call malloc with block_size, then populate with random data
void* ralloc(size_t block_size) {
    char *out = malloc(block_size); // char* for 1 byte blocks
    for(size_t i = 0; i < block_size; i++)
        out[i] = rand() * 1<<8 / RAND_MAX; // fill with random 8-bit values

    return out;
}


// linked list to keep pointers within memory allocation numbers we are counting, don't need another array
struct node {
    struct node *next;
    // block size should exceed the size of this struct, we will fill this space with random data
};


int main(int argc, char **argv) {
    srand(time(NULL));

    // parse command line inputs
    long limit =      1 * 1<<30;    // default to 1 GiB
    long block_size = 4 * 1<<20;    // default to 4 KiB
    if(argc > 1) limit = parse_human_readable(argv[1]);
    if(argc > 2) block_size = parse_human_readable(argv[2]);

    // calculate num_blocks and display configuration to user
    int num_blocks = DIV_ROUND_UP(limit, block_size);
    printf("Limit: %.3lG, Block size: %.3lG, Num blocks: %.3G\n",
            (double)limit, (double)block_size, (double)num_blocks);
    getchar(); // wait for user to press a key
    

    // allocate the blocks, fill with random numbers

    struct node *head = malloc(sizeof(struct node)); // head only stores a pointer, no data, this uses less than block_size
    struct node *cur = head;

    clock_t start = clock();
    for(int i = 1; i <= num_blocks; i++) {
        cur = cur->next = ralloc(block_size);
        printf("Allocated block %d, Total usage: %.3lG\n", i, (double)i * block_size);
    }


    // calculate and display execution time
    int seconds = (double)(clock() - start) / CLOCKS_PER_SEC;
    printf("Finished in %02d:%02d\n", seconds / 60, seconds % 60);
    getchar(); // wait for user input before freeing

    // free memory
    cur->next = NULL;
    cur = head;
    while(cur) {
        struct node *next = cur->next;
        free(cur);
        cur = next;
    }

    return 0;
}
