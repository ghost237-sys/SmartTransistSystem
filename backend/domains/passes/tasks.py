from celery import shared_task
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
import logging

from .models import CommuterPass, WeeklySettlement, CreditTransaction, CreditScore
from domains.payments.mpesa import initiate_stk_push, normalize_phone_number

logger = logging.getLogger(__name__)


@shared_task
def update_credit_scores():
    """
    Recalculate credit scores for all commuters with post-paid passes.
    Runs daily to update scores based on payment history.
    """
    post_paid_passes = CommuterPass.objects.filter(
        tier__tier_type=CommuterPass.TierType.POSTPAID,
        status=CommuterPass.Status.ACTIVE
    )
    
    updated_count = 0
    for pass_instance in post_paid_passes:
        try:
            credit_score = pass_instance.user.credit_score
            credit_score.calculate_score()
            updated_count += 1
        except CreditScore.DoesNotExist:
            # Create initial credit score if missing
            CreditScore.objects.create(user=pass_instance.user)
            updated_count += 1
    
    logger.info(f"Updated credit scores for {updated_count} commuters")
    return updated_count


@shared_task
def process_weekly_settlements():
    """
    Process weekly settlements for all post-paid passes.
    Runs every Friday to initiate M-Pesa STK push for accumulated charges.
    """
    today = timezone.now().date()
    
    # Calculate week start (Monday) and end (Sunday)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Find post-paid passes that need settlement
    post_paid_passes = CommuterPass.objects.filter(
        tier__tier_type=CommuterPass.TierType.POSTPAID,
        status=CommuterPass.Status.ACTIVE,
        current_balance__gt=0
    )
    
    processed_count = 0
    for pass_instance in post_paid_passes:
        # Check if settlement already exists for this week
        existing = WeeklySettlement.objects.filter(
            pass_instance=pass_instance,
            week_start=week_start
        ).first()
        
        if existing:
            continue
        
        # Calculate total amount for the week
        total_amount = pass_instance.current_balance
        
        if total_amount <= 0:
            continue
        
        # Create weekly settlement record
        settlement = WeeklySettlement.objects.create(
            pass_instance=pass_instance,
            week_start=week_start,
            week_end=week_end,
            total_amount=total_amount,
            status=WeeklySettlement.Status.PROCESSING
        )
        
        # Initiate M-Pesa STK push
        try:
            phone_number = pass_instance.user.phone_number
            if not phone_number:
                logger.warning(f"No phone number for user {pass_instance.user.username}")
                settlement.status = WeeklySettlement.Status.FAILED
                settlement.save()
                continue
            
            normalized_phone = normalize_phone_number(phone_number)
            account_reference = f"WEEKLY-{pass_instance.id}"
            transaction_desc = f"Weekly settlement for {week_start}"
            
            mpesa_response = initiate_stk_push(
                phone_number=normalized_phone,
                amount=float(total_amount),
                account_reference=account_reference,
                transaction_desc=transaction_desc
            )
            
            # Create credit transaction for the settlement
            CreditTransaction.objects.create(
                pass_instance=pass_instance,
                transaction_type=CreditTransaction.TransactionType.SETTLEMENT,
                amount=total_amount,
                balance_before=pass_instance.current_balance,
                balance_after=Decimal('0.00'),
                description=f'Weekly settlement {week_start}',
                reference=mpesa_response.get('CheckoutRequestID', '')
            )
            
            # Reset balance after successful settlement initiation
            pass_instance.current_balance = Decimal('0.00')
            pass_instance.save()
            
            processed_count += 1
            logger.info(f"Initiated settlement for {pass_instance.user.username}: KES {total_amount}")
            
        except Exception as e:
            logger.error(f"Settlement failed for {pass_instance.user.username}: {str(e)}")
            settlement.status = WeeklySettlement.Status.FAILED
            settlement.save()
    
    logger.info(f"Processed {processed_count} weekly settlements")
    return processed_count


@shared_task
def expire_old_passes():
    """
    Mark expired passes as expired.
    Runs daily to check for passes past their end_date.
    """
    today = timezone.now()
    expired_passes = CommuterPass.objects.filter(
        status=CommuterPass.Status.ACTIVE,
        end_date__lt=today
    )
    
    expired_count = expired_passes.update(status=CommuterPass.Status.EXPIRED)
    logger.info(f"Expired {expired_count} passes")
    return expired_count


@shared_task
def auto_renew_passes():
    """
    Auto-renew passes with auto_renew enabled.
    Runs daily to renew passes that are expiring soon.
    """
    tomorrow = timezone.now() + timedelta(days=1)
    
    # Find passes expiring tomorrow with auto_renew enabled
    passes_to_renew = CommuterPass.objects.filter(
        status=CommuterPass.Status.ACTIVE,
        auto_renew=True,
        end_date__date=tomorrow.date(),
        tier__tier_type__in=[CommuterPass.TierType.WEEKLY, CommuterPass.TierType.MONTHLY]
    )
    
    renewed_count = 0
    for pass_instance in passes_to_renew:
        tier = pass_instance.tier
        
        # Calculate new dates
        start_date = timezone.now()
        end_date = start_date + timedelta(days=tier.duration_days)
        
        # Reset trip counts
        pass_instance.trips_remaining = tier.trip_allowance
        pass_instance.start_date = start_date
        pass_instance.end_date = end_date
        pass_instance.save()
        
        renewed_count += 1
        logger.info(f"Auto-renewed pass for {pass_instance.user.username}")
    
    logger.info(f"Auto-renewed {renewed_count} passes")
    return renewed_count
