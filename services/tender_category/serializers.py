from rest_framework import serializers
from ..models import TenderCategory

class TenderCategorySerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = TenderCategory
        fields = ['category_id', 'name', 'description', 'created_at', 'updated_at']