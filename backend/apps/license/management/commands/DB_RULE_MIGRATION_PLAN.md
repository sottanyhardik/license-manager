# PHASE 2C: DB Rule Migration Plan & Seed Configuration

## 1. RULE MIGRATION CHECKLIST

### NORM: E1 (Confectionery)

**Current State:**
- Hard-coded planner: `compute_e1_auto_plan()` in `e1_auto_plan.py`
- Classification logic: `classify_e1_item()` in `e1_plan.py`
- 9 output item names, but 2 primary matching rules needed

**Database Migration:**
- Rules: 2 (OTHER_CONFECTIONERY, COCOA_MASS + MILK_SPLIT + remaining categories)
- Actions: 5 (MATCH → GROUP → ALLOCATE → REBALANCE → MAP_OUTPUT)
- New Algorithms: None (use existing CAPPED_FIXED_RATE_WATERFALL)
- Reused Utilities: 
  - `classify_e1_item()` (classification logic)
  - `merge_items_for_classification()` (grouping)
  - `validate_fresh_plan_lines()` (safety net)
- Test Coverage: 15+ existing `test_e1_auto_plan` cases
- Risk: **MEDIUM** — Waterfall has balance-driven dynamic pricing (DWP/SWP/WPC); must preserve exact sequencing

**Migration Path:**
1. Create SionPlanningProfile (stable_key="E1:CONFECTIONERY_V1")
2. Create 2 SionPlanningRule rows (categories)
3. Create 5 SionPlanningAction rows (pipeline)
4. Implement adapter: `LegacyE1Adapter` that delegates to hard-coded classifier
5. Run parity tests: hard-code vs DB rules on golden licenses

---

### NORM: E5 (Biscuits)

**Current State:**
- Hard-coded planner: `compute_e5_auto_plan()` in `e5_auto_plan.py`
- Classification logic: `classify_e5_item()` in `e5_plan.py`
- Split: YES (oils split into PKO/Olive)
- 9 output item names

**Database Migration:**
- Rules: 8 (DIETARY_FIBRE, PKO, RBD_PALMOLEIN, REMAINING_OILS, DWP, SWP, WPC, WHEAT_FLOUR)
- Actions: 6 (MATCH → GROUP → ALLOCATE → SPLIT → REBALANCE → MAP_OUTPUT)
- New Algorithms: None (use CAPPED_FIXED_RATE_WATERFALL + SPLIT strategy)
- Reused Utilities:
  - `classify_e5_item()` (classification)
  - `merge_items_for_classification()` (grouping)
  - `validate_fresh_plan_lines()` (safety net)
- Test Coverage: 12+ existing `test_e5_auto_plan` cases; add 5+ split variation tests
- Risk: **HIGH** — Split logic requires careful handling; oils have dynamic allocation

**Migration Path:**
1. Create SionPlanningProfile (stable_key="E5:BISCUITS_V1")
2. Create 8 SionPlanningRule rows
3. Create 6 SionPlanningAction rows (including SPLIT with 50%/50% config)
4. Implement adapter: `LegacyE5Adapter` that delegates to hard-coded classifier
5. Test split behavior: verify PKO and OLIVE outputs are generated correctly

**Split Configuration (E5):**
```json
{
  "action_type": "SPLIT",
  "priority": 4,
  "stable_key": "E5:SPLIT_OILS",
  "config": {
    "algorithm": "FIXED_RATIO_SPLIT",
    "source_category": "REMAINING_OILS",
    "targets": [
      {"category": "PALM_KERNEL_OIL", "ratio": 0.5},
      {"category": "OLIVE_OIL", "ratio": 0.5}
    ],
    "inherit_quantity": true,
    "split_remainder": "PROPORTIONAL"
  }
}
```

---

### NORM: E126 (Nuts & Edible Oils)

**Current State:**
- Hard-coded planner: `compute_e126_auto_plan()` in `e126_auto_plan.py`
- Classification logic: `classify_e126_record()` in `e126_plan.py`
- Split: YES (PKO/Olive 50%/50%)
- 3 output item names

**Database Migration:**
- Rules: 3 (NUT_NUTS, PKO, OLIVE_OIL)
- Actions: 6 (MATCH → GROUP → ALLOCATE → SPLIT → REBALANCE → MAP_OUTPUT)
- New Algorithms: None (use FIXED_RATIO_SPLIT for 50%/50%)
- Reused Utilities:
  - `classify_e126_record()` (classification)
  - `merge_items_for_classification()` (grouping)
  - `validate_group_plan_lines()` (price ceiling)
- Test Coverage: 10+ existing `test_e126_auto_plan` cases; add 5+ split variation tests
- Risk: **HIGH** — Split is 50%/50%, must be fixed once generated

**Migration Path:**
1. Create SionPlanningProfile (stable_key="E126:NUTS_OILS_V1")
2. Create 3 SionPlanningRule rows (simple HSN matchers)
3. Create 6 SionPlanningAction rows (including SPLIT with 50%/50% split)
4. Implement adapter: `LegacyE126Adapter` that delegates to hard-coded classifier
5. Test split preservation: verify split doesn't regenerate on re-run

**Split Configuration (E126):**
```json
{
  "action_type": "SPLIT",
  "priority": 4,
  "stable_key": "E126:SPLIT_PKO_OLIVE",
  "config": {
    "algorithm": "FIXED_RATIO_SPLIT",
    "source_category": "PKO",
    "targets": [
      {"category": "PALM_KERNEL_OIL", "ratio": 0.5},
      {"category": "OLIVE_OIL", "ratio": 0.5}
    ],
    "inherit_quantity": true,
    "split_remainder": "PROPORTIONAL",
    "preserve_split_once_generated": true
  }
}
```

---

### NORM: E132 (Vegetable Oils & Products)

**Current State:**
- Hard-coded planner: `compute_e132_auto_plan()` in `e132_auto_plan.py`
- Classification logic: `classify_e132_record()` in `e132_plan.py`
- Split: YES (PKO/Cheese 40%/60%)
- Complex priority logic: 6 categories
- 6 output item names

**Database Migration:**
- Rules: 6 (NUT_NUTS, YEAST, PKO, RBD, CHEESE, ALUMINIUM)
- Actions: 7 (MATCH → GROUP → ALLOCATE → SPLIT → REBALANCE → ROUND → MAP_OUTPUT)
- New Algorithms: None (use FIXED_RATIO_SPLIT for 40%/60%)
- Reused Utilities:
  - `classify_e132_record()` (classification with strict Cheese detection)
  - `merge_items_for_classification()` (grouping)
  - `validate_group_plan_lines()` (price ceiling)
- Test Coverage: 20+ existing `test_e132_auto_plan` cases; add 10+ priority/split edge cases
- Risk: **HIGHEST** — Complex priority logic (6 categories), split is 40%/60%, strict Cheese detection must match before generic PKO

**Migration Path:**
1. Create SionPlanningProfile (stable_key="E132:OILS_PRODUCTS_V1")
2. Create 6 SionPlanningRule rows (careful priority ordering)
3. Create 7 SionPlanningAction rows (including complex SPLIT)
4. Implement adapter: `LegacyE132Adapter` that delegates to hard-coded classifier
5. Test priority ordering: verify Cheese detection doesn't incorrectly match RBD
6. Test split preservation: verify split doesn't regenerate

**Critical Rule Ordering (E132):**
- Priority 1: NUT_NUTS (HSN 0802 + "nut"/"nuts" word boundary)
- Priority 2: YEAST (HSN 2106 + "yeast" word boundary)
- Priority 3: PKO (HSN 1513 alone)
- Priority 4: RBD (HSN 1510 alone, blocks split)
- Priority 5: CHEESE (strict dairy + vegetable + oil, 40%/60% split with PKO)
- Priority 6: ALUMINIUM (HSN 7607 or "aluminium foil" description)

**Split Configuration (E132):**
```json
{
  "action_type": "SPLIT",
  "priority": 5,
  "stable_key": "E132:SPLIT_PKO_CHEESE",
  "config": {
    "algorithm": "FIXED_RATIO_SPLIT",
    "source_category": "PKO",
    "targets": [
      {"category": "PKO", "ratio": 0.4},
      {"category": "CHEESE", "ratio": 0.6}
    ],
    "inherit_quantity": true,
    "split_remainder": "PROPORTIONAL",
    "preserve_split_once_generated": true
  }
}
```

---

### NORM: A3627 (Glass & Ceramics)

**Current State:**
- Hard-coded planner: `compute_a3627_auto_plan()` in `a3627_auto_plan.py`
- Classification logic: `_matched_ids_by_category()` using `item_matcher.get_item_filters()`
- Split: NO (but dynamic pricing on RUTILE)
- 4 output item names

**Database Migration:**
- Rules: 4 (RUTILE, TITANIUM_DIOXIDE, SODA_ASH, PP)
- Actions: 6 (MATCH → GROUP → ALLOCATE → ROUND → REBALANCE → MAP_OUTPUT)
- New Algorithms: YES — DYNAMIC_RUTILE_FIXED_RATE_WATERFALL (avg import price > $3.00 → $3.50, else $2.50)
- Reused Utilities:
  - `get_item_filters()` (classification)
  - `merge_items_for_classification()` (grouping)
  - `validate_group_plan_lines()` (price ceiling)
- Test Coverage: 5+ existing `test_a3627_auto_plan` cases; add 5+ dynamic pricing edge cases
- Risk: **HIGH** — Dynamic pricing requires average import price calculation; must preserve weighted-average logic

**Migration Path:**
1. Create SionPlanningProfile (stable_key="A3627:GLASS_CERAMICS_V1")
2. Create 4 SionPlanningRule rows
3. Create 6 SionPlanningAction rows (including ALLOCATE with RUTILE dynamic pricing)
4. Implement adapter: `LegacyA3627Adapter` that delegates to item_matcher
5. Test dynamic pricing: verify RUTILE avg price threshold logic

**RUTILE Dynamic Pricing Algorithm:**
```json
{
  "action_type": "ALLOCATE",
  "priority": 1,
  "stable_key": "A3627:ALLOCATE_RUTILE",
  "config": {
    "algorithm": "DYNAMIC_RUTILE_FIXED_RATE_WATERFALL",
    "category": "RUTILE",
    "price_low": "2.50",
    "price_high": "3.50",
    "price_threshold": "3.00",
    "compute_threshold_on": "average_import_price_of_matched_items",
    "granularity": "WHOLE_UNIT",
    "consume_remaining": true
  }
}
```

---

## 2. SEED CONFIGURATION STRUCTURE

### High-Level Design

The seed configuration system uses a **three-tier hierarchy:**

1. **SionPlanningProfile** (1 per norm or shared)
   - `stable_key`: Immutable identifier (e.g., "E1:CONFECTIONERY_V1")
   - `strategy_type`: "ACTION_PIPELINE" (only type for now)
   - `config`: Optional shared config (e.g., default split strategy)
   - `version`: Incremented when rules/actions change
   - `is_active`: Only ONE profile per norm can be active

2. **SionPlanningRule** (many per norm)
   - `stable_key`: Immutable identifier (e.g., "E1:OTHER_CONFECTIONERY")
   - `name`: Human-readable name
   - `expression`: JSON expression (matcher predicates)
   - `max_unit_price`: Business rule ceiling
   - `unit`: Always "mt" (metric tons)
   - `priority`: Execution order (1-based)
   - `is_active`: Only active rules participate in planning

3. **SionPlanningAction** (5-7 per profile)
   - `stable_key`: Immutable identifier (e.g., "E1:MATCH")
   - `action_type`: One of MATCH, GROUP, ALLOCATE, SPLIT, REBALANCE, ROUND, MAP_OUTPUT
   - `priority`: Execution order (1-based, unique per profile)
   - `config`: Algorithm-specific config (rate, split ratios, etc.)
   - `is_active`: All active profile actions must execute in order

### Management Command Structure

```python
# backend/apps/license/management/commands/seed_sion_planning_rules.py

class Command(BaseCommand):
    """Seed all 5 SION planning rules from verified, audited configurations.
    
    Idempotent: can be re-run safely; uses stable_key for get_or_create.
    Produces: 1 profile + 5 actions per norm, plus 18 rules total.
    """
    
    def add_arguments(self, parser):
        parser.add_argument("--sion", action="append", 
                          choices=["E1", "E5", "E126", "E132", "A3627"],
                          help="Only seed specific norm(s); default is all")
        parser.add_argument("--dry-run", action="store_true",
                          help="Print what would be created; don't persist")
        parser.add_argument("--force-recreate", action="store_true",
                          help="Delete old version before seeding (dangerous)")
    
    def handle(self, *args, **options):
        norms = options["sion"] or ["E1", "E5", "E126", "E132", "A3627"]
        
        # Phase 1: Ensure SION norms exist
        norms_by_code = self._ensure_sion_norms(norms)
        
        # Phase 2: Seed profiles, rules, actions (idempotent)
        results = {}
        for norm_code in norms:
            results[norm_code] = self._seed_norm(
                norm_code, 
                norms_by_code[norm_code],
                force_recreate=options["force_recreate"],
                dry_run=options["dry_run"],
            )
        
        # Phase 3: Report
        self._report(results, options["dry_run"])
    
    def _ensure_sion_norms(self, norm_codes: list[str]) -> dict:
        """Get or create SionNormClassModel rows."""
        from apps.core.models import SionNormClassModel
        result = {}
        for code in norm_codes:
            obj, created = SionNormClassModel.objects.get_or_create(
                norm_class=code,
                defaults={"description": f"{code} norm"}
            )
            result[code] = obj
            if created:
                self.stdout.write(f"Created SION norm: {code}")
        return result
    
    def _seed_norm(self, norm_code: str, sion_obj, *, 
                  force_recreate=False, dry_run=False) -> dict:
        """Seed profile, rules, actions for one norm."""
        from apps.license.models import SionPlanningProfile, SionPlanningRule, SionPlanningAction
        from apps.license.services.sion_planner_seeders import get_seeder
        
        seeder_class = get_seeder(norm_code)  # E1Seeder, E5Seeder, etc.
        seeder = seeder_class(sion_obj)
        
        if dry_run:
            profile_spec, rules_specs, actions_specs = seeder.get_specifications()
            return {
                "norm": norm_code,
                "profile_spec": profile_spec,
                "rules_count": len(rules_specs),
                "actions_count": len(actions_specs),
                "dry_run": True,
            }
        
        # Get-or-create profile
        profile_spec = seeder.get_profile_specification()
        profile, created = SionPlanningProfile.objects.get_or_create(
            sion=sion_obj,
            stable_key=profile_spec["stable_key"],
            defaults=profile_spec,
        )
        
        # Seed rules (bulk create if new profile)
        rules = []
        for rule_spec in seeder.get_rules_specifications():
            rule, rule_created = SionPlanningRule.objects.get_or_create(
                sion=sion_obj,
                stable_key=rule_spec["stable_key"],
                defaults=rule_spec,
            )
            rules.append(rule)
        
        # Seed actions (link to profile)
        actions = []
        for action_spec in seeder.get_actions_specifications():
            action, action_created = SionPlanningAction.objects.get_or_create(
                profile=profile,
                stable_key=action_spec["stable_key"],
                defaults=action_spec,
            )
            actions.append(action)
        
        return {
            "norm": norm_code,
            "profile_id": profile.pk,
            "profile_created": created,
            "rules_count": len(rules),
            "actions_count": len(actions),
        }
```

### Seeder Pattern

Each norm gets a dedicated seeder class:

```python
# backend/apps/license/services/sion_planner_seeders/base.py

class SionPlannerSeeder(ABC):
    """Base seeder for a norm's profile, rules, actions."""
    
    def __init__(self, sion_obj):
        self.sion = sion_obj
    
    @abstractmethod
    def get_profile_specification(self) -> dict:
        """Return SionPlanningProfile defaults dict."""
    
    @abstractmethod
    def get_rules_specifications(self) -> list[dict]:
        """Return list of SionPlanningRule defaults dicts."""
    
    @abstractmethod
    def get_actions_specifications(self) -> list[dict]:
        """Return list of SionPlanningAction defaults dicts (unparsed config)."""
    
    def get_specifications(self) -> tuple:
        """Return (profile_spec, rules_specs, actions_specs) for dry-run."""
        return (
            self.get_profile_specification(),
            self.get_rules_specifications(),
            self.get_actions_specifications(),
        )
```

---

## 3. E1 SEED CONFIGURATION

### Profile

```python
# In E1Seeder.get_profile_specification():
{
    "sion": e1_norm,
    "stable_key": "E1:CONFECTIONERY_V1",
    "strategy_type": "ACTION_PIPELINE",
    "config": {
        "description": "E1 Confectionery — Waterfall with milk DWP/SWP/WPC split",
        "classification_approach": "LEGACY_ADAPTER",
        "classifier_fn": "apps.license.services.e1_plan.classify_e1_item",
    },
    "version": 1,
    "is_active": False,  # Activate after parity tests pass
}
```

### Rules (2 primary categories)

```python
# In E1Seeder.get_rules_specifications():

[
    {
        "sion": e1_norm,
        "stable_key": "E1:OTHER_CONFECTIONERY",
        "name": "OTHER CONFECTIONERY INGREDIENTS",
        "expression": {
            "operator": "AND",
            "conditions": [
                {
                    "field": "ITEM_KEY",
                    "operator": "not_contains",
                    "value": "food flavour"
                },
                {
                    "operator": "OR",
                    "conditions": [
                        {"field": "HSN_DIGITS", "operator": "starts_with", "value": "0802"},
                        {"field": "ITEM_KEY", "operator": "contains", "value": "other confectionery"},
                        {"field": "PRODUCT_DESCRIPTION", "operator": "contains", "value": "other confectionery"},
                    ]
                }
            ]
        },
        "max_unit_price": "99.99",  # No real ceiling; legacy planners set this liberally
        "unit": "mt",
        "priority": 1,
        "version": 1,
        "is_active": True,
    },
    {
        "sion": e1_norm,
        "stable_key": "E1:COCOA_MILK_AND_REST",
        "name": "COCOA / MILK / FRUITS / ACIDS / PACKAGING",
        "expression": {
            "operator": "OR",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "1803"},
                {
                    "operator": "AND",
                    "conditions": [
                        {"field": "HSN_DIGITS", "operator": "starts_with", "value": "0404"},
                        {"field": "PRODUCT_DESCRIPTION", "operator": "contains", "value": "milk"},
                    ]
                },
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "3502"},
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "2009"},
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "2918"},
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "7607"},
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "3902"},
            ]
        },
        "max_unit_price": "99.99",
        "unit": "mt",
        "priority": 2,
        "version": 1,
        "is_active": True,
    },
]
```

### Actions (5-stage pipeline)

```python
# In E1Seeder.get_actions_specifications():

[
    {
        "profile": profile,  # FK resolved in management command
        "stable_key": "E1:MATCH",
        "action_type": "MATCH",
        "priority": 1,
        "config": {
            "algorithm": "LEGACY_RULE_MATCHER",
            "classifier_fn": "apps.license.services.e1_plan.classify_e1_item",
            "use_rules": False,  # Delegate to legacy classifier
        },
        "version": 1,
        "is_active": True,
    },
    {
        "profile": profile,
        "stable_key": "E1:GROUP",
        "action_type": "GROUP",
        "priority": 2,
        "config": {
            "algorithm": "CANONICAL_PLAN_GROUP_KEY",
            "group_by": ["hs_code", "normalized_description"],
            "representative_selection": "LOWEST_SERIAL",
        },
        "version": 1,
        "is_active": True,
    },
    {
        "profile": profile,
        "stable_key": "E1:ALLOCATE",
        "action_type": "ALLOCATE",
        "priority": 3,
        "config": {
            "algorithm": "CAPPED_FIXED_RATE_WATERFALL",
            "items": [
                {
                    "category": "OTHER CONFECTIONERY INGREDIENTS",
                    "rate": "1.50",
                    "granularity": "FRACTIONAL",
                },
                {
                    "category": "COCOA MASS",
                    "rate": "7.50",
                    "granularity": "FRACTIONAL",
                },
                # ... DWP, SWP, WPC are dynamic (balance-driven, not fixed rates)
                # ... remaining categories are fixed but not shown here for brevity
            ],
            "consume_remaining": True,
        },
        "version": 1,
        "is_active": True,
    },
    {
        "profile": profile,
        "stable_key": "E1:REBALANCE",
        "action_type": "REBALANCE",
        "priority": 4,
        "config": {
            "algorithm": "WASTAGE_REDUCTION",
            "preserve_rate_hierarchy": True,
        },
        "version": 1,
        "is_active": True,
    },
    {
        "profile": profile,
        "stable_key": "E1:MAP_OUTPUT",
        "action_type": "MAP_OUTPUT",
        "priority": 5,
        "config": {
            "algorithm": "LEGACY_STEP_TO_ITEM_NAME",
            "step_mapping": {
                "OTHER CONFECTIONERY INGREDIENTS": "OTHER CONFECTIONERY INGREDIENTS - E1",
                "COCOA MASS": "FRUIT/COCOA - E1",
                "DWP": "DWP - E1",
                "SWP": "SWP - E1",
                "EGG ALBUMIN": "WPC - E1",
                "FRUIT JUICE": "FRUIT JUICE - E1",
                "TARTARIC ACID": "CITRIC ACID / TARTARIC ACID - E1",
                "ALUMINIUM FOIL": "ALUMINIUM FOIL - E1",
                "POLYPROPYLENE": "PP - E1",
            },
        },
        "version": 1,
        "is_active": True,
    },
]
```

---

## 4. E5 SEED CONFIGURATION (Abridged)

### Profile

```python
{
    "sion": e5_norm,
    "stable_key": "E5:BISCUITS_V1",
    "strategy_type": "ACTION_PIPELINE",
    "config": {
        "description": "E5 Biscuits — Waterfall with oils split",
        "split_targets": ["PALM KERNEL OIL - E5", "OLIVE OIL - E5"],
    },
    "version": 1,
    "is_active": False,
}
```

### Rules (8 categories)

```python
[
    {"stable_key": "E5:DIETARY_FIBRE", "priority": 1, "expression": {...}},
    {"stable_key": "E5:PKO", "priority": 2, "expression": {...}},
    {"stable_key": "E5:RBD_PALMOLEIN", "priority": 3, "expression": {...}},
    {"stable_key": "E5:REMAINING_OILS", "priority": 4, "expression": {...}},
    {"stable_key": "E5:DWP", "priority": 5, "expression": {...}},  # Milk
    {"stable_key": "E5:SWP", "priority": 6, "expression": {...}},  # Milk
    {"stable_key": "E5:WPC", "priority": 7, "expression": {...}},  # Egg
    {"stable_key": "E5:WHEAT_FLOUR", "priority": 8, "expression": {...}},  # Mop-up
]
```

### Actions (6-stage pipeline with SPLIT)

Key action:
```python
{
    "stable_key": "E5:SPLIT_OILS",
    "action_type": "SPLIT",
    "priority": 4,
    "config": {
        "algorithm": "FIXED_RATIO_SPLIT",
        "source_category": "REMAINING_OILS",
        "targets": [
            {"category": "PALM KERNEL OIL - E5", "ratio": 0.5},
            {"category": "OLIVE OIL - E5", "ratio": 0.5},
        ],
        "inherit_quantity": True,
        "split_remainder": "PROPORTIONAL",
    },
}
```

---

## 5. E126 SEED CONFIGURATION (Abridged)

### Profile

```python
{
    "sion": e126_norm,
    "stable_key": "E126:NUTS_OILS_V1",
    "strategy_type": "ACTION_PIPELINE",
    "config": {
        "description": "E126 Nuts & Oils — 3-category with 50/50 PKO/Olive split",
        "split_targets": ["PALM KERNEL OIL - E126", "OLIVE OIL - E126"],
        "preserve_split_once_generated": True,
    },
    "version": 1,
    "is_active": False,
}
```

### Rules (3 categories)

```python
[
    {
        "stable_key": "E126:NUTS",
        "name": "NUTS - E126",
        "priority": 1,
        "expression": {
            "operator": "OR",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "0802"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "nut"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "nuts"},
            ]
        },
        "max_unit_price": "15.00",
    },
    {
        "stable_key": "E126:PKO",
        "name": "PALM KERNEL OIL - E126",
        "priority": 2,
        "expression": {
            "operator": "OR",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "1513"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "contains", "value": "1513"},
            ]
        },
        "max_unit_price": "2.00",
    },
    {
        "stable_key": "E126:OLIVE",
        "name": "OLIVE OIL - E126",
        "priority": 3,
        "expression": {
            "operator": "OR",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "1509"},
                # Substring match (not word boundary) for 1500/1509/1510
                {"field": "PRODUCT_DESCRIPTION", "operator": "contains", "value": "1500"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "contains", "value": "1509"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "contains", "value": "1510"},
            ]
        },
        "max_unit_price": "2.00",
    },
]
```

### Actions with SPLIT

```python
{
    "stable_key": "E126:SPLIT_PKO_OLIVE",
    "action_type": "SPLIT",
    "priority": 4,
    "config": {
        "algorithm": "FIXED_RATIO_SPLIT",
        "source_category": "PALM KERNEL OIL - E126",
        "targets": [
            {"category": "PALM KERNEL OIL - E126", "ratio": 0.5},
            {"category": "OLIVE OIL - E126", "ratio": 0.5},
        ],
        "inherit_quantity": True,
        "split_remainder": "PROPORTIONAL",
        "preserve_split_once_generated": True,
    },
}
```

---

## 6. E132 SEED CONFIGURATION (Complex)

### Profile

```python
{
    "sion": e132_norm,
    "stable_key": "E132:OILS_PRODUCTS_V1",
    "strategy_type": "ACTION_PIPELINE",
    "config": {
        "description": "E132 Oils & Products — 6 categories with complex priority + 40/60 split",
        "split_targets": ["PKO - E132", "CHEESE CREAM BUTTER AND FATS - E132"],
        "preserve_split_once_generated": True,
    },
    "version": 1,
    "is_active": False,
}
```

### Rules (6 categories, **careful priority ordering**)

```python
[
    {
        "stable_key": "E132:NUT",
        "name": "NUT & NUTS - E132",
        "priority": 1,  # Must be first (highest priority)
        "expression": {
            "operator": "AND",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "0802"},
                {
                    "operator": "OR",
                    "conditions": [
                        {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "nut"},
                        {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "nuts"},
                    ]
                }
            ]
        },
        "max_unit_price": "20.00",
    },
    {
        "stable_key": "E132:YEAST",
        "name": "Yeast - E132",
        "priority": 2,
        "expression": {
            "operator": "AND",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "2106"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "yeast"},
            ]
        },
        "max_unit_price": "5.00",
    },
    {
        "stable_key": "E132:PKO",
        "name": "PKO - E132",
        "priority": 3,
        "expression": {
            "operator": "AND",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "1513"},
                # Must NOT also match Cheese signals (strict dairy HSN codes)
                {
                    "operator": "NOT",
                    "conditions": [
                        {
                            "operator": "AND",
                            "conditions": [
                                {
                                    "operator": "OR",
                                    "conditions": [
                                        {"field": "HSN_DIGITS", "operator": "in", "value": ["0401", "0405", "0406"]},
                                    ]
                                },
                                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "vegetable"},
                                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "oil"},
                            ]
                        }
                    ]
                }
            ]
        },
        "max_unit_price": "2.00",
    },
    {
        "stable_key": "E132:RBD",
        "name": "RBD - E132",
        "priority": 4,
        "expression": {
            "operator": "AND",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "1510"},
            ]
        },
        "max_unit_price": "2.00",
    },
    {
        "stable_key": "E132:CHEESE",
        "name": "CHEESE CREAM BUTTER AND FATS - E132",
        "priority": 5,
        "expression": {
            "operator": "AND",
            "conditions": [
                {
                    "operator": "OR",
                    "conditions": [
                        {"field": "HSN_DIGITS", "operator": "in", "value": ["0401", "0405", "0406"]},
                    ]
                },
                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "vegetable"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "oil"},
            ]
        },
        "max_unit_price": "2.00",
    },
    {
        "stable_key": "E132:ALUMINIUM",
        "name": "Aluminium Foil - E132",
        "priority": 6,
        "expression": {
            "operator": "OR",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "7607"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "contains", "value": "aluminium foil"},
            ]
        },
        "max_unit_price": "3.00",
    },
]
```

### Actions with Complex SPLIT

```python
{
    "stable_key": "E132:SPLIT_PKO_CHEESE",
    "action_type": "SPLIT",
    "priority": 5,
    "config": {
        "algorithm": "FIXED_RATIO_SPLIT",
        "source_category": "PKO - E132",
        "targets": [
            {"category": "PKO - E132", "ratio": 0.4},
            {"category": "CHEESE CREAM BUTTER AND FATS - E132", "ratio": 0.6},
        ],
        "inherit_quantity": True,
        "split_remainder": "PROPORTIONAL",
        "preserve_split_once_generated": True,
    },
}
```

---

## 7. A3627 SEED CONFIGURATION (Dynamic Pricing)

### Profile

```python
{
    "sion": a3627_norm,
    "stable_key": "A3627:GLASS_CERAMICS_V1",
    "strategy_type": "ACTION_PIPELINE",
    "config": {
        "description": "A3627 Glass & Ceramics — 4-priority with RUTILE dynamic pricing",
        "rutile_price_threshold": "3.00",
    },
    "version": 1,
    "is_active": False,
}
```

### Rules (4 categories)

```python
[
    {
        "stable_key": "A3627:RUTILE",
        "name": "RUTILE - A3627",
        "priority": 1,
        "expression": {
            "operator": "AND",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "3206"},
                {
                    "operator": "OR",
                    "conditions": [
                        {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "Glass Formers"},
                        {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "Rutile"},
                        {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "Formers"},
                        {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "borax"},
                    ]
                }
            ]
        },
        "max_unit_price": "3.50",
    },
    {
        "stable_key": "A3627:TITANIUM",
        "name": "TITANIUM DIOXIDE - A3627",
        "priority": 2,
        "expression": {
            "operator": "AND",
            "conditions": [
                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "Titanium Dioxide"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "other than"},
            ]
        },
        "max_unit_price": "2.00",
    },
    {
        "stable_key": "A3627:SODA",
        "name": "SODA ASH - A3627",
        "priority": 3,
        "expression": {
            "operator": "AND",
            "conditions": [
                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "Soda Ash"},
            ]
        },
        "max_unit_price": "0.70",
    },
    {
        "stable_key": "A3627:PP",
        "name": "PP - A3627",
        "priority": 4,
        "expression": {
            "operator": "OR",
            "conditions": [
                {"field": "HSN_DIGITS", "operator": "starts_with", "value": "3902"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "Polypropylene"},
                {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "pp granules"},
                {
                    "operator": "AND",
                    "conditions": [
                        {"field": "HSN_DIGITS", "operator": "starts_with", "value": "39"},
                        {"field": "PRODUCT_DESCRIPTION", "operator": "word_contains", "value": "packing"},
                    ]
                },
            ]
        },
        "max_unit_price": "1.20",
    },
]
```

### Actions with DYNAMIC_RUTILE_FIXED_RATE_WATERFALL

Key action (Priority 1):
```python
{
    "stable_key": "A3627:ALLOCATE_RUTILE",
    "action_type": "ALLOCATE",
    "priority": 1,
    "config": {
        "algorithm": "DYNAMIC_RUTILE_FIXED_RATE_WATERFALL",
        "category": "RUTILE - A3627",
        "price_low": "2.50",
        "price_high": "3.50",
        "price_threshold": "3.00",
        "compute_threshold_on": "average_import_price_of_matched_items",
        "granularity": "WHOLE_UNIT",
        "consume_remaining": True,
    },
}
```

Other actions (fixed rates):
```python
[
    {
        "stable_key": "A3627:ALLOCATE_TITANIUM",
        "action_type": "ALLOCATE",
        "priority": 2,
        "config": {
            "algorithm": "CAPPED_FIXED_RATE_WATERFALL",
            "category": "TITANIUM DIOXIDE - A3627",
            "rate": "2.00",
            "granularity": "WHOLE_UNIT",
            "consume_remaining": True,
        },
    },
    {
        "stable_key": "A3627:ALLOCATE_SODA",
        "action_type": "ALLOCATE",
        "priority": 3,
        "config": {
            "algorithm": "CAPPED_FIXED_RATE_WATERFALL",
            "category": "SODA ASH - A3627",
            "rate": "0.70",
            "granularity": "WHOLE_UNIT",
            "consume_remaining": True,
        },
    },
    {
        "stable_key": "A3627:ALLOCATE_PP",
        "action_type": "ALLOCATE",
        "priority": 4,
        "config": {
            "algorithm": "CAPPED_FIXED_RATE_WATERFALL",
            "category": "PP - A3627",
            "rate": "1.20",
            "granularity": "WHOLE_UNIT",
            "consume_remaining": True,
        },
    },
]
```

---

## 8. SHARED ACTION PIPELINE DESIGN

### Question: Can all 5 norms share a single profile?

**Answer: NO** — Each norm has different:
1. **Match predicates** (E1 confectionery vs A3627 glass formers)
2. **Split logic** (E5/E126/E132 split, A3627 doesn't)
3. **Pricing algorithms** (E1/E5 dynamic milk, A3627 dynamic RUTILE)
4. **Output mappings** (each norm has its own item-name taxonomy)

### Recommended: Norm-Scoped Profiles + Shared Actions

```python
# Architecture:
# 1. One profile per norm (5 profiles total)
# 2. Each profile has its own rules (18 rules total)
# 3. Actions are INLINE per profile (not shared)
#    - But action config schema is consistent across all norms
#    - All follow: MATCH → GROUP → ALLOCATE → (SPLIT?) → REBALANCE → MAP_OUTPUT
#    - Priority 1-7 is consistent across norms

# Benefit: Clarity + isolation
#   - Each norm's rules are scoped to its profile
#   - If one norm's rules change, others are unaffected
#   - Simple audit trail (profile.version increments with rule changes)

# Future: Could extract common action configs to a shared library
#   - e.g., CANONICAL_PLAN_GROUP_KEY action config is identical for all norms
#   - But don't refactor now; keep it simple until the pattern is proven
```

---

## 9. IDEMPOTENCY & VERSIONING STRATEGY

### Idempotency via stable_key

```python
# All creates use get_or_create with stable_key:

SionPlanningProfile.objects.get_or_create(
    sion=e1_norm,
    stable_key="E1:CONFECTIONERY_V1",
    defaults={...}
)

SionPlanningRule.objects.get_or_create(
    sion=e1_norm,
    stable_key="E1:OTHER_CONFECTIONERY",
    defaults={...}
)

SionPlanningAction.objects.get_or_create(
    profile=profile,
    stable_key="E1:MATCH",
    defaults={...}
)
```

### Versioning Strategy

**Version Increments:**
- `SionPlanningProfile.version`: Increments when rules or actions change
- `SionPlanningRule.version`: Increments when expression or max_unit_price changes
- `SionPlanningAction.version`: Increments when config changes

**Active/Inactive Phases:**
1. **Draft Phase** (`is_active=False`)
   - New profile/rules/actions created in draft state
   - Tests run against draft (side-by-side with hard-code)
   - No user-facing impact

2. **Activation Phase** (`is_active=True`)
   - Set `is_active=True` for ONE profile per norm after parity tests pass
   - Old version (if any) remains as inactive row (audit trail)
   - Hard-code planner can be deprecated (but not deleted)

3. **Rollback** (if needed)
   - Set `is_active=False` for new profile
   - Set `is_active=True` for previous version
   - Revert to hard-code if needed

**Constraint in Model:**
```python
# From core.py SionPlanningProfile.Meta:
constraints = [
    models.UniqueConstraint(
        fields=("sion",), 
        condition=models.Q(is_active=True),
        name="uniq_active_sion_planning_profile",
    ),
]

# Ensures only one active profile per norm at a time
```

---

## 10. RULE EXPRESSION EXAMPLES (Complex Matchers)

### E126: PKO + Olive Oil Split Trigger

**Business Rule:** If BOTH HSN 1513 (PKO) AND olive signals (HSN 1509, or description contains 1500/1509/1510) are present on the SAME record, split 50%/50%.

**Expression Design:**
```json
{
  "operator": "AND",
  "conditions": [
    {
      "field": "HSN_DIGITS",
      "operator": "starts_with",
      "value": "1513"
    },
    {
      "operator": "OR",
      "conditions": [
        {
          "field": "HSN_DIGITS",
          "operator": "starts_with",
          "value": "1509"
        },
        {
          "field": "PRODUCT_DESCRIPTION",
          "operator": "contains",
          "value": "1500"
        },
        {
          "field": "PRODUCT_DESCRIPTION",
          "operator": "contains",
          "value": "1509"
        },
        {
          "field": "PRODUCT_DESCRIPTION",
          "operator": "contains",
          "value": "1510"
        }
      ]
    }
  ]
}
```

**Operator Semantics:**
- `starts_with`: HSN code prefix (case-insensitive, normalized)
- `contains`: Substring match (NOT word boundary), normalized lowercase
- `word_contains`: Word-boundary match (used for "nut" vs "peanut" distinction)
- `in`: List membership (e.g., HSN in ["0401", "0405", "0406"])

---

### E132: Strict Cheese (Dairy + Vegetable + Oil)

**Business Rule:** Vegetable oil (1513) that ALSO signals dairy (0401/0405/0406) + both "vegetable" and "oil" in description = 40% PKO / 60% Cheese split.

**Expression Design:**
```json
{
  "operator": "AND",
  "conditions": [
    {
      "field": "HSN_DIGITS",
      "operator": "in",
      "value": ["0401", "0405", "0406"]
    },
    {
      "field": "PRODUCT_DESCRIPTION",
      "operator": "word_contains",
      "value": "vegetable"
    },
    {
      "field": "PRODUCT_DESCRIPTION",
      "operator": "word_contains",
      "value": "oil"
    }
  ]
}
```

**Why word_contains (not contains)?**
- Ensures "vegetable" is a full word (not substring of "vegetables2" or "vegetable-derived")
- Avoids false matches on typos or concatenations
- Consistent with data quality in DGFT imports

---

### A3627: RUTILE (Glass Formers / Rutile / Formers + Borax)

**Business Rule:** HSN 3206 + (mention of "Glass Formers" OR "Rutile" OR "Formers" + "borax") = RUTILE (dynamic pricing).

**Expression Design:**
```json
{
  "operator": "AND",
  "conditions": [
    {
      "field": "HSN_DIGITS",
      "operator": "starts_with",
      "value": "3206"
    },
    {
      "operator": "OR",
      "conditions": [
        {
          "field": "PRODUCT_DESCRIPTION",
          "operator": "word_contains",
          "value": "Glass Formers"
        },
        {
          "field": "PRODUCT_DESCRIPTION",
          "operator": "word_contains",
          "value": "Rutile"
        },
        {
          "operator": "AND",
          "conditions": [
            {
              "field": "PRODUCT_DESCRIPTION",
              "operator": "word_contains",
              "value": "Formers"
            },
            {
              "field": "PRODUCT_DESCRIPTION",
              "operator": "word_contains",
              "value": "borax"
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 11. SEED MIGRATION ROADMAP (Phased Timeline)

### Phase 1: Infrastructure & E1 (Days 1-2)

**Deliverables:**
- ✅ Management command: `seed_sion_planning_rules.py`
- ✅ Seeder base class: `SionPlannerSeeder`
- ✅ E1Seeder implementation
- ✅ E1 SionPlanningProfile (1 row, `is_active=False`)
- ✅ E1 SionPlanningRule (2 rows)
- ✅ E1 SionPlanningAction (5 rows)
- ✅ LegacyE1Adapter (delegates to hard-code classifier)
- ✅ Golden test cases (5 licenses, hard-code vs DB parity)

**Task:**
```bash
python manage.py seed_sion_planning_rules --sion E1 --dry-run
python manage.py seed_sion_planning_rules --sion E1 --apply
pytest backend/apps/license/tests/test_sion_rule_seed_e1.py -v
```

**Success Criteria:**
- All 2 rules created
- All 5 actions created with correct priority
- E1 parity tests pass (hard-code output == DB rule output)
- Can re-run command without errors (idempotent)

---

### Phase 2: E5 (Days 3-4)

**Deliverables:**
- ✅ E5Seeder implementation
- ✅ E5 SionPlanningProfile (1 row, `is_active=False`)
- ✅ E5 SionPlanningRule (8 rows)
- ✅ E5 SionPlanningAction (6 rows, including SPLIT)
- ✅ LegacyE5Adapter
- ✅ Golden test cases (5 licenses with splits)

**Critical Test Case:**
- License with oil items that trigger split (PKO + Olive signals)
- Verify output has both PKO - E5 and OLIVE OIL - E5 lines (50%/50% split)
- Verify split is preserved on re-run

**Success Criteria:**
- All 8 rules created with correct expressions
- SPLIT action generates 2 output categories (PKO + Olive)
- Split parity tests pass
- No regression: existing E1 tests still pass

---

### Phase 3: E126 (Days 5-6)

**Deliverables:**
- ✅ E126Seeder implementation
- ✅ E126 SionPlanningProfile (1 row)
- ✅ E126 SionPlanningRule (3 rows: NUT, PKO, OLIVE)
- ✅ E126 SionPlanningAction (6 rows, including 50%/50% SPLIT)
- ✅ LegacyE126Adapter
- ✅ Golden test cases (5 licenses)

**Critical Test Case:**
- License with record that has BOTH 1513 (PKO) and 1509 (Olive) signals
- Verify split generates exactly 2 lines (PKO - E126 @ 50%, OLIVE OIL - E126 @ 50%)
- Verify split is NOT regenerated if already exists on group

**Success Criteria:**
- E126 parity tests pass
- 50%/50% split is generated correctly
- Split preservation logic works (no double-split on re-run)

---

### Phase 4: E132 (Days 7-9)

**Deliverables:**
- ✅ E132Seeder implementation
- ✅ E132 SionPlanningProfile (1 row)
- ✅ E132 SionPlanningRule (6 rows, **careful priority ordering**)
- ✅ E132 SionPlanningAction (7 rows, including 40%/60% SPLIT)
- ✅ LegacyE132Adapter
- ✅ Priority ordering tests (5 licenses with multi-match records)
- ✅ Golden test cases (10+ licenses)

**Critical Test Cases:**
1. Record with NUT_NUTS signal → should classify as NUT (not Yeast or Cheese)
2. Record with Cheese + PKO signals → should split 40/60, not allocate 100% to one
3. Record with RBD signal alone → should NOT trigger split (RBD blocks split)
4. Record with both Cheese + RBD signals → should go to RBD (priority 4 > 5)

**Success Criteria:**
- All 6 rules created with correct priority ordering
- Priority logic verified: NUT > YEAST > PKO > RBD > CHEESE > ALUMINIUM
- Strict Cheese detection works (dairy HSN + "vegetable" + "oil" required)
- 40%/60% split is generated correctly
- E132 parity tests pass

---

### Phase 5: A3627 (Days 10-11)

**Deliverables:**
- ✅ A3627Seeder implementation
- ✅ A3627 SionPlanningProfile (1 row)
- ✅ A3627 SionPlanningRule (4 rows)
- ✅ A3627 SionPlanningAction (6 rows, including DYNAMIC_RUTILE_FIXED_RATE_WATERFALL)
- ✅ LegacyA3627Adapter
- ✅ Dynamic pricing logic (RUTILE_AVERAGE_IMPORT_PRICE_CALCULATOR)
- ✅ Golden test cases (5 licenses, varying RUTILE avg prices)

**Critical Test Cases:**
1. License with RUTILE items, avg price $2.85 → should allocate at $2.50/mt
2. License with RUTILE items, avg price $3.22 → should allocate at $3.50/mt
3. License with mixed RUTILE + TITANIUM + SODA → verify waterfall order (RUTILE first)

**Success Criteria:**
- Dynamic pricing logic implemented and tested
- RUTILE avg price threshold correctly applied
- A3627 parity tests pass

---

### Phase 6: Activation & Cutover (Day 12)

**Deliverables:**
- ✅ All 5 profiles created with `is_active=False`
- ✅ Integration tests pass (all 5 norms)
- ✅ Cutover script: activate profiles, deprecate hard-code
- ✅ Rollback plan documented

**Activation Steps:**
```python
# Activate all profiles
for norm in ["E1", "E5", "E126", "E132", "A3627"]:
    profile = SionPlanningProfile.objects.get(
        sion__norm_class=norm,
        is_active=False
    )
    profile.is_active = True
    profile.save()
    # Hard-code planner auto-disabled (wrapped in if profile.is_active check)
```

**Success Criteria:**
- All 5 norms produce identical output (hard-code vs DB rules)
- No regression in existing tests
- Performance comparable (queries optimized)

---

## 12. TESTING STRATEGY FOR SEED CONFIGURATION

### Test Suite Structure

```python
# backend/apps/license/tests/test_sion_rule_seed_*.py

class SeedConfigurationTests(TestCase):
    """Verify all seeded rules and actions are valid."""
    
    @classmethod
    def setUpClass(cls):
        # Ensure profiles, rules, actions exist
        cls.cmd = Command()
        cls.cmd.handle(sion=["E1", "E5", "E126", "E132", "A3627"], apply=True)
    
    def test_all_profiles_created(self):
        profiles = SionPlanningProfile.objects.filter(is_active=False)
        self.assertEqual(profiles.count(), 5)
        for norm in ["E1", "E5", "E126", "E132", "A3627"]:
            self.assertTrue(
                profiles.filter(sion__norm_class=norm).exists(),
                f"Profile for {norm} not created"
            )
    
    def test_all_rules_created(self):
        rules = SionPlanningRule.objects.filter(is_active=True)
        # E1: 2, E5: 8, E126: 3, E132: 6, A3627: 4 = 23 total
        self.assertEqual(rules.count(), 23)
    
    def test_all_actions_created(self):
        actions = SionPlanningAction.objects.filter(is_active=True)
        # Each profile has 5-7 actions
        # E1: 5, E5: 6, E126: 6, E132: 7, A3627: 6 = 30 total
        self.assertGreaterEqual(actions.count(), 30)
    
    def test_all_rules_have_valid_expression(self):
        from apps.license.services.sion_rule_engine import validate_expression
        for rule in SionPlanningRule.objects.filter(is_active=True):
            try:
                validate_expression(rule.expression)
            except ValidationError as e:
                self.fail(f"Rule {rule.stable_key} has invalid expression: {e}")
    
    def test_all_actions_have_valid_config(self):
        from apps.license.models import _validate_planning_json
        for action in SionPlanningAction.objects.filter(is_active=True):
            try:
                _validate_planning_json(action.config, f"Action {action.stable_key}")
            except ValidationError as e:
                self.fail(f"Action {action.stable_key} has invalid config: {e}")
    
    def test_no_duplicate_rule_priorities(self):
        for norm in ["E1", "E5", "E126", "E132", "A3627"]:
            rules = SionPlanningRule.objects.filter(
                sion__norm_class=norm,
                is_active=True
            )
            priorities = list(rules.values_list("priority", flat=True))
            self.assertEqual(len(priorities), len(set(priorities)),
                f"Duplicate priorities in {norm} rules: {priorities}")
    
    def test_no_duplicate_action_priorities(self):
        for profile in SionPlanningProfile.objects.filter(is_active=False):
            actions = profile.actions.filter(is_active=True)
            priorities = list(actions.values_list("priority", flat=True))
            self.assertEqual(len(priorities), len(set(priorities)),
                f"Duplicate priorities in {profile.stable_key} actions: {priorities}")
    
    def test_e1_parity(self):
        """Hard-code vs DB rule output parity."""
        license_obj = create_test_e1_license()
        
        # Hard-code output
        hard_code_lines, hard_code_cif = compute_e1_auto_plan(license_obj)
        
        # DB rule output
        from apps.license.services.canonical_planning_service import CanonicalPlanningService
        svc = CanonicalPlanningService(license_obj)
        db_lines, db_cif = svc.compute_plan()
        
        self.assertEqual(len(hard_code_lines), len(db_lines))
        self.assertAlmostEqual(hard_code_cif, db_cif, places=2)
        # Detailed line comparison...
    
    def test_e5_split_preservation(self):
        """E5 split should not regenerate on re-run."""
        license_obj = create_test_e5_license_with_oils()
        
        # First run: generate split
        lines_v1, _ = compute_e5_auto_plan(license_obj)
        pko_lines = [l for l in lines_v1 if l["item_name"].name == "PALM KERNEL OIL - E5"]
        olive_lines = [l for l in lines_v1 if l["item_name"].name == "OLIVE OIL - E5"]
        self.assertEqual(len(pko_lines), 1)
        self.assertEqual(len(olive_lines), 1)
        
        # Persist split
        for line in lines_v1:
            LicenseItemPlan.objects.create(license_item=..., **line)
        
        # Second run: split should be preserved
        lines_v2, _ = compute_e5_auto_plan(license_obj)
        pko_lines_v2 = [l for l in lines_v2 if l["item_name"].name == "PALM KERNEL OIL - E5"]
        olive_lines_v2 = [l for l in lines_v2 if l["item_name"].name == "OLIVE OIL - E5"]
        
        # Same split should be reproduced (not regenerated)
        self.assertEqual(pko_lines[0]["planned_quantity"], pko_lines_v2[0]["planned_quantity"])
        self.assertEqual(olive_lines[0]["planned_quantity"], olive_lines_v2[0]["planned_quantity"])
    
    def test_e132_priority_ordering(self):
        """E132 priority logic verified."""
        # License with multi-match record (NUT + Yeast + PKO signals)
        # Should classify as NUT (priority 1), not Yeast or PKO
        record = create_test_e132_multi_match_record()
        
        from apps.license.services.sion_rule_engine import evaluate_expression
        rules = SionPlanningRule.objects.filter(
            sion__norm_class="E132",
            is_active=True
        ).order_by("priority")
        
        matched_rule = None
        for rule in rules:
            if evaluate_expression(rule.expression, record.as_context()):
                matched_rule = rule
                break
        
        self.assertEqual(matched_rule.stable_key, "E132:NUT",
            "Multi-match record should classify as NUT (priority 1)")
    
    def test_a3627_dynamic_pricing_low(self):
        """A3627 RUTILE dynamic pricing: avg < $3.00 → $2.50."""
        license_obj = create_test_a3627_license_with_rutile_avg_2_85()
        
        lines, _ = compute_a3627_auto_plan(license_obj)
        rutile_lines = [l for l in lines if l["item_name"].name == "RUTILE - A3627"]
        
        self.assertGreater(len(rutile_lines), 0, "Should generate RUTILE line")
        self.assertAlmostEqual(
            rutile_lines[0]["unit_price"], 2.50, places=2,
            "RUTILE price should be $2.50 when avg < $3.00"
        )
    
    def test_a3627_dynamic_pricing_high(self):
        """A3627 RUTILE dynamic pricing: avg >= $3.00 → $3.50."""
        license_obj = create_test_a3627_license_with_rutile_avg_3_22()
        
        lines, _ = compute_a3627_auto_plan(license_obj)
        rutile_lines = [l for l in lines if l["item_name"].name == "RUTILE - A3627"]
        
        self.assertGreater(len(rutile_lines), 0)
        self.assertAlmostEqual(
            rutile_lines[0]["unit_price"], 3.50, places=2,
            "RUTILE price should be $3.50 when avg >= $3.00"
        )
```

### Integration Test (Multi-Norm)

```python
class SeedIntegrationTests(TestCase):
    """End-to-end tests across all norms."""
    
    def test_all_norms_produce_valid_plans(self):
        test_licenses = {
            "E1": create_test_e1_license(),
            "E5": create_test_e5_license(),
            "E126": create_test_e126_license(),
            "E132": create_test_e132_license(),
            "A3627": create_test_a3627_license(),
        }
        
        from apps.license.services.canonical_planning_service import CanonicalPlanningService
        
        for norm, license_obj in test_licenses.items():
            svc = CanonicalPlanningService(license_obj)
            lines, remaining_cif = svc.compute_plan()
            
            # Basic validations
            self.assertIsNotNone(lines)
            self.assertIsInstance(lines, list)
            self.assertGreater(len(lines), 0, f"{norm} should generate at least one line")
            
            # Line shape validation
            for line in lines:
                self.assertIn("import_item", line)
                self.assertIn("item_name", line)
                self.assertIn("planned_quantity", line)
                self.assertIn("unit_price", line)
    
    def test_no_regression_vs_hard_code(self):
        """All hard-code outputs should match DB rule outputs."""
        test_cases = {
            "E1": (create_test_e1_license(), compute_e1_auto_plan),
            "E5": (create_test_e5_license(), compute_e5_auto_plan),
            "E126": (create_test_e126_license(), compute_e126_auto_plan),
            "E132": (create_test_e132_license(), compute_e132_auto_plan),
            "A3627": (create_test_a3627_license(), compute_a3627_auto_plan),
        }
        
        from apps.license.services.canonical_planning_service import CanonicalPlanningService
        
        for norm, (license_obj, hard_code_fn) in test_cases.items():
            hard_code_lines, hard_code_cif = hard_code_fn(license_obj)
            
            svc = CanonicalPlanningService(license_obj)
            db_lines, db_cif = svc.compute_plan()
            
            self.assertEqual(
                len(hard_code_lines), len(db_lines),
                f"{norm}: line count mismatch"
            )
            self.assertAlmostEqual(
                hard_code_cif, db_cif, places=2,
                f"{norm}: remaining CIF mismatch"
            )
```

---

## Summary

| Phase | Deliverable | Rules | Actions | Tests | Days |
|-------|-------------|-------|---------|-------|------|
| 1 | E1 Infrastructure | 2 | 5 | 5 | 2 |
| 2 | E5 + Split | 8 | 6 | 8 | 2 |
| 3 | E126 + 50/50 Split | 3 | 6 | 5 | 2 |
| 4 | E132 + Priority + 40/60 Split | 6 | 7 | 10 | 3 |
| 5 | A3627 + Dynamic RUTILE | 4 | 6 | 8 | 2 |
| 6 | Activation & Cutover | — | — | Integration | 1 |
| **TOTAL** | **All 5 Norms** | **23** | **30+** | **40+** | **12 days** |

**Key Risks & Mitigations:**
1. **E1/E5 dynamic pricing** (DWP/SWP/WPC) — Use existing `CanonicalPlanningService` to compute balance-driven rates
2. **E126/E132 split preservation** — Implement `preserve_split_once_generated=True` in SPLIT action config
3. **E132 priority ordering** — Validate with multi-match test cases before activation
4. **A3627 RUTILE dynamic pricing** — Test with golden licenses at avg prices $2.85 and $3.22

---

## Next Steps

1. **Start Phase 1:** Implement management command + E1Seeder + golden tests
2. **Parallel:** Implement `DYNAMIC_RUTILE_FIXED_RATE_WATERFALL` algorithm (for A3627)
3. **Validate:** Run all golden tests daily; iterate on rule expressions based on test failures
4. **Phase-by-phase cutover:** Activate each norm only after parity tests pass
5. **Monitor:** After cutover, compare hard-code vs DB rule output for 30 days before deprecating hard-code
