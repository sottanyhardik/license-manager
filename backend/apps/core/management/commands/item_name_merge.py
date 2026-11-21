"""Approval-gated Item Name merges (owner rule 2026-11-21).

    item_name_merge register --decisions FILE --approved-by "..."   # record owner-approved groups (no data change)
    item_name_merge list
    item_name_merge preview GROUP_KEY                               # read-only impact + conflicts
    item_name_merge execute GROUP_KEY --confirm                     # one group at a time
    item_name_merge rollback GROUP_KEY --confirm

Only groups whose decision is MERGE / APPROVED with ``final_confirmation: true`` can be registered,
and a merge executes only one group per invocation with an explicit ``--confirm``.
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import ItemNameMerge, ItemNameMergeSource, ItemNameModel
from apps.core.services import item_name_merge as engine


class Command(BaseCommand):
    help = "Register, preview, execute and roll back owner-approved Item Name merges (never automatic)."

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="action", required=True)
        reg = sub.add_parser("register")
        reg.add_argument("--decisions", required=True)
        reg.add_argument("--approved-by", required=True)
        sub.add_parser("list")
        for name in ("preview", "execute", "rollback"):
            p = sub.add_parser(name)
            p.add_argument("group_key")
            if name != "preview":
                p.add_argument("--confirm", action="store_true", help="Explicit final confirmation (required)")
                p.add_argument("--by", default="management command")

    def handle(self, *args, **o):
        return getattr(self, f"_{o['action']}")(o)

    def _register(self, o):
        with open(o["decisions"]) as fh:
            data = json.load(fh)
        created = 0
        with transaction.atomic():
            for d in data["decisions"]:
                if d.get("decision") != "MERGE" or d.get("state") != "APPROVED" or d.get("final_confirmation") is not True:
                    continue
                if ItemNameMerge.objects.filter(group_key=d["group"]).exists():
                    self.stdout.write(f"  {d['group']}: already registered — skipped")
                    continue
                canonical = ItemNameModel.objects.filter(pk=d["canonical"]).first()
                sources = list(ItemNameModel.objects.filter(pk__in=d["sources"]))
                if canonical is None or len(sources) != len(set(d["sources"])):
                    raise CommandError(f"{d['group']}: canonical/source ids no longer exist — nothing registered")
                merge = ItemNameMerge.objects.create(
                    group_key=d["group"], canonical=canonical, approved_by=o["approved_by"],
                    approval_reference=o["decisions"], approved_on=d["confirmed_on"], final_confirmation=True,
                    norm_union=d.get("norm_union", []),
                    preview={"approved_references_moved": d.get("preview", {}).get("references_moved"),
                             "approved_decision": d})
                for s in sorted(sources, key=lambda x: x.pk):
                    ItemNameMergeSource.objects.create(merge=merge, source=s, original_name=s.name)
                created += 1
                self.stdout.write(f"  {d['group']}: registered canonical={canonical.pk} sources={sorted(d['sources'])}")
        self.stdout.write(self.style.SUCCESS(f"Registered {created} approved merge(s). No item data changed."))

    def _list(self, o):
        for m in ItemNameMerge.objects.prefetch_related("sources"):
            self.stdout.write(f"{m.group_key:18} {m.status:9} canonical={m.canonical_id} sources={[s.source_id for s in m.sources.all()]}"
                              f"{'  error=' + m.error[:120] if m.error else ''}")

    def _get(self, key):
        m = ItemNameMerge.objects.filter(group_key=key).first()
        if m is None:
            raise CommandError(f"No registered merge {key}")
        return m

    def _preview(self, o):
        m = self._get(o["group_key"])
        pv = engine.preview(m.canonical_id, [s.source_id for s in m.sources.all()], m.norm_union)
        self.stdout.write(json.dumps(pv, indent=1, default=str))

    def _execute(self, o):
        if not o["confirm"]:
            raise CommandError("Refusing: --confirm is required (explicit final confirmation).")
        m = self._get(o["group_key"])
        try:
            m = engine.execute(m.pk, confirm=True, executed_by=o["by"])
        except Exception as exc:
            raise CommandError(f"Merge {m.group_key} NOT executed (rolled back): {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"{m.group_key} EXECUTED: {json.dumps(m.verification)}"))

    def _rollback(self, o):
        if not o["confirm"]:
            raise CommandError("Refusing: --confirm is required.")
        m = self._get(o["group_key"])
        try:
            m = engine.rollback(m.pk, confirm=True, reversed_by=o["by"])
        except Exception as exc:
            raise CommandError(f"Rollback of {m.group_key} NOT applied: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"{m.group_key} REVERSED: {json.dumps(m.verification)}"))
