import secrets
import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone

from domains.tenants.models import TenantScopedModel


class Booking(TenantScopedModel):
    HOLD_DURATION_MINUTES = 5

    class BookingType(models.TextChoices):
        SINGLE = 'single', 'Single'
        RETURN_OUTWARD = 'return_outward', 'Return Outward'
        RETURN_INWARD = 'return_inward', 'Return Inward'
        LINK_LEG_1 = 'link_leg_1', 'Link Leg 1'
        LINK_LEG_2 = 'link_leg_2', 'Link Leg 2'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey('routing.Trip', on_delete=models.CASCADE, related_name='bookings')
    booking_type = models.CharField(
        max_length=20,
        choices=BookingType.choices,
        default=BookingType.SINGLE,
        help_text='Type of booking for multi-mode trip support'
    )
    commuter = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='bookings',
        limit_choices_to={'role': 'commuter'},
        null=True, blank=True,
        help_text='Null for cash walk-up bookings recorded by a conductor.'
    )
    
    boarding_stop = models.ForeignKey(
        'routing.Stop', on_delete=models.PROTECT, related_name='boardings',
        null=True, blank=True,
    )
    alighting_stop = models.ForeignKey(
        'routing.Stop', on_delete=models.PROTECT, related_name='alightings',
        null=True, blank=True,
    )
    status = models.CharField(
        max_length=25,
        choices=[
            ('held', 'Held'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
            ('expired', 'Expired'),
            ('boarded', 'Boarded'),  # distinguishes "paid" from "actually got on"
            ('missed_delay', 'Missed Due to Delay'),  # triggered by system when connection is missed
            ('re_routed', 'Re-Routed'),  # user chose alternative bus
            ('refunded', 'Refunded'),  # user opted for refund
            ('pending_transfer', 'Pending Transfer'),  # held in pending bay for linked trips
            ('pending_manual_reroute', 'Pending Manual Reroute'),  # requires admin intervention
        ],
        default='held',
    )
    fare_paid = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    qr_code_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    short_code = models.CharField(max_length=6, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    boarded_at = models.DateTimeField(null=True, blank=True)
    hold_expires_at = models.DateTimeField(null=True, blank=True)

    # Two-way booking fields
    is_two_way = models.BooleanField(default=False, help_text='Whether this is part of a two-way (round trip) booking')
    two_way_booking = models.ForeignKey(
        'TwoWayBooking', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='legs',
        help_text='Parent two-way booking if this is a leg of a round trip'
    )
    leg_order = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Order of this leg in two-way booking (1=outbound, 2=return)'
    )

    # Multi-mode trip fields
    linked_booking = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='linked_bookings',
        help_text='Linked booking for multi-mode trips'
    )
    pending_transfer_stop = models.ForeignKey(
        'routing.TransferStation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pending_transfers',
        help_text='Transfer station where passenger is pending transfer'
    )
    transfer_trigger_km = models.FloatField(
        default=2.0,
        help_text='Distance in km to trigger transfer notification'
    )

    def save(self, *args, **kwargs):
        if self.status == 'held' and self.hold_expires_at is None:
            self.hold_expires_at = timezone.now() + timedelta(minutes=self.HOLD_DURATION_MINUTES)
        super().save(*args, **kwargs)

    def generate_ticket_codes(self):
        """
        Called once a booking is confirmed. Generates a unique QR token
        and a unique 6-digit backup code. Retries on the rare chance of
        a collision against the unique constraint.
        """
        self.qr_code_token = secrets.token_urlsafe(32)

        while True:
            candidate = f'{secrets.randbelow(1000000):06d}'
            if not Booking.all_objects.filter(short_code=candidate).exists():
                self.short_code = candidate
                break

    def __str__(self):
        return f'{self.commuter} - {self.trip} ({self.status})'


class LinkedBooking(models.Model):
    """
    Represents a journey that spans two routes with a transfer.
    Links two separate bookings (one for each leg) into a single journey.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_leg_booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name='linked_as_first_leg',
        help_text='Booking for the first route (Bus 1)'
    )
    second_leg_booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name='linked_as_second_leg',
        help_text='Booking for the second route (Bus 2)'
    )
    linked_route = models.ForeignKey(
        'routing.LinkedRoute', on_delete=models.CASCADE, related_name='linked_bookings',
        null=True, blank=True
    )
    transfer_station = models.ForeignKey(
        'routing.TransferStation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='linked_bookings'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('transfer_complete', 'Transfer Complete'),
            ('missed_connection', 'Missed Connection'),
            ('cancelled', 'Cancelled'),
        ],
        default='active',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['first_leg_booking', 'second_leg_booking']

    def __str__(self):
        return f'Linked: {self.first_leg_booking} → {self.second_leg_booking}'


class MissedConnectionEvent(models.Model):
    """
    Records when a passenger misses their transfer connection.
    Triggered when Bus 1's ETA to transfer station is within buffer time
    of Bus 2's scheduled departure.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    linked_booking = models.ForeignKey(
        LinkedBooking, on_delete=models.CASCADE, related_name='missed_connection_events'
    )
    first_leg_trip = models.ForeignKey(
        'routing.Trip', on_delete=models.CASCADE, related_name='missed_connections_as_first',
        help_text='Bus 1 that was delayed'
    )
    second_leg_trip = models.ForeignKey(
        'routing.Trip', on_delete=models.CASCADE, related_name='missed_connections_as_second',
        help_text='Bus 2 that was missed'
    )
    first_leg_eta_minutes = models.FloatField(
        help_text='ETA of Bus 1 to transfer station when event was triggered'
    )
    second_leg_departure_buffer = models.FloatField(
        help_text='Time difference between Bus 1 ETA and Bus 2 departure'
    )
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Missed connection: {self.linked_booking}'


class TransactionalVoucher(models.Model):
    """
    Temporary credit voucher created when a passenger misses their connection.
    The fare value from the missed leg is credited to this voucher for future use.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    missed_connection_event = models.ForeignKey(
        MissedConnectionEvent, on_delete=models.CASCADE, related_name='vouchers'
    )
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='transactional_vouchers',
        limit_choices_to={'role': 'commuter'}
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    original_booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name='issued_vouchers'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('redeemed', 'Redeemed'),
            ('expired', 'Expired'),
        ],
        default='active',
    )
    expires_at = models.DateTimeField(
        help_text='Voucher expiration date (typically 30 days from issue)'
    )
    redeemed_at = models.DateTimeField(null=True, blank=True)
    redeemed_booking = models.ForeignKey(
        Booking, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='redeemed_vouchers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Voucher: KES {self.amount} for {self.user.username}'


class TwoWayBooking(TenantScopedModel):
    """
    Manages round-trip bookings with two legs (outbound and return).
    Handles connection monitoring, missed connection events, and recovery options.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        ACTIVE = 'active', 'Active'  # User boarded first leg
        MISSED_CONNECTION = 'missed_connection', 'Missed Connection'
        RECOVERED = 'recovered', 'Recovered'  # User chose alternative
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    commuter = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='two_way_bookings',
        limit_choices_to={'role': 'commuter'}
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total_fare = models.DecimalField(max_digits=8, decimal_places=2)
    fare_paid = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Connection monitoring
    transfer_station = models.ForeignKey(
        'routing.Stop', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='two_way_bookings',
        help_text='Transfer station between legs (if applicable)'
    )
    connection_buffer_minutes = models.PositiveSmallIntegerField(
        default=30,
        help_text='Minimum buffer time between legs in minutes'
    )
    
    # Recovery options
    recovery_option_chosen = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('re_route', 'Re-Route'),
            ('refund', 'Refund'),
        ],
        default='none',
        null=True, blank=True
    )
    recovery_trip = models.ForeignKey(
        'routing.Trip', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recovery_bookings',
        help_text='Alternative trip if user chose re-route option'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    first_leg_boarded_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Voucher for missed connections
    voucher_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    voucher_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Two-Way Booking: {self.commuter.username} - {self.status}'

    def get_outbound_leg(self):
        """Get the first leg (outbound journey)"""
        return self.legs.filter(leg_order=1).first()

    def get_return_leg(self):
        """Get the second leg (return journey)"""
        return self.legs.filter(leg_order=2).first()

    def check_connection_status(self):
        """
        Check if the connection between legs is at risk based on GPS tracking.
        Returns True if connection is at risk of being missed.
        """
        outbound = self.get_outbound_leg()
        return_leg = self.get_return_leg()
        
        if not outbound or not return_leg:
            return False
            
        # This would integrate with the GPS tracking system
        # For now, return False - implementation would check:
        # 1. Current position of Bus 1
        # 2. ETA to transfer station
        # 3. Departure time of Bus 2
        # 4. If ETA within buffer minutes, trigger missed connection
        return False


class OpenReturnCredit(TenantScopedModel):
    """
    Open return credit for flexible return bookings.
    Commuter books outward trip now and gets credit to book any return trip
    within a time window without paying again.
    """
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        REDEEMED = 'redeemed', 'Redeemed'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    commuter = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='open_return_credits',
        limit_choices_to={'role': 'commuter'}
    )
    outbound_booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name='issued_return_credits',
        help_text='The outbound trip booking that generated this credit'
    )
    return_booking = models.ForeignKey(
        Booking, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='redeemed_return_credit',
        help_text='The return trip booking that used this credit'
    )
    credit_amount = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text='Amount credited for return trip fare'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    
    # Time window for using the credit
    valid_from = models.DateTimeField(help_text='Credit becomes valid at this time')
    valid_until = models.DateTimeField(help_text='Credit expires at this time')
    
    # Route constraints (optional - can restrict to specific routes)
    allowed_routes = models.ManyToManyField(
        'routing.Route', blank=True, related_name='open_return_credits',
        help_text='If specified, credit can only be used on these routes'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Open Return Credit: KES {self.credit_amount} for {self.commuter.username}'

    def is_valid(self):
        """Check if credit is currently valid for use."""
        if self.status != OpenReturnCredit.Status.ACTIVE:
            return False
        now = timezone.now()
        return self.valid_from <= now <= self.valid_until

    def redeem(self, return_booking):
        """Redeem the credit for a return booking."""
        if not self.is_valid():
            raise ValueError('Credit is not valid for redemption')
        
        self.status = OpenReturnCredit.Status.REDEEMED
        self.return_booking = return_booking
        self.redeemed_at = timezone.now()
        self.save()


class BookingReassignment(TenantScopedModel):
    """
    Tracks automatic reassignment of bookings when buses are cancelled or severely delayed.
    Provides audit trail for all reassignment events and supports manual intervention.
    """
    class ReassignmentReason(models.TextChoices):
        BUS_CANCELLED = 'bus_cancelled', 'Bus Cancelled'
        SEVERE_DELAY = 'severe_delay', 'Severe Delay'
        NO_SHOW = 'no_show', 'No Show'
        MAINTENANCE = 'maintenance', 'Maintenance Issue'
        OTHER = 'other', 'Other'

    class ReassignmentStatus(models.TextChoices):
        SUCCESS = 'success', 'Success'
        PENDING_MANUAL = 'pending_manual', 'Pending Manual Reroute'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name='reassignments',
        help_text='The booking that was reassigned'
    )
    original_trip = models.ForeignKey(
        'routing.Trip', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='original_reassignments',
        help_text='The original trip that was cancelled/delayed'
    )
    new_trip = models.ForeignKey(
        'routing.Trip', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='new_reassignments',
        help_text='The new trip the booking was reassigned to'
    )
    reason = models.CharField(
        max_length=20,
        choices=ReassignmentReason.choices,
        default=ReassignmentReason.BUS_CANCELLED,
        help_text='Reason for the reassignment'
    )
    status = models.CharField(
        max_length=20,
        choices=ReassignmentStatus.choices,
        default=ReassignmentStatus.SUCCESS,
        help_text='Status of the reassignment attempt'
    )
    
    # Reassignment details
    original_departure_time = models.DateTimeField(
        null=True, blank=True,
        help_text='Original scheduled departure time'
    )
    new_departure_time = models.DateTimeField(
        null=True, blank=True,
        help_text='New scheduled departure time'
    )
    original_vehicle_plate = models.CharField(
        max_length=20, null=True, blank=True,
        help_text='Original vehicle plate number'
    )
    new_vehicle_plate = models.CharField(
        max_length=20, null=True, blank=True,
        help_text='New vehicle plate number'
    )
    
    # Admin intervention fields
    admin_notes = models.TextField(
        blank=True,
        help_text='Notes from admin if manual intervention was required'
    )
    admin_user = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='handled_reassignments',
        limit_choices_to={'role__in': ['fleet_owner', 'super_admin']},
        help_text='Admin who handled manual rerouting if required'
    )
    
    # Notification tracking
    notification_sent = models.BooleanField(
        default=False,
        help_text='Whether commuter was notified of the reassignment'
    )
    notification_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When the notification was sent'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['reason']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'Reassignment: {self.booking} - {self.status}'