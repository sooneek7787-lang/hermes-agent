"""E2E: verify memory_context folds into custom_instructions through the real LCM chain.

Portable copy of ``~/.hermes/patches/hermes-lcm/test_memory_context_fold.py`` for CI.
The LCM plugin (``plugins/hermes-lcm``) is a user-specific install, not bundled in the
repo, so this test skips when the plugin is absent (e.g. upstream CI).
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

# Repo root (hermes-agent checkout) — this file lives in tests/agent/.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# The LCM plugin (``plugins/hermes-lcm``) is a user-specific install at the REAL
# home, not bundled in the repo. conftest sandboxes HERMES_HOME to a tempdir
# before this module imports, so detect the real home directly (Path.home), not
# the env var. Skip when the plugin is absent (e.g. upstream CI).
_real_home = Path.home() / ".hermes"
_LCM_PLUGIN = _real_home / "plugins" / "hermes-lcm"
if not (_LCM_PLUGIN / "compaction.py").exists():
    pytest.skip("hermes-lcm plugin not installed (user-specific)", allow_module_level=True)

# Point HERMES_HOME at the real home so the plugin manager finds the LCM plugin.
os.environ["HERMES_HOME"] = str(_real_home)

import hermes_bootstrap

from hermes_cli.plugins import get_plugin_manager

pm = get_plugin_manager()
pm.discover_and_load(force=True)

eng_obj = pm._context_engine
assert eng_obj is not None, "LCM engine not registered"

import hermes_plugins.hermes_lcm.engine as eng
import hermes_plugins.hermes_lcm.config as cfgmod


def test_memory_context_fold():
    captured = {}
    def fake_summarize(**kw):
        captured.update(kw)
        return ("SUMMARY", 0)
    eng.summarize_with_escalation = fake_summarize

    def make_self(base_instr):
        cfg = cfgmod.LCMConfig()
        cfg.custom_instructions = base_instr
        return types.SimpleNamespace(
            _config=cfg,
            _summary_circuit_breaker=None,
            _summary_spend_guard=None,
            _serialize_messages=lambda chunk: "serialized_messages",
        )

    chunk = [{"role": "user", "content": "hello"}]

    # Case 1: memory_context folded in
    eng.LCMEngine._summarize_leaf_chunk_with_rescue(
        make_self("BASE_INSTR"), chunk, memory_context="FACTS: fact1, fact2"
    )
    ci = captured["custom_instructions"]
    assert "FACTS: fact1, fact2" in ci, f"missing memory_context: {ci!r}"
    assert "BASE_INSTR" in ci, "base lost"

    # Case 2: no memory_context (back-compat)
    captured.clear()
    eng.LCMEngine._summarize_leaf_chunk_with_rescue(make_self("BASE_INSTR"), chunk)
    assert captured["custom_instructions"] == "BASE_INSTR", \
        f"back-compat broken: {captured.get('custom_instructions')!r}"

    # Case 3: empty base + memory_context
    captured.clear()
    eng.LCMEngine._summarize_leaf_chunk_with_rescue(
        make_self(""), chunk, memory_context="ONLY_FACTS"
    )
    assert captured["custom_instructions"] == "ONLY_FACTS", \
        f"empty base + memory_context: {captured.get('custom_instructions')!r}"
