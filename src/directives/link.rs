//! Navigation to this round's selected reading pages. SPEC-BLT-008.
use super::{ContentOperation, Failure, OperationOutput, parameters};
use crate::{
    model::{Arguments, Dependency, MarkdownFragment, SourceStore},
    navigation::Context,
    render,
};

pub(super) struct Link;

// {% spec "blt-008" %}
impl ContentOperation for Link {
    fn call(
        &mut self,
        arguments: &Arguments,
        sources: &mut SourceStore,
        context: &Context<'_>,
    ) -> OperationOutput {
        let mut dependencies = Vec::new();
        let mut navigation = Vec::new();
        let content = (|| {
            let path = parameters(arguments, "link", &[])?;
            let dependency = Dependency::File { path: path.into() };
            let resolved = dependency
                .resolve_with_links(&sources.root)
                .map_err(|error| Failure::new("source_error", error.to_string()))?;
            dependencies.push(dependency);
            if resolved.missing.is_some() {
                return Err(Failure::new(
                    "page_not_selected",
                    format!("link {path:?}: target is not a selected page"),
                ));
            }
            // Canonicalize identity without reading the target's contents a second time.
            let canonical = sources
                .canonical_path(std::path::Path::new(path))
                .map_err(|error| Failure::new("source_error", error.to_string()))?;
            let target = context.pages.get(&canonical).ok_or_else(|| {
                Failure::new(
                    "page_not_selected",
                    format!("link {path:?}: target is not a selected page"),
                )
            })?;
            let url = render::relative_url(context.output.parent().unwrap(), target)
                .map_err(|error| Failure::new("source_error", error.to_string()))?;
            navigation.push(crate::navigation::Reference {
                query: path.into(),
                target: target.into(),
            });
            Ok(MarkdownFragment {
                markdown: url,
                sources: context.parent.into_iter().cloned().collect(),
            })
        })();
        OperationOutput {
            content,
            dependencies,
            navigation,
        }
    }
}
