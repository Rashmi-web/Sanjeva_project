
import hashlib
import os
import secrets
import uuid
from datetime import datetime

from django.shortcuts import redirect, render
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import AuditLog, PatientCase
from .services.ocr_engine import extract_text_from_file
from .services.report_analyzer import analyze_report_text
from .services.speech_engine import transcribe_audio
from .services.summary_engine import generate_summary
from .services.triage_engine import analyze_symptoms
from .services.sms_service import normalize_indian_phone, send_template_sms


OTP_EXPIRY_SECONDS = 300
OTP_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5


def _otp_hash(otp):
    value = f"{settings.SECRET_KEY}:{otp}"
    return hashlib.sha256(value.encode()).hexdigest()


def _clear_otp_session(request):
    for key in (
        "sanjeva_otp_hash",
        "sanjeva_otp_phone",
        "sanjeva_otp_expiry",
        "sanjeva_otp_sent_at",
        "sanjeva_otp_attempts",
    ):
        request.session.pop(key, None)


def _new_patient_id():
    while True:
        patient_id = (
            f"SJ-{timezone.localdate():%Y%m%d}-"
            f"{uuid.uuid4().hex[:8].upper()}"
        )
        if not PatientCase.objects.filter(
            patient_id=patient_id
        ).exists():
            return patient_id


def _create_case_audit(case, action, details):
    return AuditLog.objects.create(
        case=case,
        action=action,
        details=details,
    )


def _process_report(case, report):
    if not report:
        return

    try:
        report_text = extract_text_from_file(case.report.path)
        report_analysis = analyze_report_text(report_text)

        case.report_text = report_text
        case.report_findings = "\n".join(
            report_analysis.get("findings", [])
        )
    except Exception as error:
        case.report_text = (
            "Report processing failed: " + str(error)
        )


def _analyze_and_save_case(case):
    analysis = analyze_symptoms(
        case.symptoms,
        case.age,
        case.symptom_duration,
    )

    case.priority = analysis.get("priority", "ROUTINE")
    case.priority_reason = analysis.get("priority_reason", "")
    case.missing_information = "\n".join(
        analysis.get("missing_information", [])
    )
    case.follow_up_questions = "\n".join(
        analysis.get("follow_up_questions", [])
    )
    case.summary = generate_summary(case, analysis)
    case.save()

    _create_case_audit(
        case,
        "ANALYSIS_GENERATED",
        "Prototype triage analysis and structured summary generated.",
    )


def home(request):
    if not request.user.is_authenticated:
        return redirect("login")

    if not request.session.get("sanjeva_verified_phone"):
        return redirect("patient_portal")

    context = {
        "total_cases": PatientCase.objects.count(),
        "waiting_cases": PatientCase.objects.filter(
            status="WAITING"
        ).count(),
        "high_cases": PatientCase.objects.filter(
            priority="HIGH"
        ).count(),
        "reviewed_cases": PatientCase.objects.filter(
            status="REVIEWED"
        ).count(),
    }

    return render(request, "triage/home.html", context)


def register(request):
    if request.user.is_authenticated:
        return redirect("patient_portal")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not username:
            messages.error(request, "Username is required.")
            return redirect("register")

        if not password:
            messages.error(request, "Password is required.")
            return redirect("register")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("register")

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        login(request, user)
        request.session.pop("sanjeva_verified_phone", None)

        return redirect("patient_portal")

    return render(request, "triage/auth/register.html")


def user_login(request):
    if request.user.is_authenticated:
        if request.session.get("sanjeva_verified_phone"):
            return redirect("intake")
        return redirect("patient_portal")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)
            request.session.pop("sanjeva_verified_phone", None)
            return redirect("patient_portal")

        messages.error(request, "Invalid username or password.")

    return render(request, "triage/auth/login.html")


@login_required
def user_logout(request):
    logout(request)
    return redirect("login")



def intake(request):
    verified_phone = request.session.get("sanjeva_verified_phone", "")

    if not request.user.is_authenticated and not verified_phone:
        return redirect("login")

    if not verified_phone:
        return redirect("patient_portal")

    is_patient = not request.user.is_authenticated

    if request.method == "POST":
        patient_id = request.POST.get("patient_id", "").strip()
        patient_name = request.POST.get("patient_name", "").strip()
        age = request.POST.get("age", "").strip()
        gender = request.POST.get("gender", "").strip()
        language = request.POST.get("language", "English").strip()
        symptoms = request.POST.get("symptoms", "").strip()
        symptom_duration = request.POST.get(
            "symptom_duration", ""
        ).strip()
        consent_given = request.POST.get("consent") == "on"
        report = request.FILES.get("report")

        if not patient_name or len(patient_name) > 150:
            messages.error(
                request,
                "Enter the patient's name (maximum 150 characters).",
            )
            return redirect("intake")

        try:
            age_value = int(age)
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid age.")
            return redirect("intake")

        if not 0 <= age_value <= 120:
            messages.error(request, "Age must be between 0 and 120.")
            return redirect("intake")

        if not symptoms:
            messages.error(request, "Please provide symptoms.")
            return redirect("intake")

        if not consent_given:
            messages.error(
                request,
                "Consent is required before submitting the case.",
            )
            return redirect("intake")

        if not patient_id:
            patient_id = _new_patient_id()

        if PatientCase.objects.filter(patient_id=patient_id).exists():
            messages.error(
                request,
                "This Patient ID already exists. Please submit again.",
            )
            return redirect("intake")

        case = PatientCase.objects.create(
            patient_id=patient_id,
            patient_name=patient_name,
            phone_number=verified_phone,
            phone_verified=True,
            age=age_value,
            gender=gender,
            language=language,
            symptoms=symptoms,
            symptom_duration=symptom_duration,
            consent_given=True,
            report=report,
        )

        _process_report(case, report)
        _analyze_and_save_case(case)

        action_details = (
            "Case created through OTP-verified patient intake."
            if is_patient
            else "Case created through OTP-verified staff intake."
        )

        _create_case_audit(
            case,
            "CASE_CREATED",
            action_details,
        )

        if is_patient:
            request.session["sanjeva_public_confirmation_id"] = case.id
            request.session.pop("sanjeva_verified_phone", None)
            return redirect("patient_confirmation")

        return redirect("case_result", case_id=case.id)

    return render(
        request,
        "triage/intake.html",
        {
            "is_patient": is_patient,
            "verified_phone": verified_phone,
        },
    )

@require_POST
def patient_send_otp(request):
    raw_phone = request.POST.get("phone_number", "").strip()

    try:
        phone_number = normalize_indian_phone(raw_phone)
    except Exception:
        phone_number = None

    if not phone_number:
        return JsonResponse(
            {
                "success": False,
                "error": "Enter a valid Indian mobile number.",
            },
            status=400,
        )

    last_sent = request.session.get("sanjeva_otp_sent_at")
    last_phone = request.session.get("sanjeva_otp_phone")

    if (
        last_sent
        and last_phone == phone_number
        and timezone.now().timestamp() - float(last_sent)
        < OTP_RESEND_SECONDS
    ):
        remaining = OTP_RESEND_SECONDS - int(
            timezone.now().timestamp() - float(last_sent)
        )
        return JsonResponse(
            {
                "success": False,
                "error": (
                    f"Please wait {max(remaining, 1)} seconds "
                    "before requesting another OTP."
                ),
            },
            status=429,
        )

    otp = f"{secrets.randbelow(1000000):06d}"
    template_id = os.environ.get("MSG91_OTP_TEMPLATE_ID", "")
    provider = os.environ.get("SMS_PROVIDER", "console").lower()

    try:
        result = send_template_sms(
            phone_number,
            template_id,
            {"otp": otp},
        )

        if result is False:
            raise RuntimeError("The SMS provider did not accept the OTP.")

    except Exception as error:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "OTP could not be sent. Check the SMS provider "
                    "configuration and try again."
                ),
            },
            status=502,
        )

    now_timestamp = timezone.now().timestamp()

    request.session["sanjeva_otp_hash"] = _otp_hash(otp)
    request.session["sanjeva_otp_phone"] = phone_number
    request.session["sanjeva_otp_expiry"] = (
        now_timestamp + OTP_EXPIRY_SECONDS
    )
    request.session["sanjeva_otp_sent_at"] = now_timestamp
    request.session["sanjeva_otp_attempts"] = 0
    request.session.pop("sanjeva_verified_phone", None)

    return JsonResponse(
        {
            "success": True,
            "message": "OTP sent. It is valid for 5 minutes.",
            "development_mode": provider == "console",
        }
    )


@require_POST
def patient_verify_otp(request):
    raw_phone = request.POST.get("phone_number", "").strip()
    otp = request.POST.get("otp", "").strip()

    try:
        phone_number = normalize_indian_phone(raw_phone)
    except Exception:
        phone_number = None

    stored_phone = request.session.get("sanjeva_otp_phone")
    stored_hash = request.session.get("sanjeva_otp_hash")
    expiry = request.session.get("sanjeva_otp_expiry")
    attempts = int(request.session.get("sanjeva_otp_attempts", 0))

    if (
        not phone_number
        or phone_number != stored_phone
        or not stored_hash
        or not expiry
    ):
        return JsonResponse(
            {
                "success": False,
                "error": "Request a new OTP for this phone number.",
            },
            status=400,
        )

    if timezone.now().timestamp() > float(expiry):
        _clear_otp_session(request)
        return JsonResponse(
            {
                "success": False,
                "error": "OTP expired. Please request a new OTP.",
            },
            status=400,
        )

    if attempts >= OTP_MAX_ATTEMPTS:
        _clear_otp_session(request)
        return JsonResponse(
            {
                "success": False,
                "error": "Too many incorrect attempts. Request a new OTP.",
            },
            status=429,
        )

    if len(otp) != 6 or not otp.isdigit() or _otp_hash(otp) != stored_hash:
        request.session["sanjeva_otp_attempts"] = attempts + 1
        return JsonResponse(
            {
                "success": False,
                "error": "Incorrect OTP. Please try again.",
            },
            status=400,
        )

    request.session["sanjeva_verified_phone"] = phone_number
    _clear_otp_session(request)

    return JsonResponse(
        {
            "success": True,
            "message": "Phone number verified successfully.",
        }
    )


def public_patient_intake(request):
    verified_phone = request.session.get("sanjeva_verified_phone", "")

    if request.method == "POST":
        if not verified_phone:
            messages.error(
                request,
                "Verify your phone number with OTP before submitting.",
            )
            return redirect("public_patient_intake")

        patient_name = request.POST.get("patient_name", "").strip()
        age = request.POST.get("age", "").strip()
        gender = request.POST.get("gender", "").strip()
        language = request.POST.get("language", "English").strip()
        symptoms = request.POST.get("symptoms", "").strip()
        symptom_duration = request.POST.get(
            "symptom_duration", ""
        ).strip()
        consent_given = request.POST.get("consent") == "on"
        report = request.FILES.get("report")

        if not patient_name or len(patient_name) > 150:
            messages.error(
                request,
                "Enter the patient's name (maximum 150 characters).",
            )
            return redirect("public_patient_intake")

        try:
            age_value = int(age)
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid age.")
            return redirect("public_patient_intake")

        if not 0 <= age_value <= 120:
            messages.error(request, "Age must be between 0 and 120.")
            return redirect("public_patient_intake")

        if not symptoms:
            messages.error(request, "Please provide symptoms.")
            return redirect("public_patient_intake")

        if not consent_given:
            messages.error(
                request,
                "Consent is required before submitting the case.",
            )
            return redirect("public_patient_intake")

        case = PatientCase.objects.create(
            patient_id=_new_patient_id(),
            patient_name=patient_name,
            phone_number=verified_phone,
            phone_verified=True,
            age=age_value,
            gender=gender,
            language=language,
            symptoms=symptoms,
            symptom_duration=symptom_duration,
            consent_given=True,
            report=report,
        )

        _process_report(case, report)
        _analyze_and_save_case(case)

        _create_case_audit(
            case,
            "CASE_CREATED",
            "Case created through OTP-verified patient intake.",
        )

        request.session["sanjeva_public_confirmation_id"] = case.id
        request.session.pop("sanjeva_verified_phone", None)

        return redirect("patient_confirmation")

    return render(
        request,
        "triage/intake.html",
        {
            "public_mode": True,
            "verified_phone": verified_phone,
        },
    )



def patient_portal(request):
    if request.session.get("sanjeva_verified_phone"):
        return redirect("intake")

    return render(request, "triage/patient_otp.html")



def patient_confirmation(request):
    case_id = request.session.get("sanjeva_public_confirmation_id")

    if not case_id:
        return redirect("patient_portal")

    case = get_object_or_404(PatientCase, id=case_id)

    return render(
        request,
        "triage/patient_confirmation.html",
        {"case": case},
    )


@require_POST
def speech_to_text(request):
    if (
        not request.user.is_authenticated
        and not request.session.get("sanjeva_verified_phone")
    ):
        return JsonResponse(
            {
                "success": False,
                "error": "Please log in or verify your phone number before using voice input.",
            },
            status=403,
        )

    audio_file = request.FILES.get("audio")

    if not audio_file:
        return JsonResponse(
            {
                "success": False,
                "error": "No audio recording was received. Please record your symptoms again.",
            },
            status=400,
        )

    temp_path = None

    try:
        import os
        import tempfile

        suffix = os.path.splitext(audio_file.name)[1] or ".webm"

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp_file:
            for chunk in audio_file.chunks():
                temp_file.write(chunk)

            temp_path = temp_file.name

        language = request.POST.get("language", "English").strip()

        transcript = transcribe_audio(
            temp_path,
            language=language,
        )

        if isinstance(transcript, dict):
            if not transcript.get("success", True):
                return JsonResponse(
                    {
                        "success": False,
                        "error": transcript.get(
                            "error",
                            "The transcription service could not process the recording.",
                        ),
                    },
                    status=502,
                )

            transcript = (
                transcript.get("text")
                or transcript.get("transcript")
                or ""
            )

        if not transcript or not str(transcript).strip():
            return JsonResponse(
                {
                    "success": False,
                    "error": "No speech was recognized. Please speak clearly and try again.",
                },
                status=422,
            )

        return JsonResponse(
            {
                "success": True,
                "text": str(transcript).strip(),
                "transcript": str(transcript).strip(),
            }
        )

    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Speech-to-text processing failed."
        )

        return JsonResponse(
            {
                "success": False,
                "error": "Voice transcription failed. Please try again.",
            },
            status=500,
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@login_required
def case_result(request, case_id):
    case = get_object_or_404(PatientCase, id=case_id)

    _create_case_audit(
        case,
        "CASE_VIEWED",
        "Case intelligence page viewed.",
    )

    return render(
        request,
        "triage/case_result.html",
        {"case": case},
    )


@login_required
def review(request):
    cases = PatientCase.objects.all().order_by(
        "-priority",
        "-created_at",
    )

    context = {
        "cases": cases,
        "total_cases": PatientCase.objects.count(),
        "waiting_cases": PatientCase.objects.filter(
            status="WAITING"
        ).count(),
        "high_cases": PatientCase.objects.filter(
            priority="HIGH"
        ).count(),
        "medium_cases": PatientCase.objects.filter(
            priority="MEDIUM"
        ).count(),
        "routine_cases": PatientCase.objects.filter(
            priority="ROUTINE"
        ).count(),
        "reviewed_cases": PatientCase.objects.filter(
            status="REVIEWED"
        ).count(),
    }

    return render(request, "triage/review.html", context)


@login_required
def review_case(request, case_id):
    case = get_object_or_404(PatientCase, id=case_id)

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        reviewer_notes = request.POST.get(
            "reviewer_notes", ""
        ).strip()

        with transaction.atomic():
            case = PatientCase.objects.select_for_update().get(
                id=case_id
            )
            case.reviewer_notes = reviewer_notes

            if action == "start_review":
                if case.status == "WAITING":
                    case.status = "UNDER_REVIEW"
                    case.save()
                    _create_case_audit(
                        case,
                        "CASE_REVIEW_STARTED",
                        "Human reviewer started reviewing the case.",
                    )
                    messages.success(request, "Review started.")
                else:
                    messages.warning(
                        request,
                        "This case is no longer waiting for review.",
                    )

            elif action == "approve":
                case.status = "REVIEWED"
                case.reviewed_at = timezone.now()
                case.save()
                _create_case_audit(
                    case,
                    "CASE_REVIEWED",
                    "Case reviewed by human reviewer.",
                )
                messages.success(request, "Case marked as reviewed.")

            elif action == "reject":
                case.status = "REJECTED"
                case.reviewed_at = timezone.now()
                case.save()
                _create_case_audit(
                    case,
                    "CASE_REJECTED",
                    "Case rejected by human reviewer.",
                )
                messages.success(request, "Case marked as rejected.")

            elif action == "reopen":
                case.status = "WAITING"
                case.reviewed_at = None
                case.save()
                _create_case_audit(
                    case,
                    "CASE_REOPENED",
                    "Case reopened for human review.",
                )
                messages.success(request, "Case reopened.")

            else:
                messages.error(request, "Unknown review action.")

        return redirect("review_case", case_id=case.id)

    logs = case.audit_logs.all().order_by("-created_at")

    return render(
        request,
        "triage/review_case.html",
        {
            "case": case,
            "logs": logs,
        },
    )
