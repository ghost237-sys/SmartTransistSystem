from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from domains.accounts.models import User
from domains.tenants.models import Tenant


class RegisterUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    tenant_slug = serializers.SlugRelatedField(
        slug_field='slug',
        queryset=Tenant.objects.all(),
        source='tenant',
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'tenant_slug', 'phone_number']
        read_only_fields = ['id']

    def validate(self, attrs):
        role = attrs.get('role', User.Role.COMMUTER)
        tenant = attrs.get('tenant', None)
        if role in (User.Role.FLEET_OWNER, User.Role.DRIVER, User.Role.CONDUCTOR):
            if tenant is None:
                raise serializers.ValidationError(
                    f"A tenant is required for role '{role}'."
                )
        if role == User.Role.SUPER_ADMIN and tenant is not None:
            raise serializers.ValidationError(
                "super_admin must not be tied to a tenant."
            )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    tenant_slug = serializers.CharField(source='tenant.slug', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'tenant_name', 'tenant_slug', 'phone_number']
        read_only_fields = fields