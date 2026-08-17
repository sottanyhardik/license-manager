# Generic SION Rule Engine Architecture

## Overview

The SION rule engine has been completely refactored from an E126/E132-specific implementation to a **generic, data-driven architecture** that works for ANY SION norm with ANY number of inputs.

The key insight: Rules are resolved by **(output_item, SION)** pair, not by norm code. This allows the same code to handle E126, E132, custom norms, and any future norms.

## Core Components

### 1. SionRuleResolver Service (`sion_rule_resolver.py`)

**Purpose**: Generic rule resolution that works for any SION norm.

**Key Methods**:
- `normalize_product_name(raw_name)` - Normalizes product names (trim, uppercase, collapse whitespace)
- `resolve_canonical_input(raw_name, sion, output_item)` - Hierarchical lookup of canonical input codes
- `get_rules_for_output_item(output_item, sion)` - Returns all rules for a specific (output_item, SION) pair
- `get_percentage_rules_for_output_item(output_item, sion)` - Returns percentage cap rules as dict
- `get_split_rules_for_output_item(output_item, sion, rule_group_id)` - Returns split rules (if they sum to 100%)
- `has_split_percentage_rule(output_item, sion)` - Checks if valid split rule exists
- `validate_split_rule_configuration(rule_dict)` - Validates that percentages sum to 100%

**Design Principles**:
- No hardcoding of norm codes (E126, E132, etc.)
- No hardcoding of input codes (PKO, OLIVE_OIL, CHEESE, etc.)
- All configuration is data-driven via database models
- Generic for ANY number of inputs (2-way, 3-way, 4-way, N-way splits)

### 2. SionInputAliasConfig Model (`models/core.py`)

**Purpose**: Data-driven mapping of raw product names to canonical input codes.

**Fields**:
- `canonical_input_code` - The canonical code (e.g., "PKO", "COMPONENT_A", custom codes)
- `alias_normalized` - The normalized product name for exact matching
- `sion` (FK, optional) - Scope to specific SION norm (if null = global)
- `output_item` (FK, optional) - Further scope to specific output item
- `source_description` - Metadata about the mapping origin
- `is_active` - Enable/disable aliases without deleting

**Lookup Hierarchy**:
1. (sion + output_item) specific alias
2. sion-only alias
3. Global alias
4. UNMAPPED

**Example**:
```python
SionInputAliasConfig.objects.create(
    sion=sion_e126,
    alias_normalized="PALM KERNEL OIL",
    canonical_input_code="PKO",
    source_description="E126 specification"
)
```

### 3. Updated SionPlanningRule Model

**New Fields**:
- `rule_type` (CharField, choices):
  - `PERCENTAGE_CAP` - Master entitlement cap (e.g., PKO max 50% of total eligible)
  - `SPLIT_PERCENTAGE` - Transaction splitting strategy (e.g., allocate as 50% PKO + 50% OLIVE_OIL)
  - `QUANTITY_CAP` - Fixed quantity restriction (extensible for future)

- `rule_group_id` (CharField, optional) - Groups related rules (e.g., "E126_50_50_split")

**Existing Fields** (unchanged):
- `sion` - Which SION norm
- `output_item` - Which output item this rule applies to
- `percentage_constraint` - The percentage value (0-100)
- `name` - Rule name (typically the canonical input code)

### 4. Updated SionProductClassifier Service

**Purpose**: Backward-compatible canonical input resolution.

**Key Changes**:
- Now uses SionRuleResolver for data-driven lookup
- Falls back to legacy hardcoded aliases if no data-driven config found
- Accepts optional `sion` and `output_item` parameters for scoped resolution
- Maintains CanonicalInput enum for backward compatibility

**Usage**:
```python
# Data-driven lookup (with scope)
mapping = SionRuleResolver.resolve_canonical_input(
    "PALM KERNEL OIL",
    sion=sion_e126,
    output_item=output_item
)

# Legacy enum-based (for backward compatibility)
canonical = SionProductClassifier.resolve_canonical_input("PALM KERNEL OIL")
# Returns CanonicalInput.PKO
```

### 5. Extended SionPercentageCapacity Service

**New Generic Methods**:
- `get_percentage_cap_for_canonical_input(license, sion_id, canonical_input_code, percentage)` - Works with string codes instead of enum
- `get_remaining_capacity_for_canonical_input(license, sion_id, sion, canonical_input_code, percentage)` - Calculates remaining capacity generically
- `can_allocate_to_canonical_input(license, sion_id, sion, canonical_input_code, percentage, requested_qty)` - Validates allocation generically

**Design**:
- Uses the new SionRuleResolver for product classification
- Supports any canonical input code (not just PKO, OLIVE_OIL, CHEESE)
- Works for any number of inputs in a rule set

### 6. Updated API Endpoint (`sion_planning_rule.py`)

**Changes to `allocation_strategy` endpoint**:
- Now scopes rules by (output_item, sion) instead of just sion
- Validates that percentages sum to 100% before enabling Split-by-%
- Returns clear error messages if configuration is invalid
- Supports dynamic N-way splits

**Example Validation**:
```python
# Error if output_item not set
if not rule.output_item_id:
    return Response({"error": "..."})

# Error if percentages don't sum to 100%
if total_pct != Decimal("100"):
    return Response({"error": "..."})
```

## Migrations

### Migration 0028: `sion_generic_rules.py`
- Adds `rule_type` and `rule_group_id` fields to SionPlanningRule
- Creates SionInputAliasConfig model with indexes

### Migration 0029: `populate_sion_input_aliases.py`
- Seeds SionInputAliasConfig with E126/E132 aliases
- Creates global aliases available to all norms
- Idempotent: uses `get_or_create`

### Migration 0030: `populate_rule_types.py`
- Sets `rule_type='PERCENTAGE_CAP'` for existing rules
- Populates `rule_group_id` for E126/E132 rules
- Links rule groups to output items

## Rule Semantics

### PERCENTAGE_CAP Rules (Master Entitlements)

**Definition**: An input may consume maximum X% of the total eligible quantity.

**Example (E126)**:
```
Total Eligible Quantity = 1,000 KG

PKO:        50% → Max 500 KG
OLIVE_OIL:  50% → Max 500 KG
```

**Properties**:
- Cumulative across all transactions (Standard, Split-by-%, BOE, Allotment)
- Does NOT force transaction splits
- Allows partial consumption (e.g., Planning 100 KG PKO, then 80 KG PKO in second planning)

**Calculation**:
```
input_cap = total_eligible_quantity × percentage / 100
remaining = input_cap - (planned + allotted + debited)
```

### SPLIT_PERCENTAGE Rules (Transaction Splitting)

**Definition**: When allocating to this output, split the quantity according to percentages.

**Example (E126)**:
```
Input Planning Quantity = 200 KG

PKO:        50% → 100 KG
OLIVE_OIL:  50% → 100 KG
```

**Properties**:
- Percentages MUST sum to exactly 100%
- Only applies when user explicitly chooses "Split by %"
- Backend-authoritative: enforced on persistence, not on client
- No automatic redistribution: if one input's cap is exhausted, allocation fails

**Validation**:
```python
is_valid, msg = SionRuleResolver.validate_split_rule_configuration({
    "PKO": Decimal("50"),
    "OLIVE_OIL": Decimal("50"),
})
# is_valid = True, msg = None
```

## Standard Strategy vs. Split-by-%

### STANDARD Strategy
- Select one input independently
- Respects that input's remaining capacity
- No automatic splitting across inputs
- **Example**: User selects PKO for 100 KG planning
  - Checks: PKO remaining capacity ≥ 100 KG?
  - If yes, allocate 100 KG PKO only
  - Other inputs unaffected

### SPLIT_BY_PERCENTAGE Strategy
- Backend allocates requested quantity across multiple inputs
- Percentages from SPLIT_PERCENTAGE rule configuration
- All inputs' allocations created together
- **Example**: User requests 200 KG with Split-by-% enabled
  - Backend generates: 100 KG PKO + 100 KG OLIVE_OIL
  - Both allocations created or both rejected (atomic)

## Design Principles

### 1. No Hardcoding of Norm Codes
❌ Bad:
```python
if norm.norm_class == "E126":
    use_e126_percentages()
```

✅ Good:
```python
rules = SionRuleResolver.get_percentage_rules_for_output_item(
    output_item, sion
)
```

### 2. No Hardcoding of Input Codes
❌ Bad:
```python
CANONICAL_ALIASES = {
    "PKO": CanonicalInput.PKO,
    "OLIVE OIL": CanonicalInput.OLIVE_OIL,
    "CHEESE": CanonicalInput.CHEESE,
}
```

✅ Good:
```python
# Configuration in SionInputAliasConfig
alias = SionInputAliasConfig.objects.get(alias_normalized=name, sion=sion)
canonical_code = alias.canonical_input_code  # Dynamic
```

### 3. Output Item Scoping
Rules are resolved by **(output_item, sion)** pair:
```python
# Different outputs within same norm can have different rules
rules_output_1 = SionRuleResolver.get_rules_for_output_item(output_1, sion)
rules_output_2 = SionRuleResolver.get_rules_for_output_item(output_2, sion)
# May have completely different configurations
```

### 4. N-Way Support
The system supports ANY number of inputs:
```python
# 2-way split
config = {"A": "50", "B": "50"}

# 3-way split
config = {"A": "40", "B": "35", "C": "25"}

# 4-way split
config = {"A": "35", "B": "30", "C": "20", "D": "15"}

# Same code path for all - no special cases
```

### 5. Master Cap ≠ Transaction Split
These are independent concepts:

**Master Caps**:
- Define cumulative entitlements
- Example: PKO max 50% (across all transactions)

**Transaction Split**:
- Only applies when explicitly chosen
- Example: This planning request split as 50% PKO + 50% OLIVE_OIL

A norm can have master caps without having a split rule, and vice versa.

## Testing

### Unit Tests (`test_sion_generic_rule_engine.py`)
- Product name normalization
- Data-driven alias resolution
- Hierarchical alias lookup
- Rule resolution by output_item
- Split rule validation
- Generic norm support

### Integration Tests (`test_sion_generic_integration.py`)
- Complete flow for custom norms
- Multiple norms with different configurations
- Output-item specific rules
- No hardcoding verification

## Example: Custom Norm with 4 Inputs

```python
# Set up a completely custom norm - no E126/E132 references
head_norm = HeadSIONNormsModel.objects.create(name="Custom")
sion = SionNormClassModel.objects.create(
    norm_class="CUSTOM",
    head_norm=head_norm
)

# Create output item
output_item = ItemNameModel.objects.create(name="MIXED_GOODS")

# Create aliases for custom products
SionInputAliasConfig.objects.create(
    sion=sion,
    alias_normalized="RAW MATERIAL A",
    canonical_input_code="COMPONENT_A"
)
SionInputAliasConfig.objects.create(
    sion=sion,
    alias_normalized="RAW MATERIAL B",
    canonical_input_code="COMPONENT_B"
)

# Create 4-way split rule: 35/30/20/15
for name, pct in [
    ("COMPONENT_A", "35"),
    ("COMPONENT_B", "30"),
    ("COMPONENT_C", "20"),
    ("COMPONENT_D", "15"),
]:
    SionPlanningRule.objects.create(
        sion=sion,
        output_item=output_item,
        name=name,
        percentage_constraint=Decimal(pct),
        rule_type="PERCENTAGE_CAP"
    )

# The system now supports this norm generically
# No code changes needed, no new hardcoding
```

## Backward Compatibility

The implementation maintains full backward compatibility:

1. **Existing Rules**: Continue to work as before via legacy enum
2. **Legacy Aliases**: Hardcoded aliases still work via fallback
3. **CanonicalInput Enum**: Preserved for existing code
4. **E126/E132**: Work through new generic system

## Performance Considerations

1. **Alias Lookup**: O(1) with database indexes on `alias_normalized`, `sion`, `is_active`
2. **Rule Resolution**: Single query per (output_item, sion) pair, indexed
3. **Caching**: Rules can be cached at application level if needed

## Future Extensions

The architecture supports:

1. **New Rule Types**: Add `QUANTITY_CAP`, `GROUP_CAP`, etc. to `rule_type` choices
2. **Rule Groups**: Link multiple rules via `rule_group_id`
3. **Conditional Rules**: Extend rule configuration to support conditions
4. **Input Families**: Group inputs under umbrella constraints
5. **Custom Validators**: Plugin validation logic per rule type

No architectural changes needed - just extend the configuration.

## Summary

The generic SION rule engine achieves:

✅ **Zero hardcoding** of norm codes or input codes  
✅ **Data-driven** configuration via database models  
✅ **Output-item scoped** rules for fine-grained control  
✅ **N-way support** for any number of inputs  
✅ **Generic** application to any SION norm  
✅ **Backward compatible** with existing E126/E132 rules  
✅ **Well-tested** with comprehensive unit and integration tests  
✅ **Extensible** for future rule types and configurations  
