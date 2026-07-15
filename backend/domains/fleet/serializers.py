from rest_framework import serializers

from .models import Fleet, Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    assigned_driver_username = serializers.CharField(source='assigned_driver.username', read_only=True, allow_null=True)
    assigned_conductor_username = serializers.CharField(source='assigned_conductor.username', read_only=True, allow_null=True)
    assigned_route_name = serializers.CharField(source='assigned_route.name', read_only=True, allow_null=True)
    assigned_driver = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    assigned_conductor = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    assigned_route = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'fleet', 'plate_number', 'fleet_code', 'vehicle_type', 'capacity', 'is_active',
            'assigned_route', 'assigned_route_name', 'assigned_driver', 'assigned_driver_username', 
            'assigned_conductor', 'assigned_conductor_username', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'fleet']
        extra_kwargs = {
            'fleet': {'required': False}
        }

    def validate(self, data):
        # Convert empty strings to None for foreign key fields
        if data.get('assigned_driver') == '':
            data['assigned_driver'] = None
        if data.get('assigned_conductor') == '':
            data['assigned_conductor'] = None
        if data.get('assigned_route') == '':
            data['assigned_route'] = None
        
        # Validate and convert foreign keys if provided
        if data.get('assigned_driver'):
            from domains.accounts.models import User
            try:
                driver = User.objects.filter(id=data['assigned_driver'], role='driver').first()
                if not driver:
                    raise serializers.ValidationError({'assigned_driver': 'Invalid driver ID'})
                # Check if driver is already assigned to another vehicle
                if self.instance and self.instance.assigned_driver_id != driver.id:
                    if Vehicle.objects.filter(assigned_driver=driver).exists():
                        raise serializers.ValidationError({'assigned_driver': 'Driver is already assigned to another vehicle'})
                elif not self.instance and Vehicle.objects.filter(assigned_driver=driver).exists():
                    raise serializers.ValidationError({'assigned_driver': 'Driver is already assigned to another vehicle'})
                data['assigned_driver'] = driver
            except (ValueError, TypeError):
                raise serializers.ValidationError({'assigned_driver': 'Invalid driver ID format'})
        
        if data.get('assigned_conductor'):
            from domains.accounts.models import User
            try:
                conductor = User.objects.filter(id=data['assigned_conductor'], role='conductor').first()
                if not conductor:
                    raise serializers.ValidationError({'assigned_conductor': 'Invalid conductor ID'})
                data['assigned_conductor'] = conductor
            except (ValueError, TypeError):
                raise serializers.ValidationError({'assigned_conductor': 'Invalid conductor ID format'})
        
        if data.get('assigned_route'):
            from domains.routing.models import Route
            try:
                route = Route.all_objects.filter(id=data['assigned_route']).first()
                if not route:
                    raise serializers.ValidationError({'assigned_route': 'Invalid route ID'})
                data['assigned_route'] = route
            except (ValueError, TypeError):
                raise serializers.ValidationError({'assigned_route': 'Invalid route ID format'})
        
        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['assigned_driver'] = str(instance.assigned_driver_id) if instance.assigned_driver_id else ''
        data['assigned_conductor'] = str(instance.assigned_conductor_id) if instance.assigned_conductor_id else ''
        data['assigned_route'] = str(instance.assigned_route_id) if instance.assigned_route_id else ''
        return data


class FleetSerializer(serializers.ModelSerializer):
    vehicles = VehicleSerializer(many=True, read_only=True)

    class Meta:
        model = Fleet
        fields = ['id', 'name', 'created_at', 'vehicles']
        read_only_fields = ['id', 'created_at']


class LiveVehicleSerializer(serializers.Serializer):
    vehicle_id = serializers.UUIDField()
    bus_id = serializers.UUIDField(source='vehicle_id')
    plate_number = serializers.CharField()
    plate = serializers.CharField(source='plate_number')
    trip_id = serializers.UUIDField(allow_null=True)
    route_name = serializers.CharField(allow_null=True)
    route = serializers.CharField(source='route_name', allow_null=True)
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
    speed_kmh = serializers.FloatField(allow_null=True)
    speed = serializers.FloatField(source='speed_kmh', allow_null=True)
    is_online = serializers.BooleanField()
    status = serializers.CharField(default='moving')


class RouteAnalyticsSerializer(serializers.Serializer):
    route_id = serializers.UUIDField()
    route_name = serializers.CharField()
    total_trips = serializers.IntegerField()
    total_passengers = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_occupancy_percent = serializers.FloatField()


class FleetAnalyticsSerializer(serializers.Serializer):
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    revenue = serializers.DecimalField(source='total_revenue', max_digits=12, decimal_places=2)
    total_passengers = serializers.IntegerField()
    total_trips = serializers.IntegerField()
    active_buses = serializers.IntegerField(required=False)
    delayed_buses = serializers.IntegerField(required=False)
    routes = RouteAnalyticsSerializer(many=True)