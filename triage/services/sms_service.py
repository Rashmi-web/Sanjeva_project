
import json
import os
import urllib.error
import urllib.request


def normalize_indian_phone(phone):
    phone = "".join(
        character for character in phone.strip()
        if character.isdigit() or character == "+"
    )

    if phone.startswith("+91"):
        digits = phone[1:]
    elif phone.startswith("91") and len(phone) == 12:
        digits = phone
    elif len(phone) == 10 and phone[0] in "6789":
        digits = "91" + phone
    else:
        raise ValueError(
            "Enter a valid Indian mobile number with 10 digits."
        )

    if not digits.isdigit() or len(digits) != 12:
        raise ValueError("Invalid Indian mobile number.")

    return digits


def send_template_sms(phone, template_id, variables):
    provider = os.getenv("SMS_PROVIDER", "console").strip().lower()

    if provider == "console":
        print("\n========== SANJEVA DEVELOPMENT SMS ==========")
        print("To:", phone)
        print("Template:", template_id or "Development message")
        print("Variables:", variables)
        print("=============================================\n")

        return True, "Development mode: printed to terminal."

    if provider != "msg91":
        return False, "Unsupported SMS_PROVIDER configuration."

    auth_key = os.getenv("MSG91_AUTH_KEY", "").strip()

    if not auth_key:
        return False, "MSG91_AUTH_KEY is not configured."

    if not template_id:
        return False, "The required MSG91 template ID is not configured."

    try:
        normalized_phone = normalize_indian_phone(phone)

        recipient = {"mobiles": normalized_phone}

        for index, value in enumerate(variables, start=1):
            recipient[f"var{index}"] = str(value)

        payload = {
            "template_id": template_id,
            "recipients": [recipient],
        }

        request = urllib.request.Request(
            "https://control.msg91.com/api/v5/flow/",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "accept": "application/json",
                "authkey": auth_key,
                "content-type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=15) as response:
            response_text = response.read().decode(
                "utf-8",
                errors="replace"
            )

            if 200 <= response.status < 300:
                return True, response_text[:2000]

            return False, response_text[:2000]

    except urllib.error.HTTPError as error:
        response_text = error.read().decode(
            "utf-8",
            errors="replace"
        )
        return False, f"MSG91 HTTP {error.code}: {response_text[:1500]}"

    except Exception as error:
        return False, str(error)[:1500]
