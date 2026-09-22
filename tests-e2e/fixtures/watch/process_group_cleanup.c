#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static int denied;

static int defer_reaping(void) {
    const char *mode = getenv("SD_CLEANUP_FAULT_MODE");
    return mode && !strcmp(mode, "exited") && !denied;
}

pid_t waitpid(pid_t pid, int *status, int options) {
    pid_t (*actual)(pid_t, int *, int) = dlsym(RTLD_NEXT, "waitpid");
    if (defer_reaping() && (options & WNOHANG)) return 0;
    return actual(pid, status, options);
}

int waitid(idtype_t type, id_t id, siginfo_t *info, int options) {
    int (*actual)(idtype_t, id_t, siginfo_t *, int) = dlsym(RTLD_NEXT, "waitid");
    if (defer_reaping() && (options & WNOHANG)) {
        memset(info, 0, sizeof *info);
        return 0;
    }
    return actual(type, id, info, options);
}

int kill(pid_t pid, int signal) {
    int (*actual)(pid_t, int) = dlsym(RTLD_NEXT, "kill");
    const char *root = getenv("SD_CLEANUP_FAULT_ROOT");
    const char *mode = getenv("SD_CLEANUP_FAULT_MODE");
    if (root && mode && pid < -1 && signal == SIGKILL &&
        (!denied || !strcmp(mode, "live"))) {
        if (!strcmp(mode, "exited")) {
            siginfo_t child = {0};
            /* Keep the real exited child unreaped, as in Darwin's group filter. */
            if (waitid(P_PID, -pid, &child, WEXITED | WNOWAIT) || child.si_pid != -pid)
                return actual(pid, signal);
        }
        char record[4096], pending[4096];
        snprintf(record, sizeof record, "%s/.source-down/cleanup-denied.pid", root);
        snprintf(pending, sizeof pending, "%s/.source-down/cleanup-denied.tmp", root);
        FILE *output = fopen(pending, "w");
        if (!output || fprintf(output, "%d\n", -pid) < 0 || fclose(output) || rename(pending, record))
            abort();
        denied = 1;
        errno = EPERM;
        return -1;
    }
    return actual(pid, signal);
}
