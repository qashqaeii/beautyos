from django.core.management.base import BaseCommand
from apps.retention.services import sync_follow_up_queue
from apps.salons.models import Salon

class Command(BaseCommand):
    help="Refresh internal follow-up queues. Does not send SMS."

    def handle(self,*args,**options):
        count=0
        for salon in Salon.objects.filter(is_active=True).iterator(chunk_size=100):
            count+=sync_follow_up_queue(salon)
        self.stdout.write(self.style.SUCCESS(f"Created {count} new follow-up cycles. No messages sent."))
