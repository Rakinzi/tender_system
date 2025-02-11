from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response 
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
from ..models import Tender, Document, Approval, ChecklistItem, User, TenderManagerAssignment, AuditLog
from .serializers import (
    TenderSerializer, TenderDocumentSerializer, 
    ChecklistItemSerializer, TenderTimelineSerializer,
)
from .utils import TenderProcessManager, check_user_permission, generate_reference_number, create_audit_log
from django.shortcuts import get_object_or_404

class TenderViewSet(viewsets.ModelViewSet):
    serializer_class = TenderSerializer
    # permission_classes = [IsAuthenticated]
    
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
        current_time = timezone.now()
        
        if not check_user_permission(request.user, 'manager'):
            return Response({
                'message': 'Only managers can create checklists',
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_403_FORBIDDEN)

        tender = self.get_object()
        items = request.data.get('items', [])
        created_items = []
        
        try:
            for item in items:
                # Set default assignee if not provided
                if 'assigned_to' not in item:
                    item['assigned_to'] = tender.created_by.user_id
                    
                serializer = ChecklistItemSerializer(data=item)
                if serializer.is_valid():
                    checklist_item = ChecklistItem.objects.create(
                        tender=tender,
                        created_by=request.user,
                        **serializer.validated_data
                    )
                    created_items.append(checklist_item)
                else:
                    return Response({
                        'message': 'Invalid checklist item data',
                        'errors': serializer.errors,
                        'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            create_audit_log(
                user=request.user,
                action='create',
                target_model='Checklist',
                target_id=tender.tender_id,
                details=f"Checklist items created by {request.user.email}"
            )
            
            return Response({
                'message': 'Checklist created successfully',
                'data': {
                    'items': ChecklistItemSerializer(created_items, many=True).data,
                    'total_items': len(created_items)
                },
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'user': request.user.email
            })
            
        except Exception as e:
            return Response({
                'message': f'Error creating checklist items: {str(e)}',
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_400_BAD_REQUEST)

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
        
    @action(detail=True, methods=['get'])
    def review_details(self, request, pk=None):
        """Get tender details including review history and approvals"""
        try:
            tender = self.get_object()
            
            # Get active manager assignment
            manager_assignment = TenderManagerAssignment.objects.filter(
                tender=tender,
                is_active=True
            ).select_related('manager', 'assigned_by').first()
            
            # Get all approvals
            approvals = tender.approvals.all().order_by('-created_at').select_related('approver')
            
            # Get audit logs
            audit_logs = AuditLog.objects.filter(
                target_model='Tender',
                target_id=tender.tender_id
            ).select_related('user').order_by('-timestamp')
            
            # Get checklist items
            checklist_items = tender.checklist_items.all().select_related('assigned_to', 'created_by')
            
            response_data = {
                'tender_id': tender.tender_id,
                'tender_name': tender.tender_name,
                'reference_number': tender.reference_number,
                'status': tender.status,
                'description': tender.description,
                'budget': str(tender.budget),
                'deadline': tender.deadline.strftime('%Y-%m-%d %H:%M:%S'),
                'created_by': {  # Added created_by information
                    'id': tender.created_by.user_id,
                    'name': f"{tender.created_by.first_name} {tender.created_by.last_name}",
                    'email': tender.created_by.email,
                    'role': tender.created_by.role
                },
                'approvals': [{
                    'status': approval.status,
                    'comments': approval.comments,
                    'approved_by': {
                        'id': approval.approver.user_id,
                        'name': f"{approval.approver.first_name} {approval.approver.last_name}",
                        'email': approval.approver.email,
                        'role': approval.approver.role
                    },
                    'created_at': approval.created_at.strftime('%Y-%m-%d %H:%M:%S')
                } for approval in approvals],
                'assigned_manager': {
                    'id': manager_assignment.manager.user_id,
                    'name': f"{manager_assignment.manager.first_name} {manager_assignment.manager.last_name}",
                    'email': manager_assignment.manager.email,
                    'assigned_at': manager_assignment.assigned_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'assigned_by': {
                        'id': manager_assignment.assigned_by.user_id,
                        'name': f"{manager_assignment.assigned_by.first_name} {manager_assignment.assigned_by.last_name}",
                        'email': manager_assignment.assigned_by.email
                    }
                } if manager_assignment else None,
                'checklist_items': [{
                    'checklist_id': item.checklist_id,
                    'name': item.name,
                    'description': item.description,
                    'status': item.status,
                    'deadline': item.deadline.strftime('%Y-%m-%d %H:%M:%S'),
                    'completed_at': item.completed_at.strftime('%Y-%m-%d %H:%M:%S') if item.completed_at else None,
                    'assigned_to': {
                        'id': item.assigned_to.user_id,
                        'name': f"{item.assigned_to.first_name} {item.assigned_to.last_name}",
                        'email': item.assigned_to.email
                    },
                    'comments': item.comments
                } for item in checklist_items],
                'review_history': [{
                    'action': log.action,
                    'details': log.details,
                    'user': {
                        'id': log.user.user_id,
                        'name': f"{log.user.first_name} {log.user.last_name}",
                        'email': log.user.email,
                        'role': log.user.role
                    },
                    'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                } for log in audit_logs]
            }
            
            return Response({
                'message': 'Tender review details retrieved successfully',
                'data': response_data,
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user': request.user.email
            })
            
        except Exception as e:
            return Response({
                'message': f'Error retrieving tender review details: {str(e)}',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_400_BAD_REQUEST)
            
# Add this to your TenderViewSet class
    @action(detail=True, url_path='checklist/(?P<checklist_id>[^/.]+)/complete', methods=['post'])
    def complete_checklist_item(self, request, pk=None, checklist_id=None):
        """Mark a checklist item as complete"""
        current_time = "2025-02-11 09:45:40"
        
        try:
            tender = self.get_object()
            checklist_item = get_object_or_404(
                ChecklistItem, 
                checklist_id=checklist_id,
                tender=tender
            )
            
            # Check if user is either the assigned person or the manager
            if request.user != checklist_item.assigned_to and not check_user_permission(request.user, 'manager'):
                return Response({
                    'message': 'You are not authorized to complete this checklist item',
                    'timestamp': current_time,
                    'user': request.user.email
                }, status=status.HTTP_403_FORBIDDEN)
            
            comments = request.data.get('comments', '')
            
            # Update checklist item
            checklist_item.status = 'completed'
            checklist_item.completed_at = timezone.now()
            checklist_item.comments = comments
            checklist_item.save()
            
            # Create audit log
            create_audit_log(
                user=request.user,
                action='complete_checklist',
                target_model='ChecklistItem',
                target_id=checklist_item.checklist_id,
                details=f"Checklist item '{checklist_item.name}' marked as complete by {request.user.email}. Comments: {comments}"
            )
            
            return Response({
                'message': 'Checklist item marked as complete',
                'data': {
                    'checklist_id': checklist_item.checklist_id,
                    'name': checklist_item.name,
                    'status': checklist_item.status,
                    'completed_at': checklist_item.completed_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'completed_by': {
                        'id': request.user.user_id,
                        'name': f"{request.user.first_name} {request.user.last_name}",
                        'email': request.user.email
                    },
                    'comments': checklist_item.comments
                },
                'timestamp': current_time,
                'user': request.user.email
            })
            
        except Exception as e:
            return Response({
                'message': f'Error completing checklist item: {str(e)}',
                'timestamp': current_time
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, url_path='checklist/(?P<checklist_id>[^/.]+)/undo', methods=['post'])
    def undo_checklist_completion(self, request, pk=None, checklist_id=None):
        """Undo completion of a checklist item"""
        current_time = "2025-02-11 09:49:44"
        
        try:
            tender = self.get_object()
            checklist_item = get_object_or_404(
                ChecklistItem, 
                checklist_id=checklist_id,
                tender=tender
            )
            
            # Check if user is either the assigned person or the manager
            if request.user != checklist_item.assigned_to and not check_user_permission(request.user, 'manager'):
                return Response({
                    'message': 'You are not authorized to modify this checklist item',
                    'timestamp': current_time,
                    'user': request.user.email
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check if item is actually completed
            if checklist_item.status != 'completed':
                return Response({
                    'message': 'Checklist item is not marked as complete',
                    'timestamp': current_time,
                    'user': request.user.email
                }, status=status.HTTP_400_BAD_REQUEST)
            
            reason = request.data.get('reason', '')
            
            # Update checklist item
            checklist_item.status = 'pending'
            checklist_item.completed_at = None
            checklist_item.comments = f"Completion undone. Reason: {reason}"
            checklist_item.save()
            
            # Create audit log
            create_audit_log(
                user=request.user,
                action='undo_checklist',
                target_model='ChecklistItem',
                target_id=checklist_item.checklist_id,
                details=f"Checklist item '{checklist_item.name}' completion undone by {request.user.email}. Reason: {reason}"
            )
            
            return Response({
                'message': 'Checklist item completion undone',
                'data': {
                    'checklist_id': checklist_item.checklist_id,
                    'name': checklist_item.name,
                    'status': checklist_item.status,
                    'undone_by': {
                        'id': request.user.user_id,
                        'name': f"{request.user.first_name} {request.user.last_name}",
                        'email': request.user.email
                    },
                    'reason': reason,
                    'timestamp': current_time
                },
                'timestamp': current_time,
                'user': request.user.email
            })
            
        except Exception as e:
            return Response({
                'message': f'Error undoing checklist completion: {str(e)}',
                'timestamp': current_time
            }, status=status.HTTP_400_BAD_REQUEST)
            
    @action(detail=True, url_path='checklist/(?P<checklist_id>[^/.]+)/review', methods=['post'])
    def review_checklist_item(self, request, pk=None, checklist_id=None):
        """Manager reviews a completed checklist item"""
        current_time = timezone.now()
        
        if not check_user_permission(request.user, 'manager'):
            return Response({
                'message': 'Only managers can review checklist items',
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            tender = self.get_object()
            checklist_item = get_object_or_404(
                ChecklistItem, 
                checklist_id=checklist_id,
                tender=tender
            )
            
            if checklist_item.status != 'pending_review':
                return Response({
                    'message': 'Checklist item is not pending review',
                    'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            decision = request.data.get('decision')
            review_comments = request.data.get('comments', '')
            
            if decision not in ['approve', 'reject']:
                return Response({
                    'message': 'Invalid decision. Must be either "approve" or "reject"',
                    'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Update checklist item based on manager's decision
            if decision == 'approve':
                checklist_item.status = 'completed'
                checklist_item.completed_at = current_time
                action_message = 'approved'
            else:
                checklist_item.status = 'revision_needed'
                checklist_item.completed_at = None
                action_message = 'rejected'
                
            checklist_item.review_comments = review_comments
            checklist_item.reviewed_by = request.user
            checklist_item.reviewed_at = current_time
            checklist_item.save()
            
            # Create audit log
            create_audit_log(
                user=request.user,
                action=f'checklist_review_{decision}',
                target_model='ChecklistItem',
                target_id=checklist_item.checklist_id,
                details=f"Checklist item '{checklist_item.name}' {action_message} by manager. Comments: {review_comments}"
            )
            
            return Response({
                'message': f'Checklist item review completed - {action_message}',
                'data': {
                    'checklist_id': checklist_item.checklist_id,
                    'name': checklist_item.name,
                    'status': checklist_item.status,
                    'submitted_by': {
                        'id': checklist_item.assigned_to.user_id,
                        'name': f"{checklist_item.assigned_to.first_name} {checklist_item.assigned_to.last_name}",
                        'email': checklist_item.assigned_to.email
                    },
                    'reviewed_by': {
                        'id': request.user.user_id,
                        'name': f"{request.user.first_name} {request.user.last_name}",
                        'email': request.user.email
                    },
                    'reviewed_at': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'decision': decision,
                    'review_comments': review_comments
                },
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
            })
            
        except Exception as e:
            return Response({
                'message': f'Error reviewing checklist item: {str(e)}',
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
            }, status=status.HTTP_400_BAD_REQUEST)
            
    @action(detail=True, methods=['get'], url_path='my-assigned-items', url_name='my_assigned_items')
    def my_assigned_items(self, request, pk=None):
        """Get checklist items assigned to the requesting user for a specific tender"""
        current_time = "2025-02-11 10:57:24"
        
        try:
            tender = self.get_object()
            
            # Remove reviewed_by from select_related since it's not a valid relationship
            checklist_items = ChecklistItem.objects.filter(
                tender=tender,
                assigned_to=request.user
            ).select_related(
                'tender',
                'assigned_to',
                'created_by'
            ).order_by('-deadline')
            
            # Apply status filter if provided
            status_filter = request.query_params.get('status', None)
            if status_filter:
                checklist_items = checklist_items.filter(status=status_filter)
            
            response_data = []
            for item in checklist_items:
                item_data = {
                    'checklist_id': item.checklist_id,
                    'name': item.name,
                    'description': item.description,
                    'status': item.status,
                    'deadline': item.deadline.strftime('%Y-%m-%d %H:%M:%S'),
                    'created_by': {
                        'id': item.created_by.user_id,
                        'name': f"{item.created_by.first_name} {item.created_by.last_name}",
                        'email': item.created_by.email,
                        'role': item.created_by.role
                    },
                    'completed_at': item.completed_at.strftime('%Y-%m-%d %H:%M:%S') if item.completed_at else None,
                    'comments': item.comments,
                }
                
                # Only include review information if review fields exist in your model
                if hasattr(item, 'review_comments'):
                    item_data['review_comments'] = item.review_comments
                
                response_data.append(item_data)
            
            # Group items by status for summary
            status_summary = {}
            for item in checklist_items:
                if item.status not in status_summary:
                    status_summary[item.status] = 0
                status_summary[item.status] += 1
            
            return Response({
                'message': 'Assigned checklist items retrieved successfully',
                'data': {
                    'tender_id': tender.tender_id,
                    'tender_name': tender.tender_name,
                    'reference_number': tender.reference_number,
                    'total_items': len(response_data),
                    'status_summary': status_summary,
                    'items': response_data
                },
                'timestamp': current_time,
                'user': request.user.email
            })
            
        except Exception as e:
            return Response({
                'message': f'Error retrieving checklist items: {str(e)}',
                'timestamp': current_time
            }, status=status.HTTP_400_BAD_REQUEST)