from django.utils import timezone
from ..models import AuditLog, User, Approval
from datetime import datetime
import uuid

def generate_reference_number():
    """Generate a unique reference number for tenders"""
    timestamp = datetime.now().strftime('%Y%m%d')
    unique_id = str(uuid.uuid4().hex)[:6].upper()
    return f"BTD-{timestamp}-{unique_id}"

def create_audit_log(user, action, target_model, target_id, details=None):
    """Create an audit log entry"""
    AuditLog.objects.create(
        user=user,
        action=action,
        target_model=target_model,
        target_id=target_id,
        details=details
    )

def check_user_permission(user, required_role):
    """Check if user has required role"""
    return user.role == required_role

def validate_tender_status_transition(current_status, new_status):
    """Validate tender status transitions"""
    valid_transitions = {
        'draft': ['in_review'],
        'in_review': ['approved', 'draft'],
        'approved': ['submitted'],
        'submitted': ['awarded', 'closed'],
        'awarded': ['closed'],
        'closed': []
    }
    return new_status in valid_transitions.get(current_status, [])

class TenderProcessManager:
    @staticmethod
    def initiate_tender(tender, user):
        """Initialize a new tender"""
        tender.reference_number = generate_reference_number()
        tender.created_by = user
        tender.status = 'draft'
        tender.save()
        
        create_audit_log(
            user=user,
            action='create',
            target_model='Tender',
            target_id=tender.tender_id,
            details=f"Tender {tender.reference_number} created"
        )
        return tender

    @staticmethod
    def submit_for_review(tender, user):
        """Submit tender for review"""
        if not validate_tender_status_transition(tender.status, 'in_review'):
            raise ValueError("Invalid status transition")
        
        tender.status = 'in_review'
        tender.save()
        
        create_audit_log(
            user=user,
            action='submit',
            target_model='Tender',
            target_id=tender.tender_id,
            details=f"Tender {tender.reference_number} submitted for review"
        )
        return tender

    @staticmethod
    def approve_tender(tender, user, comments=None):
        """Approve tender"""
        if not check_user_permission(user, 'manager'):
            raise ValueError("User not authorized to approve tenders")
            
        if not validate_tender_status_transition(tender.status, 'approved'):
            raise ValueError("Invalid status transition")
        
        tender.status = 'approved'
        tender.save()
        
        # Create approval record
        Approval.objects.create(
            tender=tender,
            approver=user,
            status='approved',
            comments=comments
        )
        
        create_audit_log(
            user=user,
            action='approve',
            target_model='Tender',
            target_id=tender.tender_id,
            details=f"Tender {tender.reference_number} approved"
        )
        return tender