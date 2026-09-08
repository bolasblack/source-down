#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Pause the next-round baseline after Idle has sampled the edited input. */
ssize_t read(int fd, void *buffer, size_t size) {
    ssize_t (*real_read)(int, void*, size_t) = dlsym(RTLD_NEXT, "read");
    const char *root = getenv("SD_WATCH_SCAN_ROOT");
    static int reads = 0, held = 0;
    if (root && !held) {
        char arm[4096], descriptor[64], path[4096];
        snprintf(arm, sizeof arm, "%s/.source-down/scan.arm", root);
        snprintf(descriptor, sizeof descriptor, "/proc/self/fd/%d", fd);
        ssize_t length = readlink(descriptor, path, sizeof path - 1);
        if (length > 0) {
            path[length] = 0;
            if (!access(arm, F_OK) && strstr(path, "/docs/index.md") && lseek(fd, 0, SEEK_CUR) == 0 && ++reads == 2) {
                held = 1;
                char ready[4096], release[4096];
                snprintf(ready, sizeof ready, "%s/.source-down/scan.ready", root);
                snprintf(release, sizeof release, "%s/.source-down/scan.release", root);
                FILE *output = fopen(ready, "w");
                if (output) { fputs("baseline read entered", output); fclose(output); }
                for (int i = 0; i < 1000 && access(release, F_OK); i++) usleep(10000);
            }
        }
    }
    return real_read(fd, buffer, size);
}
