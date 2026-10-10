import os

import pymupdf
import pytesseract
from PIL import Image


def extract_text_from_image(file_path):

    image = Image.open(
        file_path
    )

    text = pytesseract.image_to_string(
        image
    )

    return text.strip()


def extract_text_from_pdf(file_path):

    document = pymupdf.open(
        file_path
    )

    extracted_text = []

    for page in document:

        text = page.get_text()

        if text.strip():

            extracted_text.append(
                text.strip()
            )

    document.close()

    return "\n\n".join(
        extracted_text
    ).strip()


def extract_text_from_file(file_path):

    extension = os.path.splitext(
        file_path
    )[1].lower()

    if extension in [
        ".jpg",
        ".jpeg",
        ".png"
    ]:

        return extract_text_from_image(
            file_path
        )

    if extension == ".pdf":

        text = extract_text_from_pdf(
            file_path
        )

        if text:

            return text

        return (
            "No selectable text was found "
            "in this PDF."
        )

    return "Unsupported file type."