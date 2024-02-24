import os
import pandas as pd

def merge_csv_files(folder_path, output_file):
    # 지정된 폴더 내의 모든 파일 목록 가져오기
    
    files = os.listdir(folder_path)
    
    # CSV 파일만 선택하기
    csv_files = [file for file in files if file.endswith('.csv')]
    
    # 빈 DataFrame 생성
    merged_df = pd.DataFrame()
    
    # 각 CSV 파일을 읽어서 병합하기
    for file in csv_files:
        file_path = os.path.join(folder_path, file)
        df = pd.read_csv(file_path)
        merged_df = pd.concat([merged_df, df], ignore_index=True)
    
    # 결과를 하나의 CSV 파일로 저장하기
    merged_df.to_csv(output_file, index=False)
    print(f"Merged CSV files saved to {output_file}")

# 파이썬 파일이 위치한 폴더의 경로를 가져오기
current_directory = os.path.dirname(os.path.abspath(__file__))

# 폴더 경로와 병합된 파일의 이름을 지정합니다.
folder_path = current_directory
output_file = input("병합 파일명을 입력해주세요: ")
output_file = output_file + ".csv"

# CSV 파일 병합 실행
merge_csv_files(folder_path, output_file)