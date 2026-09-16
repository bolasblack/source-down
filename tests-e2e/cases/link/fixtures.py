"""Fixed file preparation for the link scenarios; no commands or expectations."""
import json
import shutil
from support.protocol import writeReportReply


def inlineLanguageFiles(prose):
    return {
        "index.md": prose + "\r\n",
        "index.rs": "// " + prose + "\r\nfn main() {}\r\n",
        "index.ml": "(* " + prose + " *)\r\nlet x = 1\r\n",
        "index.js": "// " + prose + "\r\nconst x = 1;\r\n",
        "index.ts": "// " + prose + "\r\nconst x: number = 1;\r\n",
        "index.go": "// " + prose + "\r\npackage main\r\n",
        "index.py": "# " + prose + "\r\nx = 1\r\n",
    }


def wordsPluginFiles(case):
    return {
        "source-down.toml": 'config_version=1\n[plugins.words]\n'
                            'command=["python","plugin.py"]\ndirectives=["words"]\n',
        "plugin.py": case.fixture("link/words.py"),
        "e2e_wire.py": case.fixture("plugin_wire.py"),
    }


def navigationPluginFiles(case, *, target, material, projectText, directives, override):
    return {
        "source-down.toml": 'config_version=1\n[plugins.navigation]\n'
                            'command=["python","plugin.py"]\n'
                            + 'directives=' + json.dumps(directives) + '\n'
                            + 'override=' + json.dumps(override) + '\n'
                            + '[plugins.navigation.options]\n'
                            + 'target=' + json.dumps(target) + '\n'
                            + 'material=' + json.dumps(material) + '\n'
                            + 'project_text=' + json.dumps(projectText) + '\n',
        "plugin.py": case.fixture("link/navigation.py"),
        "e2e_wire.py": case.fixture("plugin_wire.py"),
    }


def reportPluginFiles(case):
    return {
        "source-down.toml": 'config_version=1\n[plugins.report]\n'
                            'command=["python","report.py"]\ndirectives=["report"]\n',
        "report.py": case.fixture("link/report.py"),
        "e2e_wire.py": case.fixture("plugin_wire.py"),
    }


def installRustNavigationPlugin(project, *, artifact, target, material):
    plugin = project.root / artifact.name
    shutil.copy2(artifact, plugin)
    project.writeFiles({
        "source-down.toml": 'config_version=1\n[plugins.navigation]\n'
                            + 'command=[' + json.dumps(str(plugin)) + ']\ndirectives=["compose"]\n'
                            + '[plugins.navigation.options]\n'
                            + 'target=' + json.dumps(target) + '\n'
                            + 'material=' + json.dumps(material) + '\n',
    })
