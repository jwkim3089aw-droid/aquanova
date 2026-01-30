# ./scripts/tree.py

import os

def print_tree(root_dir):
    for current_path, dirs, files in os.walk(root_dir):
        # 현재 깊이 계산
        depth = current_path.replace(root_dir, "").count(os.sep)
        indent = "    " * depth
        print(f"{indent}{os.path.basename(current_path)}/")
        
        # 파일 출력
        for f in files:
            print(f"{indent}    {f}")

# 현재 폴더 기준
print_tree("app")
