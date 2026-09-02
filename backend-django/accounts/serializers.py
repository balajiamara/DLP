from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    role = serializers.ChoiceField(choices=User.Role.choices, required=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'password', 'role')

    def validate_role(self, value):
        if value not in User.Role.values:
            raise serializers.ValidationError(f"Role must be one of: {', '.join(User.Role.values)}")
        return value

    def validate_email(self, value):
        normalized_email = value.lower().strip()
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return normalized_email

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value.strip()).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value.strip()

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            role=validated_data['role']
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'role', 'first_name', 'last_name', 'date_joined')
        read_only_fields = ('id', 'date_joined')


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name')

    def validate_username(self, value):
        new_username = value.strip()
        user = self.context['request'].user
        if User.objects.filter(username__iexact=new_username).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return new_username


class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'role')
        read_only_fields = ('id', 'username', 'role')
