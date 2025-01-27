from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ..services.tender.views import TenderViewSet


tender = DefaultRouter()
tender.register(r"tenders", TenderViewSet)

urlpatterns = [
    path('api/', include(tender.urls))
]
