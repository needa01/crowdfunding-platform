from django.core.management.base import BaseCommand
from wallets.models import Wallet
from crowdfunding.enums import WalletType, Currency


class Command(BaseCommand):
    help = "Create the platform wallet if it does not already exist."

    def handle(self, *args, **options):
        wallet = Wallet.objects.filter(
            wallet_type=WalletType.PLATFORM
        ).first()

        if wallet:
            self.stdout.write(
                self.style.WARNING(
                    f"Platform wallet already exists"
                )
            )
            return

        wallet = Wallet.objects.create(
            wallet_type=WalletType.PLATFORM,
            balance=0,
            currency=Currency.INR,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Platform wallet created successfully"
            )
        )