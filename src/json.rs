//! Strict protocol JSON: serde_json::Value alone would silently lose duplicate keys.
use crate::model::{Error, Result};
use serde::de::{self, Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
use serde_json::{Map, Number, Value};
use std::fmt;

struct Strict(Value);
impl<'de> Deserialize<'de> for Strict {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> std::result::Result<Self, D::Error> {
        struct Values;
        impl<'de> Visitor<'de> for Values {
            type Value = Strict;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                f.write_str("interoperable JSON")
            }
            fn visit_unit<E: de::Error>(self) -> std::result::Result<Strict, E> {
                Ok(Strict(Value::Null))
            }
            fn visit_bool<E: de::Error>(self, v: bool) -> std::result::Result<Strict, E> {
                Ok(Strict(v.into()))
            }
            fn visit_str<E: de::Error>(self, v: &str) -> std::result::Result<Strict, E> {
                Ok(Strict(v.into()))
            }
            fn visit_string<E: de::Error>(self, v: String) -> std::result::Result<Strict, E> {
                Ok(Strict(v.into()))
            }
            fn visit_i64<E: de::Error>(self, v: i64) -> std::result::Result<Strict, E> {
                if v.unsigned_abs() > 9_007_199_254_740_991 {
                    return Err(E::custom("integer outside safe range"));
                }
                Ok(Strict(v.into()))
            }
            fn visit_u64<E: de::Error>(self, v: u64) -> std::result::Result<Strict, E> {
                if v > 9_007_199_254_740_991 {
                    return Err(E::custom("integer outside safe range"));
                }
                Ok(Strict(v.into()))
            }
            fn visit_f64<E: de::Error>(self, v: f64) -> std::result::Result<Strict, E> {
                if !v.is_finite() || (v.fract() == 0.0 && v.abs() > 9_007_199_254_740_991.0) {
                    return Err(E::custom("number outside safe range"));
                }
                Ok(Strict(Value::Number(Number::from_f64(v).unwrap())))
            }
            fn visit_seq<A: SeqAccess<'de>>(
                self,
                mut seq: A,
            ) -> std::result::Result<Strict, A::Error> {
                let mut values = vec![];
                while let Some(Strict(v)) = seq.next_element()? {
                    values.push(v);
                }
                Ok(Strict(Value::Array(values)))
            }
            fn visit_map<A: MapAccess<'de>>(
                self,
                mut map: A,
            ) -> std::result::Result<Strict, A::Error> {
                let mut values = Map::new();
                while let Some(key) = map.next_key::<String>()? {
                    if values.contains_key(&key) {
                        return Err(de::Error::custom(format!("duplicate JSON key: {key}")));
                    }
                    let Strict(value) = map.next_value()?;
                    values.insert(key, value);
                }
                Ok(Strict(Value::Object(values)))
            }
        }
        deserializer.deserialize_any(Values)
    }
}
pub fn parse(bytes: &[u8]) -> Result<Value> {
    serde_json::from_slice::<Strict>(bytes)
        .map(|s| s.0)
        .map_err(|e| Error::new(format!("invalid protocol JSON: {e}")))
}

pub(crate) fn validate(value: &Value) -> Result<()> {
    Strict::deserialize(value)
        .map(|_| ())
        .map_err(|e| Error::new(format!("invalid protocol JSON: {e}")))
}

pub(crate) fn prefix(text: &str) -> Result<(Value, usize)> {
    let mut values = serde_json::Deserializer::from_str(text).into_iter::<Strict>();
    let value = values
        .next()
        .ok_or_else(|| Error::new("expected JSON value"))?
        .map_err(|error| Error::new(format!("invalid JSON value: {error}")))?;
    Ok((value.0, values.byte_offset()))
}
