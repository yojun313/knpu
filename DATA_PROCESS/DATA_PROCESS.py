import pandas as pd
from collections import OrderedDict
from collections import Counter
import os
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog
import sys
import socket
import warnings
import platform
warnings.filterwarnings('ignore', category=UserWarning)


class data_process:
    def __init__(self):
        # 연구실 3번 컴퓨터
        if socket.gethostname() == "DESKTOP-HQK7QRT":
            self.scrapdata_path = "C:/Users/qwe/Desktop/VSCODE/CRAWLER/scrapdata"
            self.projectfolder_path = "C:/Users/qwe/Desktop/VSCODE/PROJECT"
        
        # HP OMEN
        elif socket.gethostname() == "DESKTOP-502IMU5":
            self.scrapdata_path = "C:/Users/User/Desktop/BIGMACLAB/CRAWLER/scrapdata"
            self.projectfolder_path = "C:/Users/User/Desktop/BIGMACLAB/PROJECT"
        
        # HP Z8
        elif socket.gethostname() == "DESKTOP-0I9OM9K":
            self.scrapdata_path = "C:/Users/User/Desktop/BIGMACLAB/CRAWLER/scrapdata"
            self.projectfolder_path = "C:/Users/User/Desktop/BIGMACLAB/PROJECT"
            
        # Yojun's MacBook Pro
        elif socket.gethostname() == "Yojuns-MacBook-Pro.local":
            self.scrapdata_path = "/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER/scrapdata"
            self.projectfolder_path = "/Users/yojunsmacbookprp/Documents/BIGMACLAB/PROJECT"

        
    def main(self):
        print("\n1. 파일 분할\n2. URL 제외\n3. URL 포함")
        while True:
            big_option = input("\n입력: ")
            if big_option in ["1", "2", "3"]:
                break
            else:
                print("다시 입력하세요")
                
        if big_option == "1":
            
            self.option_1()
            
            self.clear_screen()
            
            print("[파일 분할]\n")
            print("대상 csv 파일:", self.csv_path)
            print("완성 파일:", self.data_path)
            
        elif big_option == "2":
            
            self.option_2()
            
            self.clear_screen()
            
            print("[URL 제외]\n")
            print("대상 csv 파일:", self.csv_path)
            print("제외 url 파일:", self.exception_url_csv_path)
            print("완성 파일:", self.exception_url_csv_folder_path + "/" + self.file_name.replace(".csv", "") + "_url 제외.csv")
    
        
        elif big_option == "3":
            
            self.option_3()
            
            self.clear_screen()
            
            print("[URL 포함]\n")
            print("대상 csv 파일:", self.csv_path)
            print("포함 url 파일:", self.include_url_csv_csv_path)
            print("완성 파일:", self.exception_url_csv_folder_path + "/" + self.file_name.replace(".csv", "") + "_url 포함.csv")
        
            
    def option_1(self):
        self.clear_screen()
        self.csv_path = self.file_ask(self.scrapdata_path, "분할할 csv 파일을 선택하세요")
        
        # csv 저장된 폴더 경로 및 csv 파일 이름
        self.folder_path = os.path.dirname(self.csv_path)
        self.file_name = os.path.basename(self.csv_path)
        
        # 데이터 저장하는 경로
        self.data_path = self.folder_path + "/" + self.file_name.replace(".csv", "") + "_분할 데이터"
        
        try:
            os.mkdir(self.data_path)
        except:
            pass
    
        # 데이터프레임으로 변환
        self.csv_data = pd.read_csv(self.csv_path, low_memory = False, index_col = 0)
        self.csv_data = self.csv_data.loc[:, ~self.csv_data.columns.str.contains('^Unnamed')]

        # 뉴스 기사
        if "article" in self.file_name:
            self.csv_data['article date'] = pd.to_datetime(self.csv_data['article date'].str.split().str[0], format='%Y.%m.%d.', errors='coerce')
            self.csv_data['year'] = self.csv_data['article date'].dt.year
            self.csv_data['month'] = self.csv_data['article date'].dt.month
            self.csv_data['year_month'] = self.csv_data['article date'].dt.to_period('M')
            
        # 댓글
        elif "reply" in self.file_name:
            self.csv_data['reply date'] = pd.to_datetime(self.csv_data['reply_date'], errors='coerce')
            self.csv_data['year'] = self.csv_data['reply date'].dt.year
            self.csv_data['month'] = self.csv_data['reply date'].dt.month
            self.csv_data['year_month'] = self.csv_data['reply date'].dt.to_period('M')
        
        # 대댓글
        elif "rereply" in self.file_name:
            self.csv_data['rereply date'] = pd.to_datetime(self.csv_data['rereply_date'], errors='coerce')
            self.csv_data['year'] = self.csv_data['rereply date'].dt.year
            self.csv_data['month'] = self.csv_data['rereply date'].dt.month
            self.csv_data['year_month'] = self.csv_data['rereply date'].dt.to_period('M')
        
        # 유튜브 정보
        elif "info" in self.file_name:
            self.csv_data['video date'] = pd.to_datetime(self.csv_data['video_date'].str.split().str[0], format='%Y.%m.%d.', errors='coerce')
            self.csv_data['year'] = self.csv_data['video date'].dt.year
            self.csv_data['month'] = self.csv_data['video date'].dt.month
            self.csv_data['year_month'] = self.csv_data['video date'].dt.to_period('M')
        
        # 연도별로, 월별로 나눈 데이터
        self.year_divided_group = self.csv_data.groupby('year')
        self.month_divided_group = self.csv_data.groupby('year_month')
        
        print("\n1. 연도별로 csv 분할\n2. 월별로 csv 분할\n3. 둘 다\n4. 종료")
            
        while True:
            option = input("\n입력: ")
            if option in ["1", "2", "3"]:
                break
            else:
                print("다시 입력하세요")
        
        print("\n처리 중...")
        
        if option == '1':
            self.divide_data(1)
        
        elif option == '2':
            self.divide_data(2)
        
        elif option == '3':
            self.divide_data(1)
            self.divide_data(2)
        
        else:
            sys.exit()
        
        print("\n완료")
        
    def option_2(self):
        self.clear_screen()
        self.csv_path = self.file_ask(self.scrapdata_path, "대상 csv 파일을 선택하세요")
        
        # csv 파일 저장된 폴더 경로
        self.folder_path = os.path.dirname(self.csv_path)
        
        # csv 파일 이름
        self.file_name = os.path.basename(self.csv_path)
    
        self.exception_url_csv_path = self.file_ask(self.projectfolder_path, "제외 URL csv를 선택하세요")
        self.exception_url_csv_folder_path = os.path.dirname(self.exception_url_csv_path)
        
        self.origin_csv_data = pd.read_csv(self.csv_path, low_memory = False)
        self.origin_csv_data = pd.DataFrame(self.origin_csv_data)
        self.origin_csv_data = self.origin_csv_data.dropna(subset=['url'])
        
        exception_url_list = pd.read_csv(self.exception_url_csv_path, sep='\t', header = None).values.flatten().tolist()

        self.origin_csv_data = self.origin_csv_data[~self.origin_csv_data['url'].isin(exception_url_list)]
        self.origin_csv_data.to_csv(self.exception_url_csv_folder_path + "/" + self.file_name.replace(".csv", "") + "_url 제외.csv", encoding = 'utf-8-sig', index = False)

    def option_3(self):
        self.clear_screen()
        
        self.csv_path = self.file_ask(self.scrapdata_path, "대상 csv 파일을 선택하세요")
        
        # csv 파일 저장된 폴더 경로
        self.folder_path = os.path.dirname(self.csv_path)
        
        # csv 파일 이름
        self.file_name = os.path.basename(self.csv_path)
    
        self.include_url_csv_path = self.file_ask(self.projectfolder_path, "포함할 URL csv를 선택하세요")
        self.include_url_csv_folder_path = os.path.dirname(self.include_url_csv_path)
        
        # 원본 데이터 로드
        self.origin_csv_data = pd.read_csv(self.csv_path, low_memory=False)
        self.origin_csv_data = pd.DataFrame(self.origin_csv_data)
        self.origin_csv_data = self.origin_csv_data.dropna(subset=['url'])
        
        # 포함할 URL 리스트 로드
        include_url_list = pd.read_csv(self.include_url_csv_path, sep='\t', header = None).values.flatten().tolist()

        # 포함할 URL에 해당하는 데이터만 필터링
        self.origin_csv_data = self.origin_csv_data[self.origin_csv_data['url'].isin(include_url_list)]
        self.origin_csv_data.to_csv(self.include_url_csv_folder_path + "/" + self.file_name.replace(".csv", "") + "_URL 포함.csv", encoding='utf-8-sig', index=False)

    def divide_data(self, option):
        
        # 연도별로 나누기
        if option == 1:
            info_year = {}
            os.mkdir(self.data_path + "/" + "연도별 데이터")
            
            for group_name, group_data in self.year_divided_group:
                info_year[group_name] = len(group_data)
                group_data.to_csv(self.data_path + "/" + "연도별 데이터" + "/" + str(int(group_name)) + ".csv", index = False, encoding='utf-8-sig', header = True)
            
            year_info = pd.DataFrame(list(info_year.items()), columns=['Year', '개수'])
            year_info.to_csv(self.data_path + "/" + "연도별 데이터" + "/" + "연도별 개수" + ".csv", index = False, encoding='utf-8-sig', header = True)
            
            self.save_graph(info_year, "year")
            
        # 월별로 나누기
        if option == 2:
            info_month = {}
            os.mkdir(self.data_path + "/" + "월별 데이터")
            
            for group_name, group_data in self.month_divided_group:
                info_month[str(group_name)] = len(group_data)
                group_data.to_csv(self.data_path + "/" + "월별 데이터" + "/" + str(group_name) + ".csv", index = False, encoding='utf-8-sig', header = True)

            month_info = pd.DataFrame(list(info_month.items()), columns=['month', '개수'])
            month_info.to_csv(self.data_path + "/" + "월별 데이터" + "/" + "월별 개수" + ".csv", index = False, encoding='utf-8-sig', header = True)
            
            self.save_graph(info_month, "month")
    
    def save_graph(self, dic, option):
        keys = list(dic.keys())
        values = list(dic.values())

        if option == "year":
            plt.figure(figsize=(10, 6))
            plt.plot(keys, values, marker='o')
            plt.grid(True)
            plt.xticks(keys, rotation=45)
            plt.tight_layout()
            
            for i in range(len(keys)):
                plt.text(keys[i], values[i], str(values[i]), ha='center', va='bottom')
            plt.title('Yearly Data Visualization')
            plt.xlabel('Year')
            plt.ylabel('Values')
            plt.savefig(self.data_path + "/연도별 데이터/" + "연도별 데이터 그래프.png")
            
        elif option == "month":
            plt.figure(figsize=(30, 18))
            plt.plot(keys, values, marker='o')
            plt.grid(True)
            plt.xticks(keys, rotation=45)
            plt.tight_layout()
            
            plt.title('Monthly Data Visualization')
            plt.xlabel('Month')
            plt.ylabel('Values')
            plt.savefig(self.data_path + "/월별 데이터/" + "월별 데이터 그래프.png")


    def file_ask(self, initialdir, title):
        root = tk.Tk()
        root.withdraw()
        csv_path = filedialog.askopenfilename(initialdir=initialdir, title=title, filetypes = (("CSV files", "*.csv"), ("All files", "*.*")))
        return csv_path

    def clear_screen(self):
        if platform.system() == "Windows":
            os.system("cls")
        else:
            os.system("clear")



print("실행 중...")


data_process = data_process()
data_process.main()