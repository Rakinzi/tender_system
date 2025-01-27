from django.urls import path, include
from services.company.views import CompanyViewSet
from services.cv.views import CVViewSet
from services.department.views import DepartmentViewSet
from rest_framework.routers import DefaultRouter
from services.tender.views import TenderViewSet
from services.tender_category.views import TenderCategoryViewSet
from services.auth.views import RegisterView, LoginView



tender = DefaultRouter()
tender.register(r"companies", CompanyViewSet)
tender.register(r"cvs", CVViewSet)
tender.register(r"departments", DepartmentViewSet)
tender.register(r"tenders", TenderViewSet)
tender.register(r"tender_categories", TenderCategoryViewSet)



urlpatterns = [
    path("api/", include(tender.urls)),
    path('api/login/', LoginView.as_view(), name='login'),
    path('api/register/', RegisterView.as_view(), name='register'),
    
]

 
