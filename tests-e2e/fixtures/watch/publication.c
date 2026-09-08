#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

int statx(int fd, const char *path, int flags, unsigned int mask, struct statx *buf) {
    int (*real_statx)(int,const char*,int,unsigned int,struct statx*) = dlsym(RTLD_NEXT,"statx");
    const char *root = getenv("SD_WATCH_PUBLICATION_ROOT");
    const char *mode = getenv("SD_WATCH_PUBLICATION_MODE");
    if (root && mode && path) {
        char first[4096], release[4096];
        snprintf(first, sizeof first, "%s/.source-down/pages/docs/a.md.md", root);
        snprintf(release, sizeof release, "%s/.source-down/fault.release", root);
        const char *target = !strcmp(mode,"delete") ? "/pages/docs/obsolete.md.md" :
                             !strcmp(mode,"index") ? "/search/index.json" : "/pages/docs/z.md.md";
        if (strstr(path, target) && !access(first,F_OK) && access(release,F_OK)) {
            if (!strcmp(mode,"cancel")) raise(SIGINT);
            else { errno=EIO; return -1; }
        }
    }
    return real_statx(fd,path,flags,mask,buf);
}
