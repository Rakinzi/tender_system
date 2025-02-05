from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
from ..models import Tender, Document, Approval 
from .serializers import TenderSerializer, TenderDocumentSerializer
from .utils import TenderProcessManager, check_user_permission, generate_reference_number
from django.core.exceptions import ValidationError

class TenderViewSet(viewsets.ModelViewSet):
    serializer_class = TenderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter tenders based on user's role and department"""
        user = self.request.user
        
        # Base queryset based on user role
        if user.role == 'admin':
            queryset = Tender.objects.all()
        elif user.role == 'manager':
            queryset = Tender.objects.filter(required_department=user.department)
        else:
            queryset = Tender.objects.filter(
                required_department=user.department,
                created_by=user
            )
        # Apply filters from query parameters
        status = self.request.query_params.get('status', None)
        category = self.request.query_params.get('category', None)
        search = self.request.query_params.get('search', None)
        
        if status:
            queryset = queryset.filter(status=status)
        if category:
            queryset = queryset.filter(category=category)
        if search:
            queryset = queryset.filter(
                Q(tender_name__icontains=search) |
                Q(description__icontains=search) |
                Q(reference_number__icontains=search)
            )
            
        return queryset.order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        """Create a new tender"""
        if not check_user_permission(request.user, 'manager'):
            return Response({
                'message': 'Not authorized to create tenders',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user': request.user.email
            }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data.copy()
        data['created_by'] = request.user.user_id
        
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            reference_number = generate_reference_number()
            
            tender = serializer.save(
                created_by=request.user,
                reference_number=reference_number,
                status='draft'
            )
            
            return Response({
                'message': 'Tender created successfully',
                'data': TenderSerializer(tender).data,
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'created_by': request.user.email
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'message': 'Invalid data',
            'errors': serializer.errors,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        tender = self.get_object()
        
        # Only creator or manager can update tender
        if not (request.user == tender.created_by or check_user_permission(request.user, 'manager')):
            return Response({
                'message': 'Not authorized to update this tender',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user': request.user.email
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Cannot update if not in draft status
        if tender.status != 'draft':
            return Response({
                'message': 'Can only update tenders in draft status',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_400_BAD_REQUEST)
            
        serializer = self.get_serializer(tender, data=request.data, partial=True)
        if serializer.is_valid():
            tender = serializer.save()
            return Response({
                'message': 'Tender updated successfully',
                'data': TenderSerializer(tender).data,
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'updated_by': request.user.email
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        tender = self.get_object()
        
        # Only admin or creator can delete tender
        if not (request.user == tender.created_by or check_user_permission(request.user, 'admin')):
            return Response({
                'message': 'Not authorized to delete this tender',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user': request.user.email
            }, status=status.HTTP_403_FORBIDDEN)
            
        # Cannot delete if not in draft status
        if tender.status != 'draft':
            return Response({
                'message': 'Can only delete tenders in draft status',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_400_BAD_REQUEST)
            
        tender_name = tender.tender_name
        self.perform_destroy(tender)
        return Response({
            'message': f'Tender "{tender_name}" deleted successfully',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'deleted_by': request.user.email
        }, status=status.HTTP_200_OK)
    
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
    
    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """Get tender timeline"""
        tender = self.get_object()
        timeline = tender.get_timeline()
        return Response(TenderTimelineSerializer(timeline).data)
    
    @action(detail=True, methods=['post'])
    def award(self, request, pk=None):
        """Award tender"""
        tender = self.get_object()
        comments = request.data.get('comments')
        
        try:
            tender = TenderProcessManager.award_tender(
                tender, 
                request.user,
                comments
            )
            return Response({
                'message': 'Tender awarded successfully',
                'data': TenderSerializer(tender).data
            })
        except ValueError as e:
            return Response({
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close tender"""
        tender = self.get_object()
        comments = request.data.get('comments')
        
        try:
            tender = TenderProcessManager.close_tender(
                tender, 
                request.user,
                comments
            )
            return Response({
                'message': 'Tender closed successfully',
                'data': TenderSerializer(tender).data
            })
        except ValueError as e:
            return Response({
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)