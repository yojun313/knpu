import os
import sys
import pandas as pd

def parquet_to_csv(parquet_path: str) -> str:
    """
    주어진 Parquet 파일을 읽어 같은 위치에 CSV 파일로 저장하고,
    생성된 CSV 파일 경로를 반환한다.
    """
    # 파일 존재 여부 확인
    if not os.path.isfile(parquet_path):
        raise FileNotFoundError(f"Parquet 파일을 찾을 수 없습니다: {parquet_path}")

    # Parquet 읽기
    df = pd.read_parquet(parquet_path)

    # 확장자만 .csv로 교체
    base, _ = os.path.splitext(parquet_path)
    csv_path = base + '.csv'

    # CSV로 저장 (인덱스 제외)
    df.to_csv(csv_path, index=False)
    return csv_path

if __name__ == "__main__":
    parquet_file = input("변환할 Parquet 파일 경로를 입력하세요: ").strip()
    try:
        output_csv = parquet_to_csv(parquet_file)
        print(f"CSV 파일이 성공적으로 생성되었습니다: {output_csv}")
    except Exception as e:
        print(f"오류 발생: {e}")
        sys.exit(1)
