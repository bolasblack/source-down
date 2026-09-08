//! # Source Down
//!
//! {% package "Build identity" %}
//!
//! {% modules %}
//!
// {% spec "mod-001" %}
//! Source Down's reusable source and plugin model.

pub mod config;
pub mod directives;
pub mod engine;
pub mod external;
mod filesystem;
pub mod json;
pub mod lang;
pub mod markdown;
pub mod model;
mod navigation;
pub mod platform;
mod prose;
mod publication;
pub mod render;
pub mod results;
pub mod search;
mod selection;
pub mod source;
pub mod watch;
