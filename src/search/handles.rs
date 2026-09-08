//! Public aliases retain complete snapshot and target identities. SPEC-SRH-002.
use super::{Index, Result};
use crate::model::Error;
use std::collections::BTreeMap;
use xxhash_rust::xxh64::xxh64;

pub(super) struct Handles(BTreeMap<String, String>);

impl Handles {
    pub fn new(index: &Index) -> Result<Self> {
        Self::collect(
            index
                .records
                .iter()
                .map(|record| record.id.as_str())
                .chain(std::iter::once("scope"))
                .map(|target| (derive(&index.snapshot, target), target.to_owned())),
        )
    }

    fn collect(pairs: impl IntoIterator<Item = (String, String)>) -> Result<Self> {
        let mut targets = BTreeMap::new();
        for (handle, target) in pairs {
            if let Some(previous) = targets.insert(handle.clone(), target.clone())
                && previous != target
            {
                return Err(Error::new(format!(
                    "search index: handle collision {handle}: {previous} and {target}"
                )));
            }
        }
        Ok(Self(targets))
    }

    pub fn resolve(&self, handle: &str) -> Result<&str> {
        if handle.len() != 11 || !handle.bytes().all(|byte| byte.is_ascii_alphanumeric()) {
            return Err(Error::new(
                "invalid search handle; search again for an 11-character handle",
            ));
        }
        self.0
            .get(handle)
            .map(String::as_str)
            .ok_or_else(|| Error::new("unknown handle in this snapshot; search again"))
    }
}

pub(super) fn derive(snapshot: &str, target: &str) -> String {
    let (kind, record) = if target == "scope" {
        ("scope", None)
    } else {
        ("record", Some(target))
    };
    let input = serde_json::to_vec(&serde_json::json!([
        "source-down.handle.v1",
        snapshot,
        kind,
        record
    ]))
    .expect("serializable handle identity");
    base62(xxh64(&input, 0))
}

fn base62(mut value: u64) -> String {
    const ALPHABET: &[u8] = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
    let mut digits = [b'0'; 11];
    for digit in digits.iter_mut().rev() {
        *digit = ALPHABET[(value % 62) as usize];
        value /= 62;
    }
    String::from_utf8(digits.to_vec()).expect("ASCII Base62")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spec_srh_002_fixed_xxh64_and_base62_vectors() {
        assert_eq!(xxh64(b"", 0), 0xef46db3751d8e999);
        for (value, expected) in [
            (0, "00000000000"),
            (1, "00000000001"),
            (61, "0000000000z"),
            (62, "00000000010"),
            (u64::MAX, "LygHa16AHYF"),
        ] {
            assert_eq!(base62(value), expected);
        }
        let snapshot = "0".repeat(64);
        assert_eq!(derive(&snapshot, &"1".repeat(64)), "84ohrcc0RGh");
        assert_eq!(derive(&snapshot, "scope"), "AgjJUbKTXum");
    }

    #[test]
    fn spec_srh_002_mapping_rejects_both_collision_classes() {
        for targets in [["record-a", "record-b"], ["record-a", "scope"]] {
            let error =
                Handles::collect(targets.map(|target| ("00000000000".into(), target.into())))
                    .err()
                    .expect("different targets must collide");
            assert!(error.message.contains("collision 00000000000"));
            for target in targets {
                assert!(error.message.contains(target));
            }
        }
        assert!(Handles::collect(vec![("00000000000".into(), "same".into()); 2]).is_ok());
    }
}
