#!/usr/bin/env python3
"""
Shared utilities for Agent Centric framework.

Managed by: agent-centric skill
DO NOT MODIFY THIS FILE - it will be automatically updated from the skill directory.
To disable auto-update, add this filename to disableAutoUpdateScripts in config.json.
"""

import json
import re
import subprocess
from pathlib import Path

# Constants
AGENTS_DIR = '.agents'
DECISIONS_DIR = 'decisions'
AGD_PATTERN = 'AGD-*.md'
RELATION_FIELDS = [('obsoletes', 'o'), ('updates', 'u'), ('related', 'r')]
REVERSE_REF_FIELDS = {'obsoletes': 'obsoleted_by', 'updates': 'updated_by'}
FORWARD_REF_FIELDS = [field for field, _ in RELATION_FIELDS]
MANAGED_REVERSE_REF_FIELDS = list(REVERSE_REF_FIELDS.values())
REF_FIELDS = MANAGED_REVERSE_REF_FIELDS + FORWARD_REF_FIELDS


def get_agd_id(filename: str) -> str | None:
    """Extract AGD ID from filename (e.g., AGD-001 from AGD-001_name.md)."""
    match = re.match(r'(AGD-\d+)', filename)
    return match.group(1) if match else None


def get_agd_sort_key(path: str) -> int:
    """Extract AGD number as integer for sorting."""
    match = re.search(r'AGD-(\d+)', path)
    return int(match.group(1)) if match else 0


def find_agd_file(decisions_dir: Path, agd_ref: str) -> Path | None:
    """Find AGD file by its number reference."""
    agd_id = get_agd_id(agd_ref)
    if not agd_id:
        return None

    for f in decisions_dir.glob(f'{agd_id}_*.md'):
        return f
    return None


def get_decisions_dir(project_dir: Path) -> Path:
    """Get the decisions directory path."""
    return project_dir / AGENTS_DIR / DECISIONS_DIR


def get_agents_dir(project_dir: Path) -> Path:
    """Get the .agents directory path."""
    return project_dir / AGENTS_DIR


def load_config(project_dir: Path) -> dict:
    """Load .agents/config.json if present and valid."""
    config_path = get_agents_dir(project_dir) / 'config.json'
    if not config_path.exists():
        return {}

    try:
        with open(config_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def resolve_agents_script(project_dir: Path, script_path: str) -> Path:
    """Resolve a configured script path relative to .agents/config.json."""
    path = Path(script_path)
    if not script_path or not path.parts or path.is_absolute() or '..' in path.parts:
        raise ValueError(f"invalid script path '{script_path}'")

    agents_dir = get_agents_dir(project_dir).resolve()
    resolved = (agents_dir / path).resolve()
    if agents_dir != resolved and agents_dir not in resolved.parents:
        raise ValueError(f"script path escapes config directory: '{script_path}'")
    if not resolved.is_file():
        raise ValueError(f"script does not exist: '{script_path}'")
    return resolved


def run_configured_scripts(project_dir: Path, config_key: str) -> None:
    """Run scripts configured relative to .agents/config.json with project dir as argv[1]."""
    config = load_config(project_dir)
    script_paths = config.get(config_key, [])
    if not script_paths:
        return
    if not isinstance(script_paths, list) or not all(isinstance(path, str) for path in script_paths):
        raise ValueError(f"config.{config_key} must be a string array")

    for script_path in script_paths:
        script = resolve_agents_script(project_dir, script_path)
        subprocess.run([str(script), str(project_dir)], cwd=project_dir, check=True)
