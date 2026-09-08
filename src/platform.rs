//! Operating-system resources behind the shared code and native test fixtures.
//! Only this module selects native implementations; its callers never handle OS resources.
use std::fs::{File, Metadata};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus};
use std::sync::{Arc, atomic::AtomicBool};

pub(crate) use native::{
    Output, close, file_identity, file_kind, file_permissions, open_file_identity, replace_file,
    wait,
};
pub use native::{symlink_dir, symlink_file};

/// Process lifetime as observed by the host, independently of protocol completion.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProcessState {
    Running,
    /// Linux can distinguish an exited process awaiting its parent's wait.
    Zombie,
    Exited,
}

/// Observe a positive PID, retaining lookup errors and observable zombie state.
pub fn process_state(pid: i32) -> io::Result<ProcessState> {
    if pid <= 0 {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid PID"));
    }
    native::process_state(pid)
}

/// Terminate an owned tree by its root PID. On Unix the root must lead its own
/// process group; on Windows taskkill requires the root to still exist.
/// This does not reap children; the spawning owner retains that responsibility.
pub fn terminate_process_tree(root_pid: i32) -> io::Result<()> {
    if root_pid <= 1 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid root PID",
        ));
    }
    native::terminate_process_tree(root_pid)
}

/// Connect the CLI's shared cancellation flag to the host's interrupt mechanism.
pub fn register_cancellation(cancelled: Arc<AtomicBool>) -> io::Result<()> {
    native::register_cancellation(cancelled)
}

pub(crate) fn path_text(path: &Path) -> Option<String> {
    path.to_str()
        .map(|text| text.replace(std::path::MAIN_SEPARATOR, "/"))
}

pub(crate) fn program_path(root: &Path, program: &str) -> PathBuf {
    if program.chars().any(std::path::is_separator) {
        root.join(program)
    } else {
        program.into()
    }
}

pub(crate) fn encoded_path(path: &Path) -> String {
    use std::fmt::Write;
    let mut result = String::new();
    for byte in native::path_bytes(path) {
        if byte.is_ascii_alphanumeric() || b"/.-_~".contains(&byte) {
            result.push(byte as char);
        } else {
            write!(result, "%{byte:02X}").expect("writing a String");
        }
    }
    result
}

/// Own a process scope and nonblocking pipes, including cleanup during failed setup.
pub(crate) struct Child {
    scope: native::Process,
    stdin: Option<native::Input>,
    stdout: native::Stdout,
    stderr: native::Stderr,
}
impl Child {
    pub(crate) fn spawn(command: &mut Command) -> io::Result<Self> {
        let mut scope = native::Process::spawn(command)?;
        let (stdin, stdout, stderr) = native::pipes(&mut scope)?;
        Ok(Self {
            scope,
            stdin: Some(stdin),
            stdout,
            stderr,
        })
    }
    pub(crate) fn write_stdin(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.stdin
            .as_mut()
            .ok_or(io::ErrorKind::BrokenPipe)?
            .write(bytes)
    }
    pub(crate) fn read_stdout(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
        self.stdout.read(bytes)
    }
    pub(crate) fn read_stderr(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
        self.stderr.read(bytes)
    }
    pub(crate) fn drain_stderr(&mut self, consume: impl FnMut(&[u8])) {
        native::drain_stderr(&mut self.stderr, consume);
    }
    pub(crate) fn close_stdin(&mut self) {
        self.stdin.take();
    }
    pub(crate) fn try_wait(&mut self) -> io::Result<Option<ExitStatus>> {
        self.scope.child.try_wait()
    }
    pub(crate) fn stop(&mut self) -> io::Result<()> {
        self.scope.stop()
    }
    pub(crate) fn complete(&mut self) {
        self.scope.complete();
    }
}

#[cfg_attr(windows, allow(dead_code))]
pub(crate) struct Interest<'a> {
    pub child: &'a Child,
    pub stdout: bool,
    pub stderr: bool,
    pub stdin: bool,
}

#[cfg(unix)]
mod native {
    use super::*;
    pub(crate) use std::fs::rename as replace_file;
    pub use std::os::unix::fs::{symlink as symlink_dir, symlink as symlink_file};
    use std::os::{
        fd::{AsRawFd, IntoRawFd},
        unix::{ffi::OsStrExt, fs::MetadataExt, process::CommandExt},
    };
    use std::sync::atomic::Ordering;
    use std::time::Duration;
    pub(super) type Input = std::process::ChildStdin;
    pub(super) type Stdout = std::process::ChildStdout;
    pub(super) type Stderr = std::process::ChildStderr;

    #[cfg(target_os = "linux")]
    pub(super) fn process_state(pid: i32) -> io::Result<ProcessState> {
        match std::fs::read_to_string(format!("/proc/{pid}/stat")) {
            Ok(stat) => match stat
                .rsplit_once(") ")
                .and_then(|(_, tail)| tail.chars().next())
            {
                Some('Z') => Ok(ProcessState::Zombie),
                // A reaped process can still expose its dead proc entry briefly.
                Some('X' | 'x') => Ok(ProcessState::Exited),
                Some(_) => Ok(ProcessState::Running),
                None => Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "missing process state",
                )),
            },
            // A process can exit between opening its proc entry and reading it.
            Err(error)
                if error.kind() == io::ErrorKind::NotFound
                    || error.raw_os_error() == Some(libc::ESRCH) =>
            {
                Ok(ProcessState::Exited)
            }
            Err(error) => Err(error),
        }
    }

    #[cfg(not(target_os = "linux"))]
    pub(super) fn process_state(pid: i32) -> io::Result<ProcessState> {
        if unsafe { libc::kill(pid, 0) } == 0 {
            return Ok(ProcessState::Running);
        }
        let error = io::Error::last_os_error();
        if error.raw_os_error() == Some(libc::ESRCH) {
            Ok(ProcessState::Exited)
        } else {
            Err(error)
        }
    }

    pub(super) fn terminate_process_tree(root_pid: i32) -> io::Result<()> {
        if unsafe { libc::kill(-root_pid, libc::SIGKILL) } < 0 {
            let error = io::Error::last_os_error();
            if error.raw_os_error() != Some(libc::ESRCH) {
                return Err(error);
            }
        }
        Ok(())
    }

    pub(super) fn path_bytes(path: &Path) -> Vec<u8> {
        path.as_os_str().as_bytes().to_vec()
    }
    pub(crate) fn file_identity(path: &Path) -> io::Result<(u64, u64)> {
        let metadata = std::fs::metadata(path)?;
        Ok((metadata.dev(), metadata.ino()))
    }
    pub(crate) fn open_file_identity(file: &File) -> io::Result<(u64, u64)> {
        let metadata = file.metadata()?;
        Ok((metadata.dev(), metadata.ino()))
    }
    pub(crate) fn file_kind(metadata: &Metadata) -> u32 {
        // S_IFMT is u16 on macOS and u32 on Linux.
        #[allow(clippy::unnecessary_cast)]
        let mask = libc::S_IFMT as u32;
        metadata.mode() & mask
    }
    pub(crate) fn file_permissions(metadata: &Metadata) -> u32 {
        metadata.mode() & 0o7777
    }
    pub(crate) fn close(file: File) -> io::Result<()> {
        // Transfer sole ownership; retrying close could close an unrelated, reused descriptor.
        if unsafe { libc::close(file.into_raw_fd()) } == 0 {
            Ok(())
        } else {
            Err(io::Error::last_os_error())
        }
    }
    pub(super) fn register_cancellation(cancelled: Arc<AtomicBool>) -> io::Result<()> {
        signal_hook::flag::register(signal_hook::consts::SIGINT, cancelled).map(|_| ())
    }
    pub(super) struct Process {
        pub child: std::process::Child,
        armed: bool,
    }
    impl Process {
        pub(super) fn spawn(command: &mut Command) -> io::Result<Self> {
            Ok(Self {
                child: command.process_group(0).spawn()?,
                armed: true,
            })
        }
        pub(super) fn complete(&mut self) {
            self.armed = false;
        }
        pub(super) fn stop(&mut self) -> io::Result<()> {
            if !self.armed {
                return Ok(());
            }
            // The group remains ours after its leader exits, including inherited pipe holders.
            let stopped = terminate_process_tree(self.child.id() as i32);
            // Reap an already exited child even when signalling its group fails.
            // A failed signal must not make waiting for a live child unbounded.
            self.child.try_wait()?;
            stopped?;
            self.child.wait()?;
            self.armed = false;
            Ok(())
        }
    }
    impl Drop for Process {
        fn drop(&mut self) {
            let _ = self.stop();
        }
    }

    fn nonblocking(pipe: &impl AsRawFd) -> io::Result<()> {
        // fcntl operates on a live descriptor owned by the guarded child.
        let flags = unsafe { libc::fcntl(pipe.as_raw_fd(), libc::F_GETFL) };
        if flags < 0
            || unsafe { libc::fcntl(pipe.as_raw_fd(), libc::F_SETFL, flags | libc::O_NONBLOCK) } < 0
        {
            Err(io::Error::last_os_error())
        } else {
            Ok(())
        }
    }
    pub(super) fn pipes(scope: &mut Process) -> io::Result<(Input, Stdout, Stderr)> {
        let input = scope
            .child
            .stdin
            .take()
            .ok_or_else(|| io::Error::other("missing stdin pipe"))?;
        let output = scope
            .child
            .stdout
            .take()
            .ok_or_else(|| io::Error::other("missing stdout pipe"))?;
        let error = scope
            .child
            .stderr
            .take()
            .ok_or_else(|| io::Error::other("missing stderr pipe"))?;
        nonblocking(&input)?;
        nonblocking(&output)?;
        nonblocking(&error)?;
        Ok((input, output, error))
    }
    pub(super) fn drain_stderr(stderr: &mut Stderr, mut consume: impl FnMut(&[u8])) {
        let mut bytes = [0; 65536];
        while let Ok(n @ 1..) = stderr.read(&mut bytes) {
            consume(&bytes[..n]);
        }
    }
    pub(crate) fn wait(interests: &[Interest<'_>], timeout: Duration) -> io::Result<()> {
        let mut polls = Vec::new();
        let mut add = |fd, events| {
            polls.push(libc::pollfd {
                fd,
                events,
                revents: 0,
            })
        };
        for interest in interests {
            if interest.stdout {
                add(interest.child.stdout.as_raw_fd(), libc::POLLIN);
            }
            if interest.stderr {
                add(interest.child.stderr.as_raw_fd(), libc::POLLIN);
            }
            if interest.stdin
                && let Some(input) = &interest.child.stdin
            {
                add(input.as_raw_fd(), libc::POLLOUT);
            }
        }
        // The driver owns every descriptor. Bounded waits also observe commands, exits and cancellation.
        let result = unsafe {
            libc::poll(
                polls.as_mut_ptr(),
                polls.len() as libc::nfds_t,
                timeout.as_millis().min(i32::MAX as u128) as i32,
            )
        };
        if result < 0 && io::Error::last_os_error().kind() != io::ErrorKind::Interrupted {
            Err(io::Error::last_os_error())
        } else {
            Ok(())
        }
    }
    pub(crate) struct Output<'a> {
        _lock: std::io::StdoutLock<'static>,
        flags: i32,
        cancelled: &'a AtomicBool,
    }
    impl<'a> Output<'a> {
        pub(crate) fn new(cancelled: &'a AtomicBool) -> std::io::Result<Self> {
            let lock = std::io::stdout().lock();
            let flags = unsafe { libc::fcntl(libc::STDOUT_FILENO, libc::F_GETFL) };
            if flags < 0
                || unsafe {
                    libc::fcntl(libc::STDOUT_FILENO, libc::F_SETFL, flags | libc::O_NONBLOCK)
                } < 0
            {
                return Err(std::io::Error::last_os_error());
            }
            Ok(Self {
                _lock: lock,
                flags,
                cancelled,
            })
        }
    }
    impl std::io::Write for Output<'_> {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            loop {
                if self.cancelled.load(Ordering::SeqCst) {
                    return Err(std::io::Error::other("cancelled"));
                }
                let written =
                    unsafe { libc::write(libc::STDOUT_FILENO, bytes.as_ptr().cast(), bytes.len()) };
                if written >= 0 {
                    return Ok(written as usize);
                }
                let error = std::io::Error::last_os_error();
                match error.kind() {
                    std::io::ErrorKind::Interrupted => continue,
                    std::io::ErrorKind::WouldBlock => {
                        let mut poll = libc::pollfd {
                            fd: libc::STDOUT_FILENO,
                            events: libc::POLLOUT,
                            revents: 0,
                        };
                        if unsafe { libc::poll(&mut poll, 1, 50) } < 0
                            && std::io::Error::last_os_error().kind()
                                != std::io::ErrorKind::Interrupted
                        {
                            return Err(std::io::Error::last_os_error());
                        }
                    }
                    _ => return Err(error),
                }
            }
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    impl Drop for Output<'_> {
        fn drop(&mut self) {
            unsafe {
                libc::fcntl(libc::STDOUT_FILENO, libc::F_SETFL, self.flags);
            }
        }
    }
}

#[cfg(windows)]
mod native {
    use super::{File, Metadata, Path, PathBuf, ProcessState};
    use std::io::{self, Read, Write};
    use std::os::windows::{
        io::{AsRawHandle, FromRawHandle, OwnedHandle},
        process::CommandExt,
    };
    use std::process::{Child, Command};
    use std::sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
        mpsc,
    };
    use std::thread::{self, JoinHandle};
    use std::time::Duration;
    use windows_sys::Win32::{
        Foundation::*,
        System::{Diagnostics::ToolHelp::*, IO::CancelSynchronousIo, JobObjects::*, Threading::*},
    };

    // Windows stores relative symlink targets verbatim; only native separators resolve.
    pub fn symlink_file(original: impl AsRef<Path>, link: impl AsRef<Path>) -> io::Result<()> {
        std::os::windows::fs::symlink_file(
            original.as_ref().components().collect::<PathBuf>(),
            link,
        )
    }

    pub fn symlink_dir(original: impl AsRef<Path>, link: impl AsRef<Path>) -> io::Result<()> {
        std::os::windows::fs::symlink_dir(original.as_ref().components().collect::<PathBuf>(), link)
    }

    pub(crate) fn replace_file(temporary: &Path, target: &Path) -> io::Result<()> {
        use std::os::windows::ffi::OsStrExt;
        use windows_sys::Win32::Storage::FileSystem::{FILE_ATTRIBUTE_NORMAL, SetFileAttributesW};
        let path: Vec<_> = temporary.as_os_str().encode_wide().chain(Some(0)).collect();
        // Persistent outputs must not retain the temporary-file cache attribute.
        if unsafe { SetFileAttributesW(path.as_ptr(), FILE_ATTRIBUTE_NORMAL) } == 0 {
            return Err(io::Error::last_os_error());
        }
        // Rust's native rename supports readers that permit replacement sharing.
        std::fs::rename(temporary, target)
    }

    fn owned(handle: HANDLE) -> io::Result<OwnedHandle> {
        if handle.is_null() || handle == INVALID_HANDLE_VALUE {
            Err(io::Error::last_os_error())
        } else {
            // The creation/open API transfers one handle, which this owner closes exactly once.
            Ok(unsafe { OwnedHandle::from_raw_handle(handle) })
        }
    }

    pub(super) fn process_state(pid: i32) -> io::Result<ProcessState> {
        let process = unsafe { OpenProcess(PROCESS_SYNCHRONIZE, 0, pid as u32) };
        if process.is_null() {
            let error = io::Error::last_os_error();
            return if error.raw_os_error() == Some(ERROR_INVALID_PARAMETER as i32) {
                Ok(ProcessState::Exited)
            } else {
                Err(error)
            };
        }
        let process = owned(process)?;
        match unsafe { WaitForSingleObject(process.as_raw_handle(), 0) } {
            WAIT_TIMEOUT => Ok(ProcessState::Running),
            WAIT_OBJECT_0 => Ok(ProcessState::Exited),
            _ => Err(io::Error::last_os_error()),
        }
    }

    pub(super) fn terminate_process_tree(root_pid: i32) -> io::Result<()> {
        let status = Command::new("taskkill")
            .args(["/F", "/T", "/PID", &root_pid.to_string()])
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()?;
        if status.success() {
            Ok(())
        } else {
            Err(io::Error::other(format!("taskkill failed: {status}")))
        }
    }

    pub(crate) struct Process {
        pub(super) child: Child,
        armed: bool,
        job: OwnedHandle,
    }
    impl Process {
        pub(crate) fn spawn(command: &mut Command) -> io::Result<Self> {
            let job = owned(unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) })?;
            let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if unsafe {
                SetInformationJobObject(
                    job.as_raw_handle(),
                    JobObjectExtendedLimitInformation,
                    (&limits as *const JOBOBJECT_EXTENDED_LIMIT_INFORMATION).cast(),
                    std::mem::size_of_val(&limits) as u32,
                )
            } == 0
            {
                return Err(io::Error::last_os_error());
            }
            let child = command.creation_flags(CREATE_SUSPENDED).spawn()?;
            // Establish cleanup before assignment and resume: a setup failure must not leak a suspended child.
            let scope = Self {
                child,
                job,
                armed: true,
            };
            if unsafe {
                AssignProcessToJobObject(scope.job.as_raw_handle(), scope.child.as_raw_handle())
            } == 0
            {
                return Err(io::Error::last_os_error());
            }
            // std::process owns command quoting and inherited handles. Its Child does not retain the primary
            // thread handle, so locate that still-suspended thread before any plugin code can run.
            let snapshot = owned(unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0) })?;
            let mut entry = THREADENTRY32 {
                dwSize: std::mem::size_of::<THREADENTRY32>() as u32,
                ..Default::default()
            };
            let mut found = unsafe { Thread32First(snapshot.as_raw_handle(), &mut entry) };
            while found != 0 {
                if entry.th32OwnerProcessID == scope.child.id() {
                    let primary =
                        owned(unsafe { OpenThread(THREAD_SUSPEND_RESUME, 0, entry.th32ThreadID) })?;
                    if unsafe { ResumeThread(primary.as_raw_handle()) } == u32::MAX {
                        return Err(io::Error::last_os_error());
                    }
                    return Ok(scope);
                }
                entry.dwSize = std::mem::size_of::<THREADENTRY32>() as u32;
                found = unsafe { Thread32Next(snapshot.as_raw_handle(), &mut entry) };
            }
            Err(io::Error::other(
                "suspended plugin primary thread was not found",
            ))
        }

        pub(super) fn complete(&mut self) {
            self.armed = false;
        }
        pub(super) fn stop(&mut self) -> io::Result<()> {
            if !self.armed {
                return Ok(());
            }
            let job_result = if unsafe { TerminateJobObject(self.job.as_raw_handle(), 1) } == 0 {
                Err(io::Error::last_os_error())
            } else {
                Ok(())
            };
            // Also covers assignment failure while the child is still suspended.
            let kill_result = self.child.kill();
            let wait_result = self.child.wait();
            if wait_result.is_ok() {
                self.armed = false;
            }
            job_result?;
            wait_result?;
            // kill can race a completed child; a successful wait proves it has stopped.
            let _ = kill_result;
            Ok(())
        }
    }
    impl Drop for Process {
        fn drop(&mut self) {
            let _ = self.stop();
        }
    }

    struct IoThread {
        join: Option<JoinHandle<()>>,
        stopped: Arc<AtomicBool>,
    }
    impl IoThread {
        fn spawn(
            work: impl FnOnce(Arc<AtomicBool>, thread::Thread) + Send + 'static,
        ) -> io::Result<Self> {
            let stopped = Arc::new(AtomicBool::new(false));
            let worker_stop = stopped.clone();
            let owner = thread::current();
            let join = thread::Builder::new()
                .name("source-down-pipe".into())
                .spawn(move || work(worker_stop, owner))?;
            Ok(Self {
                join: Some(join),
                stopped,
            })
        }
        fn stop(&mut self) {
            self.stopped.store(true, Ordering::SeqCst);
            if let Some(join) = self.join.take() {
                // Cancellation is not a completion notification. Repeat until joined to cover the interval
                // between the worker checking `stopped` and entering a synchronous Windows I/O call.
                while !join.is_finished() {
                    unsafe {
                        CancelSynchronousIo(join.as_raw_handle());
                    }
                    thread::sleep(Duration::from_millis(1));
                }
                let _ = join.join();
            }
        }
    }

    pub(crate) struct Reader {
        receiver: Option<mpsc::Receiver<io::Result<Vec<u8>>>>,
        buffered: io::Cursor<Vec<u8>>,
        worker: IoThread,
    }
    impl Reader {
        pub(crate) fn new(mut pipe: impl Read + Send + 'static) -> io::Result<Self> {
            let (sender, receiver) = mpsc::sync_channel(1);
            let worker = IoThread::spawn(move |stopped, owner| {
                while !stopped.load(Ordering::SeqCst) {
                    let mut bytes = vec![0; 65536];
                    let read = pipe.read(&mut bytes).map(|n| {
                        bytes.truncate(n);
                        bytes
                    });
                    let finished = !read.as_ref().is_ok_and(|b| !b.is_empty());
                    if sender.send(read).is_err() {
                        break;
                    }
                    owner.unpark();
                    if finished {
                        break;
                    }
                }
            })?;
            Ok(Self {
                receiver: Some(receiver),
                buffered: io::Cursor::new(Vec::new()),
                worker,
            })
        }
    }
    impl Read for Reader {
        fn read(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
            if self.buffered.position() as usize == self.buffered.get_ref().len() {
                self.buffered = io::Cursor::new(match self.receiver.as_ref().unwrap().try_recv() {
                    Ok(result) => result?,
                    Err(mpsc::TryRecvError::Empty) => return Err(io::ErrorKind::WouldBlock.into()),
                    Err(mpsc::TryRecvError::Disconnected) => return Ok(0),
                });
            }
            self.buffered.read(bytes)
        }
    }
    impl Drop for Reader {
        fn drop(&mut self) {
            self.receiver.take(); // Unblock a bounded send before joining its producer.
            self.worker.stop();
        }
    }

    pub(crate) struct Writer {
        sender: Option<mpsc::Sender<Vec<u8>>>,
        receiver: mpsc::Receiver<io::Result<usize>>,
        pending: bool,
        worker: IoThread,
    }
    impl Writer {
        pub(crate) fn new(mut pipe: impl Write + Send + 'static) -> io::Result<Self> {
            let (sender, requests) = mpsc::channel::<Vec<u8>>();
            let (responses, receiver) = mpsc::channel();
            let worker = IoThread::spawn(move |stopped, owner| {
                while let Ok(bytes) = requests.recv() {
                    if stopped.load(Ordering::SeqCst) {
                        break;
                    }
                    let result = pipe.write(&bytes).and_then(|n| pipe.flush().map(|()| n));
                    let failed = result.is_err();
                    if responses.send(result).is_err() {
                        break;
                    }
                    owner.unpark();
                    if failed {
                        break;
                    }
                }
            })?;
            Ok(Self {
                sender: Some(sender),
                receiver,
                pending: false,
                worker,
            })
        }
    }
    impl Write for Writer {
        fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
            if !self.pending {
                // A single outstanding write bounds memory and reports completion only after the real write.
                self.sender
                    .as_ref()
                    .unwrap()
                    .send(bytes[..bytes.len().min(65536)].to_vec())
                    .map_err(|_| io::Error::from(io::ErrorKind::BrokenPipe))?;
                self.pending = true;
            }
            match self.receiver.try_recv() {
                Ok(result) => {
                    self.pending = false;
                    result
                }
                Err(mpsc::TryRecvError::Empty) => Err(io::ErrorKind::WouldBlock.into()),
                Err(mpsc::TryRecvError::Disconnected) => Err(io::ErrorKind::BrokenPipe.into()),
            }
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }
    impl Drop for Writer {
        fn drop(&mut self) {
            self.sender.take(); // Unblock an idle worker before cancellation and join.
            self.worker.stop();
        }
    }
    pub(super) type Input = Writer;
    pub(super) type Stdout = Reader;
    pub(super) type Stderr = Reader;
    pub(super) fn drain_stderr(stderr: &mut Stderr, mut consume: impl FnMut(&[u8])) {
        // Preserve queued and in-flight diagnostics before joining their producer.
        // Draining also releases a worker blocked in the bounded send; cancellation
        // releases a pending OS read even if a handle was passed outside the scope.
        stderr.worker.stopped.store(true, Ordering::SeqCst);
        let mut bytes = [0; 65536];
        loop {
            while let Ok(n @ 1..) = stderr.read(&mut bytes) {
                consume(&bytes[..n]);
            }
            let Some(join) = stderr.worker.join.as_ref() else {
                break;
            };
            if join.is_finished() {
                // The worker may have queued its final read just before finishing.
                while let Ok(n @ 1..) = stderr.read(&mut bytes) {
                    consume(&bytes[..n]);
                }
                break;
            }
            unsafe {
                CancelSynchronousIo(join.as_raw_handle());
            }
            thread::sleep(Duration::from_millis(1));
        }
        stderr.worker.stop();
    }
    pub(super) fn pipes(scope: &mut Process) -> io::Result<(Input, Stdout, Stderr)> {
        Ok((
            Writer::new(
                scope
                    .child
                    .stdin
                    .take()
                    .ok_or_else(|| io::Error::other("missing stdin pipe"))?,
            )?,
            Reader::new(
                scope
                    .child
                    .stdout
                    .take()
                    .ok_or_else(|| io::Error::other("missing stdout pipe"))?,
            )?,
            Reader::new(
                scope
                    .child
                    .stderr
                    .take()
                    .ok_or_else(|| io::Error::other("missing stderr pipe"))?,
            )?,
        ))
    }
    pub(crate) fn wait(_interests: &[super::Interest<'_>], timeout: Duration) -> io::Result<()> {
        // Pipe workers wake this owner after actual I/O. The bound observes cancellation and child exit.
        thread::park_timeout(timeout);
        Ok(())
    }
    pub(super) fn path_bytes(path: &Path) -> Vec<u8> {
        use std::os::windows::ffi::OsStrExt;
        let mut bytes = Vec::new();
        for character in char::decode_utf16(path.as_os_str().encode_wide()) {
            match character {
                Ok('\\') => bytes.push(b'/'),
                Ok(character) => {
                    bytes.extend_from_slice(character.encode_utf8(&mut [0; 4]).as_bytes())
                }
                // WTF-8 preserves unpaired UTF-16 surrogates without lossy replacement.
                Err(error) => {
                    let value = error.unpaired_surrogate();
                    bytes.extend_from_slice(&[
                        (0xe0 | value >> 12) as u8,
                        (0x80 | (value >> 6) & 0x3f) as u8,
                        (0x80 | value & 0x3f) as u8,
                    ]);
                }
            }
        }
        bytes
    }
    pub(crate) fn close(file: File) -> io::Result<()> {
        use std::os::windows::io::IntoRawHandle;
        if unsafe { CloseHandle(file.into_raw_handle()) } == 0 {
            Err(io::Error::last_os_error())
        } else {
            Ok(())
        }
    }
    pub(crate) fn file_identity(path: &Path) -> io::Result<(u64, u64)> {
        use std::os::windows::fs::OpenOptionsExt;
        use windows_sys::Win32::Storage::FileSystem::*;
        // Attribute access works for protected inputs and directories without reading their contents.
        let file = File::options()
            .access_mode(FILE_READ_ATTRIBUTES)
            .custom_flags(FILE_FLAG_BACKUP_SEMANTICS)
            .open(path)?;
        open_file_identity(&file)
    }
    pub(crate) fn open_file_identity(file: &File) -> io::Result<(u64, u64)> {
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::Storage::FileSystem::*;
        let mut info = BY_HANDLE_FILE_INFORMATION::default();
        if unsafe { GetFileInformationByHandle(file.as_raw_handle(), &mut info) } == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok((
            info.dwVolumeSerialNumber.into(),
            (u64::from(info.nFileIndexHigh) << 32) | u64::from(info.nFileIndexLow),
        ))
    }

    pub(crate) fn file_kind(metadata: &Metadata) -> u32 {
        use std::os::windows::fs::MetadataExt;
        metadata.file_attributes()
    }
    pub(crate) fn file_permissions(metadata: &Metadata) -> u32 {
        use std::os::windows::fs::MetadataExt;
        metadata.file_attributes()
    }

    pub(super) fn register_cancellation(
        cancelled: std::sync::Arc<std::sync::atomic::AtomicBool>,
    ) -> std::io::Result<()> {
        use std::sync::{
            Arc, OnceLock,
            atomic::{AtomicBool, Ordering},
        };
        use windows_sys::Win32::System::Console::*;
        static CANCELLED: OnceLock<Arc<AtomicBool>> = OnceLock::new();
        unsafe extern "system" fn handler(event: u32) -> i32 {
            if matches!(event, CTRL_C_EVENT | CTRL_BREAK_EVENT) {
                if let Some(cancelled) = CANCELLED.get() {
                    cancelled.store(true, Ordering::SeqCst);
                }
                1
            } else {
                0
            }
        }
        CANCELLED
            .set(cancelled)
            .map_err(|_| std::io::Error::other("cancellation handler already registered"))?;
        if unsafe { SetConsoleCtrlHandler(Some(handler), 1) } == 0 {
            Err(std::io::Error::last_os_error())
        } else {
            Ok(())
        }
    }
    pub(crate) struct Output<'a> {
        writer: Writer,
        cancelled: &'a AtomicBool,
    }
    impl<'a> Output<'a> {
        pub(crate) fn new(cancelled: &'a AtomicBool) -> std::io::Result<Self> {
            Ok(Self {
                writer: Writer::new(std::io::stdout())?,
                cancelled,
            })
        }
    }
    impl std::io::Write for Output<'_> {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            loop {
                if self.cancelled.load(Ordering::SeqCst) {
                    return Err(std::io::Error::other("cancelled"));
                }
                match self.writer.write(bytes) {
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        std::thread::park_timeout(std::time::Duration::from_millis(10))
                    }
                    result => return result,
                }
            }
        }
        fn flush(&mut self) -> std::io::Result<()> {
            self.writer.flush()
        }
    }
}
pub(crate) mod notifications;
