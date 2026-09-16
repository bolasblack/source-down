"""Observe one real plugin wire exchange without choosing its request semantics."""
import json
from .source_down import CommandResult


def writeReportReply(project, *, reports, diagnostics):
    project.writeFiles({"state.txt": json.dumps({"reports": reports, "diagnostics": diagnostics})})


class ProtocolResult(CommandResult):
    @property
    def messages(self):
        return [json.loads(line) for line in self._command.stdout.splitlines()]


class SpecPlugin:
    def __init__(self, project):
        self.project = project

    def runRequest(self, *, protocolVersion, plugin, options, batchId, inputFiles,
                   requestId, directive, arguments, source):
        return self.exchange([
            {"type": "initialize", "protocol_version": protocolVersion, "plugin": plugin,
             "project_root": str(self.project.root), "options": options},
            {"type": "run", "batch_id": batchId, "input_files": inputFiles,
             "requests": [{"id": requestId, "directive": directive,
                           "arguments": arguments, "source": source}]},
        ])

    def exchange(self, messages, *, timeout=30):
        project = self.project
        binary = project.root / "target/release/examples" / project.context.spec_plugin.name
        wire = "".join(json.dumps(message) + "\n" for message in messages).encode("utf-8")
        return ProtocolResult(project.context.command([binary], cwd=project.root, input=wire, timeout=timeout))
