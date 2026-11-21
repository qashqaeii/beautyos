from django.core.management.base import BaseCommand
from apps.retention.automation import prepare_automation
from apps.retention.delivery import dispatch_due, reconcile_delivery
from apps.salons.models import Salon


class Command(BaseCommand):
    help = "Prepare, optionally dispatch and reconcile opt-in customer messages."

    def add_arguments(self, parser):
        parser.add_argument("--salon", default="", help="Optional salon UUID")
        parser.add_argument("--limit", type=int, default=100, help="Max messages per salon per run")

    def handle(self, *args, **options):
        salons = Salon.objects.filter(is_active=True)
        if options["salon"]:
            salons = salons.filter(pk=options["salon"])
        counts = {"prepared": 0, "accepted": 0, "failed": 0, "unknown": 0, "reconciled": 0}
        for salon in salons.iterator(chunk_size=100):
            counts["prepared"] += prepare_automation(salon)
            result = dispatch_due(salon, limit=options["limit"])
            for key in ("accepted", "failed", "unknown"):
                counts[key] += result[key]
            counts["reconciled"] += reconcile_delivery(salon, limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(
            "Prepared={prepared}, accepted={accepted}, rejected={failed}, unknown={unknown}, reconciled={reconciled}. "
            "Provider sending requires explicit global and per-salon enablement.".format(**counts)
        ))
