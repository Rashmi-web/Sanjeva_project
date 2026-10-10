import os
import io

import pymupdf
import pytesseract

from PIL import Image, ImageOps, ImageEnhance, ImageFilter


# Supported file formats
SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".pdf",
}


def preprocess_image(image):
    """
    Improve image quality before sending it to Tesseract.
    """

    # Correct image orientation
    image = ImageOps.exif_transpose(image)

    # Convert to grayscale
    image = image.convert("L")

    # Enlarge the image to improve small-text recognition
    image = image.resize(
        (image.width * 3, image.height * 3),
        Image.Resampling.LANCZOS,
    )

    # Improve contrast
    image = ImageOps.autocontrast(image)

    image = ImageEnhance.Contrast(image).enhance(2.0)

    # Sharpen text
    image = image.filter(ImageFilter.SHARPEN)

    return image


def extract_text_from_image(file_path):
    image = Image.open(file_path).convert("RGB")

    text = pytesseract.image_to_string(
        image,
        config="--oem 3 --psm 6"
    )

    return text.strip()

def extract_text_from_pdf(file_path):
    extracted_pages = []

    with pymupdf.open(file_path) as document:

        if document.needs_pass:
            raise ValueError("The PDF is password-protected.")

        if len(document) == 0:
            return "The PDF contains no pages."

        for page_number, page in enumerate(document):

            # First, try extracting selectable PDF text.
            text = page.get_text("text").strip()

            # If no text exists, OCR the scanned page.
            if not text:
                pix = page.get_pixmap(
                    matrix=pymupdf.Matrix(3, 3),
                    alpha=False
                )

                image = Image.open(
                    io.BytesIO(pix.tobytes("png"))
                ).convert("RGB")

                text = pytesseract.image_to_string(
                    image,
                    config="--oem 3 --psm 3"
                ).strip()

            if text:
                extracted_pages.append(
                    f"--- Page {page_number + 1} ---\n{text}"
                )

    if not extracted_pages:
        return "No readable text could be extracted from this PDF."

    return "\n\n".join(extracted_pages)

def extract_text_from_file(file_path):
    extension = os.path.splitext(file_path)[1].lower()

    if extension in [".jpg", ".jpeg", ".png"]:
        return extract_text_from_image(file_path)

    if extension == ".pdf":
        return extract_text_from_pdf(file_path)

    raise ValueError("Unsupported file type.")