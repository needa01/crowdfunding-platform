from django.core.management.base import BaseCommand
from django.utils import timezone

from campaigns.models import Campaign
from crowdfunding.enums import CampaignStatus


class Command(BaseCommand):
    help = "Mark expired active campaigns as completed"

    def handle(self, *args, **options):

        updated_count = Campaign.objects.filter(
            campaign_status=CampaignStatus.ACTIVE,
            end_date__lt=timezone.localdate(),
            is_deleted=False,
        ).update(
            campaign_status=CampaignStatus.COMPLETED
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{updated_count} campaign(s) marked as completed."
            )
        )