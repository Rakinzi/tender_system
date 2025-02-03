from rest_framework import serializers
from ..models import Company

class CompanySerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = Company
        fields = [
            'company_id', 
            'company_name', 
            'description', 
            'address', 
            'phone_number', 
            'email',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['company_id', 'created_at', 'updated_at']