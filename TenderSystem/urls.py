from django.urls import path, include
from rest_framework.routers import DefaultRouter
from services.tender.views import TenderViewSet
from services.company.views import CompanyViewSet
from services.department.views import DepartmentViewSet
from services.tender_category.views import TenderCategoryViewSet
from services.cv.views import CVViewSet


tender = DefaultRouter()
tender.register(r"companies", CompanyViewSet)
tender.register(r"departments", DepartmentViewSet)
tender.register(r"cvs", CVViewSet)
tender.register(r"tenders", TenderViewSet)
tender.register(r"tender_categories", TenderCategoryViewSet)

urlpatterns = [path("api/", include(tender.urls))]
