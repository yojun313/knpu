import os
import pandas as pd
import socket
import time
import sys

# HP Z8
if socket.gethostname() == "DESKTOP-0I9OM9K":
    folder_path = "C:/Users/User/Desktop/BIGMACLAB/CRAWLER/scrapdata/FASTCRAWLER_병합폴더"
    scrapdata_path = "C:/Users/User/Desktop/BIGMACLAB/CRAWLER/scrapdata/"
    
elif socket.gethostname() == "DESKTOP-502IMU5":
    folder_path = "C:/Users/User/Desktop/BIGMACLAB/CRAWLER/scrapdata/FASTCRAWLER_병합폴더"
    scrapdata_path = "C:/Users/User/Desktop/BIGMACLAB/CRAWLER/scrapdata/"

import os

def get_all_folder_paths(root_folder):
    folder_paths = []
    for dirpath, dirnames, filenames in os.walk(root_folder):
        for dirname in dirnames:
            folder_path = os.path.join(dirpath, dirname)
            folder_path = folder_path.replace('\\', '/')
            folder_paths.append(folder_path)
    return folder_paths

def get_all_file_paths(root_folder):
    file_paths = []
    for dirpath, dirnames, filenames in os.walk(root_folder):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            file_path = file_path.replace("\\", '/')
            file_paths.append(file_path)
    return file_paths

print("파일 병합 중... 프로그램이 종료되면 scrapdata 폴더를 확인하세요")

# 특정 폴더 내의 모든 폴더 경로 가져오기
all_folder_paths = get_all_folder_paths(folder_path)

keyword = os.path.basename(all_folder_paths[0]).split('_')[2]
for folder_path in all_folder_paths:
    if os.path.basename(folder_path).split('_')[2] != keyword:
        print("\n폴더의 Keyword(검색어)가 모두 일치해야 합니다.. 프로그램 종료")
        time.sleep(5)
        sys.exit()

all_file_list = []
all_file_list_sorted = []
all_article_statistics_list = []
all_article_list = []
all_reply_list = []
all_rereply_list = []
all_log_list = []

for folder_path in all_folder_paths:
    all_file_list.append(get_all_file_paths(folder_path))

for folder in all_file_list:
    for file in folder:
        if "article(statistics).csv" in file:
            all_article_statistics_list.append(file)
        elif "article.csv" in file:
            all_article_list.append(file)
        elif "reply.csv" in file:
            all_reply_list.append(file)
        elif "rereply.csv" in file:
            all_rereply_list.append(file)

all_file_list_sorted.append(all_article_list)
all_file_list_sorted.append(all_article_statistics_list)
all_file_list_sorted.append(all_reply_list)
all_file_list_sorted.append(all_rereply_list)

start_year = all_article_list[0].split('_')[4]
end_year = all_article_list[len(all_article_list)-1].split('_')[5]
new_folder_name = os.path.basename(all_folder_paths[0]).replace(all_folder_paths[0].split('_')[5], end_year)
new_folder_path = scrapdata_path + new_folder_name

try:
    os.makedirs(new_folder_path)
except:
    print("\n이미 병합된 폴더가 존재합니다.. 프로그램 종료")
    time.sleep(5)
    sys.exit()

for file_list in all_file_list_sorted:
    if file_list != []:
        merged_df = pd.DataFrame()
        
        for file in file_list:
            df = pd.read_csv(file, encoding='utf-8-sig') # 여기에 인코딩을 지정합니다.
            merged_df = pd.concat([merged_df, df], ignore_index=True)
            
        if "article(statistics).csv" in file_list[0]:
            output_file = new_folder_name + "_article(statistics).csv"
            merged_df.to_csv(new_folder_path + '/' +output_file, index=False, encoding='utf-8-sig')
        
        elif "article.csv" in file_list[0]:
            output_file = new_folder_name + "_article.csv"
            merged_df.to_csv(new_folder_path + '/' +output_file, index=False, encoding='utf-8-sig')

        elif "reply.csv" in file_list[0]:
            output_file = new_folder_name + "_reply.csv"
            merged_df.to_csv(new_folder_path + '/' +output_file, index=False, encoding='utf-8-sig')
        
        elif "rereply.csv" in file_list[0]:
            output_file = new_folder_name + "_rereply.csv"
            merged_df.to_csv(new_folder_path + '/' +output_file, index=False, encoding='utf-8-sig')
            
