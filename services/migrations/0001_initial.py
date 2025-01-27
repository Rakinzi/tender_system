# Generated by Django 5.1.5 on 2025-01-27 08:43

import django.db.models.deletion
import services.models
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                ("company_id", models.AutoField(primary_key=True, serialize=False)),
                ("company_name", models.CharField(max_length=50)),
                ("description", models.TextField(blank=True)),
                ("address", models.CharField(max_length=255)),
                ("phone_number", models.CharField(max_length=15)),
                ("email", models.EmailField(max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "companies",
            },
        ),
        migrations.CreateModel(
            name="Department",
            fields=[
                ("department_id", models.AutoField(primary_key=True, serialize=False)),
                ("department_name", models.CharField(max_length=50)),
                ("description", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "departments",
            },
        ),
        migrations.CreateModel(
            name="TenderCategory",
            fields=[
                ("category_id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=50, unique=True)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name_plural": "tender_categories",
                "db_table": "tender_categories",
            },
        ),
        migrations.CreateModel(
            name="Tender",
            fields=[
                ("tender_id", models.AutoField(primary_key=True, serialize=False)),
                ("tender_name", models.CharField(max_length=100)),
                ("description", models.TextField()),
                ("reference_number", models.CharField(max_length=50, unique=True)),
                ("budget", models.DecimalField(decimal_places=2, max_digits=15)),
                ("deadline", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("in_review", "In Review"),
                            ("approved", "Approved"),
                            ("submitted", "Submitted"),
                            ("awarded", "Awarded"),
                            ("closed", "Closed"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="services.company",
                    ),
                ),
                (
                    "required_department",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="services.department",
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="services.tendercategory",
                    ),
                ),
            ],
            options={
                "db_table": "tenders",
            },
        ),
        migrations.CreateModel(
            name="TenderTimeline",
            fields=[
                ("timeline_id", models.AutoField(primary_key=True, serialize=False)),
                ("submission_start", models.DateTimeField()),
                ("submission_end", models.DateTimeField()),
                ("evaluation_start", models.DateTimeField()),
                ("evaluation_end", models.DateTimeField()),
                ("award_date", models.DateTimeField()),
                ("project_start_date", models.DateTimeField()),
                ("project_end_date", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tender",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="timeline",
                        to="services.tender",
                    ),
                ),
            ],
            options={
                "db_table": "tender_timelines",
            },
        ),
        migrations.CreateModel(
            name="User",
            fields=[
                ("user_id", models.AutoField(primary_key=True, serialize=False)),
                ("first_name", models.CharField(max_length=50)),
                ("last_name", models.CharField(max_length=50)),
                ("email", models.EmailField(max_length=254)),
                ("password", models.CharField(max_length=50)),
                ("role", models.CharField(max_length=20)),
                ("phone_number", models.CharField(max_length=15)),
                ("address", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="services.company",
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="services.department",
                    ),
                ),
            ],
            options={
                "db_table": "users",
            },
        ),
        migrations.AddField(
            model_name="tender",
            name="assigned_to",
            field=models.ManyToManyField(
                related_name="assigned_tenders", to="services.user"
            ),
        ),
        migrations.AddField(
            model_name="tender",
            name="created_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tenders_created",
                to="services.user",
            ),
        ),
        migrations.CreateModel(
            name="Document",
            fields=[
                ("document_id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "document_type",
                    models.CharField(
                        choices=[
                            ("notice", "Tender Notice"),
                            ("spec", "Specification Document"),
                            ("bid", "Bid Document"),
                            ("contract", "Contract"),
                            ("other", "Other"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "file",
                    models.FileField(upload_to=services.models.document_upload_path),
                ),
                (
                    "description",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="services.tender",
                    ),
                ),
                (
                    "uploader",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="services.user"
                    ),
                ),
            ],
            options={
                "db_table": "documents",
            },
        ),
        migrations.CreateModel(
            name="CV",
            fields=[
                ("cv_id", models.AutoField(primary_key=True, serialize=False)),
                ("file", models.FileField(upload_to="uploads/cvs/")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cv",
                        to="services.user",
                    ),
                ),
            ],
            options={
                "db_table": "cvs",
            },
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("log_id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("create", "Create"),
                            ("update", "Update"),
                            ("delete", "Delete"),
                            ("approve", "Approve"),
                            ("submit", "Submit"),
                        ],
                        max_length=20,
                    ),
                ),
                ("target_model", models.CharField(max_length=50)),
                ("target_id", models.IntegerField()),
                ("details", models.TextField(blank=True, null=True)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="services.user",
                    ),
                ),
            ],
            options={
                "db_table": "audit_logs",
            },
        ),
        migrations.CreateModel(
            name="Approval",
            fields=[
                ("approval_id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("comments", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approvals",
                        to="services.tender",
                    ),
                ),
                (
                    "approver",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="services.user"
                    ),
                ),
            ],
            options={
                "db_table": "approvals",
            },
        ),
    ]
