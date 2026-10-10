from triage.services.ocr_engine import extract_text_from_file

file_path = input("Enter the full path of your test PDF or image: ")
file_path = file_path.strip().strip('"')

try:
    text = extract_text_from_file(file_path)

    print("\n========== OCR RESULT ==========\n")
    print(text if text else "No text was detected.")
    print("\n========== END OF RESULT ==========")

except Exception as error:
    print(f"OCR failed: {error}")