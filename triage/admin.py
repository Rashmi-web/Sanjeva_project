from django.contrib import admin
from .models import PatientCase, AuditLog


@admin.register(PatientCase)
class PatientCaseAdmin(admin.ModelAdmin):
    list_display = (
        "patient_id",
        "age",
        "priority",
        "status",
        "created_at",
    )

    list_filter = (
        "priority",
        "status",
        "language",
    )

    search_fields = (
        "patient_id",
        "symptoms",
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "case",
        "action",
        "created_at",
    )

    list_filter = (
        "action",
        "created_at",
    )

    search_fields = (
        "case__patient_id",
        "details",
    )