# app/scripts/extract_file_list.py
import os
from pathlib import Path


def list_code_files():
    # 1. 경로 설정
    # 현재 스크립트가 위치한 경로 (.../code/scripts)
    current_script_path = Path(__file__).parent.resolve()

    # 탐색할 루트 경로 (한 단계 위인 .../code)
    target_root_path = current_script_path.parent

    # 2. 찾고자 하는 코드 파일 확장자 설정
    # 🛑 [수정됨] React UI 컴포넌트 확장자(.tsx, .jsx) 추가!
    CODE_EXTENSIONS = {
        ".py",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".js",
        ".ts",
        ".tsx",  # <-- 추가됨! (React TypeScript 컴포넌트)
        ".jsx",  # <-- 추가됨! (React JavaScript 컴포넌트)
        ".html",
        ".css",
        ".java",
        ".cs",
        ".json",
        ".xml",
        ".yaml",
    }

    # 3. 제외할 폴더명 (검색하고 싶지 않은 폴더)
    IGNORE_DIRS = {
        ".git",
        "__pycache__",
        ".idea",
        ".vscode",
        "build",
        "dist",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "bin",
        "obj",
        "Debug",
        "Release",
    }

    output_file = current_script_path / "file_list.txt"
    found_files = []

    print(f"탐색 시작 위치: {target_root_path}")
    print("파일 리스트 추출 중...")

    # 4. 파일 탐색 (os.walk를 사용하여 하위 폴더까지 재귀 탐색)
    for root, dirs, files in os.walk(target_root_path):
        # 제외할 폴더는 탐색에서 배제
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            file_path = Path(root) / file
            # 확장자 확인 (대소문자 무시)
            if file_path.suffix.lower() in CODE_EXTENSIONS:
                # 루트로부터의 상대 경로 계산 (깔끔하게 보기 위함)
                relative_path = file_path.relative_to(target_root_path)
                found_files.append(str(relative_path))

    # 5. 결과 저장
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# 프로젝트 코드 파일 리스트\n")
            f.write(f"# 기준 경로: {target_root_path}\n")
            f.write(f"# 추출 일시: {os.path.abspath(output_file)}\n")
            f.write("-" * 50 + "\n\n")

            if not found_files:
                f.write("코드 파일을 찾지 못했습니다.\n")
                print("해당하는 확장자의 파일이 없습니다.")
            else:
                for file_path in sorted(found_files):
                    f.write(f"{file_path}\n")
                print(f"\n성공! 총 {len(found_files)}개의 파일 목록을 추출했습니다.")
                print(f"저장된 파일: {output_file}")

    except Exception as e:
        print(f"파일 저장 중 오류 발생: {e}")


if __name__ == "__main__":
    list_code_files()
