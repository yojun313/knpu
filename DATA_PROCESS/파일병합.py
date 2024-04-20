import os
import pandas as pd
import socket
import sys

sys.dont_write_bytecode = True

# HP Z8
if socket.gethostname() == "DESKTOP-0I9OM9K":
    folder_path = "C:/Users/User/Desktop/BIGMACLAB/CRAWLER/scrapdata/파일병합폴더"
    
elif socket.gethostname() == "DESKTOP-502IMU5":
    folder_path = "C:/Users/User/Desktop/BIGMACLAB/CRAWLER/scrapdata/파일병합폴더"

def merge_csv_files(folder_path, output_file):
    # 지정된 폴더 내의 모든 파일 목록 가져오기
    files = os.listdir(folder_path)
    
    # CSV 파일만 선택하기
    csv_files = [file for file in files if file.endswith('.csv')]
    
    # 빈 DataFrame 생성
    merged_df = pd.DataFrame()
    
    # 각 CSV 파일을 읽어서 병합하기, 인코딩 지정 추가
    for file in csv_files:
        file_path = os.path.join(folder_path, file)
        df = pd.read_csv(file_path, encoding='utf-8-sig') # 여기에 인코딩을 지정합니다.
        merged_df = pd.concat([merged_df, df], ignore_index=True)
    
    # 결과를 하나의 CSV 파일로 저장하기, 인코딩 지정 추가
    merged_df.to_csv(output_file, index=False, encoding='utf-8-sig') # 여기에 인코딩을 지정합니다.
    print(f"Merged CSV files saved to {output_file}")

# 실행 부분 (__file__ 사용 부분 제거, 대신 직접 경로 지정 또는 입력받기 필요)
# 병합 파일명 입력 받기
if __name__ == "__main__":
    output_file = input("병합 파일명을 입력해주세요: ")
    output_file = folder_path + "/" + output_file + ".csv"

    # CSV 파일 병합 실행 (folder_path 직접 지정 또는 입력 받기 필요)
    merge_csv_files(folder_path, output_file)
