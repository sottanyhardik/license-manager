"""Product matching for Item Pivot consolidation (deterministic, AI-pluggable).

Suggests a master item (``ItemNameModel``) for import items that have no
master link (Unmapped) or several (Ambiguous). Matching is a *suggestion
layer*: it never changes HSN codes, SION rules, entitlement groups, quantities
or CIF. Every suggestion carries a confidence, an explanation and explicit
compatibility checks; conflicts are never auto-approvable.

Pipeline per source group (normalised description + HSN + SION):
1. Reuse a prior human decision for the same source key (no re-matching).
2. Candidate masters legitimate for the SION (``ItemNameModel.norms``).
3. Score text similarity after normalisation (spelling variants, abbreviations,
   '&'→'and', plurals, HS-code tokens removed).
4. Validate: SION legitimacy, HSN compatibility with the master's existing
   import items, entitlement-profile product aliases (e.g. E126 Sunflower →
   Olive Oil entitlement) and multi-entitlement descriptions.
5. Optional advisor hook (``ProductMatchAdvisor``) may re-rank — the default is
   the deterministic advisor; no external AI is called (owner decision 2026-11-18).

Approval links the import items to the chosen master (owner decision
2026-11-18: this also feeds Auto Plan classification), records the previous and
new links, and flags each affected licence for re-planning (not dispatched).
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Iterable, Protocol

from django.db import transaction

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import LicenseImportItemsModel, ProductMatchDecision, SionPlanningRule
from apps.license.services.sion_planner_config.entitlement_profiles import entitlement_profile

logger = logging.getLogger(__name__)

MATCHER_VERSION = "deterministic-v1"
# Entitlement implied by the HSN itself, per norm (domain audit 2026-11-19): an E126 record without any alias
# wording still may not be linked across the PKO / Olive Oil entitlements. Only norms listed here are affected.
ENTITLEMENT_HSN_PREFIXES = {"E126": {"1513": "PALM KERNEL OIL", "1509": "OLIVE OIL", "1510": "OLIVE OIL"}}
# Owner spec 2026-11-19: 95–100 strong (suggest, bulk-eligible) · 80–94 probable (review) · <80 keep separate.
HIGH, STRONG, REVIEW = 95, 90, 80

# Spelling variants / abbreviations → canonical token(s). Applied to whole words.
VARIANTS = {
    "aluminum": "aluminium", "alu": "aluminium", "al": "aluminium",
    "pp": "polypropylene", "polyproplene": "polypropylene", "polypropelene": "polypropylene",
    "flavor": "flavour", "flavors": "flavour", "flavours": "flavour", "flavoring": "flavouring",
    "colour": "color", "colours": "color", "colors": "color",
    "paperboard": "paper board", "paperboards": "paper board",
    "boards": "board", "papers": "paper", "oils": "oil", "nuts": "nut", "chemicals": "chemical",
    "veg": "vegetable", "pko": "palm kernel oil",
}
PHRASES = [(re.compile(r"\bpoly[\s-]*propylene\b"), "polypropylene"), (re.compile(r"\bp\s*\.\s*p\b(?!\.?[a-z]\b)\.?"), "polypropylene"),
           (re.compile(r"\bsun\s+flower\b"), "sunflower"),
           (re.compile(r"\bpaper\s*&\s*paper\s*board\b"), "paper and paper board")]
STOPWORDS = {"hs", "hsn", "code", "of", "the", "for", "and", "or", "with", "other", "than", "namely", "such", "as", "e", "g",
             "relevant", "approved", "by", "fssai", "fda", "min", "max", "purity", "grade", "a", "b", "c", "i", "ii", "iii", "iv", "v",
             "vi", "vii", "viii", "ix", "x"}


def normalise(text: str | None) -> str:
    value = str(text or "").lower().replace("&", " and ")
    for pattern, repl in PHRASES:
        value = pattern.sub(repl, value)
    value = re.sub(r"\(\s*hs\s*code[^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    words = [VARIANTS.get(w, w) for w in value.split()]
    words = [_singular(w) for w in " ".join(words).split()]
    return " ".join(w for w in words if not w.isdigit() and w not in STOPWORDS)


def _singular(word: str) -> str:
    if len(word) > 4 and word.endswith(("ches", "shes", "xes", "ses")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


SEGMENT_SPLIT = re.compile(r"\s*(?:/|,|;|\+|\bor\b|\band\b(?=\s+\w+\s+(?:oil|foil|ash|oxide)))\s*", re.IGNORECASE)


# Product-phrase extraction (review 2026-11-19, root causes found on real licence wording):
# * enumeration markers "(A) … (B) …" / "(i) …" / "(1) …" separate products — they were deleted together with
#   every other parenthesis BEFORE splitting, collapsing five products into one segment;
# * a category heading before "namely / viz / such as / including / i.e." is a label, not a product
#   ("MODIFIERS NAMELY, (A) …" produced a bogus "modifier" product);
# * licence condition clauses ("- With the condition the import of … is not allowed …", "subject to …",
#   "as per PC 13/…") are restrictions, not products;
# * a detached modifier ("Dense / Light", "Refined", "Powder") qualifies the previous product, it is not a product.
ENUMERATION = re.compile(r"\(\s*(?:[a-z]|[ivx]{1,4}|\d{1,2})\s*\)", re.IGNORECASE)
CONDITION_CLAUSE = re.compile(
    r"[\s,;-]*\b(?:with\s+the\s+condition|on\s+condition|condition\s+that|subject\s+to|provided\s+that|is\s+not\s+allowed|"
    r"are\s+not\s+allowed|as\s+per\s+(?:pc|policy\s+circular|public\s+notice|notification|(?:the\s+)?(?:packing\s+)?policy)|"
    r"cif\s+value\s+(?:of\s+)?this|(?:shall|should)\s+not\s+exceed)\b"
    # The clause ends at ";" or a sentence-ending "." — a product listed after it is kept (dates like 31.01.2011 are not ends).
    r"(?:[^;.]|\.(?=\S))*", re.IGNORECASE)
HEADING = re.compile(r"^.*?\b(?:namely|viz\.?|such\s+as|including|i\.\s?e\.?)\b[\s,:;.-]*", re.IGNORECASE)
# Only grade / form qualifiers that never name a product on their own (review 2026-11-19: colours, "food",
# "liquid", "powder" … can be products and are NOT merged).
MODIFIER_WORDS = {"dense", "light", "heavy", "fine", "coarse", "refined", "crude", "pure"}
# A segment made only of these words is a category label ("Packing Material / PP"), not a product — dropped when the
# description names a real product besides it.
CATEGORY_WORDS = {"packing", "packaging", "material", "matarial", "matrial", "packimg", "item", "input", "other"}


def _lists_products(inner: str) -> bool:
    if not SEGMENT_SPLIT.search(inner):
        return False
    parts = [normalise(p) for p in SEGMENT_SPLIT.split(inner)]
    real = [p for p in parts if p and not all(w in MODIFIER_WORDS for w in p.split())]
    return len(real) >= 2


def segment_pairs(text: str | None) -> list[tuple[str, str]]:
    """[(display phrase, normalised phrase)] — distinct products a description lists, in order."""
    raw = ENUMERATION.sub(" / ", str(text or ""))
    raw = CONDITION_CLAUSE.sub("", raw)
    # A parenthetical that itself lists products ("(Olive oil / Sunflower oil)") stays reviewable as extra products;
    # descriptive notes ("(Edible grade)", "(HS Code 1509 / 1510)", "(Dense / Light)") are dropped.
    raw = re.sub(r"\(([^)]*)\)", lambda m: f" / {m.group(1)} " if _lists_products(m.group(1)) else " ", raw)
    headed = HEADING.sub("", raw, count=1)
    if headed.strip() and headed.strip() != raw.strip() and SEGMENT_SPLIT.search(headed):
        raw = headed  # "X namely A / B" → the list, not the heading
    parts = [part for part in SEGMENT_SPLIT.split(raw) if normalise(part)]
    # Only a LEADING label is a heading ("Packing Material / PP"); a label later in the list ("PP / Packing Material")
    # may be a genuine second item, so the description stays multi-product for human review.
    while len(parts) > 1 and all(w in CATEGORY_WORDS for w in normalise(parts[0]).split()):
        parts = parts[1:]
    pairs: list[tuple[str, str]] = []
    for part in parts:
        norm = normalise(part)
        if not norm:
            continue
        words = norm.split()
        if pairs and all(w in MODIFIER_WORDS for w in words):
            display, prev = pairs[-1]
            pairs[-1] = (f"{display} / {part.strip()}", prev)  # modifier of the previous product
            continue
        if norm not in {n for _, n in pairs}:
            pairs.append((part.strip(" -:.,;"), norm))
    return pairs


def product_segments(text: str | None) -> list[str]:
    """Distinct product phrases a description lists (e.g. 'HDPE/PP/GRANULES' → 3)."""
    return [norm for _, norm in segment_pairs(text)]


def tokens(text: str) -> set[str]:
    return {t for t in text.split() if len(t) > 1}


def source_key(normalised: str, hsn: str | None, sion: str | None) -> str:
    return f"{normalised[:500]}|{hsn or '-'}|{sion or '-'}"


@dataclass
class Candidate:
    item_id: int
    name: str
    score: int
    reasons: list[str] = field(default_factory=list)


class ProductMatchAdvisor(Protocol):
    """Pluggable re-ranking step (e.g. an LLM). Must return the same candidates, re-scored."""
    name: str

    def rerank(self, source_text: str, candidates: list[Candidate]) -> list[Candidate]: ...


class DeterministicAdvisor:
    name = MATCHER_VERSION

    def rerank(self, source_text: str, candidates: list[Candidate]) -> list[Candidate]:
        return candidates


NORM_SUFFIX = re.compile(r"\s-\s*[A-Z]+\d+\s*$")


def master_label(name: str) -> str:
    """Master name without a trailing norm suffix ('PP - E5' → 'PP'); the SION is checked separately."""
    return NORM_SUFFIX.sub("", str(name or "")).strip()


def text_score(source: str, master: str) -> tuple[int, list[str]]:
    a, b = normalise(source), normalise(master_label(master))
    if not a or not b:
        return 0, ["Empty description after normalisation"]
    if a == b:
        return 100, ["Exact match after normalising spelling, abbreviations and punctuation"]
    ta, tb = tokens(a), tokens(b)
    reasons = []
    contain = len(tb & ta) / len(tb) if tb else 0.0
    coverage = len(tb & ta) / len(ta) if ta else 0.0  # how much of the description the master explains
    jaccard = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    ratio = SequenceMatcher(None, a, b).ratio()
    score = max(ratio, jaccard, (0.6 + 0.39 * coverage) if contain == 1 else contain * 0.8)
    if contain == 1:
        reasons.append(f"All master-name words ({', '.join(sorted(tb))}) appear in the description")
    elif ta & tb:
        reasons.append(f"Shared words: {', '.join(sorted(ta & tb))}")
    reasons.append(f"Text similarity {round(ratio * 100)}%")
    return min(99, round(score * 100)), reasons


def _master_hsn_chapters(item_ids: Iterable[int]) -> dict[int, set[str]]:
    chapters: dict[int, set[str]] = defaultdict(set)
    through = LicenseImportItemsModel.items.through
    for name_id, hsn in through.objects.filter(itemnamemodel_id__in=list(item_ids)).values_list(
        "itemnamemodel_id", "licenseimportitemsmodel__hs_code__hs_code",
    ):
        if hsn:
            chapters[name_id].add(str(hsn)[:2])
    return chapters


def _entitlement_targets(sion: str | None, text: str, hsn: str | None = None) -> dict[str, str]:
    """Entitlement-profile product aliases found in the text (and, for listed norms, the HSN) → required entitlement."""
    hits: dict[str, str] = {}
    for prefix, entitlement in ENTITLEMENT_HSN_PREFIXES.get(sion or "", {}).items():
        if str(hsn or "").startswith(prefix):
            hits[f"HSN {prefix}"] = entitlement
    upper = str(text or "").upper()
    for group in entitlement_profile(sion or "").get("groups", []):
        for product in group.get("products", []):
            if any(alias.upper() in upper for alias in product.get("aliases", [])):
                hits[product["name"]] = product["entitlement"]
    return hits


def _ruled_items(sion_id: int | None) -> set[int]:
    if not sion_id:
        return set()
    ids = set(SionPlanningRule.objects.filter(sion_id=sion_id, is_active=True, import_item__isnull=False).values_list("import_item_id", flat=True))
    rules = SionPlanningRule.objects.filter(sion_id=sion_id, is_active=True).prefetch_related("percentage_rows", "unit_value_rows")
    for rule in rules:
        ids.update(r.import_item_id for r in rule.percentage_rows.all())
        ids.update(r.import_item_id for r in rule.unit_value_rows.all())
    return ids


def suggest(groups: list[dict], *, advisor: ProductMatchAdvisor | None = None, limit_candidates: int = 5) -> list[dict]:
    """``groups``: [{source_key, description, hsn_code, sion, import_item_ids, license_numbers}] (Unmapped / Ambiguous)."""
    from apps.license.services.product_intelligence.aliases import alias_index
    from apps.license.services.product_intelligence.lifecycle import ModelScorer
    from apps.license.services.product_intelligence.multi_product import approved_by_source, segment_rows

    advisor = advisor or DeterministicAdvisor()
    sion_codes = {g["sion"] for g in groups if g.get("sion")}
    sions = {s.norm_class: s for s in SionNormClassModel.objects.filter(norm_class__in=sion_codes)}
    masters_by_sion: dict[str, list[ItemNameModel]] = defaultdict(list)
    for name in ItemNameModel.objects.filter(is_active=True).prefetch_related("norms").select_related("sion_norm_class"):
        legit = {n.norm_class for n in name.norms.all()} or ({name.sion_norm_class.norm_class} if name.sion_norm_class_id else set())
        for code in legit & sion_codes:
            masters_by_sion[code].append(name)
    all_master_ids = {m.pk for ms in masters_by_sion.values() for m in ms}
    master_chapters = _master_hsn_chapters(all_master_ids)
    aliases = alias_index(sion_codes)  # approved aliases (human) → 100 % suggestions, still validated + approved
    scorer = ModelScorer.build(all_master_ids)  # ACTIVE database-trained model, or None → deterministic only
    ruled = {code: _ruled_items(s.pk) for code, s in sions.items()}
    classified = approved_by_source([g["source_key"] for g in groups])  # approved multi-product classifications
    prior: dict[str, list[ProductMatchDecision]] = defaultdict(list)
    for decision in ProductMatchDecision.objects.filter(source_key__in=[g["source_key"] for g in groups]).select_related("chosen_item", "suggested_item", "decided_by").order_by("-decided_on", "-pk"):
        prior[decision.source_key].append(decision)
    from apps.license.services.product_intelligence.item_name_mapping import undone_import_decision_ids
    undone = undone_import_decision_ids(d.pk for ds in prior.values() for d in ds if d.decision == ProductMatchDecision.APPROVED)

    out = []
    for group in groups:
        sion, hsn, text = group.get("sion"), group.get("hsn_code") or "", group["description"]
        decisions = prior.get(group["source_key"], [])
        # An approval reversed by Undo (Mapping workspace) is history only: the source is pending again and needs a fresh selection.
        approved = next((d for d in decisions if d.decision == ProductMatchDecision.APPROVED and d.chosen_item_id and d.pk not in undone), None)
        rejected_ids = {d.suggested_item_id for d in decisions if d.decision in {ProductMatchDecision.REJECTED, ProductMatchDecision.DIFFERENT}}
        entitlement_hits = _entitlement_targets(sion, text, hsn)
        required_entitlements = set(entitlement_hits.values())
        base = {**group, "sion_known": sion in sions, "entitlement_hits": entitlement_hits,
                "rejected_item_ids": sorted(i for i in rejected_ids if i), "history": [
            {"id": d.pk, "decision": d.decision, "item": (d.chosen_item or d.suggested_item).name if (d.chosen_item_id or d.suggested_item_id) else None,
             "by": getattr(d.decided_by, "username", None), "on": d.decided_on.isoformat()} for d in decisions]}
        if approved:
            out.append({**base, "band": "APPROVED", "action": "APPLY_APPROVED_MAPPING", "confidence": 100, "matcher": "approved",
                         "model": None, "alias_match": False,
                         "suggestion": {"item_id": approved.chosen_item_id, "name": approved.chosen_item.name},
                         "explanation": f"Previously approved mapping #{approved.pk} — reused without re-matching", "conflicts": [], "candidates": [],
                         "checks": approved.checks})
            continue
        scored: list[Candidate] = []
        alias_hits = {item_id: (alias_id, alias_text) for item_id, alias_id, alias_text in aliases.get(sion or "", {}).get(normalise(text), [])}
        for master in masters_by_sion.get(sion or "", []):
            if master.pk in rejected_ids:
                continue
            score, reasons = text_score(text, master.name)
            if master.pk in alias_hits:
                alias_id, alias_text = alias_hits[master.pk]
                score, reasons = 100, [f"Approved alias “{alias_text}” (#{alias_id}) of {master.name}", *reasons]
            scored.append(Candidate(master.pk, master.name, score, reasons))
        model_scores = scorer.score(text, hsn, [c.item_id for c in scored]) if scorer else {}
        if model_scores:
            for c in scored:
                m = model_scores[c.item_id]
                if c.score < 100:  # an approved alias or exact match stays authoritative evidence
                    c.reasons.append(f"Model {scorer.record.version} probability {m['probability']:.2f} (text score {c.score}%)")
                    model_score = round(m["probability"] * 100)
                    # Without textual support the model alone can never reach STRONG / HIGH (bulk) bands.
                    c.score = model_score if c.score >= REVIEW else min(model_score, STRONG - 1)
        scored.sort(key=lambda c: (-c.score, c.name))
        candidates = advisor.rerank(text, [c for c in scored if c.score >= 50])[:limit_candidates]
        names = {m.pk: m.name for m in masters_by_sion.get(sion or "", [])}

        def evaluate(item_id: int | None) -> tuple[list[str], dict[str, Any]]:
            """Deterministic conflicts + checks for one chosen master (AI picks are re-validated the same way)."""
            conflicts: list[str] = []
            if not sion or sion not in sions:
                conflicts.append("SION not identified for these records")
            if len(required_entitlements) > 1:
                conflicts.append(f"Description names products of different entitlements ({', '.join(sorted(entitlement_hits))}) — never merged")
            if item_id is None:
                return conflicts, {}
            name = names.get(item_id, "")
            segments = product_segments(text)
            if len(segments) > 1:
                covered = [seg for seg in segments if tokens(normalise(name)) <= tokens(seg) or text_score(seg, name)[0] >= REVIEW]
                if len(covered) < len(segments):
                    conflicts.append(f"Description lists {len(segments)} products ({'; '.join(segments[:4])}); {name} covers {len(covered)} — a single master would merge different products")
            chapters = master_chapters.get(item_id, set())
            hsn_ok = not hsn or not chapters or hsn[:2] in chapters
            checks = {
                "sion": {"ok": True, "detail": f"{name} is a legitimate item for {sion} (ItemNameModel.norms)"},
                "hsn": {"ok": hsn_ok, "detail": f"Source HSN {hsn or '—'} vs master chapters {', '.join(sorted(chapters)) or 'none yet'}"},
                "entitlement": {"ok": not required_entitlements or name.upper() in {e.upper() for e in required_entitlements},
                                "detail": (f"Entitlement profile maps {', '.join(f'{k} → {v}' for k, v in entitlement_hits.items())}"
                                           if entitlement_hits else "No entitlement-profile alias in the description")},
                "planning_rule": {"ok": item_id in ruled.get(sion or "", set()),
                                  "detail": "Covered by an active planning rule" if item_id in ruled.get(sion or "", set()) else "No active planning rule uses this master item"},
            }
            if not hsn_ok:
                conflicts.append(f"HSN chapter {hsn[:2]} differs from {name}'s existing chapters {', '.join(sorted(chapters))}")
            if not checks["entitlement"]["ok"]:
                conflicts.append(f"Entitlement profile requires {', '.join(sorted(required_entitlements))}, not {name}")
            return conflicts, checks

        best = candidates[0] if candidates else None
        conflicts, checks = evaluate(best.item_id if best else None)
        confidence = best.score if best else 0
        model_info = None
        if best and model_scores:
            model_info = {"version": scorer.record.version, "algorithm": scorer.record.algorithm, **model_scores[best.item_id]}
        row = {**base, "confidence": confidence, "matcher": scorer.record.version if model_info else MATCHER_VERSION, "model": model_info,
               "alias_match": best.item_id in alias_hits if best else False,
               "suggestion": {"item_id": best.item_id, "name": best.name} if best else None,
               "explanation": "; ".join(best.reasons) if best else "No legitimate master item for this SION resembles the description",
               "conflicts": conflicts, "checks": checks,
               "candidates": [{"item_id": c.item_id, "name": c.name, "score": c.score} for c in candidates],
               # Wider, stable list offered to the AI step (it may only choose from these).
               "ai_candidates": [{"item_id": c.item_id, "name": c.name} for c in scored[:15] if c.score >= 30] or
                                [{"item_id": c.item_id, "name": c.name} for c in scored[:15]],
               "_evaluate": evaluate}
        row.update(_band(row))
        if len(product_segments(text)) > 1:
            # Multi-product wording: each detected product is reviewed and approved on its own (never merged).
            row["segments"] = segment_rows(text=text, hsn=hsn, sion=sion, masters=masters_by_sion.get(sion or "", []),
                                           chapters=master_chapters, approved=classified.get(group["source_key"], []),
                                           hsn_codes=group.get("hsn_codes") or [])
            row["classification"] = [{"item_id": c.item_id, "name": c.item.name, "phrase": c.detected_phrase} for c in classified.get(group["source_key"], [])]
            if row["classification"]:
                row["band"], row["action"] = "CLASSIFIED", "MULTI_PRODUCT_CLASSIFIED"
        out.append(row)
    return out


def _band(row: dict) -> dict:
    """Spec bands (2026-11-19): ≥95 HIGH (suggested, bulk-eligible) · 90–94 STRONG · 80–89 REVIEW (both
    probable — user review) · <80 UNCLASSIFIED (kept separate, investigate).
    Any conflict blocks approval regardless of confidence."""
    confidence = row["confidence"]
    if row["conflicts"]:
        return {"band": "CONFLICT", "action": "REVIEW_CONFLICT"}
    if not row["suggestion"]:
        return {"band": "UNMATCHED", "action": "MASTER_DATA_REVIEW"}
    if confidence >= HIGH:
        return {"band": "HIGH", "action": "BULK_REVIEW"}
    if confidence >= STRONG:
        return {"band": "STRONG", "action": "APPROVE_REQUIRED"}
    if confidence >= REVIEW:
        return {"band": "REVIEW", "action": "MANUAL_REVIEW"}
    return {"band": "UNCLASSIFIED", "action": "KEEP_SEPARATE"}


def merge_ai(row: dict, ai: dict | None) -> dict:
    """Fold an AI classification into a deterministic suggestion. AI can choose another candidate and add
    conflicts; it can never clear a deterministic conflict or pick outside the candidate list."""
    out = {k: v for k, v in row.items() if k != "_evaluate"}
    if not ai:
        return out
    out["ai"] = {k: v for k, v in ai.items() if k not in {"record_id"}}
    if ai.get("status") != "OK":
        return out
    candidates = row.get("ai_candidates") or []
    pick = ai.get("suggested_candidate")
    chosen = candidates[pick - 1] if isinstance(pick, int) and 1 <= pick <= len(candidates) else None
    conflicts, checks = row["_evaluate"](chosen["item_id"] if chosen else None)
    if ai.get("multi_product"):
        conflicts.append(f"AI: description names several products ({', '.join(ai.get('products_named') or [])})")
    if not ai.get("hsn_compatible", True):
        conflicts.append(f"AI: HSN conflict — {ai.get('hsn_note', '')}")
    if ai.get("sion_inclusion") == "excluded":
        conflicts.append(f"AI: product appears excluded under {row.get('sion')}")
    out.update({
        "suggestion": {"item_id": chosen["item_id"], "name": chosen["name"]} if chosen else None,
        "confidence": int(ai.get("confidence") or 0) if chosen else 0,
        "explanation": f"{ai.get('model')}: {ai.get('explanation', '')}",
        "conflicts": list(dict.fromkeys(conflicts)), "checks": checks, "matcher": ai.get("model"),
        "alternatives": [candidates[n - 1] for n in ai.get("alternative_candidates") or [] if isinstance(n, int) and 1 <= n <= len(candidates)],
    })
    out.update(_band(out))
    return out


def ai_contexts(suggestions: list[dict]) -> dict[str, dict]:
    """Per-SION context sent with AI requests: planning-rule item names and entitlement-profile aliases."""
    contexts = {}
    for code in {s.get("sion") for s in suggestions if s.get("sion")}:
        sion = SionNormClassModel.objects.filter(norm_class=code).first()
        ruled_ids = _ruled_items(sion.pk) if sion else set()
        aliases = [
            f"{p['name']} (aliases {', '.join(p.get('aliases', []))}) draws on the {p['entitlement']} entitlement"
            for g in entitlement_profile(code).get("groups", []) for p in g.get("products", [])
        ]
        contexts[code] = {"planning_items": sorted(ItemNameModel.objects.filter(pk__in=ruled_ids).values_list("name", flat=True)),
                          "entitlement_aliases": aliases}
    return contexts


class MatchValidationError(ValueError):
    pass


def _validate(suggestion: dict, item: ItemNameModel, *, allow_review: bool) -> None:
    if suggestion["band"] == "CONFLICT":
        raise MatchValidationError("; ".join(suggestion["conflicts"]) or "Conflicting mapping")
    if not suggestion.get("sion_known"):
        raise MatchValidationError("SION not identified for these records")
    legit = {n.norm_class for n in item.norms.all()} or ({item.sion_norm_class.norm_class} if item.sion_norm_class_id else set())
    if suggestion["sion"] not in legit:
        raise MatchValidationError(f"{item.name} is not a legitimate item for {suggestion['sion']}")
    required = set(suggestion.get("entitlement_hits", {}).values())
    if required and item.name.upper() not in {e.upper() for e in required}:
        raise MatchValidationError(f"Entitlement profile requires {', '.join(sorted(required))}")
    if not allow_review and suggestion["band"] not in {"HIGH", "APPROVED"}:
        raise MatchValidationError("Bulk approval is limited to high-confidence (95%+), conflict-free suggestions")


def decide(*, suggestions: list[dict], decision: str, user, item_id: int | None = None, bulk: bool = False,
           evaluators: dict | None = None, replace_links: bool = False, item_ids: dict | None = None) -> list[ProductMatchDecision]:
    """Record decisions atomically. APPROVED links the import items to the master item.

    An import item that already has several master links (Ambiguous) is only re-linked when the reviewer
    explicitly confirms the replacement (``replace_links``); the previous links are always audited.
    """
    if decision not in {ProductMatchDecision.APPROVED, ProductMatchDecision.REJECTED, ProductMatchDecision.DIFFERENT}:
        raise MatchValidationError("Unknown decision")
    from apps.license.models import MappingChange
    from apps.license.services.product_intelligence.propagation import record_change
    from apps.license.services.replan_requests import mark_license_replan_source_changed

    rows = []
    with transaction.atomic():
        change = None
        if decision == ProductMatchDecision.APPROVED:
            # Part 15: version the mapping change and archive the affected plans BEFORE any link is written.
            change = record_change(kind=MappingChange.MATCH_DECISION, user=user, source_model="license.ProductMatchDecision",
                                   import_item_ids={i for s_ in suggestions for i in s_.get("import_item_ids") or []})
        for suggestion in suggestions:
            # ``item_ids``: per-source selection (bulk, Mapping workspace); then one ``item_id``; then the suggestion.
            target_id = (item_ids or {}).get(suggestion["source_key"]) or item_id or (suggestion.get("suggestion") or {}).get("item_id")
            target = ItemNameModel.objects.prefetch_related("norms").select_related("sion_norm_class").filter(pk=target_id).first() if target_id else None
            if decision == ProductMatchDecision.APPROVED:
                if target is None:
                    raise MatchValidationError("Choose a master item to approve")
                if not target.is_active:
                    raise MatchValidationError(f"{target.name} is not an active Item Name")
                # Bulk was limited to HIGH-band suggestions; a row whose Item Name the reviewer selected explicitly
                # (``item_ids``, Mapping workspace) is validated exactly like a single approval instead.
                explicit = suggestion["source_key"] in (item_ids or {})
                _validate(suggestion, target, allow_review=not bulk or explicit)
                # A reviewer-chosen master is re-checked with the full deterministic rules (HSN chapter,
                # multi-product, entitlement) — not only the checks computed for the original suggestion.
                evaluate = (evaluators or {}).get(suggestion["source_key"])
                if evaluate and target.pk != (suggestion.get("suggestion") or {}).get("item_id"):
                    conflicts, _ = evaluate(target.pk)
                    if conflicts:
                        raise MatchValidationError("; ".join(conflicts))
            items = list(LicenseImportItemsModel.objects.select_for_update().filter(pk__in=suggestion["import_item_ids"]).order_by("pk").prefetch_related("items"))
            if len(items) != len(set(suggestion["import_item_ids"])):
                raise MatchValidationError("Some source records no longer exist")
            previous = {str(i.pk): sorted(n.pk for n in i.items.all()) for i in items}
            multi = [k for k, links in previous.items() if len(links) > 1]
            if decision == ProductMatchDecision.APPROVED and multi and not replace_links:
                raise MatchValidationError(f"{len(multi)} source record(s) already link several master items — confirm replacing those links")
            new = previous
            if decision == ProductMatchDecision.APPROVED:
                for item in items:
                    item.items.set([target])
                new = {str(i.pk): [target.pk] for i in items}
                for licence_id in sorted({i.license_id for i in items}):
                    # Owner decision 2026-11-19 (Part 15): approved mapping changes re-plan automatically.
                    mark_license_replan_source_changed(
                        license_id=licence_id, reason="item_master_link_changed",
                        source_model="license.MappingChange", source_pk=change.pk if change else None, dispatch=True,
                    )
            rows.append(ProductMatchDecision.objects.create(
                source_key=suggestion["source_key"], source_description=suggestion["description"][:5000],
                normalized_description=normalise(suggestion["description"])[:500], hsn_code=(suggestion.get("hsn_code") or "")[:20],
                sion=SionNormClassModel.objects.filter(norm_class=suggestion.get("sion")).first(),
                import_item_ids=sorted(suggestion["import_item_ids"]),
                suggested_item_id=(suggestion.get("suggestion") or {}).get("item_id"),
                chosen_item=target if decision == ProductMatchDecision.APPROVED else None,
                confidence=suggestion.get("confidence") or 0, explanation=suggestion.get("explanation", "")[:5000],
                checks=suggestion.get("checks") or {}, matcher=(suggestion.get("matcher") or MATCHER_VERSION)[:40], decision=decision,
                previous_links=previous, new_links=new, decided_by=user,
            ))
            if decision == ProductMatchDecision.APPROVED and len(product_segments(suggestion["description"])) == 1:
                # The approved wording becomes an alias so the same description is suggested at 100 % next time.
                from apps.license.services.product_intelligence.aliases import create_alias
                from apps.license.models import ProductAlias
                try:
                    with transaction.atomic():
                        create_alias(text=suggestion["description"], item_id=target.pk, sion=suggestion.get("sion"), user=user,
                                     source=ProductAlias.DECISION, decision=rows[-1])
                except MatchValidationError as exc:
                    # An alias clash never blocks the approval itself; it is logged and reported to the reviewer.
                    logger.warning("Approval %s recorded without alias for %r: %s", rows[-1].pk, suggestion["source_key"], exc)
                    rows[-1].alias_skipped = str(exc)
        if change is not None:
            change.source_refs = [r.pk for r in rows]
            change.detail = {"decisions": [{"id": r.pk, "description": r.source_description[:200], "previous": r.previous_links, "new": r.new_links} for r in rows]}
            change.save(update_fields=["source_refs", "detail"])
    return rows


def matching_groups(intelligence: dict) -> list[dict]:
    """Unmapped / Ambiguous / multi-product rows of an intelligence report → matching source groups.

    Report rows are keyed by raw wording, matching by *normalised* wording + HSN + SION, so several report rows can
    be one matching group (e.g. two spellings of the same description). They are merged here — one review row, one
    decision covering every source record (review 2026-11-19: duplicate rows had covered only half the records).
    """
    from decimal import Decimal

    merged: dict[str, dict] = {}
    for product in intelligence["products"]:
        if product["kind"] == "MAPPED":
            continue
        original_wording = product["kind"] in {"UNMAPPED", "MULTI_PRODUCT"}
        description = (product["aliases"][0] if product["aliases"] else product["product"]) if original_wording else product["product"]
        hsn = product["hsn_codes"][0] if product["hsn_codes"] else ""
        key = source_key(normalise(description), hsn, product["sion"])
        group = merged.get(key)
        if group is None:
            merged[key] = {
                "source_key": key, "product_key": product["key"], "product_keys": [product["key"]],
                "kind": product["kind"], "description": description, "aliases": list(product["aliases"]), "hsn_code": hsn,
                "hsn_codes": list(product["hsn_codes"]), "sion": product["sion"],
                "import_item_ids": sorted({r["import_item_id"] for r in product["source_records"]}),
                "license_numbers": sorted({r["license_number"] for r in product["source_records"]}),
                "entitlement_qty": product["entitlement_qty"], "balance_qty": product["balance_qty"],
                "source_records": list(product["source_records"]),
            }
            continue
        group["product_keys"].append(product["key"])
        precedence = {"UNMAPPED": 0, "AMBIGUOUS": 1, "MULTI_PRODUCT": 2}  # still-open records keep the group open for review
        if precedence.get(product["kind"], 9) < precedence.get(group["kind"], 9):
            group["kind"] = product["kind"]
        group["aliases"] = sorted(set(group["aliases"]) | set(product["aliases"]))
        group["hsn_codes"] = sorted(set(group["hsn_codes"]) | set(product["hsn_codes"]))
        group["source_records"].extend(product["source_records"])
        group["import_item_ids"] = sorted(set(group["import_item_ids"]) | {r["import_item_id"] for r in product["source_records"]})
        group["license_numbers"] = sorted(set(group["license_numbers"]) | {r["license_number"] for r in product["source_records"]})
        for field in ("entitlement_qty", "balance_qty"):
            group[field] = str(Decimal(group[field]) + Decimal(product[field]))
    return list(merged.values())


def matching_summary(suggestions: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in suggestions:
        counts[row["band"]] += 1
    return dict(counts)
