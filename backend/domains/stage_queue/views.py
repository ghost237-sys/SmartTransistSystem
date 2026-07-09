from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from domains.accounts.permissions import IsDriver, IsFleetOwnerOrSuperAdminOrStageManager, IsStageManager, IsStageManagerOrDriver
from .models import QueueEntry, Stage
from .serializers import (
    ArrivedAtLoadingBaySerializer, CallUpSerializer, CheckInSerializer, ConfirmSerializer, DepartSerializer,
    MarkFullSerializer, QueueEntrySerializer, QueueStatusSerializer, ReorderQueueSerializer, StageSerializer
)


class StageViewSet(ModelViewSet):
    def get_queryset(self):
        # Use all_objects to bypass tenant filtering
        # Fleet owners need to see stages to assign to drivers
        return Stage.all_objects.all()
    serializer_class = StageSerializer
    permission_classes = [IsFleetOwnerOrSuperAdminOrStageManager]


class QueueEntryViewSet(ModelViewSet):
    serializer_class = QueueEntrySerializer
    permission_classes = [IsStageManagerOrDriver]

    def get_queryset(self):
        # Use all_objects to bypass tenant filtering
        queryset = QueueEntry.all_objects.select_related('stage', 'vehicle', 'driver', 'route')
        stage_id = self.request.query_params.get('stage_id')
        if stage_id:
            queryset = queryset.filter(stage_id=stage_id)
        return queryset


class CheckInView(APIView):
    """
    Driver checks in at a stage.
    Creates a QueueEntry in 'holding' status (unconfirmed).
    """
    permission_classes = [IsDriver]

    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        stage_id = serializer.validated_data['stage_id']
        vehicle_id = serializer.validated_data['vehicle_id']
        
        # Check if already checked in
        existing = QueueEntry.all_objects.filter(
            vehicle_id=vehicle_id,
            status__in=['holding', 'called_up', 'loading']
        ).first()
        
        if existing:
            return Response(
                {'error': 'Vehicle already in queue', 'queue_entry_id': str(existing.id)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get stage to set tenant
        stage = Stage.all_objects.get(id=stage_id)
        
        # Create queue entry
        queue_entry = QueueEntry.objects.create(
            stage=stage,
            vehicle_id=vehicle_id,
            driver_id=request.user.id,
            tenant=stage.tenant,
            status='holding',
            confirmed=False
        )
        
        return Response(
            QueueEntrySerializer(queue_entry).data,
            status=status.HTTP_201_CREATED
        )


class ConfirmView(APIView):
    """
    Stage manager confirms a bus has physically arrived.
    Sets confirmed=True and confirmed_at.
    """
    permission_classes = [IsStageManager]

    def post(self, request):
        serializer = ConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        queue_entry_id = serializer.validated_data['queue_entry_id']
        
        try:
            queue_entry = QueueEntry.objects.get(id=queue_entry_id)
        except QueueEntry.DoesNotExist:
            return Response(
                {'error': 'Queue entry not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if queue_entry.confirmed:
            return Response(
                {'error': 'Already confirmed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if queue_entry.status != 'holding':
            return Response(
                {'error': 'Can only confirm holding entries'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queue_entry.confirmed = True
        queue_entry.confirmed_at = timezone.now()
        queue_entry.save()
        
        return Response(QueueEntrySerializer(queue_entry).data)


class CallUpView(APIView):
    """
    Stage manager calls up a bus to the loading bay.
    Sets status='called_up' and called_up_at.
    """
    permission_classes = [IsStageManager]

    def post(self, request):
        serializer = CallUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        queue_entry_id = serializer.validated_data['queue_entry_id']
        
        try:
            queue_entry = QueueEntry.objects.get(id=queue_entry_id)
        except QueueEntry.DoesNotExist:
            return Response(
                {'error': 'Queue entry not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if queue_entry.status != 'holding':
            return Response(
                {'error': 'Can only call up holding entries'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not queue_entry.confirmed:
            return Response(
                {'error': 'Must confirm before calling up'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check loading bay capacity
        if not queue_entry.stage.loading_bay_available:
            return Response(
                {'error': 'Loading bay at capacity'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queue_entry.status = 'called_up'
        queue_entry.called_up_at = timezone.now()
        queue_entry.save()
        
        # Schedule time-cap enforcement task
        from .tasks import enforce_time_cap
        enforce_time_cap.apply_async(
            args=[str(queue_entry.id)],
            countdown=queue_entry.time_cap_minutes * 60
        )
        
        return Response(QueueEntrySerializer(queue_entry).data)


class ArrivedAtLoadingBayView(APIView):
    """
    Driver acknowledges arrival at loading bay.
    Sets status='loading' and loading_started_at.
    Creates a Trip for the driver and conductor.
    """
    permission_classes = [IsDriver]

    def post(self, request):
        serializer = ArrivedAtLoadingBaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        queue_entry_id = serializer.validated_data['queue_entry_id']
        
        try:
            queue_entry = QueueEntry.all_objects.get(id=queue_entry_id, driver_id=request.user.id)
        except QueueEntry.DoesNotExist:
            return Response(
                {'error': 'Queue entry not found or not yours'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if queue_entry.status != 'called_up':
            return Response(
                {'error': 'Can only arrive at loading bay from called_up status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queue_entry.status = 'loading'
        queue_entry.loading_started_at = timezone.now()
        
        # Get conductor from vehicle assignment
        conductor = queue_entry.vehicle.assigned_conductor
        queue_entry.conductor = conductor
        
        # Get route - try queue entry first, then vehicle assignment
        route = queue_entry.route or queue_entry.vehicle.assigned_route
        
        # Only create trip if route is available
        if route:
            from domains.routing.models import Trip
            trip = Trip.objects.create(
                route=route,
                vehicle=queue_entry.vehicle,
                driver=queue_entry.driver,
                conductor=conductor,
                departure_time=timezone.now(),
                total_seats=queue_entry.vehicle.capacity,
                fare=route.distance_km * 10 if route.distance_km else 50,  # Simple fare calculation
                status='active',
                tenant=queue_entry.tenant
            )
            queue_entry.trip = trip
        
        queue_entry.save()
        
        return Response(QueueEntrySerializer(queue_entry).data)


class DepartView(APIView):
    """
    Driver departs the stage.
    Sets queue entry status='departed' and departed_at.
    Note: This is QueueEntry status, not Trip status (trips remain 'active' in on-demand model).
    """
    permission_classes = [IsDriver]

    def post(self, request):
        serializer = DepartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        queue_entry_id = serializer.validated_data['queue_entry_id']
        
        try:
            queue_entry = QueueEntry.all_objects.get(id=queue_entry_id, driver_id=request.user.id)
        except QueueEntry.DoesNotExist:
            return Response(
                {'error': 'Queue entry not found or not yours'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if queue_entry.status not in ['called_up', 'loading']:
            return Response(
                {'error': 'Can only depart from called_up or loading status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queue_entry.status = 'departed'
        queue_entry.departed_at = timezone.now()
        queue_entry.save()
        
        # Suggest next bus
        next_entry = queue_entry.stage.next_in_queue
        next_suggestion = None
        if next_entry:
            next_suggestion = {
                'queue_entry_id': str(next_entry.id),
                'vehicle_code': next_entry.vehicle.fleet_code or next_entry.vehicle.plate_number,
                'queue_position': next_entry.queue_position
            }
        
        return Response({
            'queue_entry': QueueEntrySerializer(queue_entry).data,
            'next_suggestion': next_suggestion
        })


class QueueStatusView(APIView):
    """
    Get current queue status for a stage.
    Returns all entries ordered by position.
    """
    permission_classes = [IsStageManagerOrDriver]

    def get(self, request):
        serializer = QueueStatusSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        stage_id = serializer.validated_data['stage_id']
        
        entries = QueueEntry.all_objects.filter(
            stage_id=stage_id,
            status__in=['holding', 'called_up', 'loading']
        ).select_related('vehicle', 'driver').order_by('arrived_at')
        
        stage = Stage.all_objects.get(id=stage_id)
        
        return Response({
            'stage_id': stage_id,
            'entries': QueueEntrySerializer(entries, many=True).data,
            'loading_bay_count': stage.loading_bay_count,
            'loading_bay_available': stage.loading_bay_available
        })


class MyQueueStatusView(APIView):
    """
    Driver gets their current queue status.
    """
    permission_classes = [IsDriver]

    def get(self, request):
        entry = QueueEntry.all_objects.filter(
            driver_id=request.user.id,
            status__in=['holding', 'called_up', 'loading', 'full']
        ).select_related('stage', 'vehicle').first()
        
        if not entry:
            return Response(
                {'message': 'Not currently in queue'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get queue position
        position = entry.queue_position if entry.status == 'holding' else None
        
        # Get entries ahead
        ahead_count = 0
        if entry.status == 'holding' and entry.confirmed:
            ahead_count = QueueEntry.all_objects.filter(
                stage=entry.stage,
                status='holding',
                confirmed=True,
                confirmed_at__lt=entry.confirmed_at
            ).count()
        
        return Response({
            'queue_entry': QueueEntrySerializer(entry).data,
            'queue_position': position,
            'entries_ahead': ahead_count,
            'loading_bay_available': entry.stage.loading_bay_available
        })


class ReorderQueueView(APIView):
    """
    Stage manager reorders the queue by changing positions.
    """
    permission_classes = [IsStageManager]

    def post(self, request):
        serializer = ReorderQueueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        queue_entry_id = serializer.validated_data['queue_entry_id']
        new_position = serializer.validated_data['new_position']
        
        try:
            queue_entry = QueueEntry.objects.get(id=queue_entry_id)
        except QueueEntry.DoesNotExist:
            return Response(
                {'error': 'Queue entry not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if queue_entry.status != 'holding':
            return Response(
                {'error': 'Can only reorder holding entries'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update position
        queue_entry.position = new_position
        queue_entry.save()
        
        return Response(QueueEntrySerializer(queue_entry).data)


class MarkFullView(APIView):
    """
    Stage manager marks vehicle as full.
    Sends notification to driver and removes from queue.
    """
    permission_classes = [IsStageManager]

    def post(self, request):
        serializer = MarkFullSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        queue_entry_id = serializer.validated_data['queue_entry_id']
        
        try:
            queue_entry = QueueEntry.objects.get(id=queue_entry_id)
        except QueueEntry.DoesNotExist:
            return Response(
                {'error': 'Queue entry not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if queue_entry.status != 'loading':
            return Response(
                {'error': 'Can only mark loading entries as full'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark as full
        queue_entry.status = 'full'
        queue_entry.departed_at = timezone.now()
        queue_entry.save()
        
        # Update trip status to departed
        if queue_entry.trip:
            queue_entry.trip.status = 'departed'
            queue_entry.trip.save()
        
        # Send notification to driver
        from domains.notifications.models import Notification
        Notification.objects.create(
            user=queue_entry.driver,
            title='Vehicle Full',
            message=f'Your vehicle {queue_entry.vehicle.fleet_code or queue_entry.vehicle.plate_number} is full. Please depart from the loading bay.',
            type='info',
            tenant=queue_entry.tenant
        )
        
        # Send notification to conductor if assigned
        if queue_entry.conductor:
            Notification.objects.create(
                user=queue_entry.conductor,
                title='Vehicle Full',
                message=f'Your vehicle {queue_entry.vehicle.fleet_code or queue_entry.vehicle.plate_number} is full. Please depart from the loading bay.',
                type='info',
                tenant=queue_entry.tenant
            )
        
        return Response(QueueEntrySerializer(queue_entry).data)
