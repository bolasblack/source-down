//! A project plugin composes text with standard material and page URL operations.
use serde::Deserialize;
use source_down::{
    external::protocol::{self, HostMessage, PluginMessage},
    model::*,
};
use std::{collections::BTreeMap, io};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    target: String,
    material: String,
}

fn standard(directive: &str, path: &str) -> ContentNode {
    ContentNode::StandardCall {
        directive: directive.into(),
        arguments: Arguments {
            positional: vec![path.into()],
            ..Arguments::default()
        },
    }
}

// The core computes each URL from its actual page, appendix or report position.
// {% spec "plg-007" %}
// {% spec "blt-008" %}
fn main() -> Result<()> {
    let mut input = io::stdin().lock();
    let mut output = io::stdout().lock();
    let Some(HostMessage::Initialize {
        protocol_version: 1,
        options,
        ..
    }) = protocol::read(&mut input)?
    else {
        return Err(Error::new("expected protocol version 1 initialize"));
    };
    let options: Options =
        serde_json::from_value(options).map_err(|error| Error::new(error.to_string()))?;
    protocol::write(
        &mut output,
        &PluginMessage::Ready {
            protocol_version: 1,
        },
    )?;
    while let Some(message) = protocol::read(&mut input)? {
        let HostMessage::Run {
            batch_id, requests, ..
        } = message
        else {
            return Err(Error::new("expected run"));
        };
        let navigation = Content::Blocks {
            content: vec![standard("link", &options.target)],
        };
        let results = requests
            .into_iter()
            .map(|request| PluginResult::Ok {
                id: request.id,
                content: Content::Blocks {
                    content: vec![
                        ContentNode::Text {
                            text: "Before".into(),
                            sources: vec![request.source.clone()],
                        },
                        standard("include", &options.material),
                        standard("link", &options.target),
                        ContentNode::Text {
                            text: "After".into(),
                            sources: vec![request.source],
                        },
                    ],
                },
            })
            .collect();
        protocol::write(
            &mut output,
            &PluginMessage::result(
                batch_id,
                PluginOutput {
                    results,
                    append: vec![PageAppend {
                        page: options.target.clone(),
                        content: navigation.clone(),
                    }],
                    reports: BTreeMap::from([("overview".into(), navigation)]),
                    ..PluginOutput::default()
                },
            ),
        )?;
    }
    Ok(())
}
