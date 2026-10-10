HIGH_RISK_KEYWORDS = [
    "severe chest pain",
    "chest pain",
    "difficulty breathing",
    "shortness of breath",
    "unconscious",
    "loss of consciousness",
    "fainted",
    "heavy bleeding",
    "severe bleeding",
    "cannot breathe",
    "not breathing",
    "stroke",
    "seizure",
    "convulsion"
]

MEDIUM_RISK_KEYWORDS = [
    "high fever",
    "persistent fever",
    "vomiting",
    "persistent vomiting",
    "dizziness",
    "severe headache",
    "abdominal pain",
    "dehydration",
    "weakness",
    "confusion"
]


def analyze_symptoms(symptoms, age, duration):
    text = symptoms.lower().strip()

    high_matches = [
        keyword
        for keyword in HIGH_RISK_KEYWORDS
        if keyword in text
    ]

    medium_matches = [
        keyword
        for keyword in MEDIUM_RISK_KEYWORDS
        if keyword in text
    ]

    if high_matches:
        priority = "HIGH"
        reason = (
            "Potential urgency signals were detected in the reported "
            "symptoms. Qualified clinical review is recommended promptly."
        )

    elif medium_matches:
        priority = "MEDIUM"
        reason = (
            "The reported symptoms contain information that may require "
            "further assessment by qualified staff."
        )

    else:
        priority = "ROUTINE"
        reason = (
            "No predefined potential urgency signal was detected by the "
            "current prototype rules. Qualified review is still required."
        )

    missing_information = []

    if not symptoms:
        missing_information.append("Symptoms")

    if not duration:
        missing_information.append("Symptom duration")

    if not age:
        missing_information.append("Age")

    follow_up_questions = []

    if "chest pain" in text:
        follow_up_questions.append(
            "When did the chest discomfort begin?"
        )
        follow_up_questions.append(
            "Is the discomfort continuous or does it come and go?"
        )

    if "fever" in text:
        follow_up_questions.append(
            "What was the highest temperature recorded?"
        )
        follow_up_questions.append(
            "When did the fever start?"
        )

    if "vomiting" in text:
        follow_up_questions.append(
            "How many times have you vomited?"
        )
        follow_up_questions.append(
            "Are you able to keep fluids down?"
        )

    if "dizziness" in text:
        follow_up_questions.append(
            "When did the dizziness begin?"
        )
        follow_up_questions.append(
            "Have you experienced fainting or loss of consciousness?"
        )

    if "headache" in text:
        follow_up_questions.append(
            "When did the headache begin?"
        )
        follow_up_questions.append(
            "How severe is the headache on a scale from 1 to 10?"
        )

    if not follow_up_questions:
        follow_up_questions.append(
            "When did the symptoms first begin?"
        )
        follow_up_questions.append(
            "Have the symptoms become better, worse, or stayed the same?"
        )

    return {
        "priority": priority,
        "priority_reason": reason,
        "missing_information": missing_information,
        "follow_up_questions": follow_up_questions,
        "high_matches": high_matches,
        "medium_matches": medium_matches
    }