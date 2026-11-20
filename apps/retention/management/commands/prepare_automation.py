from django.core.management.base import BaseCommand
from apps.retention.automation import prepare_automation
from apps.salons.models import Salon

class Command(BaseCommand):
    help="Prepare internal automation message intents. Does not send SMS."
    def handle(self,*args,**options):
        count=0
        for salon in Salon.objects.filter(is_active=True).iterator(chunk_size=100):
            count+=prepare_automation(salon)
        self.stdout.write(self.style.SUCCESS(f"Prepared {count} new intents. No SMS sent."))
