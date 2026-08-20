"""Contract boundaries for the generic SION shortage engine.

The execution engine has one supported action vocabulary. Historical tests
used a removed ``WATERFALL`` algorithm and a ``ShortageRecord`` Python type;
shortages are now data in ``DatabaseDrivenPlanResult.metadata`` and the
supported algorithm is ``SEQUENTIAL_CIF_WATERFALL``. Exact partial-allocation
behaviour is exercised end-to-end in ``test_shortage_integration.py``.
"""
from decimal import Decimal

import pytest

from apps.license.services.database_driven_sion_planner import (
    DatabaseDrivenSionPlanner,
    InvalidPlannerConfiguration,
)


def test_retired_waterfall_algorithm_is_rejected_instead_of_silently_reinterpreted():
    """Reject stale configuration rather than applying an ambiguous fallback."""
    definition = {
        "actions": [{
            "action_type": "ALLOCATE",
            "priority": 1,
            "config": {"algorithm": "WATERFALL", "order": ["PKO"]},
        }],
    }

    with pytest.raises(
        InvalidPlannerConfiguration,
        match="Unsupported allocation algorithm: WATERFALL",
    ):
        DatabaseDrivenSionPlanner().execute(definition, [], Decimal("1"))
