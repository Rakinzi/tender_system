from django.db import models
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

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
        

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    user_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=15)
    address = models.CharField(max_length=255)
    department = models.ForeignKey('Department', on_delete=models.CASCADE)
    company = models.ForeignKey('Company', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    email_verification_token = models.CharField(max_length=255, null=True, blank=True)

    # Add related_name to avoid clashes
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'users'
        
    @property
    def id(self):
        return self.user_id
        
                   
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
    submission_start = models.DateTimeField(null=True, blank=True)
    submission_end = models.DateTimeField(null=True, blank=True)
    evaluation_start = models.DateTimeField(null=True, blank=True)
    evaluation_end = models.DateTimeField(null=True, blank=True)
    award_date = models.DateTimeField(null=True, blank=True)
    project_start_date = models.DateTimeField(null=True, blank=True)
    project_end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tender_timelines'

    def update_dates_based_on_status(self, status):
        """Update timeline dates based on tender status"""
        now = timezone.now()
        
        if status == 'draft':
            self.submission_start = now
        elif status == 'in_review':
            if not self.submission_end:
                self.submission_end = now
            if not self.evaluation_start:
                self.evaluation_start = now
        elif status == 'approved':
            if not self.evaluation_end:
                self.evaluation_end = now
        elif status == 'awarded':
            if not self.award_date:
                self.award_date = now
            if not self.project_start_date:
                self.project_start_date = now + timedelta(days=30)
        elif status == 'closed':
            if not self.project_end_date:
                self.project_end_date = now
        
        self.save()
         
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
        super().save(*args, **kwargs)
        
        # Auto-assign managers from required department
        if self.required_department:
            managers = User.objects.filter(
                department=self.required_department,
                role='manager'
            )
            self.assigned_to.set(managers)

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

