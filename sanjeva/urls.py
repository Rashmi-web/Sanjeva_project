from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from triage.views import (
    home,
    register,
    user_login,
    user_logout,
    intake,
    speech_to_text,
    case_result,
    review,
    review_case,
    patient_portal,
    patient_send_otp,
    patient_verify_otp,
    patient_confirmation,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", home, name="home"),

    path("register/", register, name="register"),
    path("login/", user_login, name="login"),
    path("logout/", user_logout, name="logout"),
    path("intake/", intake, name="intake"),

    path("intake/", intake, name="intake"),
    path("speech-to-text/", speech_to_text, name="speech_to_text"),

    path("case/<int:case_id>/", case_result, name="case_result"),

    path("review/", review, name="review"),
    path("review/case/<int:case_id>/", review_case, name="review_case"),

    path("patient/", patient_portal, name="patient_portal"),
    path("patient/send-otp/", patient_send_otp, name="patient_send_otp"),
    path("patient/verify-otp/", patient_verify_otp, name="patient_verify_otp"),
    path("patient/confirmation/", patient_confirmation, name="patient_confirmation"),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )