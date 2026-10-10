
from django.db import models


class PatientCase(models.Model):
    PRIORITY_CHOICES = [
        ("ROUTINE", "Routine"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
    ]

    STATUS_CHOICES = [
        ("WAITING", "Waiting for Review"),
        ("UNDER_REVIEW", "Under Review"),
        ("REVIEWED", "Reviewed"),
        ("REJECTED", "Rejected"),
    ]

    patient_id = models.CharField(
        max_length=50,
        unique=True
    )

    patient_name = models.CharField(
        max_length=150,
        blank=True
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        db_index=True
    )

    phone_verified = models.BooleanField(default=False)

    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=20, blank=True)
    language = models.CharField(max_length=30, default="English")
    symptoms = models.TextField()
    symptom_duration = models.CharField(max_length=200, blank=True)
    consent_given = models.BooleanField(default=False)

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="ROUTINE"
    )

    priority_reason = models.TextField(blank=True)
    missing_information = models.TextField(blank=True)
    follow_up_questions = models.TextField(blank=True)
    summary = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="WAITING"
    )

    reviewer_notes = models.TextField(blank=True)

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    report = models.FileField(
        upload_to="reports/",
        blank=True,
        null=True
    )

    report_text = models.TextField(blank=True)
    report_findings = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.patient_id


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("CASE_CREATED", "Case Created"),
        ("ANALYSIS_GENERATED", "Analysis Generated"),
        ("CASE_VIEWED", "Case Viewed"),
        ("CASE_REVIEW_STARTED", "Review Started"),
        ("CASE_REVIEWED", "Case Reviewed"),
        ("CASE_REJECTED", "Case Rejected"),
        ("CASE_REOPENED", "Case Reopened"),
        ("CASE_STATUS_CHANGED", "Case Status Changed"),
        ("PATIENT_NOTIFIED", "Patient Notified"),
        ("PATIENT_NOTIFICATION_FAILED", "Patient Notification Failed"),
    ]

    case = models.ForeignKey(
        PatientCase,
        on_delete=models.CASCADE,
        related_name="audit_logs"
    )

    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES
    )

    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.case.patient_id} - {self.action}"


class NotificationLog(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("FAILED", "Failed"),
    ]

    case = models.ForeignKey(
        PatientCase,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    phone_number = models.CharField(max_length=20)
    purpose = models.CharField(
        max_length=50,
        default="QUEUE_READY"
    )

    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    provider_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (
            f"{self.case.patient_id} - "
            f"{self.purpose} - {self.status}"
        )
