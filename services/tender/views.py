from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from ..models import Tender, Document, Approval 
from .serializers import TenderSerializer, TenderDocumentSerializer
from .utils import TenderProcessManager, check_user_permission
from django.core.exceptions import ValidationError

class TenderViewSet(viewsets.ModelViewSet):
    serializer_class = TenderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter tenders based on user's role and department"""
        user = self.request.user
        if user.role == 'admin':
            return Tender.objects.all()
        elif user.role == 'manager':
            return Tender.objects.filter(required_department=user.department)
        else:
            return Tender.objects.filter(
                required_department=user.department,
                created_by=user
            )

    def create(self, request, *args, **kwargs):
        """Create a new tender"""
        if not check_user_permission(request.user, 'manager'):
            return Response({
                'message': 'Not authorized to create tenders'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            tender = TenderProcessManager.initiate_tender(
                serializer.save(),
                request.user
            )
            return Response({
                'message': 'Tender created successfully',
                'data': TenderSerializer(tender).data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def submit_for_review(self, request, pk=None):
        """Submit tender for review"""
        tender = self.get_object()
        
        try:
            tender = TenderProcessManager.submit_for_review(tender, request.user)
            return Response({
                'message': 'Tender submitted for review',
                'data': TenderSerializer(tender).data
            })
        except ValueError as e:
            return Response({
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve tender"""
        tender = self.get_object()
        comments = request.data.get('comments')
        
        try:
            tender = TenderProcessManager.approve_tender(
                tender, 
                request.user,
                comments
            )
            return Response({
                'message': 'Tender approved successfully',
                'data': TenderSerializer(tender).data
            })
        except ValueError as e:
            return Response({
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def upload_document(self, request, pk=None):
        """Upload tender document"""
        tender = self.get_object()
        
        serializer = TenderDocumentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                tender=tender,
                uploader=request.user
            )
            return Response({
                'message': 'Document uploaded successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)