# scripts/dump_raw_ocr_text.py
import os
import re
import sys
import subprocess
from pdf2image import convert_from_path
import pytesseract

# 설정 상수 정의 (하드코딩 방지)
POPPLER_PATH = r"C:\poppler-26.02.0\Library\bin"
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
INPUT_DIR = "./WAVE_PIPELINE/1_INPUT"
OUTPUT_FILE = "./ocr_raw_dump.txt"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def dump_pdf_ocr_text():
    """PDF 폴더 내 모든 파일의 OCR 추출 텍스트를 하나의 파일로 저장"""
    if not os.path.exists(INPUT_DIR):
        print(f"Error: Input directory {INPUT_DIR} does not exist.")
        return

    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]
    if not files:
        print("No PDF files found.")
        return

    print(f"Starting OCR text dump for {len(files)} files...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
        for idx, file_name in enumerate(files, 1):
            file_path = os.path.join(INPUT_DIR, file_name)
            print(f"[{idx}/{len(files)}] Processing: {file_name}")

            out_f.write(f"\n\n{'='*60}\n")
            out_f.write(f"[FILE NAME] {file_name}\n")
            out_f.write(f"{'='*60}\n")

            try:
                # PDF 전체 페이지를 고해상도 이미지로 변환
                images = convert_from_path(
                    file_path, dpi=300, poppler_path=POPPLER_PATH
                )

                for page_num, image in enumerate(images, 1):
                    page_text = pytesseract.image_to_string(image, lang="eng")
                    out_f.write(f"\n--- PAGE {page_num} ---\n")
                    out_f.write(page_text)

            except Exception as e:
                out_f.write(f"\nOCR Error occurred: {str(e)}\n")
                print(f"Error processing {file_name}: {e}")

    print(f"Completed. Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    dump_pdf_ocr_text()
