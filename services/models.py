from django.db import models
from django.core.exceptions import ValidationError
from datetime import timedelta

# Create your models here.





class Company(models.Model):
    company_id = models.AutoField(primary_key=True)
    company_name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'companies'

class Department(models.Model):
    department_id = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=50)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'departments'

class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=15)
    address = models.CharField(max_length=255)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        
class TenderCategory(models.Model):
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tender_categories'
        verbose_name_plural = 'tender_categories'

    def __str__(self):
        return self.name


class TenderTimeline(models.Model):
    timeline_id = models.AutoField(primary_key=True)
    tender = models.OneToOneField('Tender', on_delete=models.CASCADE, related_name='timeline')
    submission_start = models.DateTimeField()
    submission_end = models.DateTimeField()
    evaluation_start = models.DateTimeField()
    evaluation_end = models.DateTimeField()
    award_date = models.DateTimeField()
    project_start_date = models.DateTimeField()
    project_end_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tender_timelines'

    def clean(self):
        if self.submission_start and self.submission_end and self.submission_start > self.submission_end:
            raise ValidationError('Submission start date must be before end date')
        if self.evaluation_start and self.evaluation_end and self.evaluation_start > self.evaluation_end:
            raise ValidationError('Evaluation start date must be before end date')
        if self.project_start_date and self.project_end_date and self.project_start_date > self.project_end_date:
            raise ValidationError('Project start date must be before end date')
        
class Tender(models.Model):
    TENDER_STATUS = [
        ('draft', 'Draft'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('submitted', 'Submitted'),
        ('awarded', 'Awarded'),
        ('closed', 'Closed'),
    ]

    tender_id = models.AutoField(primary_key=True)
    tender_name = models.CharField(max_length=100)
    description = models.TextField()
    reference_number = models.CharField(max_length=50, unique=True)
    budget = models.DecimalField(max_digits=15, decimal_places=2)
    deadline = models.DateTimeField()
    status = models.CharField(max_length=20, choices=TENDER_STATUS, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenders_created')
    assigned_to = models.ManyToManyField(User, related_name='assigned_tenders')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    category = models.ForeignKey(TenderCategory, on_delete=models.SET_NULL, null=True)
    required_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenders'

    def __str__(self):
        return f"{self.reference_number} - {self.tender_name}"

    def save(self, *args, **kwargs):
        # First save the tender
        super().save(*args, **kwargs)
        
        # Auto-assign users based on department
        if self.required_department:
            potential_users = User.objects.filter(
                department=self.required_department,
                cv__isnull=False,
                cv__is_active=True
            )
            for user in potential_users:
                self.assigned_to.add(user)

    def get_timeline(self):
        """Get or create a timeline for the tender"""
        timeline, created = TenderTimeline.objects.get_or_create(
            tender=self,
            defaults={
                'submission_start': self.created_at,
                'submission_end': self.deadline,
                'evaluation_start': self.deadline + timedelta(days=1),
                'evaluation_end': self.deadline + timedelta(days=14),
                'award_date': self.deadline + timedelta(days=21),
                'project_start_date': self.deadline + timedelta(days=30),
                'project_end_date': self.deadline + timedelta(days=90),
            }
        )
        return timeline 
    
def document_upload_path(instance, filename):
    return f"uploads/documents/{instance.document_type}/{filename}"

class Document(models.Model):
    DOCUMENT_TYPES = [
        ('notice', 'Tender Notice'),
        ('spec', 'Specification Document'),
        ('bid', 'Bid Document'),
        ('contract', 'Contract'),
        ('other', 'Other'),
    ]

    document_id = models.AutoField(primary_key=True)
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='documents')
    uploader = models.ForeignKey(User, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to=document_upload_path) 
    description = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'documents'

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.tender.tender_name}"
    
class Approval(models.Model):
    APPROVAL_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    approval_id = models.AutoField(primary_key=True)
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='approvals')
    approver = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=APPROVAL_STATUS, default='pending')
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'approvals'

    def __str__(self):
        return f"{self.tender} - {self.approver}"
    
class AuditLog(models.Model):
    ACTION_TYPES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('approve', 'Approve'),
        ('submit', 'Submit'),
    ]

    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    target_model = models.CharField(max_length=50)  # e.g., "Tender", "Document"
    target_id = models.IntegerField()  # ID of the affected object
    details = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'

    def __str__(self):
        return f"{self.user} - {self.action} {self.target_model}"
    
class CV(models.Model):
    cv_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cv')
    file = models.FileField(upload_to='uploads/cvs/')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cvs'

    def __str__(self):
        return f"CV - {self.user.first_name} {self.user.last_name}"
    
# models.py (Token model)

class Token(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'tokens'
