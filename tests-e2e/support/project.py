"""Prepare a mutable copy of this project; case files own its acceptance rules."""
from contextlib import contextmanager
import shutil
from .case import E2ECase


class SelfUseCase(E2ECase):
    @contextmanager
    def self_use(self):
        with self.project() as project:
            for name in ("src", "docs/specs", "docs/guide", "tools", "tests", "examples"):
                shutil.copytree(self.context.repository / name, project.root / name,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            # The tested project contains the same E2E source that this run loaded.
            shutil.copytree(self.context.run / "tests-e2e", project.root / "tests-e2e",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for name in ("Cargo.toml", "source-down.toml"):
                shutil.copy2(self.context.repository / name, project.root / name)
            (project.root / "docs/engineering").mkdir(exist_ok=True)
            shutil.copy2(self.context.run / "docs/engineering/search-queries.json",
                         project.root / "docs/engineering/search-queries.json")
            plugin = project.root / "target/release/examples" / self.context.spec_plugin.name
            plugin.parent.mkdir(parents=True)
            shutil.copy2(self.context.spec_plugin, plugin)
            yield project


def markdown_snapshot(project, output=".source-down"):
    return {name: data for name, data in project.snapshot(output).items() if name.endswith(".md")}
