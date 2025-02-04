from django.urls import path, include
from rest_framework.routers import DefaultRouter
from services.auth.views import (
    CustomTokenObtainPairView,
    register,
    verify_email,
    request_password_reset,
    change_password
)
from rest_framework_simplejwt.views import TokenRefreshView
from services.company.views import CompanyViewSet
from services.department.views import DepartmentViewSet
from services.tender.views import TenderViewSet

tender_router = DefaultRouter()
tender_router.register(r'companies', CompanyViewSet, basename='company')
tender_router.register(r'departments', DepartmentViewSet, basename='department')
tender_router.register(r'tenders', TenderViewSet, basename='tender')



urlpatterns = [
    path('api/auth/register/', register, name='register'),
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/verify-email/<str:token>/', verify_email, name='verify-email'),
    path('api/auth/request-password-reset/', request_password_reset, name='request-password-reset'),
    path('api/auth/change-password/', change_password, name='change-password'),
    
    path('api/', include(tender_router.urls)),
]

 
