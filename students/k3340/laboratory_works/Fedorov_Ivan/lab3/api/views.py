from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from hotel.models import Room, Client, Employee, CleaningSchedule
from api.serializers import *

# Временные фильтры прямо в views.py
import django_filters


class RoomFilter(django_filters.FilterSet):
    room_type = django_filters.ChoiceFilter(choices=Room.ROOM_TYPES)
    floor = django_filters.NumberFilter()
    min_price = django_filters.NumberFilter(field_name='price_per_day', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price_per_day', lookup_expr='lte')

    class Meta:
        model = Room
        fields = ['room_type', 'floor', 'is_available']


class ClientFilter(django_filters.FilterSet):
    city = django_filters.CharFilter(lookup_expr='icontains')
    check_in_after = django_filters.DateFilter(field_name='check_in_date', lookup_expr='gte')
    check_in_before = django_filters.DateFilter(field_name='check_in_date', lookup_expr='lte')

    class Meta:
        model = Client
        fields = ['city', 'room']


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RoomFilter

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Свободные номера"""
        rooms = Room.objects.filter(is_available=True)
        serializer = self.get_serializer(rooms, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def clients_in_period(self, request):
        """Клиенты в номере за период"""
        serializer = RoomClientsPeriodSerializer(data=request.data)
        if serializer.is_valid():
            room_id = serializer.validated_data['room_id']
            start_date = serializer.validated_data['start_date']
            end_date = serializer.validated_data['end_date']

            clients = Client.objects.filter(
                room_id=room_id,
                check_in_date__lte=end_date,
            ).filter(
                Q(check_out_date__gte=start_date) | Q(check_out_date__isnull=True)
            )

            result = ClientSerializer(clients, many=True).data
            return Response(result)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ClientFilter

    @action(detail=False, methods=['get'])
    def from_city(self, request):
        """Количество клиентов из города"""
        city = request.query_params.get('city')
        if city:
            count = Client.objects.filter(city__iexact=city).count()
            return Response({'city': city, 'count': count})
        return Response({'error': 'Укажите параметр city'}, status=400)

    @action(detail=False, methods=['post'])
    def same_period_clients(self, request):
        """Клиенты, проживавшие в тот же период"""
        serializer = ClientSamePeriodSerializer(data=request.data)
        if serializer.is_valid():
            client_id = serializer.validated_data['client_id']
            start_date = serializer.validated_data['start_date']
            end_date = serializer.validated_data['end_date']

            try:
                target_client = Client.objects.get(id=client_id)
                target_check_in = target_client.check_in_date
                target_check_out = target_client.check_out_date or timezone.now().date()

                # Находим пересекающиеся периоды
                clients = Client.objects.exclude(id=client_id).filter(
                    Q(check_in_date__lte=end_date) &
                    Q(
                        Q(check_out_date__gte=start_date) |
                        Q(check_out_date__isnull=True)
                    )
                )

                result = []
                for client in clients:
                    result.append({
                        'id': client.id,
                        'full_name': f"{client.last_name} {client.first_name}",
                        'city': client.city,
                        'check_in': client.check_in_date,
                        'check_out': client.check_out_date,
                        'room': client.room.number
                    })

                return Response(result)
            except Client.DoesNotExist:
                return Response({'error': 'Клиент не найден'}, status=404)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()  # Убираем фильтр is_active
    serializer_class = EmployeeSerializer

    @action(detail=True, methods=['post'])
    def fire(self, request, pk=None):
        """Уволить сотрудника"""
        employee = self.get_object()
        employee.is_active = False
        employee.save()
        return Response({'status': 'сотрудник уволен'})

    @action(detail=True, methods=['post'])
    def hire(self, request, pk=None):
        """Нанять сотрудника обратно"""
        employee = self.get_object()
        employee.is_active = True
        employee.save()
        return Response({'status': 'сотрудник нанят'})

    @action(detail=True, methods=['get'])
    def cleaning_info(self, request, pk=None):
        """Кто убирал номер клиента в заданный день"""
        employee = self.get_object()
        client_id = request.query_params.get('client_id')
        day = request.query_params.get('day')

        if not client_id or not day:
            return Response({'error': 'Укажите client_id и day'}, status=400)

        try:
            client = Client.objects.get(id=client_id)
            schedules = CleaningSchedule.objects.filter(
                employee=employee,
                floor=client.room.floor,
                day_of_week=day
            )
            serializer = CleaningScheduleSerializer(schedules, many=True)
            return Response(serializer.data)
        except Client.DoesNotExist:
            return Response({'error': 'Клиент не найден'}, status=404)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Только активные сотрудники"""
        employees = Employee.objects.filter(is_active=True)
        serializer = self.get_serializer(employees, many=True)
        return Response(serializer.data)

    # В class EmployeeViewSet добавьте:
    @action(detail=True, methods=['post'])
    def hire(self, request, pk=None):
        """Нанять сотрудника обратно"""
        employee = self.get_object()
        employee.is_active = True
        employee.save()
        return Response({'status': 'сотрудник нанят'})

    # В class ClientViewSet добавьте:
    @action(detail=True, methods=['post'])
    def check_out(self, request, pk=None):
        """Выселить клиента"""
        client = self.get_object()
        check_out_date = request.data.get('check_out_date')

        if not check_out_date:
            client.check_out_date = timezone.now().date()
        else:
            client.check_out_date = check_out_date

        # Освобождаем номер
        client.room.is_available = True
        client.room.save()

        client.save()

        return Response({
            'status': 'клиент выселен',
            'client_id': client.id,
            'check_out_date': client.check_out_date,
            'room_number': client.room.number,
            'room_status': 'свободен'
        })

    @action(detail=False, methods=['get'])
    def who_cleaned_client_room(self, request):
        """Кто убирал номер указанного клиента в заданный день"""
        client_id = request.query_params.get('client_id')
        day_of_week = request.query_params.get('day')

        if not client_id or not day_of_week:
            return Response(
                {'error': 'Укажите параметры client_id и day'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = Client.objects.get(id=client_id)
            room_floor = client.room.floor

            # Ищем сотрудников, которые убирают этот этаж в указанный день
            schedules = CleaningSchedule.objects.filter(
                floor=room_floor,
                day_of_week=day_of_week
            ).select_related('employee')

            result = []
            for schedule in schedules:
                result.append({
                    'employee_id': schedule.employee.id,
                    'employee_name': str(schedule.employee),
                    'floor': schedule.floor,
                    'day_of_week': schedule.get_day_of_week_display(),
                    'client_info': {
                        'id': client.id,
                        'name': f"{client.last_name} {client.first_name}",
                        'room_number': client.room.number,
                        'room_floor': client.room.floor
                    }
                })

            return Response(result)

        except Client.DoesNotExist:
            return Response(
                {'error': 'Клиент не найден'},
                status=status.HTTP_404_NOT_FOUND
            )


class CleaningScheduleViewSet(viewsets.ModelViewSet):
    queryset = CleaningSchedule.objects.all()
    serializer_class = CleaningScheduleSerializer


class ReportView(generics.GenericAPIView):
    """Отчёт за квартал"""

    def get(self, request):
        quarter = request.query_params.get('quarter')
        year = request.query_params.get('year')

        # Проверяем обязательные параметры
        if not quarter or not year:
            return Response(
                {'error': 'Необходимы параметры quarter и year'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quarter = int(quarter)
            year = int(year)

            # Проверяем валидность quarter
            if quarter not in [1, 2, 3, 4]:
                return Response(
                    {'error': 'Квартал должен быть 1, 2, 3 или 4'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверяем валидность года
            if year < 2000 or year > 2100:
                return Response(
                    {'error': 'Год должен быть между 2000 и 2100'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Определяем месяцы квартала
            month_start = (quarter - 1) * 3 + 1
            start_date = datetime(year, month_start, 1).date()

            # Конец квартала
            if quarter == 4:
                end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(year, month_start + 3, 1).date() - timedelta(days=1)

            # Клиенты по номерам
            clients_by_room = Client.objects.filter(
                check_in_date__lte=end_date
            ).filter(
                Q(check_out_date__gte=start_date) | Q(check_out_date__isnull=True)
            ).values('room__number', 'room__room_type').annotate(
                client_count=Count('id')
            ).order_by('room__number')

            # Номера по этажам
            rooms_by_floor = Room.objects.values('floor').annotate(
                room_count=Count('id'),
                available_count=Count('id', filter=Q(is_available=True))
            ).order_by('floor')

            # Доход по номерам
            income_by_room = []
            total_income = 0

            for room in Room.objects.all():
                room_clients = Client.objects.filter(
                    room=room,
                    check_in_date__lte=end_date
                ).filter(
                    Q(check_out_date__gte=start_date) | Q(check_out_date__isnull=True)
                )

                room_income = 0
                for client in room_clients:
                    days_in_quarter = self._days_in_period(
                        client.check_in_date,
                        client.check_out_date or timezone.now().date(),
                        start_date,
                        end_date
                    )
                    room_income += days_in_quarter * room.price_per_day

                income_by_room.append({
                    'room_number': room.number,
                    'room_type': room.get_room_type_display(),
                    'floor': room.floor,
                    'income': float(room_income),
                    'days_in_quarter': self._days_in_period(
                        start_date, end_date, start_date, end_date
                    )  # всего дней в квартале
                })
                total_income += room_income

            # Общая статистика
            total_clients = Client.objects.filter(
                check_in_date__lte=end_date
            ).filter(
                Q(check_out_date__gte=start_date) | Q(check_out_date__isnull=True)
            ).count()

            avg_income_per_room = total_income / Room.objects.count() if Room.objects.count() > 0 else 0

            report = {
                'period': f'{year} Q{quarter}',
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_rooms': Room.objects.count(),
                'total_clients': total_clients,
                'clients_by_room': list(clients_by_room),
                'rooms_by_floor': list(rooms_by_floor),
                'income_by_room': income_by_room,
                'total_income': float(total_income),
                'average_income_per_room': float(avg_income_per_room),
                'generated_at': timezone.now().isoformat()
            }

            return Response(report)

        except ValueError as e:
            return Response(
                {'error': f'Неверный формат данных: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Внутренняя ошибка: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _days_in_period(self, check_in, check_out, period_start, period_end):
        """Вычисляет количество дней в периоде"""
        start = max(check_in, period_start)
        end = min(check_out, period_end) if check_out else period_end

        if start > end:
            return 0

        return (end - start).days + 1

    def _days_in_period(self, check_in, check_out, period_start, period_end):
        start = max(check_in, period_start)
        end = min(check_out, period_end) if check_out else period_end
        if start > end:
            return 0
        return (end - start).days + 1