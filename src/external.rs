//! Session transport. One driver owns every child and pipe (SPEC-PLG-004, SPEC-PLG-008).
mod driver;
pub mod protocol;

use crate::{config::ExternalConfig, model::*};
use std::collections::BTreeMap;
use std::path::Path;
use std::sync::{Arc, Mutex, atomic::AtomicBool, mpsc};
use std::thread::JoinHandle;

/// A serial process session. Semantic output validation belongs to `results`.
pub struct ExternalSession {
    commands: mpsc::Sender<driver::Command>,
    status: Arc<Mutex<driver::Status>>,
    cancelled: Arc<AtomicBool>,
    worker: Option<JoinHandle<()>>,
}

impl ExternalSession {
    pub fn new(cancelled: Arc<AtomicBool>) -> Self {
        let (commands, receiver) = mpsc::channel();
        let status = Arc::new(Mutex::new(driver::Status::default()));
        let worker_status = status.clone();
        let worker_cancelled = cancelled.clone();
        let worker =
            std::thread::spawn(move || driver::drive(receiver, worker_status, worker_cancelled));
        Self {
            commands,
            status,
            cancelled,
            worker: Some(worker),
        }
    }

    pub fn initialize(
        &mut self,
        root: &Path,
        plugins: &BTreeMap<String, ExternalConfig>,
    ) -> Result<()> {
        for (id, config) in plugins {
            self.request(|reply| driver::Command::Start {
                id: id.clone(),
                root: root.to_owned(),
                config: config.clone(),
                reply,
            })?;
        }
        Ok(())
    }

    pub fn run(&mut self, id: &str, batch: &PluginBatch) -> Result<PluginOutput> {
        match self.request(|reply| driver::Command::Run {
            id: id.into(),
            batch: batch.clone(),
            reply,
        })? {
            driver::Reply::Output(output) => Ok(output),
            driver::Reply::Done => unreachable!("run command returns output"),
        }
    }

    /// Observe the driver's fault state, including failures detected while idle.
    pub fn check(&self) -> Result<()> {
        match &self.status.lock().unwrap().error {
            Some(error) => Err(error.clone()),
            None => crate::publication::check_cancelled(&self.cancelled),
        }
    }

    pub fn stderr(&self) -> BTreeMap<String, String> {
        self.status
            .lock()
            .unwrap()
            .stderr
            .iter()
            .filter_map(|(id, tail)| {
                let text = tail.text();
                (!text.is_empty()).then(|| (id.clone(), text))
            })
            .collect()
    }

    /// Close stdin, then confirm zero exit and pipe EOF for every plugin.
    pub fn close(&mut self) -> Result<()> {
        let result = if self.worker.is_some() {
            self.request(driver::Command::Close).map(|_| ())
        } else {
            self.check()
        };
        self.join();
        result
    }

    /// Semantic validation and other caller failures terminate the whole scope.
    pub fn abort(&mut self) {
        let _ = self.commands.send(driver::Command::Abort);
        self.join();
    }

    pub(crate) fn check_cancelled(&self) -> Result<()> {
        crate::publication::check_cancelled(&self.cancelled)
    }

    pub(crate) fn cleanup_result(&self) -> Result<()> {
        self.status
            .lock()
            .unwrap()
            .cleanup_error
            .clone()
            .map_or(Ok(()), Err)
    }

    fn join(&mut self) {
        if let Some(worker) = self.worker.take() {
            worker.join().expect("plugin I/O driver panicked");
        }
    }

    fn request(
        &mut self,
        command: impl FnOnce(driver::Responder) -> driver::Command,
    ) -> Result<driver::Reply> {
        self.check()?;
        let (sender, receiver) = mpsc::channel();
        if self.commands.send(command(sender)).is_err() {
            return Err(self
                .check()
                .err()
                .unwrap_or_else(|| Error::new("plugin session is closed")));
        }
        match receiver.recv() {
            Ok(reply) => reply,
            Err(_) => {
                self.join();
                Err(self
                    .check()
                    .err()
                    .unwrap_or_else(|| Error::new("plugin session is closed")))
            }
        }
    }
}

impl Drop for ExternalSession {
    fn drop(&mut self) {
        self.abort();
    }
}
