from rest_framework import viewsets
from ..models import TenderCategory
from .serializer import TenderCategorySerializer

class TenderCategoryViewSet(viewsets.ModelViewSet):
    queryset = TenderCategory.objects.all()
    serializer_class = TenderCategorySerializer