//! Measure snapshot load, filesystem freshness, ranking and result serialization separately.
use source_down::search::{ReadOptions, Reader};
use std::path::PathBuf;
use std::sync::{Arc, atomic::AtomicBool};
use std::time::Instant;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let root = PathBuf::from(args.next().ok_or("expected root")?);
    let query = args.next().ok_or("expected query")?;
    let file = args.next().ok_or("expected file")?;
    let id = args.next().ok_or("expected selector")?;
    let started = Instant::now();
    let reader = Reader::open(&root, None, None, false, Arc::new(AtomicBool::new(false)))?;
    let found = reader.query(&query, None, 10)?;
    let encode = Instant::now();
    let bytes = serde_json::to_vec(&found)?;
    let serialization_seconds = encode.elapsed().as_secs_f64();
    let query_seconds = started.elapsed().as_secs_f64();
    let read = Instant::now();
    let mut read_bytes = 0;
    if let Some(hit) = found["hits"].as_array().unwrap().first() {
        read_bytes = serde_json::to_vec(
            &reader.read(hit["handle"].as_str().unwrap(), &ReadOptions::default())?,
        )?
        .len();
    }
    let read_fragment_seconds = read.elapsed().as_secs_f64();
    let file_started = Instant::now();
    let current = source_down::search::read_file(&root, &file, &id, None, &AtomicBool::new(false))?;
    let file_select_seconds = file_started.elapsed().as_secs_f64();
    let file_result_bytes = serde_json::to_vec(&current)?.len();
    println!(
        "{}",
        serde_json::json!({"stages":reader.timings(),"serialization_seconds":serialization_seconds,
        "query_seconds":query_seconds,"read_fragment_seconds":read_fragment_seconds,
        "file_select_seconds":file_select_seconds,"file_result_bytes":file_result_bytes,
        "result_bytes":bytes.len(),"read_bytes":read_bytes,"total_matches":found["total_matches"]})
    );
    Ok(())
}
