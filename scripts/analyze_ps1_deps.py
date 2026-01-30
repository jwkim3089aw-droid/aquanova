import os
import re
import sys

# =========================================================
# 설정: 경로 정의
# =========================================================
# 프로젝트 코드 루트 (run_aquanova.ps1이 있는 곳)
BASE_DIR = r"C:\Users\a\Desktop\프로젝트\AquaNova\code"

# 분석할 대상 파일
PS1_FILE_PATH = os.path.join(BASE_DIR, "run_aquanova.ps1")

# 결과물을 저장할 경로 (scripts 폴더)
OUTPUT_DIR = os.path.join(BASE_DIR, "scripts")
OUTPUT_FILE_PATH = os.path.join(OUTPUT_DIR, "aquanova_dependencies.txt")
OUTPUT_CODE_PATH = os.path.join(OUTPUT_DIR, "aquanova_code_extract.txt") # 코드 추출 파일 경로

# =========================================================
# 도우미 함수: Python Import 분석
# =========================================================

def get_imports_from_file(file_path):
    """
    Python 파일을 읽어서 import 구문에 있는 모듈명들을 추출합니다.
    (예: 'app.core.config', 'app.utils' 등)
    """
    imports = []
    if not os.path.exists(file_path):
        return imports

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return imports

    # 정규식: from ... import ... 및 import ...
    # 간단한 정적 분석만 수행합니다.
    regex_from = re.compile(r'^\s*from\s+([\w\.]+)\s+import')
    regex_import = re.compile(r'^\s*import\s+([\w\.]+)')

    for line in lines:
        # from app.core import config
        m_from = regex_from.search(line)
        if m_from:
            imports.append(m_from.group(1))
            continue
        
        # import app.main
        m_import = regex_import.search(line)
        if m_import:
            imports.append(m_import.group(1))
            continue

    return imports

def resolve_module_to_path(module_name):
    """
    모듈명(app.core)을 실제 파일 경로(app\core.py 또는 app\core\__init__.py)로 변환합니다.
    프로젝트 내부 파일인 경우에만 경로를 반환하고, 외부 라이브러리라면 None을 반환합니다.
    """
    # 상대 경로 처리를 위해 점(.)을 경로 구분자로 변경
    rel_path = module_name.replace(".", os.sep)
    
    # 1. .py 파일인 경우 (예: app\core.py)
    candidate_1 = os.path.join(BASE_DIR, rel_path + ".py")
    if os.path.isfile(candidate_1):
        return candidate_1
    
    # 2. 패키지 폴더인 경우 (예: app\core\__init__.py)
    candidate_2 = os.path.join(BASE_DIR, rel_path, "__init__.py")
    if os.path.isfile(candidate_2):
        return candidate_2
    
    return None

def scan_recursive_dependencies(start_files):
    """
    시작 파일 리스트에서 출발하여 재귀적으로 import된 모든 로컬 파일을 찾습니다.
    """
    visited = set()
    to_scan = list(start_files) # 스캔해야 할 파일 큐
    
    # 시작 파일들은 이미 발견된 것으로 간주
    for f in start_files:
        visited.add(os.path.normpath(f))

    print(f"   [Scan] Starting recursive scan from {len(start_files)} entry points...")
    
    found_dependencies = []

    while to_scan:
        current_file = to_scan.pop(0)
        
        # import 구문 추출
        modules = get_imports_from_file(current_file)
        
        for mod in modules:
            resolved_path = resolve_module_to_path(mod)
            
            # 프로젝트 내부 파일이고, 아직 방문하지 않았다면 추가
            if resolved_path:
                norm_path = os.path.normpath(resolved_path)
                if norm_path not in visited:
                    visited.add(norm_path)
                    to_scan.append(norm_path) # 큐에 추가하여 내부 또 검색
                    
                    found_dependencies.append({
                        "category": "Python Code (Internal)",
                        "path": resolved_path,
                        "desc": f"Imported by {os.path.basename(current_file)}"
                    })
    
    return found_dependencies

# =========================================================
# 도우미 함수: 코드 내용 추출
# =========================================================
def is_binary_file(file_path):
    """
    확장자를 기반으로 이진 파일 여부를 판단합니다.
    """
    binary_extensions = {'.exe', '.dll', '.ttf', '.png', '.jpg', '.jpeg', '.pyc', '.zip'}
    _, ext = os.path.splitext(file_path)
    return ext.lower() in binary_extensions

def save_code_contents(dependencies):
    """
    식별된 모든 텍스트 기반 파일의 내용을 하나의 파일로 병합하여 저장합니다.
    """
    print(f"   [Extract] Saving content of {len(dependencies)} files...")
    
    with open(OUTPUT_CODE_PATH, 'w', encoding='utf-8') as out_f:
        out_f.write("=========================================================\n")
        out_f.write(" AquaNova Source Code Extraction\n")
        out_f.write(f" Generated: {os.times}\n")
        out_f.write("=========================================================\n\n")

        # 경로 기준 정렬
        sorted_deps = sorted(dependencies, key=lambda x: x['path'])
        
        # 중복 방지용
        processed_paths = set()

        for item in sorted_deps:
            path = item['path']
            if path in processed_paths:
                continue
            processed_paths.add(path)

            # 이진 파일 스킵
            if is_binary_file(path):
                out_f.write(f"\n\n# [SKIP] Binary file excluded: {os.path.basename(path)}\n")
                out_f.write("-" * 60 + "\n")
                continue

            # 파일 읽기 및 쓰기
            try:
                out_f.write(f"\n\n{'='*80}\n")
                out_f.write(f" FILE: {os.path.basename(path)}\n")
                out_f.write(f" PATH: {path}\n")
                out_f.write(f" TYPE: {item['category']}\n")
                out_f.write(f"{'='*80}\n\n")
                
                with open(path, 'r', encoding='utf-8', errors='replace') as in_f:
                    out_f.write(in_f.read())
                    
            except Exception as e:
                out_f.write(f"\n[ERROR reading file]: {str(e)}\n")

    print(f"[SUCCESS] 모든 코드가 추출되었습니다: {OUTPUT_CODE_PATH}")

# =========================================================
# 메인 로직: PS1 분석
# =========================================================

def parse_python_module_path(module_str):
    """
    'app.main:app' -> 파일 경로 변환
    """
    if ":" in module_str:
        module_str = module_str.split(":")[0]
    rel_path = module_str.replace(".", os.sep) + ".py"
    return os.path.join(BASE_DIR, rel_path)

def analyze_ps1():
    print(f"Analyzing: {PS1_FILE_PATH}...")
    
    dependencies = []
    python_entry_points = [] # 재귀 검색을 위한 시작점 리스트
    
    # 1. 대상 PS1 파일 자체 추가
    dependencies.append({
        "category": "Launcher Script",
        "path": PS1_FILE_PATH,
        "desc": "메인 실행 스크립트"
    })

    try:
        with open(PS1_FILE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # -------------------------------------------------
        # 2. Python 가상환경
        # -------------------------------------------------
        venv_match = re.search(r'Join-Path \$ScriptDir "(.*?python\.exe)"', content, re.IGNORECASE)
        if venv_match:
            rel_path = venv_match.group(1).lstrip('.\\')
            dependencies.append({
                "category": "Executable",
                "path": os.path.join(BASE_DIR, rel_path),
                "desc": "Python 가상환경 실행 파일"
            })

        # -------------------------------------------------
        # 3. Uvicorn API 진입점
        # -------------------------------------------------
        uvicorn_match = re.search(r"'uvicorn',\s*'(.*?)'", content)
        if uvicorn_match:
            module_str = uvicorn_match.group(1)
            full_path = parse_python_module_path(module_str)
            dependencies.append({
                "category": "Python Code (Entry)",
                "path": full_path,
                "desc": f"API 서버 엔트리포인트 ({module_str})"
            })
            if os.path.exists(full_path):
                python_entry_points.append(full_path)

        # -------------------------------------------------
        # 4. Worker 모듈
        # -------------------------------------------------
        worker_match = re.search(r"'-m',\s*'(.*?)'", content)
        if worker_match:
            module_str = worker_match.group(1)
            if "uvicorn" not in module_str:
                full_path = parse_python_module_path(module_str)
                dependencies.append({
                    "category": "Python Code (Entry)",
                    "path": full_path,
                    "desc": f"백그라운드 워커 ({module_str})"
                })
                if os.path.exists(full_path):
                    python_entry_points.append(full_path)

        # -------------------------------------------------
        # 5. UI (Frontend)
        # -------------------------------------------------
        ui_match = re.search(r'Join-Path \$ScriptDir "ui"', content)
        if ui_match:
            ui_entry = os.path.join(BASE_DIR, "ui", "package.json")
            dependencies.append({
                "category": "Frontend (UI)",
                "path": ui_entry,
                "desc": "UI 프로젝트 설정 파일"
            })
            vite_config = os.path.join(BASE_DIR, "ui", "vite.config.js")
            dependencies.append({
                "category": "Frontend (UI)",
                "path": vite_config,
                "desc": "Vite 번들러 설정"
            })

        # -------------------------------------------------
        # 6. Assets
        # -------------------------------------------------
        font_match = re.search(r'Join-Path \$FontDir "(.*?)"', content)
        if font_match:
            font_file = font_match.group(1)
            font_path = os.path.join(BASE_DIR, ".assets", "fonts", font_file)
            dependencies.append({
                "category": "Assets",
                "path": font_path,
                "desc": "사용 폰트 파일"
            })
            
        # -------------------------------------------------
        # 7. 재귀적 의존성 스캔 실행 (추가된 로직)
        # -------------------------------------------------
        if python_entry_points:
            internal_deps = scan_recursive_dependencies(python_entry_points)
            dependencies.extend(internal_deps)

    except FileNotFoundError:
        print(f"[ERROR] '{PS1_FILE_PATH}' 파일을 찾을 수 없습니다.")
        return

    # =========================================================
    # 결과 파일 작성 (1) 목록 파일
    # =========================================================
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write("=========================================================\n")
        f.write(f"AquaNova 전체 코드 의존성 분석 보고서\n")
        f.write(f"생성 일시: {os.times}\n")
        f.write("=========================================================\n\n")

        dependencies.sort(key=lambda x: (x['category'], x['path']))
        seen_paths = set()
        count = 0
        for item in dependencies:
            if item['path'] in seen_paths:
                continue
            seen_paths.add(item['path'])
            count += 1
            f.write(f"[{count}] {item['category']}\n")
            f.write(f"    - 설명: {item['desc']}\n")
            f.write(f"    - 경로: {item['path']}\n\n")
        
        f.write("=========================================================\n")
        f.write(f"Total Files Found: {count}\n")

    print(f"[SUCCESS] 목록 파일 생성 완료: {OUTPUT_FILE_PATH}")

    # =========================================================
    # 결과 파일 작성 (2) 코드 전체 추출 파일 (추가됨)
    # =========================================================
    save_code_contents(dependencies)

if __name__ == "__main__":
    analyze_ps1()