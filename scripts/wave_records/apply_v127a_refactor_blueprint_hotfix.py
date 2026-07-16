#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

def backup(path: Path) -> None:
    b = path.with_suffix(path.suffix + ".v127_before_v127a.bak")
    if path.exists() and not b.exists():
        b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

def main() -> int:
    root = Path.cwd().resolve()
    path = root / "scripts" / "wave_records" / "aquanova_refactor_blueprint.py"
    if not path.exists():
        raise SystemExit(f"not found: {path}")

    backup(path)
    text = path.read_text(encoding="utf-8")

    old = '''def parse_ast(p: Path):
    try:
        return ast.parse(read_text(p), filename=str(p))
    except SyntaxError as e:
        return None, str(e)
'''
    new = '''def parse_ast(p: Path):
    try:
        return ast.parse(read_text(p), filename=str(p)), None
    except SyntaxError as e:
        return None, str(e)
'''

    if old not in text:
        text2 = text.replace(
            "return ast.parse(read_text(p), filename=str(p))\n    except SyntaxError as e:\n        return None, str(e)",
            "return ast.parse(read_text(p), filename=str(p)), None\n    except SyntaxError as e:\n        return None, str(e)",
        )
        if text2 == text:
            raise SystemExit("Could not find parse_ast return pattern. Paste the parse_ast function.")
        text = text2
    else:
        text = text.replace(old, new)

    path.write_text(text, encoding="utf-8")
    print("V127A refactor blueprint hotfix applied")
    print(f"patched: {path}")
    print("Fixed parse_ast() to return (tree, error) consistently.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
