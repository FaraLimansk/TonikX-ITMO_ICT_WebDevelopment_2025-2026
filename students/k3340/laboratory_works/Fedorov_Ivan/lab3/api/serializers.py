from rest_framework import serializers
from django.contrib.auth.models import User
from hotel.models import Room, Client, Employee, CleaningSchedule


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class CustomUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'first_name', 'last_name']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = '__all__'


class ClientSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.number', read_only=True)

    class Meta:
        model = Client
        fields = '__all__'


class EmployeeSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(write_only=True, required=False)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'
        extra_fields = ['username']

    def create(self, validated_data):
        user_id = validated_data.pop('user_id', None)

        employee = Employee.objects.create(**validated_data)

        if user_id:
            try:
                user = User.objects.get(id=user_id)
                employee.user = user
                employee.save()
            except User.DoesNotExist:
                pass

        return employee


class CleaningScheduleSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.__str__', read_only=True)

    class Meta:
        model = CleaningSchedule
        fields = '__all__'


# Специальные сериализаторы для запросов
class RoomClientsPeriodSerializer(serializers.Serializer):
    room_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class ClientSamePeriodSerializer(serializers.Serializer):
    client_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()