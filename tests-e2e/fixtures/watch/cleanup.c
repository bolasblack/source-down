#define _GNU_SOURCE
#include <dlfcn.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

/* Hold the actual process-owner cleanup call while the author repairs a query. */
int kill(pid_t pid, int signal) {
    int (*real_kill)(pid_t, int) = dlsym(RTLD_NEXT, "kill");
    static int held = 0;
    const char *root = getenv("SD_WATCH_CLEANUP_ROOT");
    if (root && pid < -1 && signal == SIGKILL && !held) {
        held = 1;
        char ready[4096], release[4096];
        snprintf(ready, sizeof ready, "%s/.source-down/cleanup.ready", root);
        snprintf(release, sizeof release, "%s/.source-down/cleanup.release", root);
        FILE *output = fopen(ready, "w");
        if (output) { fputs("cleanup entered", output); fclose(output); }
        for (int i = 0; i < 1000 && access(release, F_OK); i++) usleep(10000);
    }
    return real_kill(pid, signal);
}
