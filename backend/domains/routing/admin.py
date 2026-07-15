from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import Route, Stop, Trip, Seat, TransferStation, LinkedRoute


# ─── Inline: Stops within Route ──────────────────────────────────────────────

class StopInline(admin.TabularInline):
    """
    Inline editor for stops on a route.
    Stops are ordered by sequence and editable directly from the Route page.
    """
    model = Stop
    extra = 1
    fields = ('sequence', 'name', 'location')
    ordering = ('sequence',)
    show_change_link = True

    class Media:
        css = {'all': ('admin/css/forms.css',)}


# ─── Route Admin ─────────────────────────────────────────────────────────────

@admin.register(Route)
class RouteAdmin(GISModelAdmin):
    list_display = ('name', 'stop_count', 'distance_km', 'estimated_duration_minutes', 'is_active', 'tenant', 'created_at')
    list_filter = ('is_active', 'tenant')
    search_fields = ('name',)
    list_editable = ('is_active',)
    ordering = ('name',)
    inlines = [StopInline]
    readonly_fields = ('id', 'created_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'is_active', 'tenant'),
        }),
        ('Route Geometry & Metrics', {
            'fields': ('path', 'distance_km', 'estimated_duration_minutes', 'max_pickup_distance_km'),
        }),
        ('System', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def stop_count(self, obj):
        return obj.stops.count()
    stop_count.short_description = 'Stops'


# ─── Stop Admin (standalone) ─────────────────────────────────────────────────

@admin.register(Stop)
class StopAdmin(GISModelAdmin):
    list_display = ('name', 'route', 'sequence', 'latitude', 'longitude')
    list_filter = ('route',)
    search_fields = ('name', 'route__name')
    list_editable = ('sequence',)
    ordering = ('route__name', 'sequence')

    def latitude(self, obj):
        return round(obj.location.y, 6) if obj.location else '—'
    latitude.short_description = 'Lat'

    def longitude(self, obj):
        return round(obj.location.x, 6) if obj.location else '—'
    longitude.short_description = 'Lng'


# ─── Trip Admin ──────────────────────────────────────────────────────────────

class SeatInline(admin.TabularInline):
    model = Seat
    extra = 0
    fields = ('seat_number', 'is_available')
    readonly_fields = ('seat_number',)
    ordering = ('seat_number',)
    show_change_link = False
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('route', 'vehicle_display', 'driver', 'conductor', 'departure_time', 'fare', 'status', 'available_seats_display', 'created_at')
    list_filter = ('status', 'route', 'created_at')
    search_fields = ('route__name', 'vehicle__plate_number', 'driver__username')
    list_editable = ('status',)
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'available_seats_display')
    inlines = [SeatInline]
    raw_id_fields = ('driver', 'conductor', 'vehicle')

    fieldsets = (
        (None, {
            'fields': ('route', 'vehicle', 'status'),
        }),
        ('Crew', {
            'fields': ('driver', 'conductor'),
        }),
        ('Scheduling & Pricing', {
            'fields': ('departure_time', 'total_seats', 'fare'),
        }),
        ('Capacity', {
            'fields': ('available_seats_display',),
        }),
        ('System', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def vehicle_display(self, obj):
        return obj.vehicle.fleet_code or obj.vehicle.plate_number
    vehicle_display.short_description = 'Vehicle'

    def available_seats_display(self, obj):
        return f'{obj.available_seats} / {obj.total_seats}'
    available_seats_display.short_description = 'Available Seats'


# ─── Transfer Station Admin ──────────────────────────────────────────────────

@admin.register(TransferStation)
class TransferStationAdmin(GISModelAdmin):
    list_display = ('name', 'buffer_minutes', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    list_editable = ('is_active', 'buffer_minutes')
    ordering = ('name',)
    readonly_fields = ('id', 'created_at')


# ─── Linked Route Admin ─────────────────────────────────────────────────────

@admin.register(LinkedRoute)
class LinkedRouteAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'first_route', 'second_route', 'transfer_station', 'is_active', 'created_at')
    list_filter = ('is_active', 'transfer_station')
    search_fields = ('first_route__name', 'second_route__name', 'transfer_station__name')
    list_editable = ('is_active',)
    ordering = ('first_route__name',)
    readonly_fields = ('id', 'created_at')
    raw_id_fields = ('first_route_stop', 'second_route_stop')