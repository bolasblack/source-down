// Pause configuration loading boundaries through real watch diagnostics.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static atomic_int paused, loaded;

static void pause_window(const char *root, const char *point) {
    char ready[4096], release[4096];
    snprintf(ready, sizeof ready, "%s/.source-down/%s.ready", root, point);
    snprintf(release, sizeof release, "%s/.source-down/%s.release", root, point);
    int marker = open(ready, O_CREAT | O_WRONLY, 0600);
    if (marker >= 0) close(marker);
    for (int i = 0; i < 1000 && access(release, F_OK); ++i) usleep(10000);
}

ssize_t write(int fd, const void *buffer, size_t size) {
    ssize_t (*original)(int, const void *, size_t) = dlsym(RTLD_NEXT, "write");
    const char *root = getenv("SD_WATCH_CONFIG_ROOT");
    if (root && fd == 2 && memmem(buffer, size, "starting", 8)
        && !atomic_exchange(&paused, 1)) {
        pause_window(root, "config");
    }
    if (root && fd == 2 && getenv("SD_WATCH_CONFIG_AFTER_LOAD")
        && memmem(buffer, size, "not adopting existing pages", 27)
        && !atomic_exchange(&loaded, 1)) {
        pause_window(root, "config.loaded");
    }
    return original(fd, buffer, size);
}
