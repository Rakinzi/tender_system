from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from django.utils import timezone
from .serializers import RegisterSerializer, CustomTokenObtainPairSerializer
from .utils import generate_verification_token, send_verification_email, send_password_reset_email
from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        verification_token = generate_verification_token()
        user = serializer.save(
            email_verification_token=verification_token,
            is_active=False
        )
        send_verification_email(user, verification_token)
        
        return Response({
            "message": "Registration successful. Please check your email to verify your account.",
            "timestamp": timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
            "user": {
                "email": user.email,
                "full_name": f"{user.first_name} {user.last_name}"
            }
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, token):
    try:
        user = User.objects.get(email_verification_token=token, is_active=False)
        user.is_active = True
        user.email_verification_token = None
        user.save()
        return Response({
            "message": "Email verified successfully. You can now login.",
            "timestamp": timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
            "email": user.email
        })
    except User.DoesNotExist:
        return Response({
            "message": "Invalid or expired verification token.",
            "timestamp": timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    try:
        email = request.data.get('email')
        user = User.objects.get(email=email)
        token = generate_verification_token()
        user.password_reset_token = token
        user.save()
        send_password_reset_email(user, token)
        return Response({
            "message": "Password reset instructions have been sent to your email.",
            "timestamp": timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        })
    except User.DoesNotExist:
        return Response({
            "message": "User with this email does not exist.",
            "timestamp": timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not user.check_password(old_password):
        return Response({
            "message": "Current password is incorrect.",
            "timestamp": timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user.set_password(new_password)
    user.save()
    return Response({
        "message": "Password changed successfully.",
        "timestamp": timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    })