//! Measure the public Session API in one host process with real project plugins.
use source_down::engine::Session;
use std::path::PathBuf;
use std::sync::{Arc, atomic::AtomicBool};
use std::time::Instant;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let root = PathBuf::from(args.next().ok_or("expected project root")?);
    let count: usize = args.next().ok_or("expected round count")?.parse()?;
    let mut session = Session::new(&root, None, None, Arc::new(AtomicBool::new(false)))?;
    let mut rounds = Vec::new();
    for _ in 0..count {
        let started = Instant::now();
        let outcome = session.prepare(&["src".into()])?.publish()?;
        if outcome.check_failed {
            return Err("plugin checks failed".into());
        }
        rounds.push(serde_json::json!({"batch_id":outcome.batch_id,"elapsed_ms":started.elapsed().as_secs_f64()*1000.0}));
    }
    let closing = Instant::now();
    session.close()?;
    println!(
        "{}",
        serde_json::json!({"rounds":rounds,"close_ms":closing.elapsed().as_secs_f64()*1000.0})
    );
    Ok(())
}
