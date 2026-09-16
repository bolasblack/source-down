"""Concrete guide destinations and source expectations shared by refresh scenarios."""

# The authored guide composes link directives. Expected URLs are independent
# literals, so these checks do not reproduce the directive evaluator.
guidePages = {
    "docs/guide/index.md": (
        "reading-source.md.md#reading-source", "expanding-directives.md.md#expanding-directives",
        "building-pages.md.md#building-pages", "searching.md.md#searching",
    ),
    "docs/guide/reading-source.md": ("expanding-directives.md.md#expanding-directives",),
    "docs/guide/expanding-directives.md": (
        "reading-source.md.md#parse-source", "building-pages.md.md#building-pages",
    ),
    "docs/guide/building-pages.md": (
        "expanding-directives.md.md#directive-routing", "index.md.md#source-down-book",
    ),
}
def assertGuideNavigation(case, reading):
    for page, urls in guidePages.items():
        case.assertPageLinks(reading, fromPage=page, to=urls)


def assertGuideSources(case, reading):
    excerpts = case.assertSourceExcerptsMatchOriginals(
        reading, inPagesUnder="docs/guide", language="rust",
        exactlyFrom=["src/source.rs", "src/engine.rs", "src/render.rs", "src/model.rs"],
    )
    case.assertSameExcerptOnDifferentPages(
        reading, source="src/source.rs", inPagesUnder="docs/guide", language="rust", times=2,
    )
    return excerpts
