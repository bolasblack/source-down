"""Install the fixed directory-facts plugin with explicit dependency data."""
import json


def directoryFactsPluginFiles(case, *, dependencies):
    return {
        "plugin.py": case.fixture("search/directory_facts.py"),
        "e2e_wire.py": case.fixture("plugin_wire.py"),
        "dependencies.json": json.dumps(dependencies),
        "source-down.toml": "config_version=1\n[plugins.project]\ncommand=['python','plugin.py']\n",
    }
