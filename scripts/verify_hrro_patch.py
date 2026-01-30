import os
import re
import sys

# ------------------------------------------------------------------------------
# Configuration & Helpers
# ------------------------------------------------------------------------------

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

def get_project_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(script_dir)
    
    app_path = os.path.join(root, 'app')
    ui_path = os.path.join(root, 'ui')
    
    if not os.path.exists(app_path) or not os.path.exists(ui_path):
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, 'app')):
            return cwd
        print(f"{Colors.RED}❌ 루트(code) 추정 실패.{Colors.RESET}")
        sys.exit(1)
        
    return root

def check_patterns(file_path, title, must_have=None, must_not_have=None):
    if must_have is None: must_have = []
    if must_not_have is None: must_not_have = []
    
    result = {
        "title": title,
        "file": file_path,
        "pass": False,
        "reason": "",
        "missing": [],
        "found_bad": []
    }

    if not os.path.exists(file_path):
        result["reason"] = "FILE_NOT_FOUND"
        result["missing"] = must_have
        return result

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        result["reason"] = f"READ_ERROR: {str(e)}"
        return result

    flags = re.DOTALL | re.IGNORECASE

    for pattern in must_have:
        if not re.search(pattern, content, flags):
            result["missing"].append(pattern)

    for pattern in must_not_have:
        if re.search(pattern, content, flags):
            result["found_bad"].append(pattern)

    if not result["missing"] and not result["found_bad"]:
        result["pass"] = True
        result["reason"] = "OK"
    else:
        result["reason"] = "PATTERN_MISMATCH"

    return result

def print_result(r):
    icon = "✅ PASS" if r["pass"] else "❌ FAIL"
    color = Colors.GREEN if r["pass"] else Colors.RED
    print(f"{color}{icon}  {r['title']}{Colors.RESET}")
    # 성공한 경우 파일 경로는 생략하거나 간략히 보여줌 (가독성 위해)
    if not r["pass"]:
        print(f"     File: {r['file']}")
        print(f"     {Colors.YELLOW}Reason: {r['reason']}{Colors.RESET}")
        if r["missing"]:
            print(f"     {Colors.YELLOW}Missing patterns (찾지 못함):{Colors.RESET}")
            for m in r["missing"]:
                print(f"       - {Colors.YELLOW}{m}{Colors.RESET}")
        if r["found_bad"]:
            print(f"     {Colors.YELLOW}Forbidden patterns found (있으면 안됨):{Colors.RESET}")
            for b in r["found_bad"]:
                print(f"       - {Colors.YELLOW}{b}{Colors.RESET}")
        print("")

# ------------------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------------------

def main():
    root = get_project_root()
    print(f"{Colors.CYAN}Root detected: {root}{Colors.RESET}\n")

    path_schemas = os.path.join(root, 'app', 'api', 'v1', 'schemas.py')
    path_engine  = os.path.join(root, 'app', 'services', 'simulation', 'engine.py')
    path_hrro_py = os.path.join(root, 'app', 'services', 'simulation', 'solvers', 'hrro.py')
    path_types_ts = os.path.join(root, 'ui', 'src', 'features', 'flow-builder', 'model', 'types.ts')
    path_utils_ts = os.path.join(root, 'ui', 'src', 'features', 'flow-builder', 'FlowBuilder.utils.ts')
    path_logic_ts = os.path.join(root, 'ui', 'src', 'features', 'flow-builder', 'model', 'logic.ts')
    path_hook_ts  = os.path.join(root, 'ui', 'src', 'features', 'flow-builder', 'hooks', 'useFlowLogic.ts')

    checks = []

    # 1) Backend schemas.py
    checks.append(check_patterns(
        path_schemas,
        'Backend(schemas.py): ScenarioInput.stages의 Stage 모델 정의 존재',
        must_have=[
            r'class\s+ScenarioInput\s*\(',
            r'stages\s*:\s*List\s*\[\s*Stage\s*\]',
            r'class\s+Stage\s*\(',
            r'model_config\s*=\s*ConfigDict\s*\(\s*extra\s*=\s*[\'"]allow[\'"]\s*\)',
            r'type\s*:\s*str\s*=\s*Field\s*\(\s*default\s*=\s*[\'"]RO[\'"]'
        ]
    ))

    # 2) Backend engine.py
    checks.append(check_patterns(
        path_engine,
        'Backend(engine.py): HRRO time_history(TimeSeriesPoint) 생성/StageMetric 바인딩',
        must_have=[
            r'time_history_data\s*:\s*Optional\s*\[\s*List\s*\[\s*TimeSeriesPoint\s*\]\s*\]',
            r'time_history_data\s*=\s*\[\s*TimeSeriesPoint\s*\(',
            r'time_min\s*=',
            r'pressure_bar\s*=',
            r'tds_mgL\s*=',
            r'recovery_pct\s*=',
            r'StageMetric\s*\(',
            r'time_history\s*=\s*time_history_data'
        ]
    ))

    # 3) Backend hrro.py
    checks.append(check_patterns(
        path_hrro_py,
        'Backend(hrro.py): _calc_physics 존재 + steady_state import 미사용',
        must_have=[
            r'def\s+_calc_physics\s*\(',
            r'def\s+simulate_hrro_cycle\s*\(',
            r'_calc_physics\s*\('
        ],
        must_not_have=[
            r'from\s+app\.services\.simulation\.steady_state\s+import',
            r'import\s+steady_state'
        ]
    ))

    # 4) Frontend types.ts HRROConfig advanced
    checks.append(check_patterns(
        path_types_ts,
        'Frontend(types.ts): HRROConfig에 mass_transfer/spacer 정의 존재',
        must_have=[
            r'export\s+type\s+HRROConfig\s*=\s*BaseMembraneConfig\s*&\s*\{',
            r'mass_transfer\?\s*:\s*\{',
            r'spacer\?\s*:\s*\{'
        ]
    ))

    # 5) Frontend types.ts HRRORunOutput.kpi
    checks.append(check_patterns(
        path_types_ts,
        'Frontend(types.ts): HRRORunOutput.kpi가 avg_* 또는 flux/ndp 키를 포함',
        must_have=[
            r'export\s+interface\s+HRRORunOutput\s*\{',
            r'kpi\?\s*:\s*\{',
            r'(avg_flux_lmh\s*\??\s*:|flux_lmh\s*\??\s*:)',
            r'(avg_ndp_bar\s*\??\s*:|ndp_bar\s*\??\s*:)'
        ]
    ))

    # 6) Frontend FlowBuilder.utils.ts HRRO defaultConfig advanced
    checks.append(check_patterns(
        path_utils_ts,
        'Frontend(FlowBuilder.utils.ts): HRRO defaultConfig에 mass_transfer/spacer 기본값 포함',
        must_have=[
            r'if\s*\(\s*k\s*===\s*[\'"]HRRO[\'"]\s*\)\s*\{',
            r'mass_transfer\s*:\s*\{',
            r'spacer\s*:\s*\{'
        ]
    ))

    # 7) Frontend logic.ts toStagePayload(HRRO)
    checks.append(check_patterns(
        path_logic_ts,
        'Frontend(logic.ts): toStagePayload(HRRO)에서 pressure_bar + mass_transfer/spacer 포함',
        must_have=[
            r'function\s+toStagePayload\s*\(',
            r'd\.kind\s*===\s*[\'"]HRRO[\'"]',
            r'type\s*:\s*[\'"]HRRO[\'"]',
            r'pressure_bar\s*:',
            r'mass_transfer\s*:',
            r'spacer\s*:'
        ],
        must_not_have=[
            r'p_set_bar\s*:'
        ]
    ))

    # 8) Frontend logic.ts toHRROStage
    checks.append(check_patterns(
        path_logic_ts,
        'Frontend(logic.ts): toHRROStage에서 pressure_bar + mass_transfer/spacer 포함',
        must_have=[
            r'function\s+toHRROStage\s*\(',
            r'pressure_bar\s*:',
            r'mass_transfer\s*:',
            r'spacer\s*:'
        ],
        must_not_have=[
            r'p_set_bar\s*:'
        ]
    ))

    # 9) Frontend logic.ts applyHRROChips
    checks.append(check_patterns(
        path_logic_ts,
        'Frontend(logic.ts): applyHRROChips가 kpi.avg_* / kpi.* 둘 다 수용',
        must_have=[
            r'function\s+applyHRROChips\s*\(',
            r'avg_flux_lmh',
            r'flux_lmh',
            r'avg_ndp_bar',
            r'ndp_bar'
        ]
    ))

    # 10) Frontend useFlowLogic.ts finalStages(HRRO)
    checks.append(check_patterns(
        path_hook_ts,
        'Frontend(useFlowLogic.ts): finalStages(HRRO)에서 advanced 유지 + cfg.p_set_bar 강제 덮어쓰기 패턴 제거',
        must_have=[
            r'if\s*\(\s*kind\s*===\s*[\'"]HRRO[\'"]\s*\)\s*\{',
            r'pressure_bar\s*:',
            r'mass_transfer\s*:',
            r'spacer\s*:'
        ],
        must_not_have=[
            r'pressure_bar\s*:\s*cfg\.p_set_bar\s*\|\|\s*28(\.0)?'
        ]
    ))

    # -------------------------
    # 결과 출력 및 요약
    # -------------------------
    pass_count = 0
    for r in checks:
        print_result(r)
        if r['pass']:
            pass_count += 1

    total = len(checks)

    print("-" * 40)
    summary_color = Colors.GREEN if pass_count == total else Colors.YELLOW
    print(f"{summary_color}Summary: {pass_count}/{total} checks passed{Colors.RESET}")
    print("-" * 40)

    if pass_count != total:
        sys.exit(1)
    
    sys.exit(0)

if __name__ == "__main__":
    main()