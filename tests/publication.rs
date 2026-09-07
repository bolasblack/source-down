#[test]
#[cfg(target_os = "linux")]
fn a_failed_close_does_not_publish_the_temporary_output() {
    // SPEC-CLI-004: a real close(2) failure must preserve the old file.
    let dir = tempfile::tempdir().unwrap();
    let shim = r#"
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
int close(int fd) {
    int (*real_close)(int) = dlsym(RTLD_NEXT, "close");
    char name[64], path[4096];
    snprintf(name, sizeof name, "/proc/self/fd/%d", fd);
    ssize_t length = readlink(name, path, sizeof path-1);
    if (length >= 0) path[length] = 0; else path[0] = 0;
    int result = real_close(fd);
    if (strstr(path, "/.tmp") != NULL) {
        fputs("injected output close EIO\n", stderr);
        errno = EIO;
        return -1;
    }
    return result;
}

"#;
    std::fs::write(dir.path().join("close.c"), shim).unwrap();
    let compiled =
        std::process::Command::new(std::env::var_os("CC").expect("run tests through mise"))
            .current_dir(dir.path())
            .args(["-shared", "-fPIC", "close.c", "-o", "close.so", "-ldl"])
            .output()
            .unwrap();
    assert!(
        compiled.status.success(),
        "{}",
        String::from_utf8_lossy(&compiled.stderr)
    );
    std::fs::write(dir.path().join("a.rs"), "// new content\n").unwrap();
    std::fs::create_dir_all(dir.path().join(".source-down/pages")).unwrap();
    std::fs::write(
        dir.path().join(".source-down/pages/a.rs.md"),
        "old content\n",
    )
    .unwrap();
    let output = std::process::Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "a.rs", "--root"])
        .arg(dir.path())
        .env("LD_PRELOAD", dir.path().join("close.so"))
        .output()
        .unwrap();
    assert!(String::from_utf8_lossy(&output.stderr).contains("injected output close EIO"));
    assert_eq!(
        output.status.code(),
        Some(1),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(output.stdout.is_empty());
    assert_eq!(
        std::fs::read(dir.path().join(".source-down/pages/a.rs.md")).unwrap(),
        b"old content\n"
    );
    assert!(
        !std::fs::read_dir(dir.path().join(".source-down/pages"))
            .unwrap()
            .any(|entry| {
                entry
                    .unwrap()
                    .file_name()
                    .to_string_lossy()
                    .starts_with(".tmp")
            })
    );
}

#[test]
#[cfg(target_os = "linux")]
fn partial_publication_reports_completed_and_stopped_paths_for_io_and_sigint() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(
        dir.path().join("fault.c"),
        r#"
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
int statx(int fd, const char *path, int flags, unsigned int mask, struct statx *buf) {
    int (*real_statx)(int,const char*,int,unsigned int,struct statx*) = dlsym(RTLD_NEXT,"statx");
    if (strstr(path,"/pages/b.rs.md")) {
        FILE *first = fopen(getenv("SD_TEST_FIRST_PATH"),"r");
        int published = first && fgetc(first)=='#';
        if (first) fclose(first);
        if (published) {
            fputs("injected failure after first page\n",stderr);
            if (!strcmp(getenv("SD_TEST_FAULT_MODE"),"cancel")) raise(SIGINT);
            else { errno=EIO; return -1; }
        }
    }
    return real_statx(fd,path,flags,mask,buf);
}
"#,
    )
    .unwrap();
    let compiled =
        std::process::Command::new(std::env::var_os("CC").expect("run tests through mise"))
            .current_dir(dir.path())
            .args(["-shared", "-fPIC", "fault.c", "-o", "fault.so", "-ldl"])
            .output()
            .unwrap();
    assert!(
        compiled.status.success(),
        "{}",
        String::from_utf8_lossy(&compiled.stderr)
    );
    std::fs::create_dir_all(dir.path().join(".source-down/pages")).unwrap();
    for mode in ["io", "cancel"] {
        for name in ["a", "b", "c"] {
            std::fs::write(
                dir.path().join(format!("{name}.rs")),
                format!("fn {name}() {{}}\n"),
            )
            .unwrap();
            std::fs::write(
                dir.path().join(format!(".source-down/pages/{name}.rs.md")),
                "old bytes",
            )
            .unwrap();
        }
        let output = std::process::Command::new(env!("CARGO_BIN_EXE_source-down"))
            .args(["render", "a.rs", "b.rs", "c.rs", "--root"])
            .arg(dir.path())
            .env("LD_PRELOAD", dir.path().join("fault.so"))
            .env(
                "SD_TEST_FIRST_PATH",
                dir.path().join(".source-down/pages/a.rs.md"),
            )
            .env("SD_TEST_FAULT_MODE", mode)
            .output()
            .unwrap();
        let diagnostic = String::from_utf8(output.stderr).unwrap();
        assert!(
            diagnostic.contains("injected failure after first page"),
            "{diagnostic}"
        );
        assert_eq!(
            output.status.code(),
            Some(if mode == "cancel" { 130 } else { 1 }),
            "{diagnostic}"
        );
        assert!(
            diagnostic.contains("completed: .source-down/pages/a.rs.md"),
            "{diagnostic}"
        );
        assert!(
            diagnostic.contains("stopped at .source-down/pages/b.rs.md"),
            "{diagnostic}"
        );
        assert!(
            std::fs::read_to_string(dir.path().join(".source-down/pages/a.rs.md"))
                .unwrap()
                .starts_with('#')
        );
        for name in ["b", "c"] {
            assert_eq!(
                std::fs::read_to_string(
                    dir.path().join(format!(".source-down/pages/{name}.rs.md"))
                )
                .unwrap(),
                "old bytes"
            );
        }
        assert!(
            !std::fs::read_dir(dir.path().join(".source-down/pages"))
                .unwrap()
                .any(|e| e.unwrap().file_name().to_string_lossy().starts_with(".tmp"))
        );
    }
}
