"""Filter conditions for the licence import description mapping table (owner specs 2026-11-19, "advanced filters" and
"nested filter condition groups — match Licence Planning").

Filters only SELECT description rows; they never define a mapping identity (that is always the strict
``description_key`` of one description). One implementation, used by the listing and by bulk-update revalidation, so
what the user sees is exactly what a bulk update touches.

Shape — the Licence Planning rule-builder tree (``sion_rule_engine``): a group is
``{"operator": "AND" | "OR", "conditions": [<condition or group>, ...]}`` (``ALL`` / ``ANY`` are accepted as aliases;
a separate ``"groups"`` list is merged after ``conditions``), and a condition is
``{"field": "description" | "hsn" | "sion", "op": <operator>, "value": str}``. Like Planning: at most ``MAX_DEPTH``
levels and ``MAX_NODES`` nodes; empty nested groups are pruned. Unlike a Planning rule (whose empty root matches
nothing), an empty root here means "no filter" — every row matches. The earlier flat payload
``{"logic": "all" | "any", "conditions": [...]}`` is still accepted.

A row can carry several original wordings / HSN codes / SION norms:

* positive operators (contains, starts_with, ends_with, equals, not_empty) are true when ANY value satisfies them;
* negative operators (not_contains, not_starts_with, not_ends_with, not_equals, empty) are the exact negation of their
  positive counterpart — true when NO value satisfies it.

Description text is compared case-insensitively ("equals" compares the strict description keys). HSN / SION are compared
as code strings (upper-cased, never numeric), so leading zeros are preserved.
"""
from __future__ import annotations

from typing import Any

from apps.license.services.product_intelligence.description_mapping import description_key

FIELDS = ("description", "hsn", "sion")
POSITIVE = {"contains", "starts_with", "ends_with", "equals", "not_empty"}
NEGATION = {"not_contains": "contains", "not_starts_with": "starts_with", "not_ends_with": "ends_with",
            "not_equals": "equals", "empty": "not_empty"}
OPERATORS = POSITIVE | set(NEGATION)
GROUP_OPERATORS = {"AND": "AND", "OR": "OR", "ALL": "AND", "ANY": "OR"}
MAX_DEPTH = 12   # same limits as the Licence Planning rule engine (sion_rule_engine)
MAX_NODES = 128
MAX_VALUE = 200
EMPTY = {"operator": "AND", "conditions": []}


class FilterError(ValueError):
    pass


_GROUP_KEYS = {"operator", "logic", "conditions", "groups", "id"}
_LEAF_KEYS = {"field", "op", "value", "id"}


def _kind(node: Any, where: str) -> str:
    """Strictly classify a node as "group" or "leaf" — never guess (a mis-classified node must not silently vanish)."""
    if not isinstance(node, dict):
        raise FilterError(f"{where}: every filter node must be an object")
    keys = set(node)
    if keys & {"field", "op"} and not keys & {"conditions", "groups", "operator", "logic"} and keys <= _LEAF_KEYS:
        return "leaf"
    if keys & {"conditions", "groups", "operator", "logic"} and not keys & {"field", "op", "value"} and keys <= _GROUP_KEYS:
        return "group"
    raise FilterError(f"{where}: not a valid condition ({{field, op, value}}) or group ({{operator, conditions}})")


def clean_filters(raw: Any) -> dict:
    """Validate + normalise a filter payload → ``{"operator": "AND"|"OR", "conditions": [...]}`` (raises FilterError).
    The root must be a group; only genuinely empty nested groups are pruned."""
    if raw in (None, "", {}):
        return dict(EMPTY, conditions=[])
    if _kind(raw, "Filter") != "group":
        raise FilterError("Filter: the root must be a group ({operator, conditions})")
    count = 0

    def bump(where: str, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_NODES:
            raise FilterError(f"Filters are too large (max {MAX_NODES} conditions and groups)")
        if depth > MAX_DEPTH:
            raise FilterError(f"Filters are too deeply nested (max {MAX_DEPTH} levels) at {where}")

    def group(node: dict, path: str, depth: int) -> dict | None:
        """``path``: "" for the root, else "2", "2.1", … (matches the editor's labels)."""
        where = f"Group {path}" if path else "Filter"
        bump(where, depth)
        op = node.get("operator", node.get("logic", "AND"))
        if not isinstance(op, str) or op.strip().upper() not in GROUP_OPERATORS:
            raise FilterError(f"{where}: logic must be ALL or ANY")
        children, extra = node.get("conditions") or [], node.get("groups") or []
        if not isinstance(children, list) or not isinstance(extra, list):
            raise FilterError(f"{where}: conditions / groups must be lists")
        out = []
        for n, child in enumerate([*children, *extra], 1):
            child_path = f"{path}.{n}" if path else str(n)
            if _kind(child, f"Condition {child_path}") == "group":
                cleaned = group(child, child_path, depth + 1)
            else:
                cleaned = leaf(child, f"Condition {child_path}", depth + 1)
            if cleaned is not None:
                out.append(cleaned)
        if not out and path:
            return None  # empty nested group: carries no predicate (pruned, as in Licence Planning)
        return {"operator": GROUP_OPERATORS[op.strip().upper()], "conditions": out}

    def leaf(c: dict, where: str, depth: int) -> dict:
        bump(where, depth)
        if not isinstance(c.get("field"), str) or not isinstance(c.get("op"), str) or c["field"] not in FIELDS or c["op"] not in OPERATORS:
            raise FilterError(f"{where}: unknown field or operator")
        value = c.get("value", "")
        if not isinstance(value, str) or len(value) > MAX_VALUE:
            raise FilterError(f"{where}: value must be text (max {MAX_VALUE} characters)")
        value = value.strip()
        if c["op"] not in ("empty", "not_empty") and not value:
            raise FilterError(f"{where}: a value is required")
        return {"field": c["field"], "op": c["op"], "value": value}

    return group(raw, "", 0)


def _positive(op: str, values: list[str], value: str, field: str) -> bool:
    if op == "not_empty":
        return any(v and v.strip() for v in values)
    if field == "description":
        if op == "equals":
            target = description_key(value)
            return any(description_key(v) == target for v in values)
        needle = value.casefold()
        hay = [v.casefold() for v in values]
    else:
        needle = value.strip().upper()
        hay = [v.strip().upper() for v in values if v]
    if op == "contains":
        return any(needle in v for v in hay)
    if op == "starts_with":
        return any(v.startswith(needle) for v in hay)
    if op == "ends_with":
        return any(v.endswith(needle) for v in hay)
    if op == "equals":
        return any(v == needle for v in hay)
    raise FilterError(f"Unknown operator {op}")


def _condition(row_values: dict[str, list[str]], c: dict) -> bool:
    values = [v for v in row_values.get(c["field"], []) if v is not None]
    if c["op"] in NEGATION:
        return not _positive(NEGATION[c["op"]], values, c["value"], c["field"])
    return _positive(c["op"], values, c["value"], c["field"])


def _group(row_values: dict[str, list[str]], g: dict) -> bool:
    results = (_group(row_values, n) if "conditions" in n else _condition(row_values, n) for n in g["conditions"])
    return all(results) if g["operator"] == "AND" else any(results)


def matches(row_values: dict[str, list[str]], filters: dict) -> bool:
    """``row_values``: {"description": [wordings], "hsn": [codes], "sion": [codes]}; ``filters`` from ``clean_filters``.
    Recursive: every group keeps its own ALL / ANY logic. An empty root matches every row."""
    if not filters or not filters.get("conditions"):
        return True
    return _group(row_values, filters)


def describe(filters: dict) -> str:
    """Human-readable form for audit / confirmation, e.g. ``(description contains "OIL") AND (hsn starts_with "1511" OR …)``."""
    def node(n: dict) -> str:
        if "conditions" in n:
            return "(" + f" {n['operator']} ".join(node(c) for c in n["conditions"]) + ")"
        return f'{n["field"]} {n["op"]}' + ("" if n["op"] in ("empty", "not_empty") else f' "{n["value"]}"')
    return node(filters) if filters and filters.get("conditions") else ""
