//! Search records come from this round's validated content. SPEC-SRH-001.
use crate::model::*;
use pulldown_cmark::{Event, Parser, Tag};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::Path;
mod facts;
mod file;
pub use file::read_file;
mod handles;
mod output;
mod query;
pub use output::{print_file_result, print_result};
mod read;
pub use query::validate_query;
pub use read::ReadOptions;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Prose,
    Code,
    Expansion,
    Appendix,
    Report,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
enum Format {
    Markdown,
    Code,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Mapping {
    body: [usize; 2],
    source: [usize; 2],
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Origin {
    span: SourceSpan,
    mapping: Vec<Mapping>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Occurrence {
    id: String,
    page: String,
    input_path: Option<String>,
    position: usize,
    title_path: Vec<String>,
    plugin: Option<String>,
    call_site: Option<SourceSpan>,
    selector: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Record {
    id: String,
    kind: Kind,
    format: Format,
    body: String,
    sources: Vec<Origin>,
    occurrences: Vec<Occurrence>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Manifest {
    generator: String,
    output_root: String,
    report_owners: Vec<String>,
    config: crate::config::Config,
    config_path: String,
    config_sources: BTreeMap<String, facts::Fingerprint>,
    input_files: Vec<String>,
    selections: Vec<String>,
    excludes: Exclusions,
    sources: BTreeMap<String, facts::Fingerprint>,
    dependencies: BTreeMap<String, Vec<facts::DependencyFact>>,
    outputs: BTreeMap<String, String>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Exclusions {
    directory_names: Vec<String>,
    paths: Vec<String>,
}

fn generator() -> String {
    format!(
        "source-down/{};search-rules=1;dependencies={}",
        env!("CARGO_PKG_VERSION"),
        digest(include_bytes!("../../Cargo.lock"))
    )
}

pub(crate) struct Round<'a> {
    pub input_files: Vec<String>,
    pub report_owners: Vec<String>,
    pub output: &'a Path,
    pub config: &'a crate::config::Config,
    pub config_path: &'a Path,
    pub selections: &'a [std::path::PathBuf],
    pub sources: &'a SourceStore,
    pub config_sources: &'a SourceStore,
    pub dependencies: &'a BTreeMap<String, Vec<Dependency>>,
    pub check: &'a dyn Fn() -> Result<()>,
    pub pages: &'a [(std::path::PathBuf, String)],
    pub reports: &'a [(std::path::PathBuf, String)],
}

fn relative(root: &Path, path: &Path) -> Result<String> {
    let joined = root.join(path);
    let relative = joined
        .strip_prefix(root)
        .map_err(|_| Error::new("path must be inside project root"))?;
    if relative.as_os_str().is_empty() {
        return Ok(".".into());
    }
    path_text(relative)
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Index {
    format_version: u32,
    snapshot: String,
    manifest: Manifest,
    records: Vec<Record>,
}

fn canonical<T: Serialize>(value: &T) -> Vec<u8> {
    // serde_json's default map is a BTreeMap, including nested object keys.
    serde_json::to_vec(&serde_json::to_value(value).expect("serializable snapshot"))
        .expect("serializable JSON")
}

fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

impl Index {
    fn validate(&self) -> Result<()> {
        use std::collections::BTreeSet;
        let invalid = || Error::new("invalid snapshot structure");
        let hash = |s: &str| {
            s.len() == 64
                && s.bytes()
                    .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        };
        let manifest = &self.manifest;
        if manifest.output_root != "." {
            validate_relative_path(&manifest.output_root)?;
        }
        validate_relative_path(&manifest.config_path)?;
        for path in manifest
            .input_files
            .iter()
            .chain(&manifest.excludes.paths)
            .chain(manifest.sources.keys())
            .chain(manifest.config_sources.keys())
            .chain(manifest.outputs.keys())
        {
            validate_relative_path(path)?;
        }
        if manifest.input_files.is_empty()
            || !manifest.input_files.windows(2).all(|w| w[0] < w[1])
            || !manifest
                .input_files
                .iter()
                .all(|p| manifest.sources.contains_key(p))
            || manifest.config.config_version != 1
            || manifest.excludes.paths != manifest.config.inputs.exclude
            || manifest.outputs.values().any(|s| !hash(s))
            || !self.records.windows(2).all(|w| w[0].id < w[1].id)
        {
            return Err(invalid());
        }
        let span_valid = |s: &SourceSpan| -> Result<()> {
            validate_relative_path(&s.path)?;
            if !manifest.sources.contains_key(&s.path)
                || s.start_byte >= s.end_byte
                || s.start_line == 0
                || s.start_line > s.end_line
            {
                return Err(invalid());
            }
            Ok(())
        };
        let mut positions = BTreeMap::new();
        let mut ids = BTreeSet::new();
        for record in &self.records {
            if record.body.trim().is_empty()
                || record.occurrences.is_empty()
                || record.id
                    != digest(&canonical(&serde_json::json!({
                        "kind":record.kind,"format":record.format,"body":record.body,"sources":record.sources
                    })))
            {
                return Err(invalid());
            }
            for origin in &record.sources {
                span_valid(&origin.span)?;
                let mut end = 0;
                for map in &origin.mapping {
                    if map.body[0] < end
                        || map.body[0] >= map.body[1]
                        || map.source[0] < origin.span.start_byte
                        || map.source[1] > origin.span.end_byte
                        || map.source[0] >= map.source[1]
                        || map.body[1] - map.body[0] != map.source[1] - map.source[0]
                        || record.body.get(map.body[0]..map.body[1]).is_none()
                    {
                        return Err(invalid());
                    }
                    end = map.body[1];
                }
            }
            for at in &record.occurrences {
                validate_relative_path(&at.page)?;
                if !manifest.outputs.contains_key(&at.page)
                    || !ids.insert(&at.id)
                    || positions.insert((&at.page, at.position), &at.id).is_some()
                {
                    return Err(invalid());
                }
                if let Some(input) = &at.input_path {
                    if record.kind == Kind::Report
                        || manifest.input_files.binary_search(input).is_err()
                        || Path::new(if manifest.output_root == "." {
                            ""
                        } else {
                            &manifest.output_root
                        })
                        .join("pages")
                        .join(format!("{input}.md"))
                            != Path::new(&at.page)
                    {
                        return Err(invalid());
                    }
                } else if record.kind != Kind::Report || at.plugin.is_none() {
                    return Err(invalid());
                }
                if let Some(site) = &at.call_site {
                    span_valid(site)?;
                }
            }
            if !record
                .occurrences
                .windows(2)
                .all(|w| (&w[0].page, w[0].position) < (&w[1].page, w[1].position))
            {
                return Err(invalid());
            }
        }
        let mut page_positions = BTreeMap::new();
        for (n, ((page, position), id)) in positions.into_iter().enumerate() {
            let expected = page_positions.entry(page).or_insert(0);
            if position != *expected || id != &format!("o{n}") {
                return Err(invalid());
            }
            *expected += 1;
        }
        Ok(())
    }

    // {% spec "srh-002" %}
    fn identity(&self) -> String {
        digest(&canonical(&serde_json::json!({
            "format_version": self.format_version,
            "manifest": self.manifest,
            "records": self.records,
        })))
    }
}

// CommonMark omits paragraph events inside tight list items. Keep their inline runs as leaves.
fn prose_leaves(
    text: &str,
) -> Vec<(
    Kind,
    Option<pulldown_cmark::HeadingLevel>,
    std::ops::Range<usize>,
)> {
    let mut leaves = Vec::new();
    let mut blocks = Vec::new();
    let mut tight: Option<std::ops::Range<usize>> = None;
    let flush = |tight: &mut Option<std::ops::Range<usize>>, leaves: &mut Vec<_>| {
        if let Some(range) = tight.take() {
            leaves.push((Kind::Prose, None, range));
        }
    };
    for (event, range) in Parser::new(text).into_offset_iter() {
        match &event {
            Event::Start(
                tag @ (Tag::Paragraph
                | Tag::Heading { .. }
                | Tag::CodeBlock(_)
                | Tag::HtmlBlock
                | Tag::List(_)
                | Tag::Item
                | Tag::BlockQuote(_)),
            ) => {
                flush(&mut tight, &mut leaves);
                match tag {
                    Tag::Paragraph => leaves.push((Kind::Prose, None, range)),
                    Tag::Heading { level, .. } => leaves.push((Kind::Prose, Some(*level), range)),
                    Tag::CodeBlock(_) => leaves.push((Kind::Code, None, range)),
                    _ => {}
                }
                blocks.push(tag.to_end());
            }
            Event::End(tag) if blocks.last() == Some(tag) => {
                flush(&mut tight, &mut leaves);
                blocks.pop();
            }
            Event::Rule => flush(&mut tight, &mut leaves),
            _ if blocks.last() == Some(&pulldown_cmark::TagEnd::Item) => {
                if let Some(current) = &mut tight {
                    current.end = current.end.max(range.end);
                } else {
                    tight = Some(range);
                }
            }
            _ => {}
        }
    }
    flush(&mut tight, &mut leaves);
    leaves.sort_by_key(|(_, _, range)| range.start);
    leaves
}

#[derive(Default)]
pub(crate) struct Collector {
    records: BTreeMap<String, Record>,
    positions: BTreeMap<String, usize>,
    requests: BTreeMap<(String, usize), (String, Request)>,
}

impl Collector {
    pub(crate) fn requests(&mut self, plugin: &str, requests: &[Request]) {
        for request in requests {
            self.requests.insert(
                (request.source.path.clone(), request.source.start_byte),
                (plugin.into(), request.clone()),
            );
        }
    }

    fn blocks(&mut self, kind: Kind, blocks: &Expansion, at: Occurrence) {
        for block in blocks {
            self.add(
                kind,
                Format::Markdown,
                &block.markdown,
                block
                    .sources
                    .iter()
                    .map(|span| Origin {
                        span: span.clone(),
                        mapping: vec![],
                    })
                    .collect(),
                at.clone(),
            );
        }
    }

    pub(crate) fn report(&mut self, plugin: &str, name: &str, blocks: &Expansion, page: &str) {
        self.blocks(
            Kind::Report,
            blocks,
            Occurrence {
                id: String::new(),
                page: page.into(),
                input_path: None,
                position: 0,
                title_path: vec![name.into()],
                plugin: Some(plugin.into()),
                call_site: None,
                selector: None,
            },
        );
    }

    pub(crate) fn appendices(
        &mut self,
        input: &str,
        page: &str,
        appendices: &[(String, Expansion)],
    ) {
        for (plugin, blocks) in appendices {
            self.blocks(
                Kind::Appendix,
                blocks,
                Occurrence {
                    id: String::new(),
                    page: page.into(),
                    input_path: Some(input.into()),
                    position: 0,
                    title_path: vec![],
                    plugin: Some(plugin.clone()),
                    call_site: None,
                    selector: None,
                },
            );
        }
    }
    fn add(
        &mut self,
        kind: Kind,
        format: Format,
        body: &str,
        mut sources: Vec<Origin>,
        mut at: Occurrence,
    ) {
        if body.trim().is_empty() {
            return;
        }
        let position = self.positions.entry(at.page.clone()).or_default();
        at.position = *position;
        *position += 1;
        sources.sort_by(|a, b| {
            (&a.span.path, a.span.start_byte, a.span.end_byte).cmp(&(
                &b.span.path,
                b.span.start_byte,
                b.span.end_byte,
            ))
        });
        sources.dedup();
        let id = digest(&canonical(&serde_json::json!({
            "kind":kind, "format":format, "body":body, "sources":sources,
        })));
        self.records
            .entry(id.clone())
            .or_insert_with(|| Record {
                id,
                kind,
                format,
                body: body.into(),
                sources,
                occurrences: vec![],
            })
            .occurrences
            .push(at);
    }

    // {% spec "srh-001" %}
    pub(crate) fn document(
        &mut self,
        document: &Document,
        page: &str,
        expansions: &BTreeMap<usize, Expansion>,
    ) -> Result<()> {
        let mut titles: Vec<(u8, String)> = vec![];
        for segment in &document.segments {
            let at = |titles: &[(u8, String)]| Occurrence {
                id: String::new(),
                page: page.into(),
                input_path: Some(document.source.path.clone()),
                position: 0,
                title_path: titles.iter().map(|(_, title)| title.clone()).collect(),
                plugin: None,
                call_site: None,
                selector: None,
            };
            match segment.kind {
                SegmentKind::Layout => {}
                SegmentKind::Code => self.add(
                    Kind::Code,
                    Format::Code,
                    &segment.text,
                    vec![Origin {
                        span: segment.span.clone(),
                        mapping: vec![Mapping {
                            body: [0, segment.text.len()],
                            source: [segment.span.start_byte, segment.span.end_byte],
                        }],
                    }],
                    at(&titles),
                ),
                SegmentKind::Prose => {
                    for part in crate::prose::parts(segment, &document.source, expansions)? {
                        match part {
                            crate::prose::Part::Text(text) => {
                                self.prose(document, segment, &text, page, &mut titles)?
                            }
                            crate::prose::Part::Block { source, expansion } => {
                                self.expansion(&source, expansion, at(&titles))
                            }
                        }
                    }
                }
            }
        }
        Ok(())
    }

    fn expansion(
        &mut self,
        source: &SourceSpan,
        expansion: &Expansion,
        mut occurrence: Occurrence,
    ) {
        let (plugin, request) = &self.requests[&(source.path.clone(), source.start_byte)];
        occurrence.plugin = Some(plugin.clone());
        occurrence.call_site = Some(request.source.clone());
        occurrence.selector = if plugin == "builtin:include" {
            request.arguments.named.get("id").cloned()
        } else {
            None
        };
        self.blocks(Kind::Expansion, expansion, occurrence);
    }

    fn inline(
        &mut self,
        call: &crate::prose::Inline<'_>,
        page: &str,
        input: &str,
        titles: &[(u8, String)],
    ) {
        self.expansion(
            &call.source,
            call.expansion,
            Occurrence {
                id: String::new(),
                page: page.into(),
                input_path: Some(input.into()),
                position: 0,
                title_path: titles.iter().map(|(_, title)| title.clone()).collect(),
                plugin: None,
                call_site: None,
                selector: None,
            },
        );
    }

    fn prose(
        &mut self,
        document: &Document,
        segment: &Segment,
        text: &crate::prose::Text<'_>,
        page: &str,
        titles: &mut Vec<(u8, String)>,
    ) -> Result<()> {
        let raw = text.body.as_ref();
        let (view, offsets) = crate::render::markdown_view(raw);
        let original = |offset: usize| offsets.as_ref().map_or(offset, |m| m[offset]);
        let sections = crate::markdown::sections(raw);
        let mut calls = text.calls.iter().peekable();
        for (kind, heading, range) in prose_leaves(&view) {
            let range = original(range.start)..original(range.end);
            while calls
                .peek()
                .is_some_and(|call| call.range.start < range.start)
            {
                self.inline(calls.next().unwrap(), page, &document.source.path, titles);
            }
            if let Some(level) = heading.map(|level| level as u8)
                && let Some(section) = sections.iter().find(|s| {
                    s.level == level && s.range.start <= range.start && range.start < s.range.end
                })
            {
                while titles.last().is_some_and(|(old, _)| *old >= level) {
                    titles.pop();
                }
                titles.push((level, section.title.clone()));
            }
            let body = &raw[range.clone()];
            if body
                .lines()
                .all(|line| line.trim().is_empty() || crate::markdown::anchor_id(line).is_some())
            {
                continue;
            }
            let start = range.start;
            let mut mapping: Vec<Mapping> = vec![];
            for (byte, ch) in body.char_indices() {
                let source_start = match &text.mapping {
                    Some(mapping) => match mapping[start + byte] {
                        Some(offset) => offset,
                        None => continue,
                    },
                    None => segment.mapping[text.original.start + start + byte],
                };
                let source_end = source_start + ch.len_utf8();
                if document.source.text.get(source_start..source_end)
                    != Some(&body[byte..byte + ch.len_utf8()])
                {
                    continue;
                }
                if let Some(last) = mapping.last_mut()
                    && last.body[1] == byte
                    && last.source[1] == source_start
                {
                    last.body[1] += ch.len_utf8();
                    last.source[1] = source_end;
                } else {
                    mapping.push(Mapping {
                        body: [byte, byte + ch.len_utf8()],
                        source: [source_start, source_end],
                    });
                }
            }
            self.add(
                kind,
                Format::Markdown,
                body,
                vec![Origin {
                    span: segment.span.clone(),
                    mapping,
                }],
                Occurrence {
                    id: String::new(),
                    page: page.into(),
                    input_path: Some(document.source.path.clone()),
                    position: 0,
                    title_path: titles.iter().map(|(_, title)| title.clone()).collect(),
                    plugin: None,
                    call_site: None,
                    selector: None,
                },
            );
            while calls
                .peek()
                .is_some_and(|call| call.range.start < range.end)
            {
                self.inline(calls.next().unwrap(), page, &document.source.path, titles);
            }
        }
        for call in calls {
            self.inline(call, page, &document.source.path, titles);
        }
        Ok(())
    }

    pub(crate) fn finish(mut self, round: Round<'_>) -> Result<(std::path::PathBuf, String)> {
        let root = &round.sources.root;
        let index_path = round.output.join("search/index.json");
        let mut dependencies =
            facts::dependencies(round.sources, round.dependencies, &|| (round.check)())?;
        let stale: Vec<_> = crate::publication::report_files(
            root,
            round.output,
            round.report_owners.iter().map(String::as_str),
            &|| (round.check)(),
        )?
        .into_iter()
        .filter(|path| !round.reports.iter().any(|(target, _)| target == path))
        .collect();
        let targets: Vec<_> = round
            .pages
            .iter()
            .chain(round.reports)
            .map(|(path, _)| path.clone())
            .chain(std::iter::once(index_path.clone()))
            .collect();
        facts::after_publication(&mut dependencies, root, &targets, &stale);
        let mut occurrence_ids = BTreeMap::new();
        for (page, count) in self.positions {
            for position in 0..count {
                let id = format!("o{}", occurrence_ids.len());
                occurrence_ids.insert((page.clone(), position), id);
            }
        }
        for record in self.records.values_mut() {
            record
                .occurrences
                .sort_by(|a, b| (&a.page, a.position).cmp(&(&b.page, b.position)));
            for at in &mut record.occurrences {
                at.id = occurrence_ids[&(at.page.clone(), at.position)].clone();
            }
        }
        let mut index = Index {
            format_version: 1,
            snapshot: String::new(),
            manifest: Manifest {
                generator: generator(),
                output_root: relative(root, round.output)?,
                report_owners: round.report_owners,
                config: round.config.clone(),
                config_path: relative(&round.sources.root, round.config_path)?,
                config_sources: facts::capture(round.config_sources)?,
                input_files: round.input_files,
                selections: round
                    .selections
                    .iter()
                    .map(|p| relative(&round.sources.root, p))
                    .collect::<Result<_>>()?,
                excludes: Exclusions {
                    directory_names: crate::config::EXCLUDED_DIRECTORY_NAMES
                        .iter()
                        .map(|s| (*s).into())
                        .collect(),
                    paths: round.config.inputs.exclude.clone(),
                },
                sources: facts::capture(round.sources)?,
                dependencies,
                outputs: round
                    .reports
                    .iter()
                    .chain(round.pages)
                    .map(|(path, body)| {
                        Ok((
                            relative(&round.sources.root, path)?,
                            digest(body.as_bytes()),
                        ))
                    })
                    .collect::<Result<_>>()?,
            },
            records: self.records.into_values().collect(),
        };
        index.snapshot = index.identity();
        handles::Handles::new(&index)?;
        Ok((
            index_path,
            String::from_utf8(canonical(&index)).expect("JSON is UTF-8"),
        ))
    }
}

pub struct Reader {
    index: Index,
    handles: handles::Handles,
    snapshot_only: bool,
    cancelled: std::sync::Arc<std::sync::atomic::AtomicBool>,
    timings: std::cell::Cell<Timings>,
}

/// Wall times for the public benchmark; current-file verification includes full byte hashing.
#[derive(Clone, Copy, Default, serde::Serialize)]
pub struct Timings {
    pub load_seconds: f64,
    pub freshness_seconds: f64,
    pub rank_seconds: f64,
    pub result_seconds: f64,
}

impl Reader {
    pub fn open(
        root: &Path,
        config_path: Option<&Path>,
        output: Option<&Path>,
        snapshot_only: bool,
        cancelled: std::sync::Arc<std::sync::atomic::AtomicBool>,
    ) -> Result<Self> {
        let started = std::time::Instant::now();
        crate::publication::check_cancelled(&cancelled)?;
        let root = root
            .canonicalize()
            .map_err(|e| Error::new(format!("project root: {e}")))?;
        let output =
            crate::publication::output_root(&root, output.unwrap_or(Path::new(".source-down")))?;
        let fail = |e| Error::new(format!("search index: {e}; rebuild with render"));
        let bytes =
            std::fs::read(output.join("search/index.json")).map_err(|e| fail(e.to_string()))?;
        let value = crate::json::parse(&bytes).map_err(|e| fail(e.to_string()))?;
        let index = Index::deserialize(&value).map_err(|e| fail(e.to_string()))?;
        // SPEC-SRH-002: storage decoding must preserve explicit nulls and complete configuration.
        if serde_json::to_value(&index).expect("serializable snapshot") != value {
            return Err(fail(
                "invalid snapshot structure: storage fields must be explicit".into(),
            ));
        }
        drop(value);
        if index.format_version != 1 || index.snapshot != index.identity() {
            return Err(fail(
                "unknown format version or corrupt content identity".into(),
            ));
        }
        index.validate().map_err(|e| fail(e.to_string()))?;
        let handles = handles::Handles::new(&index)?;
        let load_seconds = started.elapsed().as_secs_f64();
        let checking = std::time::Instant::now();
        if !snapshot_only {
            let stale = |e: Error| Error {
                exit_code: e.exit_code,
                message: format!("stale search index: {e}; rebuild with render"),
            };
            let mut sources = SourceStore::new(root.clone());
            let mut config = crate::config::load(&mut sources, config_path)?;
            crate::engine::validate_config(&config)?;
            crate::config::exclude_outputs(&mut config, &root, &output);
            if index.manifest.generator != generator()
                || index.manifest.output_root != relative(&root, &output)?
                || canonical(&index.manifest.config) != canonical(&config)
                || index.manifest.config_sources != facts::capture(&sources).map_err(stale)?
                || index.manifest.config_path
                    != relative(&root, config_path.unwrap_or(Path::new("source-down.toml")))?
            {
                return Err(stale(Error::new("generator or configuration changed")));
            }
            let paths: Vec<_> = index
                .manifest
                .selections
                .iter()
                .map(std::path::PathBuf::from)
                .collect();
            if crate::config::select(&sources, &config, &paths).map_err(stale)?
                != index.manifest.input_files
            {
                return Err(stale(Error::new("selected input files changed")));
            }
            facts::verify(&root, &index.manifest.sources, &|| {
                crate::publication::check_cancelled(&cancelled)
            })
            .map_err(stale)?;
            facts::verify_dependencies(&sources, &index.manifest.dependencies, &|| {
                crate::publication::check_cancelled(&cancelled)
            })
            .map_err(stale)?;
            facts::verify_outputs(&root, &index.manifest.outputs, &|| {
                crate::publication::check_cancelled(&cancelled)
            })
            .map_err(stale)?;
            let reports: Vec<_> = crate::publication::report_files(
                &root,
                &output,
                index.manifest.report_owners.iter().map(String::as_str),
                &|| crate::publication::check_cancelled(&cancelled),
            )?
            .iter()
            .map(|path| relative(&root, path))
            .collect::<Result<_>>()?;
            let report_root = relative(&root, &output.join("reports"))? + "/";
            if reports
                != index
                    .manifest
                    .outputs
                    .keys()
                    .filter(|path| path.starts_with(&report_root))
                    .cloned()
                    .collect::<Vec<_>>()
            {
                return Err(stale(Error::new("published report set changed")));
            }
        }
        Ok(Self {
            index,
            handles,
            snapshot_only,
            cancelled,
            timings: std::cell::Cell::new(Timings {
                load_seconds,
                freshness_seconds: checking.elapsed().as_secs_f64(),
                ..Timings::default()
            }),
        })
    }

    pub fn timings(&self) -> Timings {
        self.timings.get()
    }

    fn freshness(&self) -> &'static str {
        if self.snapshot_only {
            "unchecked"
        } else {
            "matched"
        }
    }
    fn handle(&self, record: &str) -> String {
        handles::derive(&self.index.snapshot, record)
    }
    fn page(
        &self,
        record: &str,
        list: &str,
        items: Vec<serde_json::Value>,
        total: usize,
        start: usize,
    ) -> serde_json::Value {
        let next = start + items.len();
        serde_json::json!({"returned":items.len(),"items":items,"total":total,"truncated":next<total,
            "next_cursor":(next<total).then(||format!("{}:{record}:{list}:{next}",self.index.snapshot))})
    }
    fn scope(&self) -> serde_json::Value {
        serde_json::json!({"handle":self.handle("scope"),"selections":self.index.manifest.selections,"excludes":self.index.manifest.excludes,
            "input_files":self.inputs("scope",0)})
    }
    fn inputs(&self, id: &str, start: usize) -> serde_json::Value {
        self.page(
            id,
            "input_files",
            self.index
                .manifest
                .input_files
                .iter()
                .skip(start)
                .take(5)
                .map(|p| serde_json::json!(p))
                .collect(),
            self.index.manifest.input_files.len(),
            start,
        )
    }
    fn link(&self, path: &str, line: Option<usize>) -> Option<String> {
        if self.snapshot_only {
            return None;
        }
        let mut link = String::new();
        use std::fmt::Write;
        for byte in path.bytes() {
            if byte.is_ascii_alphanumeric() || b"-._~/".contains(&byte) {
                link.push(byte as char);
            } else {
                write!(link, "%{byte:02X}").expect("writing a String");
            }
        }
        if let Some(line) = line {
            write!(link, "#L{line}").expect("writing a String");
        }
        Some(link)
    }
    fn origins(&self, record: &Record, start: usize) -> serde_json::Value {
        self.page(&record.id,"sources",record.sources.iter().skip(start).take(5).map(|source|serde_json::json!({
            "span":source.span,"mapping":if source.mapping.is_empty(){"provenance"}else if source.mapping.iter().map(|m|m.body[1]-m.body[0]).sum::<usize>()==record.body.len(){"complete"}else{"partial"},"current_link":self.link(&source.span.path,Some(source.span.start_line))
        })).collect(),record.sources.len(),start)
    }
    fn occurrences(&self, record: &Record, start: usize) -> serde_json::Value {
        self.page(
            &record.id,
            "occurrences",
            record
                .occurrences
                .iter()
                .skip(start)
                .take(5)
                .map(|at| {
                    let mut value = serde_json::to_value(at).expect("serializable occurrence");
                    value["current_link"] = serde_json::json!(self.link(&at.page, None));
                    value
                })
                .collect(),
            record.occurrences.len(),
            start,
        )
    }
}
