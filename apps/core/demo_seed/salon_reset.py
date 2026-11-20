"""Remove transactional demo-salon data (demo-salon-a only)."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q

from apps.appointments.models import Appointment
from apps.commissions.models import CommissionEntry, CommissionRule, CommissionSettlement
from apps.customers.models import Customer, CustomerNote, CustomerTag
from apps.expenses.models import Expense
from apps.finance.models import (
    AccountMovement,
    CashClose,
    ExpenseOccurrence,
    FinancialAccount,
    Invoice,
    InvoiceLine,
    MaterialCost,
    Payment,
    ProductReturn,
    ProductSale,
    RecurringExpense,
    Refund,
    SalonDebt,
    SalonDebtPayment,
    StaffAgreement,
    StaffPeriod,
    StaffPeriodPayment,
)
from apps.inventory.models import InventoryItem, StockMovement
from apps.loyalty.models import (
    LoyaltyAward,
    LoyaltyReward,
    LoyaltyTransaction,
    MembershipCycle,
    Referral,
    RewardRedemption,
    LoyaltyVoucher,
)
from apps.packages.models import CustomerPackage, PackageSessionUse, ServicePackage
from apps.portfolio.models import PortfolioItem
from apps.retention.models import Campaign, CampaignRecipient, FollowUp
from apps.staff.models import StaffProfile
from apps.waitlist.models import WaitlistEntry

from apps.core.demo_seed.engine import demo_customer_phone_prefix
from apps.core.demo_seed.salon_dataset import (
    DEMO_SALON_MARKER,
    PRODUCTS,
    specialist_phone,
)


def _specialist_qs(salon):
    from apps.core.demo_seed.salon_dataset import SPECIALISTS

    phones = [specialist_phone(i) for i in range(1, len(SPECIALISTS) + 1)]
    return StaffProfile.scoped(salon).filter(membership__user__phone__in=phones)


@transaction.atomic
def reset_demo_salon(salon) -> None:
    if salon.slug != "demo-salon-a":
        raise ValueError("reset_demo_salon only supports demo-salon-a")

    prefix = demo_customer_phone_prefix(salon.slug)
    demo_customers = Customer.scoped(salon).filter(Q(phone__startswith=prefix))
    cids = list(demo_customers.values_list("pk", flat=True))

    specialist_ids = list(_specialist_qs(salon).values_list("pk", flat=True))
    appt_qs = Appointment.scoped(salon).filter(Q(customer_id__in=cids) | Q(staff_id__in=specialist_ids))
    appt_ids = list(appt_qs.values_list("pk", flat=True))

    ProductReturn.scoped(salon).filter(sale__salon=salon).delete()
    ProductSale.scoped(salon).delete()
    MaterialCost.scoped(salon).delete()
    Refund.scoped(salon).filter(payment__customer_id__in=cids).delete()
    InvoiceLine.scoped(salon).filter(appointment_id__in=appt_ids).delete()
    Invoice.scoped(salon).filter(customer_id__in=cids).delete()
    Payment.scoped(salon).filter(customer_id__in=cids).delete()

    PackageSessionUse.scoped(salon).filter(customer_package__customer_id__in=cids).delete()
    MembershipCycle.scoped(salon).filter(purchase__customer_id__in=cids).delete()
    CustomerPackage.scoped(salon).filter(customer_id__in=cids).delete()
    ServicePackage.scoped(salon).filter(description__startswith=DEMO_SALON_MARKER).delete()

    CommissionSettlement.scoped(salon).delete()
    CommissionEntry.scoped(salon).filter(
        Q(appointment_id__in=appt_ids) | Q(staff_id__in=specialist_ids)
    ).delete()
    CommissionRule.scoped(salon).filter(name__startswith=DEMO_SALON_MARKER).delete()

    StaffPeriodPayment.scoped(salon).delete()
    StaffPeriod.scoped(salon).filter(staff_id__in=specialist_ids).delete()
    StaffAgreement.scoped(salon).filter(staff_id__in=specialist_ids).delete()

    AccountMovement.scoped(salon).filter(note__startswith=DEMO_SALON_MARKER).delete()
    FinancialAccount.scoped(salon).filter(name__startswith="[نمایشی]").delete()
    CashClose.scoped(salon).delete()

    ExpenseOccurrence.scoped(salon).delete()
    RecurringExpense.scoped(salon).filter(title__startswith=DEMO_SALON_MARKER).delete()
    Expense.scoped(salon).filter(description__startswith=DEMO_SALON_MARKER).delete()

    LoyaltyVoucher.scoped(salon).filter(customer_id__in=cids).delete()
    RewardRedemption.scoped(salon).filter(account__customer_id__in=cids).delete()
    LoyaltyAward.scoped(salon).filter(account__customer_id__in=cids).delete()
    LoyaltyTransaction.scoped(salon).filter(account__customer_id__in=cids).delete()
    Referral.scoped(salon).filter(Q(referrer_id__in=cids) | Q(referred_id__in=cids)).delete()

    LoyaltyReward.scoped(salon).filter(description__startswith=DEMO_SALON_MARKER).delete()

    StockMovement.scoped(salon).filter(
        Q(item__name__in=[p[0] for p in PRODUCTS]) | Q(appointment_id__in=appt_ids)
    ).delete()
    InventoryItem.scoped(salon).filter(name__in=[p[0] for p in PRODUCTS]).delete()

    CampaignRecipient.scoped(salon).delete()
    Campaign.scoped(salon).filter(title__startswith=DEMO_SALON_MARKER).delete()
    FollowUp.scoped(salon).filter(customer_id__in=cids).delete()
    WaitlistEntry.scoped(salon).filter(customer_id__in=cids).delete()

    SalonDebtPayment.scoped(salon).delete()
    SalonDebt.scoped(salon).filter(note__startswith=DEMO_SALON_MARKER).delete()

    CustomerNote.scoped(salon).filter(customer_id__in=cids).delete()
    appt_qs.delete()

    PortfolioItem.scoped(salon).filter(description__startswith=DEMO_SALON_MARKER).delete()

    from apps.services.models import Service

    Service.scoped(salon).filter(description__startswith=DEMO_SALON_MARKER).delete()

    demo_customers.update(is_deleted=True)