from ..models import AuditLog, User, Approval

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
