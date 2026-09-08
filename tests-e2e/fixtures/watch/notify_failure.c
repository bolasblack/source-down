#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

/* A real backend syscall failure; the CLI has no fault-injection options. */
int inotify_init1(int flags) {
    const char *record = getenv("SD_WATCH_NOTIFY_FAILURE_RECORD");
    if (record) {
        int output = open(record, O_WRONLY | O_CREAT | O_APPEND, 0600);
        if (output >= 0) { write(output, "init\n", 5); close(output); }
        const char *release = getenv("SD_WATCH_NOTIFY_RELEASE");
        if (release) {
            for (int i = 0; i < 1000 && access(release, F_OK); i++) usleep(10000);
        }
        errno = EMFILE;
        return -1;
    }
    int (*real_init)(int) = dlsym(RTLD_NEXT, "inotify_init1");
    return real_init(flags);
}
