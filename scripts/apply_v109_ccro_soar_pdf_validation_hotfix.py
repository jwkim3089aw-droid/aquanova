#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "wave_records" / "wave_ccro.py"

OLD_HEAD = '''def validate_exported_ccro_pdf(path: Path, case: CCROVideoCase) -> dict[str, Any]:
    text, provider = _extract_pdf_text(path)
    normalized = text.replace("\\r", "")
    element_tokens = [case.element_type, case.element_type.replace("FilmTec™ ", "").replace("FilmTec ", "")]
    pass2_present = bool(re.search(r"\\bPass\\s*2\\b", normalized, re.I))
'''

NEW_HEAD = '''def validate_exported_ccro_pdf(path: Path, case: CCROVideoCase) -> dict[str, Any]:
    text, provider = _extract_pdf_text(path)
    normalized = text.replace("\\r", "")

    # V109: WAVE/PyMuPDF can extract FilmTec™ as FilmTecΡ or split
    # "FilmTec™ SOAR 5000i" across lines/tabs. Validate element type using
    # both the original regex and a loose alphanumeric canonical form so valid
    # SOAR 4000i/5000i PDFs are not falsely rejected.
    def _canon_element_text(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", " ", value or "").strip().lower()

    element_tokens = [
        case.element_type,
        case.element_type.replace("FilmTec™ ", "").replace("FilmTec ", ""),
    ]
    element_tokens.extend(
        token.replace("™", "").replace("Ρ", "").replace("FilmTec", "").strip()
        for token in list(element_tokens)
    )
    normalized_element_text = _canon_element_text(normalized)
    element_type_ok = any(
        re.search(re.escape(token), normalized, re.I)
        or (_canon_element_text(token) and _canon_element_text(token) in normalized_element_text)
        for token in element_tokens
    )
    pass2_present = bool(re.search(r"\\bPass\\s*2\\b", normalized, re.I))
'''

OLD_CHECK = '''        "element_type": any(re.search(re.escape(token), normalized, re.I) for token in element_tokens),'''
NEW_CHECK = '''        "element_type": element_type_ok,'''

def main() -> int:
    if not TARGET.exists():
        raise SystemExit(f"missing target: {TARGET}")

    text = TARGET.read_text(encoding="utf-8")

    if "V109: WAVE/PyMuPDF can extract FilmTec" in text:
        print(f"V109 CCRO PDF validation hotfix already applied: {TARGET}")
        return 0

    if OLD_HEAD not in text:
        raise SystemExit("Could not find validate_exported_ccro_pdf header block. Send the latest wave_ccro.py or feedback ZIP.")

    text = text.replace(OLD_HEAD, NEW_HEAD)
    if OLD_CHECK not in text:
        raise SystemExit("Could not find element_type check line.")
    text = text.replace(OLD_CHECK, NEW_CHECK)

    TARGET.write_text(text, encoding="utf-8")
    print(f"V109 CCRO SOAR PDF validation hotfix applied: {TARGET}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
