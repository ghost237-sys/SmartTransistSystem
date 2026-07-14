from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import (
    PassTier, CommuterPass, CreditScore, CreditTransaction,
    PassUsage, WeeklySettlement
)


class PassTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = PassTier
        fields = [
            'id', 'name', 'tier_type', 'trip_allowance', 'discount_percent',
            'price', 'duration_days', 'min_credit_score', 'max_credit_limit',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CreditScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditScore
        fields = [
            'id', 'score', 'total_trips', 'on_time_payments',
            'missed_payments', 'last_calculated'
        ]
        read_only_fields = ['id', 'last_calculated']


class CreditTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditTransaction
        fields = [
            'id', 'transaction_type', 'amount', 'balance_before',
            'balance_after', 'description', 'reference', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PassUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PassUsage
        fields = [
            'id', 'original_fare', 'discount_applied', 'final_amount',
            'route_name', 'used_at'
        ]
        read_only_fields = ['id', 'used_at']


class WeeklySettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklySettlement
        fields = [
            'id', 'week_start', 'week_end', 'total_amount', 'status',
            'mpesa_receipt', 'settled_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class CommuterPassSerializer(serializers.ModelSerializer):
    tier_details = PassTierSerializer(source='tier', read_only=True)
    credit_score = serializers.SerializerMethodField()
    recent_transactions = serializers.SerializerMethodField()
    recent_usage = serializers.SerializerMethodField()
    upcoming_settlement = serializers.SerializerMethodField()
    
    class Meta:
        model = CommuterPass
        fields = [
            'id', 'tier', 'tier_details', 'trips_remaining', 'trips_used',
            'start_date', 'end_date', 'current_balance', 'credit_limit',
            'status', 'auto_renew', 'last_used_at', 'created_at', 'updated_at',
            'credit_score', 'recent_transactions', 'recent_usage', 'upcoming_settlement'
        ]
        read_only_fields = [
            'id', 'trips_used', 'current_balance', 'last_used_at',
            'created_at', 'updated_at', 'credit_score', 'recent_transactions',
            'recent_usage', 'upcoming_settlement'
        ]
    
    def get_credit_score(self, obj):
        try:
            score = obj.user.credit_score
            return CreditScoreSerializer(score).data
        except CreditScore.DoesNotExist:
            return None
    
    def get_recent_transactions(self, obj):
        transactions = obj.credit_transactions.all()[:5]
        return CreditTransactionSerializer(transactions, many=True).data
    
    def get_recent_usage(self, obj):
        usage = obj.usage_records.all()[:5]
        return PassUsageSerializer(usage, many=True).data
    
    def get_upcoming_settlement(self, obj):
        if obj.tier.tier_type == PassTier.TierType.POSTPAID:
            # Get the most recent pending settlement
            settlement = obj.weekly_settlements.filter(
                status__in=[WeeklySettlement.Status.PENDING, WeeklySettlement.Status.PROCESSING]
            ).first()
            if settlement:
                return WeeklySettlementSerializer(settlement).data
        return None


class CreateCommuterPassSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommuterPass
        fields = ['tier', 'auto_renew']
    
    def validate_tier(self, value):
        if not value.is_active:
            raise serializers.ValidationError("This pass tier is not available.")
        
        # Check credit score requirement for post-paid
        if value.tier_type == PassTier.TierType.POSTPAID:
            user = self.context['request'].user
            try:
                credit_score = user.credit_score
                if credit_score.score < value.min_credit_score:
                    raise serializers.ValidationError(
                        f"Credit score of {credit_score.score} is below required minimum of {value.min_credit_score}"
                    )
            except CreditScore.DoesNotExist:
                # Create initial credit score if it doesn't exist
                CreditScore.objects.create(user=user)
                if value.min_credit_score > 50:  # Default score
                    raise serializers.ValidationError(
                        f"Credit score required for this tier is {value.min_credit_score}"
                    )
        
        return value
    
    def create(self, validated_data):
        user = self.context['request'].user
        tenant = user.tenant
        tier = validated_data['tier']
        auto_renew = validated_data.get('auto_renew', False)
        
        # Calculate dates based on tier duration
        start_date = timezone.now()
        end_date = start_date + timedelta(days=tier.duration_days)
        
        # Set initial values based on tier type
        if tier.tier_type in [PassTier.TierType.WEEKLY, PassTier.TierType.MONTHLY]:
            trips_remaining = tier.trip_allowance
            credit_limit = Decimal('0.00')
        else:  # POSTPAID
            trips_remaining = 0
            credit_limit = tier.max_credit_limit or Decimal('0.00')
        
        # Check for existing active pass
        existing_pass = CommuterPass.objects.filter(
            user=user,
            tenant=tenant,
            status=CommuterPass.Status.ACTIVE
        ).first()
        
        if existing_pass:
            # Deactivate existing pass
            existing_pass.status = CommuterPass.Status.EXPIRED
            existing_pass.save()
        
        pass_instance = CommuterPass.objects.create(
            user=user,
            tenant=tenant,
            tier=tier,
            trips_remaining=trips_remaining,
            start_date=start_date,
            end_date=end_date,
            credit_limit=credit_limit,
            auto_renew=auto_renew
        )
        
        return pass_instance


class UsePassSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()
    fare_amount = serializers.DecimalField(max_digits=8, decimal_places=2)
    route_name = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        user = self.context['request'].user
        
        # Get user's active pass
        try:
            pass_instance = CommuterPass.objects.get(
                user=user,
                status=CommuterPass.Status.ACTIVE
            )
        except CommuterPass.DoesNotExist:
            raise serializers.ValidationError("No active commuter pass found.")
        
        # Check if pass can be used
        if not pass_instance.can_use_pass():
            raise serializers.ValidationError("Pass cannot be used. Check expiration or balance.")
        
        # For prepaid passes, check remaining trips
        if pass_instance.tier.tier_type in [PassTier.TierType.WEEKLY, PassTier.TierType.MONTHLY]:
            if pass_instance.trips_remaining <= 0:
                raise serializers.ValidationError("No trips remaining on this pass.")
        
        # For post-paid, check credit limit
        if pass_instance.tier.tier_type == PassTier.TierType.POSTPAID:
            discounted_fare = data['fare_amount'] * (Decimal('1') - pass_instance.tier.discount_percent / Decimal('100'))
            if pass_instance.current_balance + discounted_fare > pass_instance.credit_limit:
                raise serializers.ValidationError("Transaction would exceed credit limit.")
        
        data['pass_instance'] = pass_instance
        return data
    
    def create(self, validated_data):
        pass_instance = validated_data['pass_instance']
        fare_amount = validated_data['fare_amount']
        route_name = validated_data.get('route_name', '')
        booking_id = validated_data.get('booking_id')
        
        # Calculate discount
        discount_percent = pass_instance.tier.discount_percent
        discount_amount = fare_amount * (discount_percent / Decimal('100'))
        final_amount = fare_amount - discount_amount
        
        # Use the trip
        pass_instance.use_trip(fare_amount)
        
        # Create pass usage record
        from domains.booking.models import Booking
        
        booking = None
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id)
            except Booking.DoesNotExist:
                pass
        
        usage_record = PassUsage.objects.create(
            pass_instance=pass_instance,
            booking=booking,
            original_fare=fare_amount,
            discount_applied=discount_amount,
            final_amount=final_amount,
            route_name=route_name
        )
        
        # For post-paid, create credit transaction
        if pass_instance.tier.tier_type == PassTier.TierType.POSTPAID:
            balance_before = pass_instance.current_balance - final_amount
            balance_after = pass_instance.current_balance
            
            CreditTransaction.objects.create(
                pass_instance=pass_instance,
                transaction_type=CreditTransaction.TransactionType.CHARGE,
                amount=final_amount,
                balance_before=balance_before,
                balance_after=balance_after,
                description=f'Trip charge - {route_name}',
                reference=str(booking_id) if booking_id else ''
            )
        
        return {
            'success': True,
            'pass_usage': PassUsageSerializer(usage_record).data,
            'pass': CommuterPassSerializer(pass_instance).data
        }


class RenewPassSerializer(serializers.Serializer):
    def validate(self, data):
        user = self.context['request'].user
        
        try:
            pass_instance = CommuterPass.objects.get(
                user=user,
                status=CommuterPass.Status.ACTIVE
            )
        except CommuterPass.DoesNotExist:
            raise serializers.ValidationError("No active pass to renew.")
        
        if pass_instance.tier.tier_type == PassTier.TierType.POSTPAID:
            raise serializers.ValidationError("Post-paid passes auto-renew weekly. Manual renewal not required.")
        
        data['pass_instance'] = pass_instance
        return data
    
    def create(self, validated_data):
        pass_instance = validated_data['pass_instance']
        tier = pass_instance.tier
        
        # Calculate new dates
        start_date = timezone.now()
        end_date = start_date + timedelta(days=tier.duration_days)
        
        # Reset trip counts
        pass_instance.trips_remaining = tier.trip_allowance
        pass_instance.start_date = start_date
        pass_instance.end_date = end_date
        pass_instance.save()
        
        return {
            'success': True,
            'pass': CommuterPassSerializer(pass_instance).data
        }
