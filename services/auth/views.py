import jwt
import datetime
from django.conf import settings
from django.utils.timezone import now
from django.contrib.auth.hashers import check_password, make_password
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import AuthenticationFailed
from django.shortcuts import redirect
from ..models import User, Token
from .serializers import RegisterSerializer, LoginSerializer

# Role-based redirection URLs (Temporary placeholders)
ROLE_REDIRECT_URLS = {
    'Admin': '/admin_dashboard/',
    'Manager': '/manager_dashboard/',
    'Employee': '/employee_dashboard/',
}

# Utility function to generate JWT token
def generate_token(user):
    expiration_time = now() + datetime.timedelta(days=7)  # Token expires in 1 hour
    payload = {
        'user_id': user.user_id,
        'email': user.email,
        'role': user.role,
        'exp': expiration_time.timestamp()
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    Token.objects.create(user=user, token=token, expires_at=expiration_time)
    return token

# Register view
class RegisterView(APIView):
    def post(self, request):
        try:
            serializer = RegisterSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                activation_expiry = now() + datetime.timedelta(days=7)
                Token.objects.create(user=user, token='ACTIVATION_TOKEN', expires_at=activation_expiry)
                return Response({'message': 'User registered successfully', 'email': user.email, 'role': user.role}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Login view
class LoginView(APIView):
    def post(self, request):
        try:
            serializer = LoginSerializer(data=request.data)
            if serializer.is_valid():
                email = serializer.validated_data['email']
                password = serializer.validated_data['password']
                user = User.objects.filter(email=email).first()
                if not user or not check_password(password, user.password):
                    raise AuthenticationFailed('Invalid username or password')
                token = generate_token(user)
                print(f'Token: {token}')
                redirect_url = ROLE_REDIRECT_URLS.get(user.role, '/default_dashboard/')
                return Response({'token': token, 'redirect_url': redirect_url}, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except AuthenticationFailed as e:
            return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Token cleanup function
def delete_expired_tokens():
    Token.objects.filter(expires_at__lt=now()).delete()