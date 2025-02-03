from rest_framework import serializers
from ..models import Department

class DepartmentSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = Department
        fields = [
            'department_id',
            'department_name',
            'description',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['department_id', 'created_at', 'updated_at']