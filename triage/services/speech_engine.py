import os

from dotenv import load_dotenv
from sarvamai import SarvamAI


load_dotenv()


API_KEY = os.getenv(
    "SARVAM_API_KEY"
)


LANGUAGE_CODES = {
    "Odia": "od-IN",
    "Hindi": "hi-IN",
    "English": "en-IN"
}


def get_client():

    if not API_KEY:

        raise RuntimeError(
            "SARVAM_API_KEY is not configured."
        )

    return SarvamAI(
        api_subscription_key=API_KEY
    )


def transcribe_audio(
    file_path,
    language="Odia"
):

    client = get_client()

    language_code = LANGUAGE_CODES.get(
        language,
        "unknown"
    )

    with open(
        file_path,
        "rb"
    ) as audio_file:

        response = client.speech_to_text.transcribe(
            file=audio_file,
            model="saaras:v4",
            language_code=language_code,
            mode="transcribe"
        )

    transcript = getattr(
        response,
        "transcript",
        ""
    )

    return transcript.strip()