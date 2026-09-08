//! SPEC-CLI-004, SPEC-PLG-008: publication observes the live session's I/O owner.
#[cfg(target_os = "linux")]
mod common;

#[test]
#[cfg(target_os = "linux")]
fn a_plugin_fault_after_the_first_report_stops_subsequent_publication() {
    if let Some(root) = std::env::var_os("SD_SESSION_PUBLICATION_ROOT") {
        let root = std::path::PathBuf::from(root);
        let mut session = source_down::engine::Session::new(
            &root,
            None,
            None,
            std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)),
        )
        .unwrap();
        let error = session
            .prepare(&["a.rs".into()])
            .unwrap()
            .publish()
            .unwrap_err();
        assert!(error.message.contains("stdout EOF"), "{error}");
        assert!(
            error
                .message
                .contains("completed: .source-down/reports/checker/a.md"),
            "{error}"
        );
        assert!(
            error
                .message
                .contains("stopped at .source-down/reports/checker/b.md"),
            "{error}"
        );
        return;
    }
    let root = tempfile::tempdir().unwrap();
    std::fs::write(
        root.path().join("barrier.c"),
        r#"
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
int statx(int fd, const char *path, int flags, unsigned int mask, struct statx *buf) {
    int (*real_statx)(int,const char*,int,unsigned int,struct statx*) = dlsym(RTLD_NEXT,"statx");
    if (path && strstr(path,"/reports/checker/b.md")) {
        FILE *first=fopen(getenv("SD_FIRST_REPORT"),"r");
        int published=first && fgetc(first)=='#';
        if (first) fclose(first);
        if (published) {
            FILE *pidfile=fopen(getenv("SD_PLUGIN_PID"),"r");
            int pid=0;
            if (!pidfile || fscanf(pidfile,"%d",&pid)!=1 || pid<2) abort();
            fclose(pidfile);
            FILE *release=fopen(getenv("SD_RELEASE_PLUGIN"),"w");
            if (!release) abort();
            fclose(release);
            char proc[64];snprintf(proc,sizeof proc,"/proc/%d",pid);
            struct timespec start,now;clock_gettime(CLOCK_MONOTONIC,&start);
            while (access(proc,F_OK)==0) {
                clock_gettime(CLOCK_MONOTONIC,&now);
                if (now.tv_sec-start.tv_sec>=3) { errno=ETIMEDOUT; return -1; }
                usleep(1000);
            }
        }
    }
    return real_statx(fd,path,flags,mask,buf);
}
"#,
    )
    .unwrap();
    let compiled = std::process::Command::new(std::env::var_os("CC").expect("run through mise"))
        .current_dir(root.path())
        .args(["-shared", "-fPIC", "barrier.c", "-o", "barrier.so", "-ldl"])
        .output()
        .unwrap();
    assert!(
        compiled.status.success(),
        "{}",
        String::from_utf8_lossy(&compiled.stderr)
    );
    std::fs::write(root.path().join("a.rs"), "// page\n").unwrap();
    std::fs::write(
        root.path().join("source-down.toml"),
        "config_version=1\n[plugins.checker]\ncommand=['python','plugin.py']\n",
    )
    .unwrap();
    std::fs::write(root.path().join("plugin.py"), common::plugin(r#"
import os,time
open('pid','w').write(str(os.getpid()))
emit({'type':'result','batch_id':b['batch_id'],'results':[],'append':[],'diagnostics':[],'dependencies':[],
    'reports':{'a':{'markdown':'new A','sources':[]},'b':{'markdown':'new B','sources':[]}}})
while not os.path.exists('release'): time.sleep(0.001)
# Stay alive after closing stdout, so reaping proves the owner has observed the fault and killed us.
os.close(1)
time.sleep(30)
"#)).unwrap();
    for path in [
        ".source-down/pages/a.rs.md",
        ".source-down/reports/checker/a.md",
        ".source-down/reports/checker/b.md",
    ] {
        std::fs::create_dir_all(root.path().join(path).parent().unwrap()).unwrap();
        std::fs::write(root.path().join(path), "old bytes").unwrap();
    }
    let output = std::process::Command::new(std::env::current_exe().unwrap())
        .args([
            "--exact",
            "a_plugin_fault_after_the_first_report_stops_subsequent_publication",
            "--nocapture",
        ])
        .env("SD_SESSION_PUBLICATION_ROOT", root.path())
        .env("LD_PRELOAD", root.path().join("barrier.so"))
        .env(
            "SD_FIRST_REPORT",
            root.path().join(".source-down/reports/checker/a.md"),
        )
        .env("SD_PLUGIN_PID", root.path().join("pid"))
        .env("SD_RELEASE_PLUGIN", root.path().join("release"))
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(
        std::fs::read_to_string(root.path().join(".source-down/reports/checker/a.md"))
            .unwrap()
            .contains("new A")
    );
    for path in [
        ".source-down/reports/checker/b.md",
        ".source-down/pages/a.rs.md",
    ] {
        assert_eq!(
            std::fs::read_to_string(root.path().join(path)).unwrap(),
            "old bytes"
        );
    }
}
