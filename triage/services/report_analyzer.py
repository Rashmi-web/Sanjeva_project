import re


KEYWORDS = [
    "hemoglobin",
    "glucose",
    "blood pressure",
    "temperature",
    "cholesterol",
    "platelet",
    "creatinine",
    "wbc",
    "rbc",
    "spo2",
    "oxygen saturation",
    "heart rate",
    "pulse",
]


def analyze_report_text(text):
    if not text:
        return {
            "findings": [],
            "message": "No report text was extracted."
        }

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    findings = []

    for line in lines:
        lower_line = line.lower()

        for keyword in KEYWORDS:

            if keyword in lower_line:
                findings.append(line)
                break

    if not findings:
        return {
            "findings": [],
            "message": (
                "No predefined report values were "
                "detected by the prototype."
            )
        }

    return {
        "findings": findings,
        "message": (
            "Potentially relevant report lines "
            "were extracted for reviewer verification."
        )
    }