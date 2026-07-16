from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from domains.accounts.permissions import IsFleetOwnerOrSuperAdmin

from .models import User
from .serializers import CustomTokenObtainPairSerializer, StaffSerializer


@method_decorator(
    ratelimit(key='ip', rate='10/m', method='POST', block=True),
    name='dispatch'
)
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


from rest_framework.permissions import IsAuthenticated

class RegisterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != User.Role.SUPER_ADMIN:
            return Response({'detail': 'Only super admins can register users.'}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username')
        password = request.data.get('password')
        role = request.data.get('role')
        tenant_slug = request.data.get('tenant_slug')

        if not username or not password or not role:
            return Response({'detail': 'Username, password and role are required.'}, status=status.HTTP_400_BAD_REQUEST)

        from domains.tenants.models import Tenant
        tenant = None
        if role == User.Role.FLEET_OWNER:
            if not tenant_slug:
                return Response({'detail': 'Tenant slug is required for fleet owners.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                tenant = Tenant.objects.get(slug=tenant_slug)
            except Tenant.DoesNotExist:
                return Response({'detail': 'Tenant not found.'}, status=status.HTTP_400_BAD_REQUEST)
        elif role == User.Role.SUPER_ADMIN:
            if tenant_slug:
                return Response({'detail': 'Super admin cannot be assigned to a tenant.'}, status=status.HTTP_400_BAD_REQUEST)

        from django.db import IntegrityError
        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                role=role,
                tenant=tenant
            )
            return Response({'message': 'User registered successfully.'}, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response({'detail': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'username': user.username,
            'role': user.role,
            'tenant_slug': user.tenant.slug if user.tenant else None
        }, status=status.HTTP_200_OK)


class StaffViewSet(viewsets.ModelViewSet):
    serializer_class = StaffSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        qs = User.objects.filter(
            tenant=self.request.user.tenant,
            role__in=[User.Role.DRIVER, User.Role.CONDUCTOR],
        ).order_by('role', 'username')
        role = self.request.query_params.get('role')
        if role in ('driver', 'conductor'):
            qs = qs.filter(role=role)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        from domains.fleet.models import Vehicle
        Vehicle.objects.filter(assigned_driver=user).update(assigned_driver=None)
        Vehicle.objects.filter(assigned_conductor=user).update(assigned_conductor=None)
        return super().destroy(request, *args, **kwargs)


import uuid
import random
from datetime import timedelta
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from domains.accounts.permissions import IsCommuter
from .models import Device, DeviceVerificationToken
from domains.notifications.sms import send_sms
from domains.booking.models import Booking

class DeviceHandshakeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        device_uuid_str = request.data.get('device_uuid')
        if not device_uuid_str:
            return Response({'detail': 'device_uuid is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            device_uuid = uuid.UUID(device_uuid_str)
        except ValueError:
            return Response({'detail': 'Invalid device_uuid format.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if Device exists
        device = Device.objects.filter(device_uuid=device_uuid).first()
        if device:
            user = device.user
            # Update last active
            device.save()
        else:
            # Create a new guest user
            short_uuid = str(device_uuid)[:8]
            random_suffix = random.randint(1000, 9999)
            username = f'guest_{short_uuid}_{random_suffix}'
            
            while User.objects.filter(username=username).exists():
                random_suffix = random.randint(1000, 9999)
                username = f'guest_{short_uuid}_{random_suffix}'

            user = User.objects.create_user(
                username=username,
                password=User.objects.make_random_password(),
                role=User.Role.COMMUTER
            )
            # Default demo location at Nairobi CBD
            user.demo_latitude = -1.2921
            user.demo_longitude = 36.8219
            user.demo_location_label = 'Nairobi CBD'
            user.save()

            device = Device.objects.create(device_uuid=device_uuid, user=user)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'username': user.username,
            'role': user.role
        }, status=status.HTTP_200_OK)


class RequestDeviceMigrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone_number = request.data.get('phone_number')
        device_uuid_str = request.data.get('device_uuid')

        if not phone_number or not device_uuid_str:
            return Response({'detail': 'phone_number and device_uuid are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device_uuid = uuid.UUID(device_uuid_str)
        except ValueError:
            return Response({'detail': 'Invalid device_uuid format.'}, status=status.HTTP_400_BAD_REQUEST)

        # Clean/format phone number to ensure +254 prefix
        clean_phone = phone_number.strip()
        if clean_phone.startswith('0'):
            clean_phone = '+254' + clean_phone[1:]
        elif not clean_phone.startswith('+'):
            clean_phone = '+' + clean_phone

        # Create token
        token_obj = DeviceVerificationToken.objects.create(
            phone_number=clean_phone,
            device_uuid=device_uuid
        )

        # Resolve verification URL using HTTP Origin/Referer or default Render domain
        origin = request.headers.get('origin') or request.META.get('HTTP_ORIGIN')
        if not origin:
            referer = request.META.get('HTTP_REFERER')
            if referer:
                from urllib.parse import urlparse
                parsed = urlparse(referer)
                origin = f"{parsed.scheme}://{parsed.netloc}"
            else:
                origin = "https://smarttransitsystem-frontend.onrender.com"

        verification_link = f"{origin}/app/session/verify/{token_obj.token}"

        # Send SMS
        message = f"SmartTransit: Re-enter your session and recover your ticket history by clicking here: {verification_link}"
        try:
            send_sms(clean_phone, message)
        except Exception as e:
            return Response({'detail': f'Failed to send SMS: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'message': 'Session recovery SMS sent successfully.'}, status=status.HTTP_200_OK)


class VerifyDeviceMigrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get('token')
        if not token_str:
            return Response({'detail': 'token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token_uuid = uuid.UUID(token_str)
        except ValueError:
            return Response({'detail': 'Invalid token format.'}, status=status.HTTP_400_BAD_REQUEST)

        token_obj = DeviceVerificationToken.objects.filter(token=token_uuid, is_used=False).first()
        if not token_obj:
            return Response({'detail': 'Verification token is invalid or has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        # Token valid for 15 minutes
        if timezone.now() - token_obj.created_at > timedelta(minutes=15):
            token_obj.is_used = True
            token_obj.save()
            return Response({'detail': 'Verification token has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        token_obj.is_used = True
        token_obj.save()

        # Find existing commuter user with this phone number
        user = User.objects.filter(phone_number=token_obj.phone_number, role=User.Role.COMMUTER).first()
        
        if not user:
            # Update guest user associated with this device
            device = Device.objects.filter(device_uuid=token_obj.device_uuid).first()
            if device:
                user = device.user
                user.phone_number = token_obj.phone_number
                user.save()
            else:
                username = f'commuter_{str(uuid.uuid4())[:8]}'
                user = User.objects.create_user(
                    username=username,
                    password=User.objects.make_random_password(),
                    role=User.Role.COMMUTER,
                    phone_number=token_obj.phone_number
                )
                device = Device.objects.create(device_uuid=token_obj.device_uuid, user=user)
        else:
            # Bind device UUID to existing user
            Device.objects.update_or_create(
                device_uuid=token_obj.device_uuid,
                defaults={'user': user}
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'username': user.username,
            'role': user.role,
            'phone_number': user.phone_number
        }, status=status.HTTP_200_OK)


class CommuterProfileStatusView(APIView):
    permission_classes = [IsAuthenticated, IsCommuter]

    def get(self, request):
        user = request.user
        trip_count = Booking.objects.filter(commuter=user, status__in=['confirmed', 'boarded']).count()
        has_name = bool(user.first_name or user.last_name)
        
        return Response({
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
            'has_name': has_name,
            'trip_count': trip_count
        }, status=status.HTTP_200_OK)


class CommuterProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsCommuter]

    def post(self, request):
        user = request.user
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')

        if not first_name or not last_name:
            return Response({'detail': 'first_name and last_name are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user.first_name = first_name.strip()
        user.last_name = last_name.strip()
        user.save()

        return Response({
            'message': 'Profile updated successfully.',
            'first_name': user.first_name,
            'last_name': user.last_name
        }, status=status.HTTP_200_OK)
