from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import Department
from .serializers import DepartmentSerializer
from django.utils import timezone

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            'message': 'Department created successfully',
            'data': serializer.data,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'created_by': request.user.email
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'message': 'Department updated successfully',
            'data': serializer.data,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_by': request.user.email
        })

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        department_name = instance.department_name
        self.perform_destroy(instance)
        return Response({
            'message': f'Department {department_name} deleted successfully',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'deleted_by': request.user.email
        }, status=status.HTTP_200_OK)