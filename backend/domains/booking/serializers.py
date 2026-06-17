from rest_framework import serializers

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(write_only=True)

    class Meta:
        model = Booking
        fields = ['id', 'trip', 'status', 'fare_paid', 'created_at', 'confirmed_at', 'phone_number']
        read_only_fields = ['id', 'status', 'fare_paid', 'created_at', 'confirmed_at']