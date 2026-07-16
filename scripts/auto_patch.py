import os
import sys
import shutil
import importlib
from pathlib import Path


def find_patch_root(source_path: Path) -> Path:
    """
    이중 폴더 현상을 방지하고, 패치 루트(app, scripts가 위치한 폴더)를 찾습니다.
    """
    if (
        (source_path / "app").exists()
        or (source_path / "scripts").exists()
        or (source_path / "ui").exists()
    ):
        return source_path

    for child in source_path.iterdir():
        if child.is_dir():
            if (
                (child / "app").exists()
                or (child / "scripts").exists()
                or (child / "ui").exists()
            ):
                return child
    return source_path


def apply_patch(source_dir_input: str):
    target_dir = Path(__file__).resolve().parent.parent
    source_dir = Path(source_dir_input).resolve()

    print("\n" + "=" * 80)
    print(" 🛠️ AquaNova 스마트 자동 패치 모듈 (.py 전용, 클린업 탑재)")
    print("=" * 80)

    if not source_dir.exists():
        print(
            f"❌ [오류] 지정한 원본 폴더 경로를 찾을 수 없습니다.\n   -> 입력된 경로: {source_dir}"
        )
        return

    patch_root = find_patch_root(source_dir)

    print(f" 📂 패치 원본 (GPT 추출): {patch_root}")
    print(f" 📂 적용 대상 (내 프로젝트): {target_dir}")
    print("-" * 80 + "\n")

    patched_count = 0
    new_files_count = 0
    skipped_count = 0

    # 1. 파일 덮어쓰기 진행
    for root, dirs, files in os.walk(patch_root):
        for file in files:
            src_file = Path(root) / file

            # .py 확장자만 필터링
            if src_file.suffix != ".py":
                skipped_count += 1
                continue

            rel_path = src_file.relative_to(patch_root)
            dest_file = target_dir / rel_path

            dest_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                if dest_file.exists():
                    print(f" 🔄 [덮어쓰기 완료] : {rel_path}")
                    patched_count += 1
                else:
                    print(f" ✨ [새 파일 추가] : {rel_path}")
                    new_files_count += 1

                shutil.copy2(src_file, dest_file)
            except Exception as e:
                print(f" ❌ [오류 발생] {rel_path} 복사 중 에러: {e}")

    # 2. 캐시 무효화 (GPT가 변경된 파일을 인식하도록)
    importlib.invalidate_caches()

    print("\n" + "-" * 80)
    # 3. 원본(다운로드된) 패치 폴더 자동 삭제
    try:
        # 이중 폴더일 경우 최상위 원본 폴더(source_dir)를 통째로 날림
        shutil.rmtree(source_dir)
        print(
            f" 🗑️ [정리 완료] 다운로드된 원본 패치 폴더가 삭제되었습니다. ({source_dir})"
        )
    except Exception as e:
        print(f" ⚠️ [정리 실패] 원본 폴더 삭제 중 에러 (수동으로 지워주세요): {e}")

    print("=" * 80)
    print(" 🏆 패치 완료 리포트")
    print(f"  - 덮어쓴 기존 파일 : {patched_count} 개")
    print(f"  - 새로 추가된 파일 : {new_files_count} 개")
    print(f"  - 건너뛴 메타 파일 : {skipped_count} 개")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        src_input = sys.argv[1]
    else:
        print("💡 GPT에서 다운로드한 패치 폴더(ZIP 압축해제)의 경로를 입력하세요.")
        src_input = input("👉 경로 입력: ").strip()

    src_input = src_input.strip('"').strip("'")

    if src_input:
        apply_patch(src_input)
    else:
        print("❌ 경로가 입력되지 않아 스크립트를 종료합니다.")
