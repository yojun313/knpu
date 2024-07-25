# -*- coding: utf-8 -*-
import socket
import os
import tkinter as tk
from tkinter import filedialog
import pandas as pd
import platform
import matplotlib.pyplot as plt
class ToolModule:
    def __init__(self):
        if socket.gethostname() == "DESKTOP-502IMU5":
            crawler_folder_path = 'C:/Users/User/Desktop/BIGMACLAB/CRAWLER_ASYNC'
            self.scrapdata_path = os.path.join(crawler_folder_path, 'scrapdata')

        elif socket.gethostname() == "DESKTOP-0I9OM9K":
            crawler_folder_path = 'C:/Users/User/Desktop/BIGMACLAB/CRAWLER_ASYNC'
            self.scrapdata_path = os.path.join(crawler_folder_path, 'scrapdata')

        elif socket.gethostname() == "Yojuns-MacBook-Pro.local":
            crawler_folder_path = '/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER'
            self.scrapdata_path = os.path.join(crawler_folder_path, 'scrapdata')


    def clear_screen(self):
        if platform.system() == "Windows":
            os.system("cls")
        else:
            os.system("clear")

    def file_ask(self, title):
        root = tk.Tk()
        root.withdraw()
        csv_path = filedialog.askopenfilename(initialdir=self.scrapdata_path, title=title,
                                              filetypes=(("CSV files", "*.csv"), ("All files", "*.*")))
        return csv_path

    @staticmethod
    def csvReader(csvPath):
        csv_data = pd.read_csv(csvPath, low_memory=False, index_col=0)
        csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]
        return csv_data

    def typeChecker(self, csv_name):
        crawlType = csv_name.split('_')[0]
        fileType  = csv_name.split('_')[6]
        return {'crawlType': crawlType, 'fileType': fileType}

    def TimeSplitter(self, csv_data, crawlType, fileType):
        date_columns = {
            'NaverNews': {
                'article': 'News Date', 'statistics': 'News Date', 'reply': 'Reply Date', 'rereply': 'Rereply Date'
            },
            'NaverBlog': {
                'article': 'Blog Date', 'reply': 'Reply Date'
            },
            'NaverCafe': {
                'article': 'Cafe Date', 'reply': 'Reply Date'
            },
            'YouTube': {
                'article': 'Video Date', 'reply': 'Reply Date', 'rereply': 'Rereply Date'
            },
            'ChinaDaily': {
                'article': 'News Date'
            },
            'ChinaSina': {
                'article': 'News Date', 'reply': 'Reply Date'
            }
        }

        date_formats = {
            'NaverNews': {
                'article': '%Y.%m.%d.', 'statistics': '%Y.%m.%d.'
            },
            'NaverBlog': {
                'article': '%Y. %m. %d. %H:%M'
            },
            'NaverCafe': {
                'article': '%Y-%m-%d', 'reply': '%Y-%m-%d'
            },
            'ChinaDaily': {
                'article': '%Y-%m-%d %H:%M'
            },
            'ChinaSina': {
                'article': '%Y-%m-%d', 'reply': '%Y-%m-%d %H:%M:%S'
            }
        }

        word = date_columns.get(crawlType, {}).get(fileType)
        format = date_formats.get(crawlType, {}).get(fileType)

        if crawlType == 'NaverNews':
            csv_data[word] = pd.to_datetime(csv_data[word].str.split().str[0], format=format, errors='coerce')
        else:
            csv_data[word] = pd.to_datetime(csv_data[word], format=format, errors='coerce')

        csv_data['year'] = csv_data[word].dt.year
        csv_data['month'] = csv_data[word].dt.month
        csv_data['year_month'] = csv_data[word].dt.to_period('M')
        csv_data['week'] = csv_data[word].dt.to_period('W')

        return csv_data

    def TimeSplitToCSV(self, option, divided_group, data_path):
        # 폴더 이름과 데이터 그룹 설정
        data_group = divided_group
        if option == 1:
            folder_name = "연도별 데이터"
            info_label = 'Year'
        elif option == 2:
            folder_name = "월별 데이터"
            info_label = 'Month'
        elif option == 3:
            folder_name = "주별 데이터"
            info_label = 'Week'

        info = {}

        # 디렉토리 생성
        os.mkdir(data_path + "/" + folder_name)

        # 데이터 그룹을 순회하며 파일 저장 및 정보 수집
        for group_name, group_data in data_group:
            info[str(group_name)] = len(group_data)
            group_data.to_csv(data_path + "/" + folder_name + "/" + str(group_name) + ".csv", index=False,
                              encoding='utf-8-sig', header=True)

        # 정보 파일 생성
        info_df = pd.DataFrame(list(info.items()), columns=[info_label, '개수'])
        info_df.to_csv(data_path + "/" + folder_name + "/" + folder_name + " 개수" + ".csv", index=False,
                       encoding='utf-8-sig', header=True)

        info_df.set_index(info_label, inplace=True)
        keys = list(info_df.index)
        values = info_df['개수'].tolist()

        if option == 1:
            plt.figure(figsize=(10, 6))
        else:
            plt.figure(figsize=(30, 18))

        # 그래프 그리기
        plt.plot(keys, values, marker='o')
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()

        plt.title(f'{info_label} Data Visualization')
        plt.xlabel(info_label)
        plt.ylabel('Values')

        # 그래프 저장
        plt.savefig(f"{data_path}/{folder_name}/{folder_name} 그래프.png")
