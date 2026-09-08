use crate::model::{Error, Result};
use std::sync::atomic::{AtomicBool, Ordering};

pub fn print_result(result: &serde_json::Value, json: bool, cancelled: &AtomicBool) -> Result<()> {
    print(result, json, cancelled, None)
}

pub fn print_file_result(
    result: &serde_json::Value,
    json: bool,
    root: &std::path::Path,
    target: &str,
    id: &str,
    cancelled: &AtomicBool,
) -> Result<()> {
    let root = std::path::absolute(root).map_err(|error| Error::new(format!("root: {error}")))?;
    let root = root
        .to_str()
        .ok_or_else(|| Error::new("root is not UTF-8"))?;
    print(result, json, cancelled, Some((root, target, id)))
}

fn print(
    result: &serde_json::Value,
    json: bool,
    cancelled: &AtomicBool,
    file: Option<(&str, &str, &str)>,
) -> Result<()> {
    use std::io::Write;
    fn list(
        out: &mut impl Write,
        name: &str,
        page: &serde_json::Value,
        handle: &str,
    ) -> std::io::Result<()> {
        let Some(items) = page["items"].as_array() else {
            return Ok(());
        };
        writeln!(out, "{name}: {}/{}", page["returned"], page["total"])?;
        for item in items {
            if name == "Sources" {
                writeln!(
                    out,
                    "  Source {}:{}-{} bytes {}..{} ({}) {}",
                    item["span"]["path"].as_str().unwrap(),
                    item["span"]["start_line"],
                    item["span"]["end_line"],
                    item["span"]["start_byte"],
                    item["span"]["end_byte"],
                    item["mapping"].as_str().unwrap(),
                    item["current_link"].as_str().unwrap_or("snapshot source")
                )?;
            } else if name == "Occurrences" {
                writeln!(
                    out,
                    "  Occurrence {}: {} @{}; plugin {}; call site {}",
                    item["id"].as_str().unwrap(),
                    item["page"].as_str().unwrap(),
                    item["position"],
                    item["plugin"],
                    item["call_site"]
                )?;
            } else {
                writeln!(out, "  {}", item.as_str().unwrap())?;
            }
        }
        if let Some(cursor) = page["next_cursor"].as_str() {
            writeln!(
                out,
                "  List truncated; continue: read {handle} --cursor {cursor}"
            )?;
        }
        Ok(())
    }
    fn body(
        out: &mut impl Write,
        body: &serde_json::Value,
        command: impl Fn(usize) -> String,
    ) -> std::io::Result<()> {
        writeln!(
            out,
            "Body bytes {}..{} / {}{}\n{}",
            body["range"][0],
            body["range"][1],
            body["total_bytes"],
            if body["truncated"] == true {
                " (truncated)"
            } else {
                ""
            },
            body["text"].as_str().unwrap()
        )?;
        if let Some(offset) = body["next_offset"].as_u64() {
            writeln!(out, "Continue: {}", command(offset as usize))?;
        }
        Ok(())
    }
    let writer =
        crate::platform::Output::new(cancelled).map_err(|e| Error::new(format!("stdout: {e}")))?;
    let mut out = std::io::BufWriter::new(writer);
    let mut write = || -> std::io::Result<()> {
        if json {
            serde_json::to_writer(&mut out, result)?;
            writeln!(out)?;
            return out.flush();
        }
        if let Some((root, target, id)) = file {
            let source = &result["source"];
            writeln!(
                out,
                "Current file {}:{}-{} bytes {}..{}\nSHA-256 {}",
                source["path"].as_str().unwrap(),
                source["start_line"],
                source["end_line"],
                source["start_byte"],
                source["end_byte"],
                result["file_sha256"].as_str().unwrap()
            )?;
            let quote = |text: &str| format!("'{}'", text.replace('\'', "'\"'\"'"));
            body(&mut out, &result["body"], |offset| {
                format!(
                    "source-down read --id={} --root={} --offset={offset} -- {}",
                    quote(id),
                    quote(root),
                    quote(target)
                )
            })?;
            return out.flush();
        }
        writeln!(
            out,
            "Snapshot {} ({})",
            result["snapshot"].as_str().unwrap(),
            result["freshness"].as_str().unwrap()
        )?;
        if !result["scope"].is_null() {
            let scope = &result["scope"];
            writeln!(
                out,
                "Scope: {} inputs; read {}\nSelections: {}\nExcluded: {}",
                scope["input_files"]["total"],
                scope["handle"].as_str().unwrap(),
                scope["selections"],
                scope["excludes"]
            )?;
            list(
                &mut out,
                "Inputs",
                &scope["input_files"],
                scope["handle"].as_str().unwrap(),
            )?;
        }
        if let Some(hits) = result["hits"].as_array() {
            writeln!(
                out,
                "Matches: {}/{}{}",
                result["returned"],
                result["total_matches"],
                if result["truncated"] == true {
                    " (truncated; increase --limit)"
                } else {
                    ""
                }
            )?;
            for hit in hits {
                let handle = hit["handle"].as_str().unwrap();
                writeln!(
                    out,
                    "\n{handle} [{}] {}\n{}",
                    hit["kind"].as_str().unwrap(),
                    hit["title_path"],
                    hit["snippet"].as_str().unwrap()
                )?;
                writeln!(out, "Matched fields: {}", hit["matches"])?;
                list(&mut out, "Sources", &hit["sources"], handle)?;
                list(&mut out, "Occurrences", &hit["occurrences"], handle)?;
            }
        } else {
            let handle = result["handle"].as_str().unwrap();
            writeln!(out, "\n{handle}")?;
            if !result["body"].is_null() {
                body(&mut out, &result["body"], |offset| {
                    format!("read {handle} --offset {offset}")
                })?;
            }
            for item in result["context"].as_array().unwrap() {
                writeln!(
                    out,
                    "Context at occurrence {}",
                    item["occurrence"].as_str().unwrap()
                )?;
                body(&mut out, &item["body"], |offset| {
                    format!(
                        "read {} --offset {offset}",
                        item["handle"].as_str().unwrap()
                    )
                })?;
            }
            list(&mut out, "Sources", &result["sources"], handle)?;
            list(&mut out, "Occurrences", &result["occurrences"], handle)?;
            if !result["continuation"].is_null() {
                let continuation = &result["continuation"];
                let name = match continuation["list"].as_str().unwrap() {
                    "sources" => "Sources",
                    "occurrences" => "Occurrences",
                    _ => "Inputs",
                };
                list(&mut out, name, &continuation["page"], handle)?;
            }
        }
        out.flush()
    };
    write().map_err(|e| {
        if cancelled.load(Ordering::SeqCst) {
            Error::cancelled()
        } else {
            Error::new(format!("stdout: {e}"))
        }
    })
}
