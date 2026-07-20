"""
PlannerFactory — extensible dispatch layer for Auto Plan norms.

Adding a new norm (E2, E3, E6, …) requires only two things:
  1. Create backend/apps/license/services/<norm>_auto_plan.py that exposes
     ``compute_<norm>_auto_plan(license_obj) → (lines, remaining_cif)``.
  2. Register it here with ``PlannerFactory.register(...)``.

Nothing in the management command or the API endpoint needs to change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable


@dataclass
class PlanResult:
    """Return type from PlannerFactory.run()."""
    lines: list[dict] = field(default_factory=list)
    remaining_cif: float = 0.0


# ── Registry ──────────────────────────────────────────────────────────────────

# norm_code → callable(license_obj) → (lines, remaining_cif)
_REGISTRY: dict[str, Callable] = {}


def _load_defaults() -> None:
    """Lazily register built-in norm planners to avoid circular imports."""
    if _REGISTRY:
        return
    from apps.license.services.e1_auto_plan import compute_e1_auto_plan
    from apps.license.services.e5_auto_plan import compute_e5_auto_plan
    from apps.license.services.e132_auto_plan import compute_e132_auto_plan
    _REGISTRY['E1']  = compute_e1_auto_plan
    _REGISTRY['E5']  = compute_e5_auto_plan
    _REGISTRY['E132'] = compute_e132_auto_plan


class PlannerFactory:
    """Static facade for norm-planner dispatch."""

    @staticmethod
    def register(norm_code: str, fn: Callable) -> None:
        """Register a planner for *norm_code* (e.g. 'E6').

        Args:
            norm_code: Upper-case norm identifier matching detect_norm() output.
            fn: Callable ``fn(license_obj) → (lines, remaining_cif)``.
        """
        _REGISTRY[norm_code] = fn

    @staticmethod
    def supported_norms() -> list[str]:
        _load_defaults()
        return sorted(_REGISTRY)

    @staticmethod
    def is_supported(norm_code: str) -> bool:
        _load_defaults()
        return norm_code in _REGISTRY

    @staticmethod
    def run(license_obj, norm_code: str) -> PlanResult:
        """Execute the planner for *norm_code* against *license_obj*.

        Returns:
            PlanResult with the generated lines and remaining CIF.

        Raises:
            ValueError: when *norm_code* is not registered.
            Any exception raised by the underlying planner (callers should
            catch broadly and isolate failures per-license).
        """
        _load_defaults()
        fn = _REGISTRY.get(norm_code)
        if fn is None:
            raise ValueError(
                f"No planner registered for norm '{norm_code}'. "
                f"Supported: {', '.join(sorted(_REGISTRY))}"
            )
        lines, remaining_cif = fn(license_obj)
        return PlanResult(lines=lines, remaining_cif=remaining_cif)
