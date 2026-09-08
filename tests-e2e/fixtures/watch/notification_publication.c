#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/inotify.h>
#include <sys/stat.h>
#include <unistd.h>

static atomic_int state;

/* Feed one controlled loss/error through the actual notify reader. */
ssize_t read(int fd, void *buffer, size_t size) {
    ssize_t (*real_read)(int, void*, size_t) = dlsym(RTLD_NEXT, "read");
    const char *root = getenv("SD_WATCH_NOTIFY_ROOT");
    const char *arm = getenv("SD_WATCH_NOTIFY_ARM");
    if (arm && !access(arm, F_OK)) {
        int expected = 0;
        atomic_compare_exchange_strong(&state, &expected, 1);
    }
    if (root && atomic_load(&state)) {
        char descriptor[64], path[64];
        snprintf(descriptor, sizeof descriptor, "/proc/self/fd/%d", fd);
        ssize_t length = readlink(descriptor, path, sizeof path - 1);
        if (length > 0) {
            path[length] = 0;
            if (!strcmp(path, "anon_inode:inotify")) {
                if (atomic_load(&state) == 1) {
                    atomic_store(&state, 2);
                    if (!strcmp(getenv("SD_WATCH_NOTIFY_MODE"), "rescan")) {
                        struct inotify_event event = { .wd = -1, .mask = IN_Q_OVERFLOW };
                        if (size < sizeof event) { errno = EINVAL; return -1; }
                        memcpy(buffer, &event, sizeof event);
                        return sizeof event;
                    }
                    errno = EIO;
                    return -1;
                }
                if (atomic_load(&state) == 2) {
                    /* The preceding read's event handler has returned. */
                    char delivered[4096];
                    snprintf(delivered, sizeof delivered, "%s/.source-down/notify.delivered", root);
                    FILE *output = fopen(delivered, "w");
                    if (output) { fputs("handler completed", output); fclose(output); }
                    atomic_store(&state, 3);
                }
            }
        }
    }
    return real_read(fd, buffer, size);
}

int statx(int fd, const char *path, int flags, unsigned int mask, struct statx *buffer) {
    int (*real_statx)(int,const char*,int,unsigned int,struct statx*) = dlsym(RTLD_NEXT,"statx");
    const char *root = getenv("SD_WATCH_NOTIFY_ROOT");
    if (root && !atomic_load(&state) && path && strstr(path, "/pages/docs/z.md.md")) {
        char first[4096], wake[4096];
        snprintf(first, sizeof first, "%s/.source-down/pages/docs/a.md.md", root);
        if (!access(first, F_OK)) {
            atomic_store(&state, 1);
            snprintf(wake, sizeof wake, "%s/notification-wakeup", root);
            FILE *output = fopen(wake, "w");
            if (output) { fputs("wake native reader", output); fclose(output); }
            for (int i = 0; i < 1000 && atomic_load(&state) != 3; i++) usleep(10000);
        }
    }
    return real_statx(fd, path, flags, mask, buffer);
}
