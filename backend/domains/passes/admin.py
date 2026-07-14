from django.contrib import admin
from .models import PassTier, CommuterPass, CreditScore, CreditTransaction, PassUsage, WeeklySettlement


@admin.register(PassTier)
class PassTierAdmin(admin.ModelAdmin):
    list_display = ['name', 'tier_type', 'trip_allowance', 'discount_percent', 'price', 'is_active']
    list_filter = ['tier_type', 'is_active']
    search_fields = ['name']


@admin.register(CommuterPass)
class CommuterPassAdmin(admin.ModelAdmin):
    list_display = ['user', 'tier', 'status', 'trips_remaining', 'current_balance', 'start_date', 'end_date']
    list_filter = ['status', 'tier__tier_type']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user', 'tier']


@admin.register(CreditScore)
class CreditScoreAdmin(admin.ModelAdmin):
    list_display = ['user', 'score', 'total_trips', 'on_time_payments', 'missed_payments']
    search_fields = ['user__username']
    readonly_fields = ['last_calculated']


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ['pass_instance', 'transaction_type', 'amount', 'created_at']
    list_filter = ['transaction_type']
    raw_id_fields = ['pass_instance']


@admin.register(PassUsage)
class PassUsageAdmin(admin.ModelAdmin):
    list_display = ['pass_instance', 'original_fare', 'discount_applied', 'final_amount', 'used_at']
    raw_id_fields = ['pass_instance', 'booking']


@admin.register(WeeklySettlement)
class WeeklySettlementAdmin(admin.ModelAdmin):
    list_display = ['pass_instance', 'week_start', 'week_end', 'total_amount', 'status', 'settled_at']
    list_filter = ['status']
    raw_id_fields = ['pass_instance']
