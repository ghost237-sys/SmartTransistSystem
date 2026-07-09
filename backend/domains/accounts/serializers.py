from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password

from .models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['tenant_id'] = str(user.tenant_id) if user.tenant_id else None
        token['username'] = user.username
        if user.demo_latitude is not None and user.demo_longitude is not None:
            token['demo_lat'] = user.demo_latitude
            token['demo_lng'] = user.demo_longitude
            token['demo_location_label'] = user.demo_location_label or ''
        return token


class StaffSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=6)
    assigned_vehicle_plate = serializers.SerializerMethodField(read_only=True)
    assigned_vehicle_id = serializers.SerializerMethodField(read_only=True)
    assigned_fleet_code = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'role', 'password',
            'assigned_vehicle_plate', 'assigned_vehicle_id', 'assigned_fleet_code',
        ]
        read_only_fields = ['id', 'assigned_vehicle_plate', 'assigned_vehicle_id', 'assigned_fleet_code']

    def get_assigned_vehicle(self, obj):
        from domains.fleet.models import Vehicle
        if obj.role == User.Role.DRIVER:
            return Vehicle.all_objects.filter(assigned_driver=obj).select_related('fleet').first()
        if obj.role == User.Role.CONDUCTOR:
            return Vehicle.all_objects.filter(assigned_conductor=obj).select_related('fleet').first()
        return None

    def get_assigned_vehicle_plate(self, obj):
        vehicle = self.get_assigned_vehicle(obj)
        return vehicle.plate_number if vehicle else None

    def get_assigned_vehicle_id(self, obj):
        vehicle = self.get_assigned_vehicle(obj)
        return str(vehicle.id) if vehicle else None

    def get_assigned_fleet_code(self, obj):
        vehicle = self.get_assigned_vehicle(obj)
        return vehicle.fleet_code if vehicle and vehicle.fleet_code else None

    def validate(self, data):
        role = data.get('role') or getattr(self.instance, 'role', None)
        if role not in (User.Role.DRIVER, User.Role.CONDUCTOR):
            raise serializers.ValidationError({'role': 'Staff must be driver or conductor.'})
        password = data.get('password')
        if not self.instance and not password:
            raise serializers.ValidationError({'password': 'Password is required for new staff.'})
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        tenant = self.context['request'].user.tenant
        user = User.objects.create(
            tenant=tenant,
            **validated_data,
            password=make_password(password),
        )
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.password = make_password(password)
        instance.save()
        return instance
