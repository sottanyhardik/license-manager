"""
Regression test for the ledger-upload `logger` NameError.

`scripts.parse_ledger.create_object()` logs dispute flag/resolve activity via a
module-level `logger`. That symbol was referenced but never defined/imported, so
every re-upload that flagged or resolved a dispute row raised
`NameError: name 'logger' is not defined` — caught per-license by the upload view
and surfaced to the user as a failed license.

These tests pin the module-level `logger` so the regression can't return. They are
intentionally DB-free: the bug is a missing module symbol, not a data condition.
"""
import logging

import pytest

import scripts.parse_ledger as parse_ledger


@pytest.mark.unit
def test_module_defines_logger():
    """The module must expose a real Logger named `logger`."""
    assert hasattr(parse_ledger, "logger"), "scripts.parse_ledger is missing a module-level `logger`"
    assert isinstance(parse_ledger.logger, logging.Logger)


@pytest.mark.unit
def test_dispute_logging_calls_resolve_in_module_namespace():
    """
    The exact dispute-logging statements from create_object() must resolve the
    `logger` name in the module namespace. Before the fix this raised NameError.
    """
    namespace = parse_ledger.__dict__

    # Mirror the two logging statements in _create_object_inner (the flagged/resolved path).
    eval(
        compile(
            "logger.warning('Ledger upload: %d row(s) not found in ledger — flagged as dispute for %s', 1, 'TEST')",
            "<dispute-flagged>",
            "exec",
        ),
        namespace,
    )
    eval(
        compile(
            "logger.info('Ledger upload: %d dispute(s) resolved for %s', 1, 'TEST')",
            "<dispute-resolved>",
            "exec",
        ),
        namespace,
    )
