"""Product Intelligence lifecycle from the shell (reproducible; never promotes implicitly).

    manage.py product_intelligence inventory
    manage.py product_intelligence dataset [--train]
    manage.py product_intelligence status
    manage.py product_intelligence promote <version>
    manage.py product_intelligence rollback
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.license.models import ProductIntelModel
from apps.license.services.product_intelligence import knowledge, lifecycle


class Command(BaseCommand):
    help = "Inventory, dataset generation, training, promotion and rollback of the product matching model"

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["inventory", "dataset", "status", "promote", "rollback"])
        parser.add_argument("version", nargs="?")
        parser.add_argument("--train", action="store_true", help="Train + evaluate a candidate after building the dataset")

    def handle(self, *args, action, version=None, train=False, **opts):
        try:
            if action == "inventory":
                self.stdout.write(json.dumps(knowledge.inventory(), indent=1, default=str))
            elif action == "dataset":
                ds = knowledge.build_dataset()
                self.stdout.write(f"dataset {ds.version}: {ds.observation_count} observations, {ds.unique_description_count} unique, "
                                  f"{ds.label_count} verified labels, sha256 {ds.sha256}")
                if train:
                    m = lifecycle.train(ds)
                    self.stdout.write(f"model {m.version}: {m.status} {json.dumps(m.metrics.get('holdout') or m.metrics, default=str)}")
                    if m.notes:
                        self.stdout.write(m.notes)
            elif action == "status":
                for m in ProductIntelModel.objects.all()[:20]:
                    self.stdout.write(f"{m.version} {m.status} {m.algorithm} {json.dumps((m.metrics or {}).get('holdout'), default=str)}")
            elif action == "promote":
                model = ProductIntelModel.objects.filter(version=version).first()
                if model is None:
                    raise CommandError(f"Unknown model {version}")
                lifecycle.promote(model, user=None)
                self.stdout.write(f"promoted {model.version}")
            elif action == "rollback":
                target = lifecycle.rollback(user=None)
                self.stdout.write(f"rolled back to {getattr(target, 'version', 'deterministic matching (no model)')}")
        except lifecycle.LifecycleError as exc:
            raise CommandError(str(exc)) from exc
