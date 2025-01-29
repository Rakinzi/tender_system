from rest_framework import viewsets, status, permissions
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from ..models import Tender, User
from .serializers import TenderSerializer



class TenderViewSet(viewsets.ModelViewSet):
    queryset = Tender.objects.all()
    serializer_class = TenderSerializer
    permission_classes = []  # Empty list means no authentication required

    def get_queryset(self):
        return Tender.objects.all()