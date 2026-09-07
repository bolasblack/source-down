/* Minimal wait4 launcher: measure the CLI without Python's inherited RSS floor. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <errno.h>

int main(int argc, char **argv) {
    if (argc < 3) return 2;
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    pid_t child = fork();
    if (child < 0) { perror("fork"); return 1; }
    if (child == 0) {
        execvp(argv[2], argv + 2);
        perror("execvp");
        _exit(127);
    }
    int status;
    struct rusage usage;
    while (wait4(child, &status, 0, &usage) < 0) {
        if (errno != EINTR) { perror("wait4"); return 1; }
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    FILE *output = fopen(argv[1], "w");
    if (!output) { perror("metrics"); return 1; }
    fprintf(output, "{\"wall_seconds\":%.9f,\"user_seconds\":%.6f,\"system_seconds\":%.6f,\"max_rss_kib\":%ld,\"raw_wait4_status\":%d,\"minor_faults\":%ld,\"major_faults\":%ld}\n",
        end.tv_sec - start.tv_sec + (end.tv_nsec - start.tv_nsec) / 1e9,
        usage.ru_utime.tv_sec + usage.ru_utime.tv_usec / 1e6,
        usage.ru_stime.tv_sec + usage.ru_stime.tv_usec / 1e6,
        usage.ru_maxrss, status, usage.ru_minflt, usage.ru_majflt);
    if (fclose(output) != 0) { perror("close metrics"); return 1; }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}
