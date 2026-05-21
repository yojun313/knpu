import ast
import os


def parse_imports_from_file(file_path):
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        tree = ast.parse(content, filename=file_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # import a.b.c에서 최상위 패키지 이름만 추출 (예: 'a')
                    top_level = alias.name.split(".")[0]
                    imports.add(top_level)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:  # 절대 임포트만 수집
                    top_level = node.module.split(".")[0]
                    imports.add(top_level)
    except (UnicodeDecodeError, SyntaxError):
        pass
    return imports


def get_all_imports_in_directory(target_dir):
    all_imports = set()
    
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                file_imports = parse_imports_from_file(file_path)
                all_imports.update(file_imports)
                
    return sorted(list(all_imports))


if __name__ == "__main__":
    # 분석하고 싶은 대상 디렉토리 경로 (현재 디렉토리는 '.')
    target_directory = "." 
    
    result = get_all_imports_in_directory(target_directory)
    
    print(f"\n--- [{os.path.abspath(target_directory)}] 임포트 목록 ---")
    for module in result:
        print(module)