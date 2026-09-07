//! The sole owner of plugin children, pipes, protocol phases and bounded diagnostics.
use super::protocol::{self, HostMessage, PluginMessage};
use crate::{
    config::{ExternalConfig, json_options},
    model::*,
};
use std::collections::{BTreeMap, VecDeque};
use std::io::{Read, Write};
use std::os::{fd::AsRawFd, unix::process::CommandExt};
use std::path::PathBuf;
use std::process::{Child, ChildStderr, ChildStdin, ChildStdout, ExitStatus, Stdio};
use std::sync::{Arc, Mutex, atomic::AtomicBool, mpsc};
use std::time::{Duration, Instant};

pub(super) type Responder = mpsc::Sender<Result<Reply>>;
pub(super) enum Reply {
    Done,
    Output(PluginOutput),
}
pub(super) enum Command {
    Start {
        id: String,
        root: PathBuf,
        config: ExternalConfig,
        reply: Responder,
    },
    Run {
        id: String,
        batch: PluginBatch,
        reply: Responder,
    },
    Close(Responder),
    Abort,
}
#[derive(Default)]
pub(super) struct Status {
    pub error: Option<Error>,
    pub stderr: BTreeMap<String, Tail>,
}

#[derive(Default)]
pub(super) struct Tail {
    bytes: VecDeque<u8>,
    truncated: bool,
}
impl Tail {
    fn push(&mut self, bytes: &[u8]) {
        // SPEC-PLG-008: bound lifetime memory, including healthy idle logging.
        // Each pipe read supplies at most 64 KiB; discard before growing the buffer.
        if self.bytes.len() + bytes.len() > 65536 {
            self.bytes.drain(..self.bytes.len() + bytes.len() - 65536);
            self.truncated = true;
        }
        self.bytes.extend(bytes);
    }
    pub fn text(&self) -> String {
        let bytes: Vec<_> = self.bytes.iter().copied().collect();
        let skip = if self.truncated {
            bytes.iter().take_while(|&&b| b & 0xc0 == 0x80).count()
        } else {
            0
        };
        let bytes = &bytes[skip..];
        let end = match std::str::from_utf8(bytes) {
            Err(error) if error.error_len().is_none() => error.valid_up_to(),
            _ => bytes.len(),
        };
        format!(
            "{}{}",
            if self.truncated {
                "[stderr truncated]\n"
            } else {
                ""
            },
            String::from_utf8_lossy(&bytes[..end])
        )
    }
}

struct Exchange {
    input: Vec<u8>,
    written: usize,
    started: Instant,
    response: Option<Reply>,
    reply: Responder,
}
enum Phase {
    Initializing(Exchange),
    Running {
        batch_id: String,
        exchange: Exchange,
    },
    Idle,
    Closing(Instant),
    Closed,
}
struct Process {
    child: Child,
    stdin: Option<ChildStdin>,
    stdout: ChildStdout,
    stderr: ChildStderr,
    out_eof: bool,
    err_eof: bool,
    exit: Option<ExitStatus>,
    frame: Vec<u8>,
    phase: Phase,
    timeout: Duration,
    context: String,
    armed: bool,
}
impl Drop for Process {
    fn drop(&mut self) {
        self.stop();
    }
}

fn nonblocking(pipe: &impl AsRawFd) -> Result<()> {
    // SAFETY: fcntl operates on an owned live pipe descriptor.
    let result = unsafe {
        let flags = libc::fcntl(pipe.as_raw_fd(), libc::F_GETFL);
        if flags == -1 {
            -1
        } else {
            libc::fcntl(pipe.as_raw_fd(), libc::F_SETFL, flags | libc::O_NONBLOCK)
        }
    };
    if result == -1 {
        Err(Error::new(std::io::Error::last_os_error().to_string()))
    } else {
        Ok(())
    }
}
fn transient(error: &std::io::Error) -> bool {
    matches!(
        error.kind(),
        std::io::ErrorKind::WouldBlock | std::io::ErrorKind::Interrupted
    )
}
fn exchange(message: &HostMessage, reply: Responder, started: Instant) -> Result<Exchange> {
    let mut input = serde_json::to_vec(message).map_err(|e| Error::new(e.to_string()))?;
    input.push(b'\n');
    Ok(Exchange {
        input,
        written: 0,
        started,
        response: None,
        reply,
    })
}

impl Process {
    fn stop(&mut self) {
        if self.armed {
            // SAFETY: spawn establishes a fresh process group owned by this driver.
            unsafe {
                libc::kill(-(self.child.id() as i32), libc::SIGKILL);
            }
            let _ = self.child.wait();
            self.armed = false;
        }
    }

    fn finish(&mut self, tail: &mut Tail) {
        self.stop();
        // SPEC-PLG-008: retain buffered diagnostics after stopping their writers.
        // Nonblocking reads also bound cleanup when a pipe remains open elsewhere.
        let mut bytes = [0; 65536];
        while let Ok(n @ 1..) = self.stderr.read(&mut bytes) {
            tail.push(&bytes[..n]);
        }
    }

    fn spawn(id: &str, root: PathBuf, config: ExternalConfig, reply: Responder) -> Result<Self> {
        let options = json_options(&toml::Value::Table(config.options))?;
        let program = config
            .command
            .first()
            .filter(|p| !p.is_empty())
            .ok_or_else(|| Error::new("empty plugin command"))?;
        let program = if program.contains('/') {
            root.join(program)
        } else {
            program.into()
        };
        let mut child = std::process::Command::new(program)
            .args(&config.command[1..])
            .current_dir(&root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .process_group(0)
            .spawn()
            .map_err(|e| Error::new(format!("start failed: {e}")))?;
        let started = Instant::now();
        let stdin = child.stdin.take();
        let stdout = child.stdout.take().unwrap();
        let stderr = child.stderr.take().unwrap();
        // Establish the process guard before any fallible pipe or message setup.
        let mut process = Self {
            child,
            stdin,
            stdout,
            stderr,
            out_eof: false,
            err_eof: false,
            exit: None,
            frame: Vec::new(),
            phase: Phase::Idle,
            timeout: Duration::from_millis(config.timeout_ms),
            context: "initialize".into(),
            armed: true,
        };
        nonblocking(process.stdin.as_ref().unwrap())?;
        nonblocking(&process.stdout)?;
        nonblocking(&process.stderr)?;
        process.phase = Phase::Initializing(exchange(
            &HostMessage::Initialize {
                protocol_version: 1,
                plugin: id.into(),
                project_root: root,
                options,
            },
            reply,
            started,
        )?);
        Ok(process)
    }

    fn run(&mut self, batch: PluginBatch, reply: Responder) -> Result<()> {
        if !matches!(self.phase, Phase::Idle) {
            return Err(Error::new("plugin is not idle"));
        }
        self.context = format!(
            "batch {}: {}",
            batch.batch_id,
            batch
                .requests
                .iter()
                .map(|r| format!("{}:{}", r.source.path, r.source.start_line))
                .collect::<Vec<_>>()
                .join(", ")
        );
        let message = HostMessage::Run {
            batch_id: batch.batch_id.clone(),
            input_files: batch.input_files,
            requests: batch.requests,
        };
        self.phase = Phase::Running {
            batch_id: batch.batch_id,
            exchange: exchange(&message, reply, Instant::now())?,
        };
        Ok(())
    }

    fn exchange_mut(&mut self) -> Option<&mut Exchange> {
        match &mut self.phase {
            Phase::Initializing(e) | Phase::Running { exchange: e, .. } => Some(e),
            _ => None,
        }
    }

    fn receive(&mut self, bytes: &[u8]) -> Result<()> {
        for part in bytes.split_inclusive(|&byte| byte == b'\n') {
            if self.exchange_mut().is_none_or(|e| e.response.is_some()) {
                return Err(Error::new("unexpected stdout outside a pending response"));
            }
            self.frame.extend_from_slice(part);
            if self.frame.last() == Some(&b'\n') {
                self.frame.pop();
                let message: PluginMessage = protocol::decode(&self.frame)?;
                self.frame.clear();
                match (&mut self.phase, message) {
                    (
                        Phase::Initializing(e),
                        PluginMessage::Ready {
                            protocol_version: 1,
                        },
                    ) => e.response = Some(Reply::Done),
                    (
                        Phase::Running {
                            batch_id: expected,
                            exchange,
                        },
                        PluginMessage::Result {
                            batch_id,
                            results,
                            append,
                            reports,
                            diagnostics,
                            dependencies,
                        },
                    ) if *expected == batch_id => {
                        exchange.response = Some(Reply::Output(PluginOutput {
                            results,
                            append,
                            reports,
                            diagnostics,
                            dependencies,
                        }));
                    }
                    _ => {
                        return Err(Error::new(
                            "unexpected message type, protocol_version (expected 1), or batch_id",
                        ));
                    }
                }
            }
        }
        Ok(())
    }

    fn pump(&mut self, tail: &mut Tail) -> Result<()> {
        if matches!(self.phase, Phase::Closed) {
            return Ok(());
        }
        let mut bytes = [0; 65536];
        // One bounded read/write per turn lets every plugin and its deadline progress.
        if !self.err_eof {
            match self.stderr.read(&mut bytes) {
                Ok(0) => self.err_eof = true,
                Ok(n) => tail.push(&bytes[..n]),
                Err(e) if transient(&e) => {}
                Err(e) => return Err(Error::new(format!("stderr read: {e}"))),
            }
        }
        if !self.out_eof {
            match self.stdout.read(&mut bytes) {
                Ok(0) => self.out_eof = true,
                Ok(n) => self.receive(&bytes[..n])?,
                Err(e) if transient(&e) => {}
                Err(e) => return Err(Error::new(format!("stdout read: {e}"))),
            }
        }
        if self.exit.is_none() {
            self.exit = self
                .child
                .try_wait()
                .map_err(|e| Error::new(format!("wait failed: {e}")))?;
        }
        if let Some(status) = self.exit {
            if !status.success() || !matches!(self.phase, Phase::Closing(_)) {
                return Err(Error::new(format!(
                    "exited with {status} before normal session completion"
                )));
            }
            if self.out_eof && self.err_eof {
                self.armed = false;
                self.phase = Phase::Closed;
                return Ok(());
            }
        }
        if self.out_eof && !matches!(self.phase, Phase::Closing(_)) {
            return Err(Error::new(if self.frame.is_empty() {
                "unexpected stdout EOF"
            } else {
                "incomplete NDJSON frame at stdout EOF"
            }));
        }
        let started = match &self.phase {
            Phase::Initializing(e) | Phase::Running { exchange: e, .. } => Some(e.started),
            Phase::Closing(started) => Some(*started),
            _ => None,
        };
        if started.is_some_and(|s| s.elapsed() >= self.timeout) {
            return Err(Error::new(format!(
                "timeout after {} ms",
                self.timeout.as_millis()
            )));
        }
        match &mut self.phase {
            Phase::Initializing(e) | Phase::Running { exchange: e, .. }
                if e.written < e.input.len() =>
            {
                match self
                    .stdin
                    .as_mut()
                    .unwrap()
                    .write(&e.input[e.written..e.input.len().min(e.written + 65536)])
                {
                    Ok(0) => {
                        return Err(Error::new("plugin closed stdin before request completed"));
                    }
                    Ok(n) => e.written += n,
                    Err(error) if transient(&error) => {}
                    Err(error) => return Err(Error::new(format!("plugin stdin: {error}"))),
                }
            }
            _ => {}
        }
        Ok(())
    }

    fn complete(&mut self) {
        if let Some(e) = self.exchange_mut()
            && e.written == e.input.len()
            && let Some(response) = e.response.take()
        {
            let _ = e.reply.send(Ok(response));
            self.phase = Phase::Idle;
            self.context = "idle".into();
        }
    }

    fn polls(&self, polls: &mut Vec<libc::pollfd>) {
        let mut add = |fd, events| {
            polls.push(libc::pollfd {
                fd,
                events,
                revents: 0,
            })
        };
        if !self.out_eof {
            add(self.stdout.as_raw_fd(), libc::POLLIN);
        }
        if !self.err_eof {
            add(self.stderr.as_raw_fd(), libc::POLLIN);
        }
        if matches!(&self.phase, Phase::Initializing(e) | Phase::Running { exchange: e, .. } if e.written < e.input.len())
        {
            add(self.stdin.as_ref().unwrap().as_raw_fd(), libc::POLLOUT);
        }
    }
}

// {% spec "plg-008" %}
pub(super) fn drive(
    commands: mpsc::Receiver<Command>,
    status: Arc<Mutex<Status>>,
    cancelled: Arc<AtomicBool>,
) {
    let mut processes: BTreeMap<String, Process> = BTreeMap::new();
    let mut closing: Option<Responder> = None;
    let result = (|| -> Result<()> {
        loop {
            if let Err(error) = crate::publication::check_cancelled(&cancelled) {
                let context = processes
                    .iter()
                    .find(|(_, p)| {
                        matches!(p.phase, Phase::Initializing(_) | Phase::Running { .. })
                    })
                    .map(|(id, p)| format!("plugin {id} ({}): ", p.context))
                    .unwrap_or_default();
                return Err(Error {
                    exit_code: error.exit_code,
                    message: format!("{context}{error}"),
                });
            }
            for (id, process) in &mut processes {
                let mut shared = status.lock().unwrap();
                let tail = shared.stderr.entry(id.clone()).or_default();
                if let Err(error) = process.pump(tail) {
                    process.finish(tail);
                    return Err(Error {
                        exit_code: error.exit_code,
                        message: format!(
                            "plugin {id} ({}): {error}; plugin {id} session stderr: {}",
                            process.context,
                            tail.text()
                        ),
                    });
                }
            }
            for process in processes.values_mut() {
                process.complete();
            }
            if closing.is_some() && processes.values().all(|p| matches!(p.phase, Phase::Closed)) {
                let _ = closing.take().unwrap().send(Ok(Reply::Done));
                return Ok(());
            }
            match commands.try_recv() {
                Ok(Command::Abort) | Err(mpsc::TryRecvError::Disconnected) => return Ok(()),
                Ok(Command::Start {
                    id,
                    root,
                    config,
                    reply,
                }) => {
                    if processes.contains_key(&id) {
                        return Err(Error::new(format!("plugin {id} already initialized")));
                    }
                    let process = Process::spawn(&id, root, config, reply)
                        .map_err(|e| Error::new(format!("plugin {id}: {e}")))?;
                    processes.insert(id, process);
                }
                Ok(Command::Run { id, batch, reply }) => {
                    processes
                        .get_mut(&id)
                        .ok_or_else(|| Error::new(format!("plugin {id} is not initialized")))?
                        .run(batch, reply)?;
                }
                Ok(Command::Close(reply)) => {
                    for process in processes.values_mut() {
                        process.phase = Phase::Closing(Instant::now());
                        process.context = "closing".into();
                        process.stdin.take();
                    }
                    closing = Some(reply);
                }
                Err(mpsc::TryRecvError::Empty) => {}
            }
            let mut polls = Vec::new();
            for process in processes.values() {
                process.polls(&mut polls);
            }
            // SAFETY: all descriptors belong to this thread. A short poll also observes
            // command arrival, cancellation and exits without imposing an idle deadline.
            let result = unsafe { libc::poll(polls.as_mut_ptr(), polls.len() as libc::nfds_t, 10) };
            if result < 0
                && std::io::Error::last_os_error().kind() != std::io::ErrorKind::Interrupted
            {
                return Err(Error::new(format!(
                    "poll failed: {}",
                    std::io::Error::last_os_error()
                )));
            }
        }
    })();
    if let Err(error) = result {
        status.lock().unwrap().error = Some(error);
    }
    // Stop the entire scope and retain diagnostics before replies disconnect.
    for (id, process) in &mut processes {
        process.finish(status.lock().unwrap().stderr.entry(id.clone()).or_default());
    }
}
