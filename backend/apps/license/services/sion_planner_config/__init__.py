"""Audited, deterministic configuration used to seed DB-driven planners.

These documents are migration inputs, not runtime dispatch tables.  They do
not import the legacy planners, so applying them cannot silently change when
legacy implementation code changes.
"""

from .e1_e5 import LEGACY_PLANNER_CONFIGS

__all__ = ["LEGACY_PLANNER_CONFIGS"]
