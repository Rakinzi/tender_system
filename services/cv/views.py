from rest_framework import viewsets
from ..models import CV
from .serializer import CVSerializer

class CVViewSet(viewsets.ModelViewSet):
    queryset = CV.objects.all()
    serializer_class = CVSerializer