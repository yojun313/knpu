import os

def count_py_lines(directory: str) -> None:
    total_lines = 0
    file_count = 0

    # os.walk로 하위 디렉토리까지 모두 탐색
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        line_count = len(lines)
                        total_lines += line_count
                        file_count += 1
                        print(f"{file_path}: {line_count} 줄")
                except Exception as e:
                    print(f"[오류] {file_path} 읽기 실패: {e}")

    print(f"\n총 {file_count}개의 .py 파일")
    print(f"총 줄 수: {total_lines} 줄")

if __name__ == "__main__":
    target_dir = input("디렉토리 경로를 입력하세요: ").strip()
    if os.path.isdir(target_dir):
        count_py_lines(target_dir)
    else:
        print("유효한 디렉토리 경로가 아닙니다.")
