from rest_framework import serializers
from ..models import TenderCategory

class TenderCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TenderCategory
        fields = "__all__"