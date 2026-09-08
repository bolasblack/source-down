use super::*;
use serde_json::{Value, json};

pub(super) const BODY_BUDGET: usize = 12000;

#[derive(Default)]
pub struct ReadOptions {
    pub offset: Option<usize>,
    pub context: Option<usize>,
    pub occurrence: Option<String>,
    pub cursor: Option<String>,
}

impl ReadOptions {
    pub fn validate(&self) -> Result<()> {
        if self.cursor.is_some()
            && (self.offset.is_some() || self.context.is_some() || self.occurrence.is_some())
        {
            return Err(Error::config(
                "cursor cannot be combined with body or context options",
            ));
        }
        if self.context.unwrap_or(0) > 5 {
            return Err(Error::config("context must be 0..5"));
        }
        Ok(())
    }
}

pub(super) fn slice(text: &str, offset: usize, budget: usize) -> Result<Value> {
    if offset > text.len() || !text.is_char_boundary(offset) {
        return Err(Error::config(
            "offset must be a UTF-8 byte boundary within the fragment",
        ));
    }
    let end = text[offset..]
        .char_indices()
        .nth(budget)
        .map_or(text.len(), |(at, _)| offset + at);
    Ok(
        json!({"text":&text[offset..end],"range":[offset,end],"total_bytes":text.len(),"truncated":end<text.len(),"next_offset":(end<text.len()).then_some(end)}),
    )
}

impl Reader {
    // {% spec "srh-006" %}
    pub fn read(&self, handle: &str, options: &ReadOptions) -> Result<Value> {
        options.validate()?;
        crate::publication::check_cancelled(&self.cancelled)?;
        let id = self.handles.resolve(handle)?;
        let record = self.index.records.iter().find(|record| record.id == id);
        if let Some(cursor) = &options.cursor {
            let invalid = || Error::new("invalid cursor for this snapshot, record or list");
            let tail = cursor
                .strip_prefix(&format!("{}:{id}:", self.index.snapshot))
                .ok_or_else(invalid)?;
            let (list, offset) = tail.split_once(':').ok_or_else(invalid)?;
            let offset: usize = offset.parse().map_err(|_| invalid())?;
            if offset == 0 || !offset.is_multiple_of(5) {
                return Err(invalid());
            }
            let page = match (list, record) {
                ("input_files", _) => {
                    self.inputs(record.map_or("scope", |r| r.id.as_str()), offset)
                }
                ("sources", Some(record)) => self.origins(record, offset),
                ("occurrences", Some(record)) => self.occurrences(record, offset),
                _ => return Err(invalid()),
            };
            if offset >= page["total"].as_u64().unwrap() as usize {
                return Err(invalid());
            }
            return Ok(
                json!({"format_version":1,"snapshot":self.index.snapshot,"freshness":self.freshness(),"handle":handle,
                "kind":record.map(|r|r.kind),"scope":null,"body":null,"context":[],"sources":null,"occurrences":null,
                "continuation":{"list":list,"page":page}}),
            );
        }
        let budget = BODY_BUDGET;
        let Some(record) = record else {
            if options.offset.is_some() || options.context.is_some() || options.occurrence.is_some()
            {
                return Err(Error::config("scope has no body or occurrence"));
            }
            return Ok(
                json!({"format_version":1,"snapshot":self.index.snapshot,"freshness":self.freshness(),"handle":handle,
                "kind":null,"scope":self.scope(),"body":null,"context":[],"sources":null,"occurrences":null,"continuation":null}),
            );
        };
        let context_count = options.context.unwrap_or(0);
        let at = if let Some(id) = &options.occurrence {
            record
                .occurrences
                .iter()
                .find(|at| &at.id == id)
                .ok_or_else(|| Error::new("unknown occurrence for this record"))?
        } else {
            if context_count > 0 && record.occurrences.len() > 1 {
                return Err(Error::new(
                    "choose --occurrence for a record with multiple occurrences",
                ));
            }
            &record.occurrences[0]
        };
        let body = slice(&record.body, options.offset.unwrap_or(0), budget)?;
        let mut remaining = budget - body["text"].as_str().unwrap().chars().count();
        let mut neighbours: Vec<_> = self
            .index
            .records
            .iter()
            .flat_map(|r| r.occurrences.iter().map(move |o| (r, o)))
            .filter(|(_, o)| {
                o.page == at.page
                    && o.position != at.position
                    && o.position.abs_diff(at.position) <= context_count
            })
            .collect();
        neighbours.sort_by_key(|(_, at)| at.position);
        let mut context = vec![];
        for (record, at) in neighbours {
            let body = slice(&record.body, 0, remaining)?;
            remaining -= body["text"].as_str().unwrap().chars().count();
            context.push(json!({"handle":self.handle(&record.id),"occurrence":at.id,"body":body}));
        }
        Ok(
            json!({"format_version":1,"snapshot":self.index.snapshot,"freshness":self.freshness(),"handle":handle,
            "kind":record.kind,"scope":self.scope(),"body":body,"context":context,"sources":self.origins(record,0),
            "occurrences":self.occurrences(record,0),"continuation":null}),
        )
    }
}
