from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response 
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
from ..models import Tender, Document, Approval, ChecklistItem, User, TenderManagerAssignment
from .serializers import (
    TenderSerializer, TenderDocumentSerializer, 
    ChecklistItemSerializer, TenderTimelineSerializer,
)
from .utils import TenderProcessManager, check_user_permission, generate_reference_number, create_audit_log
from django.shortcuts import get_object_or_404

class TenderViewSet(viewsets.ModelViewSet):
    serializer_class = TenderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter tenders based on user role"""
        user = self.request.user
        
        if user.role == 'superuser':
            queryset = Tender.objects.all()
        elif user.role == 'manager':
            queryset = Tender.objects.filter(
                Q(assigned_to=user) |
                Q(required_department=user.department)
            ).distinct()
        elif user.role == 'bd_team':
            queryset = Tender.objects.filter(created_by=user)
        else:
            queryset = Tender.objects.none()
            
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
        """Only BD team can create tenders"""
        if not check_user_permission(request.user, 'bd_team'):
            return Response({
                'message': 'Only BD team members can create tenders',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user': request.user.email
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            tender = serializer.save(
                created_by=request.user,
                reference_number=generate_reference_number(),
                status='draft'
            )
            
            create_audit_log(
                user=request.user,
                action='create',
                target_model='Tender',
                target_id=tender.tender_id,
                details=f"Tender created by {request.user.email}"
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

    @action(detail=True, methods=['get'])
    def view_details(self, request, pk=None):
        """View tender details including documents and checklist"""
        tender = self.get_object()
        
        return Response({
            'tender': TenderSerializer(tender).data,
            'documents': TenderDocumentSerializer(tender.documents.all(), many=True).data,
            'checklist': ChecklistItemSerializer(tender.checklist_items.all(), many=True).data,
            'timeline': TenderTimelineSerializer(tender.get_timeline()).data,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    @action(detail=True, methods=['post'])
    def upload_document(self, request, pk=None):
        """Upload tender document"""
        if not check_user_permission(request.user, 'bd_team'):
            return Response({
                'message': 'Only BD team can upload documents',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_403_FORBIDDEN)

        tender = self.get_object()
        serializer = TenderDocumentSerializer(data=request.data)
        
        if serializer.is_valid():
            document = serializer.save(
                tender=tender,
                uploader=request.user
            )
            
            create_audit_log(
                user=request.user,
                action='upload',
                target_model='Document',
                target_id=document.document_id,
                details=f"Document uploaded by {request.user.email}"
            )
            
            return Response({
                'message': 'Document uploaded successfully',
                'data': serializer.data,
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def submit_to_superuser(self, request, pk=None):
        """BD Team submits tender for superuser review"""
        if not check_user_permission(request.user, 'bd_team'):
            return Response({
                'message': 'Only BD team can submit tenders',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_403_FORBIDDEN)

        tender = self.get_object()
        
        if not tender.documents.filter(document_type='spec').exists():
            return Response({
                'message': 'Initial tender document is required',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tender.status = 'pending_superuser_approval'
        tender.save()
        
        create_audit_log(
            user=request.user,
            action='submit',
            target_model='Tender',
            target_id=tender.tender_id,
            details=f"Tender submitted for superuser review by {request.user.email}"
        )
        
        return Response({
            'message': 'Tender submitted for superuser approval',
            'data': TenderSerializer(tender).data,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    @action(detail=True, methods=['post'])
    def superuser_review(self, request, pk=None):
        """Superuser reviews and either approves or rejects the tender"""
        current_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if not check_user_permission(request.user, 'superuser'):
            return Response({
                'message': 'Only superusers can review tenders',
                'timestamp': current_time
            }, status=status.HTTP_403_FORBIDDEN)

        tender = self.get_object()
        decision = request.data.get('decision')
        comments = request.data.get('comments')
        
        if tender.status != 'pending_superuser_approval':
            return Response({
                'message': 'Tender is not pending superuser approval',
                'timestamp': current_time
            }, status=status.HTTP_400_BAD_REQUEST)

        if decision == 'approve':
            manager_id = request.data.get('manager_id')
            if not manager_id:
                return Response({
                    'message': 'Manager ID is required for approval',
                    'timestamp': current_time
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                manager = User.objects.get(user_id=manager_id, role='manager')
            except User.DoesNotExist:
                return Response({
                    'message': 'Invalid manager ID',
                    'timestamp': current_time
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # First save the tender status
            tender.status = 'in_progress'
            tender.save()

            # Deactivate existing assignments
            TenderManagerAssignment.objects.filter(tender=tender).update(is_active=False)
            
            try:
                # Create new manager assignment using the through model
                TenderManagerAssignment.objects.create(
                    tender=tender,
                    manager=manager,
                    assigned_by=request.user,
                    is_active=True
                )
                
                # Add manager to the many-to-many field
                tender.assigned_to.add(manager)
                
                response_data = {
                    'tender_id': tender.tender_id,
                    'status': 'in_progress',
                    'assigned_manager': {
                        'id': manager.user_id,  # Changed from id to user_id
                        'email': manager.email,
                        'name': f"{manager.first_name} {manager.last_name}",
                        'assigned_at': current_time,
                        'assigned_by': {
                            'id': request.user.user_id,  # Changed from id to user_id
                            'email': request.user.email,
                            'name': f"{request.user.first_name} {request.user.last_name}"
                        }
                    },
                    'updated_at': current_time
                }
                message = 'Tender approved and manager assigned'
                
            except Exception as e:
                # If assignment fails, revert tender status
                tender.status = 'pending_superuser_approval'
                tender.save()
                return Response({
                    'message': f'Error assigning manager: {str(e)}',
                    'timestamp': current_time
                }, status=status.HTTP_400_BAD_REQUEST)
                
        elif decision == 'reject':
            tender.status = 'rejected'
            tender.save()
            
            response_data = {
                'tender_id': tender.tender_id,
                'status': 'rejected',
                'rejection_reason': comments,
                'rejected_by': {
                    'id': request.user.user_id,  # Changed from id to user_id
                    'email': request.user.email,
                    'name': f"{request.user.first_name} {request.user.last_name}"
                },
                'rejected_at': current_time
            }
            message = 'Tender rejected'
        else:
            return Response({
                'message': 'Invalid decision. Must be either "approve" or "reject"',
                'timestamp': current_time
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create approval/rejection record
        Approval.objects.create(
            tender=tender,
            approver=request.user,
            status=decision,
            comments=comments
        )
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action=f'tender_{decision}ed',
            target_model='Tender',
            target_id=tender.tender_id,
            details=f"Tender {decision}ed by {request.user.email}. Comments: {comments}"
        )
        
        return Response({
            'message': message,
            'data': response_data,
            'timestamp': current_time,
            'user': request.user.email
        })
    
    @action(detail=True, methods=['post'])
    def create_checklist(self, request, pk=None):
        """Manager creates checklist"""
        if not check_user_permission(request.user, 'manager'):
            return Response({
                'message': 'Only managers can create checklists',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_403_FORBIDDEN)

        tender = self.get_object()
        items = request.data.get('items', [])
        checklist_items = []
        
        for item in items:
            serializer = ChecklistItemSerializer(data=item)
            if serializer.is_valid():
                checklist_items.append(ChecklistItem(
                    tender=tender,
                    created_by=request.user,
                    **serializer.validated_data
                ))
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        ChecklistItem.objects.bulk_create(checklist_items)
        
        create_audit_log(
            user=request.user,
            action='create',
            target_model='Checklist',
            target_id=tender.tender_id,
            details=f"Checklist created by manager"
        )
        
        return Response({
            'message': 'Checklist created successfully',
            'data': ChecklistItemSerializer(checklist_items, many=True).data,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    @action(detail=True, methods=['post'])
    def review_document(self, request, pk=None):
        """Manager reviews document"""
        if not check_user_permission(request.user, 'manager'):
            return Response({
                'message': 'Only managers can review documents',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_403_FORBIDDEN)

        checklist_item = get_object_or_404(
            ChecklistItem, 
            pk=request.data.get('checklist_item_id')
        )
        
        decision = request.data.get('decision')
        comments = request.data.get('comments')
        
        if decision == 'approve':
            checklist_item.status = 'completed'
        else:
            checklist_item.status = 'revision_needed'
            
        checklist_item.comments = comments
        checklist_item.save()
        
        create_audit_log(
            user=request.user,
            action='review',
            target_model='Document',
            target_id=checklist_item.checklist_id,
            details=f"Document {decision}d by manager"
        )
        
        return Response({
            'message': f'Document {decision}d',
            'data': ChecklistItemSerializer(checklist_item).data,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    @action(detail=True, methods=['post'])
    def submit_to_final_review(self, request, pk=None):
        """Manager submits completed tender"""
        if not check_user_permission(request.user, 'manager'):
            return Response({
                'message': 'Only managers can submit for final review',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_403_FORBIDDEN)

        tender = self.get_object()
        
        if tender.checklist_items.exclude(status='completed').exists():
            return Response({
                'message': 'All checklist items must be completed',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tender.status = 'pending_final_approval'
        tender.save()
        
        create_audit_log(
            user=request.user,
            action='submit',
            target_model='Tender',
            target_id=tender.tender_id,
            details=f"Tender submitted for final approval by manager"
        )
        
        return Response({
            'message': 'Tender submitted for final approval',
            'data': TenderSerializer(tender).data,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """List all documents for a tender"""
        tender = self.get_object()
        documents = tender.documents.all()
        
        return Response({
            'message': 'Documents retrieved successfully',
            'data': {
                'documents': TenderDocumentSerializer(documents, many=True).data,
                'total_documents': documents.count()
            },
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    @action(detail=True, url_path='documents/(?P<document_id>[^/.]+)', methods=['get'])
    def view_document(self, request, pk=None, document_id=None):
        """View specific document details"""
        tender = self.get_object()
        document = get_object_or_404(tender.documents, document_id=document_id)
        
        return Response({
            'message': 'Document details retrieved successfully',
            'data': TenderDocumentSerializer(document).data,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    @action(detail=True, url_path='documents/(?P<document_id>[^/.]+)/download', methods=['get'])
    def download_document(self, request, pk=None, document_id=None):
        """Download document file"""
        tender = self.get_object()
        document = get_object_or_404(tender.documents, document_id=document_id)
        from django.http import FileResponse
        return FileResponse(
            document.file.open(),
            as_attachment=True,
            filename=document.file_name
        )

    @action(detail=True, url_path='checklist/(?P<checklist_id>[^/.]+)/documents', methods=['get'])
    def checklist_documents(self, request, pk=None, checklist_id=None):
        """View documents for a specific checklist item"""
        tender = self.get_object()
        checklist_item = get_object_or_404(tender.checklist_items, checklist_id=checklist_id)
        documents = checklist_item.documents.all()
        
        return Response({
            'message': 'Checklist item documents retrieved successfully',
            'data': {
                'checklist_item': ChecklistItemSerializer(checklist_item).data,
                'documents': TenderDocumentSerializer(documents, many=True).data
            },
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    @action(detail=True, url_path='documents/(?P<document_id>[^/.]+)/history', methods=['get'])
    def document_history(self, request, pk=None, document_id=None):
        """View document version history"""
        tender = self.get_object()
        document = get_object_or_404(tender.documents, document_id=document_id)
        versions = document.versions.all().order_by('-created_at')
        
        return Response({
            'message': 'Document history retrieved successfully',
            'data': {
                'document_id': document.document_id,
                'versions': TenderDocumentVersionSerializer(versions, many=True).data
            },
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    @action(detail=False, methods=['get'])
    def assigned_tenders(self, request):
        """Get tenders assigned to the requesting manager"""
        if not check_user_permission(request.user, 'manager'):
            return Response({
                'message': 'Only managers can view assigned tenders',
                'timestamp': "2025-02-07 21:38:27",
                'user': request.user.email
            }, status=status.HTTP_403_FORBIDDEN)

        # Get tenders assigned to the manager
        tenders = Tender.objects.filter(assigned_to=request.user).order_by('-created_at')
        
        # Apply filters if provided
        status_filter = request.query_params.get('status', None)
        if status_filter:
            tenders = tenders.filter(status=status_filter)

        # You can add more filters based on query parameters
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        if date_from:
            tenders = tenders.filter(created_at__gte=date_from)
        if date_to:
            tenders = tenders.filter(created_at__lte=date_to)

        return Response({
            'message': 'Assigned tenders retrieved successfully',
            'data': {
                'total_tenders': tenders.count(),
                'tenders': TenderSerializer(tenders, many=True).data
            },
            'timestamp': "2025-02-07 21:38:27",
            'manager': request.user.email
        })