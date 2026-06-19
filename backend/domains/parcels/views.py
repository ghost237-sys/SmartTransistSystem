from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import IsConductor, IsFleetOwnerOrSuperAdmin
from domains.routing.models import Stop, Trip

from .models import Parcel, ParcelScanEvent
from .serializers import (
    ParcelSerializer,
    RegisterParcelSerializer,
    ScanParcelSerializer,
)
from .utils import generate_qr_token, generate_tracking_code


class RegisterParcelView(APIView):
    """
    Fleet owner or conductor registers a parcel at the origin terminal.
    Generates a tracking code and QR token immediately on registration.
    """
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def post(self, request):
        serializer = RegisterParcelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        trip = Trip.all_objects.filter(id=data['trip_id']).first()
        if trip is None:
            return Response({'detail': 'Trip not found.'}, status=status.HTTP_404_NOT_FOUND)

        origin_stop = None
        if data.get('origin_stop_id'):
            origin_stop = Stop.objects.filter(id=data['origin_stop_id']).first()

        destination_stop = None
        if data.get('destination_stop_id'):
            destination_stop = Stop.objects.filter(id=data['destination_stop_id']).first()

        # Generate unique tracking code with collision retry
        while True:
            code = generate_tracking_code()
            if not Parcel.all_objects.filter(tracking_code=code).exists():
                break

        parcel = Parcel.objects.create(
            tenant=trip.tenant,
            tracking_code=code,
            qr_token=generate_qr_token(),
            sender_name=data['sender_name'],
            sender_phone=data['sender_phone'],
            recipient_name=data['recipient_name'],
            recipient_phone=data['recipient_phone'],
            trip=trip,
            origin_stop=origin_stop,
            destination_stop=destination_stop,
            description=data.get('description', ''),
            weight_kg=data.get('weight_kg'),
            declared_value=data.get('declared_value'),
            fee=data.get('fee', 0),
            status=Parcel.Status.REGISTERED,
        )

        return Response(ParcelSerializer(parcel).data, status=status.HTTP_201_CREATED)


class ScanParcelView(APIView):
    """
    Conductor scans a parcel QR code at a custody handoff point —
    loading onto vehicle, offloading at destination, or collection.
    Each scan creates an immutable ParcelScanEvent and advances
    the parcel's status accordingly.
    """
    permission_classes = [IsConductor]

    # Maps event_type → next parcel status
    STATUS_TRANSITIONS = {
        ParcelScanEvent.EventType.LOADED:    Parcel.Status.IN_TRANSIT,
        ParcelScanEvent.EventType.OFFLOADED: Parcel.Status.ARRIVED,
        ParcelScanEvent.EventType.COLLECTED: Parcel.Status.COLLECTED,
    }

    def post(self, request):
        serializer = ScanParcelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        parcel = Parcel.all_objects.filter(qr_token=data['qr_token']).first()
        if parcel is None:
            return Response({'detail': 'Parcel not found.'}, status=status.HTTP_404_NOT_FOUND)

        vehicle = None
        if data.get('vehicle_id'):
            from domains.fleet.models import Vehicle
            vehicle = Vehicle.all_objects.filter(id=data['vehicle_id']).first()

        ParcelScanEvent.objects.create(
            parcel=parcel,
            event_type=data['event_type'],
            scanned_by=request.user,
            vehicle=vehicle,
            notes=data.get('notes', ''),
        )

        new_status = self.STATUS_TRANSITIONS.get(data['event_type'])
        if new_status:
            parcel.status = new_status
            parcel.save()

        return Response({
            'tracking_code': parcel.tracking_code,
            'event_type': data['event_type'],
            'new_status': parcel.status,
            'detail': f'Parcel scanned successfully as {data["event_type"]}.',
        })


class TrackParcelView(APIView):
    """
    Public-ish tracking endpoint — anyone with the tracking code can
    see the parcel's current status and full scan history. Used by
    recipients checking where their parcel is.
    Authentication still required (prevents random enumeration of
    tracking codes), but no role restriction beyond being logged in.
    """
    def get(self, request, tracking_code):
        parcel = Parcel.all_objects.filter(
            tracking_code=tracking_code.upper()
        ).first()

        if parcel is None:
            return Response({'detail': 'Parcel not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(ParcelSerializer(parcel).data)


class ParcelListView(APIView):
    """
    Fleet owner sees all parcels for their tenant, filterable by status.
    """
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get(self, request):
        status_filter = request.query_params.get('status')
        parcels = Parcel.objects.all()
        if status_filter:
            parcels = parcels.filter(status=status_filter)
        parcels = parcels.order_by('-created_at')
        return Response(ParcelSerializer(parcels, many=True).data)