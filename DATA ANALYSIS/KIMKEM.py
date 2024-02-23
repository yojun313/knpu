import pandas as pd
import os
import sys
from kiwipiepy import Kiwi
from tqdm import tqdm
from collections import Counter
import socket
import tkinter as tk
from tkinter import filedialog
import warnings
import matplotlib.pyplot as plt
import datetime
import platform
plt.rcParams['axes.unicode_minus'] =False

warnings.filterwarnings('ignore', category=UserWarning)

class kimkem:
    def __init__(self):
        
        if platform.system() == "Windows":
            plt.rcParams['font.family'] ='Malgun Gothic'
        else:
            plt.rcParams['font.family'] = 'AppleGothic'

        self.now = datetime.datetime.now()
        self.kiwi = Kiwi(num_workers=8)
        
        # Yojun Moon MacBook Pro
        if socket.gethostname() == "Yojuns-MacBook-Pro.local":
            self.scrapdata_path = "/Users/yojunsmacbookprp/Documents/scrapdata" # scrapdata 폴더 경로
            self.kimkem_data_path = "/Users/yojunsmacbookprp/Documents/DATA ANALYSIS/kimkem_data" # kimkem_data_path 폴더 경로
            self.token_data_path = "/Users/yojunsmacbookprp/Documents/DATA ANALYSIS/token_data"
            self.exception_list = "/Users/yojunsmacbookprp/Documents/DATA ANALYSIS/exception_list"
        # 연구실 3번 컴퓨터 
        elif socket.gethostname() == "DESKTOP-HQK7QRT":
            self.scrapdata_path = "C:/Users/qwe/Desktop/VSCODE/CRAWLER/scrapdata"
            self.kimkem_data_path = "C:/Users/qwe/Desktop/VSCODE/DATA ANALYSIS/kimkem_data"
            self.token_data_path = "C:/Users/qwe/Desktop/VSCODE/DATA ANALYSIS/token_data"
            self.exception_list = "C:/Users/qwe/Desktop/VSCODE/DATA ANALYSIS/exception_list"
        
        print("==============KIM KEM==============")
        print("[옵션을 선택하세요]\n")
        print("1. 토큰 파일 생성하기 및 KIMKEM 분석")
        print("2. 토큰 파일 불러오기 및 KIMKEM 분석")
        print("3. 그래프 그리기")
        print("4. 프로그램 종료")
        
        while True:
            option_num = input("\n입력: ")
            if option_num in ["1", "2", "3", "4"]:
                option_num = int(option_num)
                
                if option_num == 4:
                    sys.exit()
                break
            else:
                print("다시 입력하세요")
        
        # main 함수에 option 번호를 넣어 실행
        self.main(option_num)
        
    def main(self, option_num):
        
        if option_num != 3:
            self.startyear = int(input("\n분석 시작 연도를 입력하세요: "))
            self.word_num = int(input("상위 단어 개수를 입력하세요: ")) 
            self.exception_word_list, self.except_option_display = self.make_exception()
        
        self.clear_screen()
        
        if option_num == 1:
            self.folder_path = filedialog.askdirectory(initialdir = self.scrapdata_path, title="Select folder")
            self.folder_name = self.folder_path.split("/")[-1].replace("_article.csv", "")
            self.kimkem_folder_path = f"{self.kimkem_data_path}/kimkem_{self.folder_name} (start={self.startyear} topword={self.word_num} except={self.except_option_display} time={self.now.strftime("%m%d_%H%M%S")})"
            try:
                os.mkdir(self.kimkem_folder_path) # 테스트시 끄기
            except:
                pass
            
            print("==================================KIM KEM==================================")
            print("분석 시작 연도:", self.startyear)
            print("상위 단어 개수:", self.word_num)
            print("파일 경로:", self.folder_path)
            print("===========================================================================\n\n처리 중...")
            
            self.file_list = [file for file in os.listdir(self.folder_path) if file.endswith('.csv')]
            
            for file in self.file_list:
                if "article" in file:
                    self.token_file = self.tokenization(file)
            
            self.make_kimkem(self.token_file)
            print("\n완료")
        
        elif option_num == 2:
            self.token_file = filedialog.askopenfilename(initialdir = self.token_data_path, title="Select token file", filetypes=(("CSV files", "*.csv"), ("All files", "*.*")))
            self.folder_name = self.token_file.split("/")[-1].replace("token_", "")
            self.kimkem_folder_path = f"{self.kimkem_data_path}/kimkem_{self.folder_name} (start={self.startyear} topword={self.word_num} except={self.except_option_display} time={self.now.strftime("%m%d_%H%M%S")})"
            try:
                os.mkdir(self.kimkem_folder_path) # 테스트시 끄기
            except:
                pass
            
            print("==================================KIM KEM==================================")
            print("분석 시작 연도:", self.startyear)
            print("상위 단어 개수:", self.word_num)
            print("파일 이름:", self.folder_name)
            print("===========================================================================\n\n처리 중...")
            self.make_kimkem(self.token_file)
            print("\n완료")

        elif option_num == 3:
            self.coordinates_draw_graph()
##################################################### token 생성부 #######################################################

    # 파일 입력하면 token화한 후 파일 저장 및 token 파일 경로 반환
    def tokenization(self, file_name):
        data = pd.read_csv(self.folder_path + "/" + file_name, engine='python', index_col = 0)
        data = data.loc[:, ~data.columns.str.contains('^Unnamed')]
        
        check = file_name.split("_")
        
        if check[0] == 'Naver' and check[1] == 'News':
            type = check[0] + "_" + check[1] + "_" + check[7]
            if check[7] == 'article.csv':
                analysis_data = list(data['article body'])
                data['article body'] = [str(sublist).strip('[]') for sublist in self.token_analysis(analysis_data, type)]

            elif check[7] == 'reply.csv':
                analysis_data = list(data['reply'])
                data['reply'] = [str(sublist).strip('[]') for sublist in self.token_analysis(analysis_data, type)]
                
            elif check[7] == 'rereply.csv':
                analysis_data = list(data['rereply'])
                data['rereply'] = [str(sublist).strip('[]') for sublist in self.token_analysis(analysis_data, type)]
                
            else:
                print("파일 형태가 올바르지 않습니다")
        
        token_file = self.token_data_path + "/" + "token_" + file_name
        data.to_csv(token_file, index = True, header = True, encoding = 'utf-8-sig')
        
        return token_file
    # 데이터 넣으면 kiwi token화 실행
    def token_analysis(self, analysis_data, type):
        sentence_list = []
        small_list = []
        for i in tqdm(range(len(analysis_data)), desc = type+" 분석 중: ", ncols = 150):
            sentence = analysis_data[i]
            result = self.kiwi.tokenize(str(sentence))
            for word_data in result:
                if word_data[1] == 'NNG' or word_data[1] == "NNP":
                    small_list.append(word_data[0])
            sentence_list.append(small_list)
            small_list = []
        print("")
        return sentence_list


##################################################### KIM KEM 생성부 #####################################################

    def make_kimkem(self, token_file):
        year_divided_group, csv_data = self.divide_period(token_file) 

        yyear_divided_dic = {}
        
        if "article" in token_file:
            for group_name, group_data in year_divided_group:
                yyear_divided_dic[str(int(group_name))] = group_data['article body'].tolist()
            article_kimkem_folder = self.kimkem_folder_path
            
            yyear_divided_dic = {key: value for key, value in yyear_divided_dic.items() if int(key) >= self.startyear} 

        year_divided_dic = {}
        for key, string_list in yyear_divided_dic.items():
            word_lists = []
            for string in string_list:
                try:
                    words = words = [word.strip().strip("'") for word in string.split(',')]
                    word_lists.append(words)
                except:
                    pass
            year_divided_dic[key] = word_lists
        
        year_divided_dic_merged = {key: [item for sublist in value for item in sublist] for key, value in year_divided_dic.items()} # value가 1차원 리스트
        top_common_words = {k: [item for item, count in Counter(v).most_common(self.word_num)] for k, v in year_divided_dic_merged.items()}
            
        intersection = set.intersection(*[set(value) for value in top_common_words.values()])
        
        keyword_list = [word for word in list(intersection) if len(word) >= 2]

        tf_counts = self.cal_tf(keyword_list, year_divided_dic_merged) 
        df_counts = self.cal_df(keyword_list, year_divided_dic)
        DoV_dict = self.cal_DoV(keyword_list, year_divided_dic, tf_counts)
        DoD_dict = self.cal_DoD(keyword_list, year_divided_dic, df_counts)
        
        tf_folder = article_kimkem_folder + '/' + "article_TF"
        df_folder = article_kimkem_folder + '/' + "article_DF"
        DoV_folder = article_kimkem_folder + '/' + "article_DoV"
        DoD_folder = article_kimkem_folder + '/' + "article_DoD"
        signal_folder = article_kimkem_folder + '/' + "signal"
        graph_folder = article_kimkem_folder + '/' + "graph"
        
        
        os.mkdir(tf_folder)
        os.mkdir(df_folder)
        os.mkdir(DoV_folder)
        os.mkdir(DoD_folder)
        os.mkdir(signal_folder)
        os.mkdir(graph_folder)
        
        
        for year in tf_counts:
                
            tf = pd.DataFrame(list(tf_counts[year].items()), columns=['keyword', 'TF'])
            tf.to_csv(tf_folder + "/" + str(year) + "_TF.csv", index = False, encoding='utf-8-sig')
            
            df = pd.DataFrame(list(df_counts[year].items()), columns=['keyword', 'DF'])
            df.to_csv(df_folder + "/" + str(year) + "_DF.csv", index = False, encoding='utf-8-sig')
            
            DoV = pd.DataFrame(list(DoV_dict[year].items()), columns=['keyword', 'DoV'])
            DoV.to_csv(DoV_folder + "/" + str(year) + "_DoV.csv", index = False, encoding='utf-8-sig')
            
            DoD = pd.DataFrame(list(DoD_dict[year].items()), columns=['keyword', 'DoV'])
            DoD.to_csv(DoD_folder + "/" + str(year) + "_DoD.csv", index = False, encoding='utf-8-sig')

        year_list = list(tf_counts.keys())
        max_year, min_year = max(year_list), min(year_list)
        
        avg_DoV_increase_rate = {}
        avg_DoD_increase_rate = {}
        avg_term_frequency = {}
        avg_doc_frequency = {}
        for word in keyword_list:
            # DoV 평균 증가율
            avg_DoV_increase_rate[word] = (((DoV_dict[max_year][word]/DoV_dict[min_year][word])**(1/(int(max_year)-int(min_year))))-1)*100
            
            # DoD 평균 증가율
            avg_DoD_increase_rate[word] = (((DoD_dict[max_year][word]/DoD_dict[min_year][word])**(1/(int(max_year)-int(min_year))))-1)*100
            
            # Term 평균 빈도
            term_sum = 0
            for year in year_list:
                term_sum += tf_counts[year][word]
            avg_term_frequency[word] = term_sum / len(year_list)
            
            # Document 평균 빈도
            doc_sum = 0
            for year in year_list:
                doc_sum += df_counts[year][word]
            avg_doc_frequency[word] = doc_sum / len(year_list)
        
        DoV_strong_signal, DoV_weak_signal, DoV_latent_signal, DoV_well_known_signal = self.DoV_draw_graph(avg_DoV_increase_rate, avg_term_frequency, graph_folder)
        DoD_strong_signal, DoD_weak_signal, DoD_latent_signal, DoD_well_known_signal = self.DoD_draw_graph(avg_DoD_increase_rate, avg_doc_frequency, graph_folder)
        
        DoV_signal = {'strong_signal': DoV_strong_signal, "weak_signal": DoV_weak_signal, "latent_signal": DoV_latent_signal, "well_known_signal": DoV_well_known_signal}
        DoV_signal_df = pd.DataFrame([(k, v) for k, v in DoV_signal.items()], columns=['signal', 'word'])
        DoV_signal_df.to_csv(signal_folder + "/" + "DoV_signal.csv", index = False, encoding = 'utf-8-sig')
        
        DoD_signal = {'strong_signal': DoD_strong_signal, "weak_signal": DoD_weak_signal, "latent_signal": DoD_latent_signal, "well_known_signal": DoD_well_known_signal}
        DoD_signal_df = pd.DataFrame([(k, v) for k, v in DoD_signal.items()], columns=['signal', 'word'])
        DoD_signal_df.to_csv(signal_folder + "/" + "DoD_signal.csv", index = False, encoding = 'utf-8-sig')
        
        communal_strong_signal =  [word for word in DoV_strong_signal if word in DoD_strong_signal]
        communal_weak_signal = [word for word in DoV_weak_signal if word in DoD_weak_signal]
        communal_latent_signal = [word for word in DoV_latent_signal if word in DoD_latent_signal]
        communal_well_known_signal = [word for word in DoV_well_known_signal if word in DoD_well_known_signal]
        
        final_signal = {'strong_signal': communal_strong_signal, "weak_signal": communal_weak_signal, "latent_signal": communal_latent_signal, "well_known_signal": communal_well_known_signal}
        fignal_signal_df = pd.DataFrame([(k, v) for k, v in final_signal.items()], columns=['signal', 'word'])
        fignal_signal_df.to_csv(signal_folder + "/" + "communal_signal.csv", index = False, encoding = 'utf-8-sig')

    def divide_period(self, file):
        csv_data = pd.read_csv(file, engine='python', index_col = 0)
        csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]
        
        if "article" in file:
            csv_data['article date'] = pd.to_datetime(csv_data['article date'].str.split().str[0], format='%Y.%m.%d.', errors='coerce')
            csv_data['year'] = csv_data['article date'].dt.year
            csv_data['month'] = csv_data['article date'].dt.month
            csv_data['year_month'] = csv_data['article date'].dt.to_period('M')
        
        year_divided_group = csv_data.groupby('year')
        
        return year_divided_group, csv_data
    
    # 연도별 keyword tf 딕셔너리 반환            
    def cal_tf(self, keyword_list, year_divided_dic_merged):
        tf_counts = {}
        for key, value in year_divided_dic_merged.items():
            keyword_counts = {}
            for keyword in keyword_list:
                keyword_counts[keyword] = value.count(keyword)
            
            keyword_counts = dict(sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True))
            
            tf_counts[key] = keyword_counts
        return tf_counts
    
    # 연도별 keyword df 딕셔너리 반환
    def cal_df(self, keyword_list, year_divided_dic):
        df_counts = {}
        for year in year_divided_dic:
            keyword_counts = {}
            for keyword in keyword_list: # keyword는 keyword_list의 keyword
                count = 0
                for doc in year_divided_dic[year]:
                    if keyword in doc:
                        count += 1
                keyword_counts[keyword] = count
            
            keyword_counts = dict(sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True))
            
            df_counts[year] = keyword_counts
        return df_counts
    
    # 연도별 keyword DoV 딕셔너리 반환
    def cal_DoV(self, keyword_list, year_divided_dic, tf_counts):
        DoV_dict = {}
        for year in year_divided_dic:
            keyword_DoV_dic = {}
            for keyword in keyword_list:
                value = (tf_counts[year][keyword]/len(year_divided_dic[year]))*(1-0.05*(int(year)-self.startyear))
                keyword_DoV_dic[keyword] = value
            DoV_dict[year] = keyword_DoV_dic
        return DoV_dict
    
    # 연도별 keyword DoD 딕셔너리 반환
    def cal_DoD(self, keyword_list, year_divided_dic, df_counts):
        DoD_dict = {}
        for year in year_divided_dic:
            keyword_DoV_dic = {}
            for keyword in keyword_list:
                value = (df_counts[year][keyword]/len(year_divided_dic[year]))*(1-0.05*(int(year)-self.startyear))
                keyword_DoV_dic[keyword] = value
            DoD_dict[year] = keyword_DoV_dic
        return DoD_dict
                    
    def find_median(self, lst):               
        sorted_lst = sorted(lst)
        n = len(sorted_lst)

        # 리스트의 길이가 홀수일 경우
        if n % 2 == 1:
            return sorted_lst[n // 2]
        # 리스트의 길이가 짝수일 경우
        else:
            return (sorted_lst[n // 2 - 1] + sorted_lst[n // 2]) / 2
    
    def DoV_draw_graph(self, avg_DoV_increase_rate, avg_term_frequency, graph_folder):
        median_avg_term = self.find_median(list(avg_term_frequency.values())) #x축, 평균 단어 빈도
        median_avg_DoV = self.find_median(list(avg_DoV_increase_rate.values())) #y축, 평균 증가율
        
        coordinates = {}
        coordinates['axis'] = [median_avg_term, median_avg_DoV]
        
        for key in avg_DoV_increase_rate:
            if key not in self.exception_word_list:
                coordinates[key] = (avg_term_frequency[key], avg_DoV_increase_rate[key])
        
        plt.figure(figsize = (100,100))
        plt.axvline(x=median_avg_term, color='k', linestyle='--')  # x축 중앙값 수직선
        plt.axhline(y=median_avg_DoV, color='k', linestyle='--')  # y축 중앙값 수평선
        
        strong_signal = [word for word in coordinates if coordinates[word][0] > median_avg_term and coordinates[word][1] > median_avg_DoV]
        weak_signal = [word for word in coordinates if coordinates[word][0] < median_avg_term and coordinates[word][1] > median_avg_DoV]
        latent_signal = [word for word in coordinates if coordinates[word][0] < median_avg_term and coordinates[word][1] < median_avg_DoV]
        well_known_signal = [word for word in coordinates if coordinates[word][0] > median_avg_term and coordinates[word][1] < median_avg_DoV]
        
        strong_signal = [word for word in strong_signal if word not in self.exception_word_list]
        weak_signal = [word for word in weak_signal if word not in self.exception_word_list]
        latent_signal = [word for word in latent_signal if word not in self.exception_word_list]
        well_known_signal = [word for word in well_known_signal if word not in self.exception_word_list]
        
        # 각 좌표와 해당 키를 표시, 글자 크기 변경
        for key, value in coordinates.items():
            if key != 'axis':
                plt.scatter(value[0], value[1])
                plt.text(value[0], value[1], key, fontsize=15)

        # 그래프 제목 및 레이블 설정
        plt.title("Keyword Emergence Map", fontsize=50)
        plt.xlabel("Average Term Frequency(TF)", fontsize=50)
        plt.ylabel("Time-Weighted increasing rate", fontsize=50)
        
        # 그래프 표시
        plt.savefig(graph_folder + "/" + "TF_DOV_graph (size=100 font=50).png")
        
        coordinates_df =  pd.DataFrame([(k, v) for k, v in coordinates.items()], columns=['key', 'value'])
        coordinates_df.to_csv(graph_folder + "/" + "DOV_coordinates.csv", index = False, encoding = 'utf-8-sig')
        
        return strong_signal, weak_signal, latent_signal, well_known_signal

    def DoD_draw_graph(self, avg_DoD_increase_rate, avg_doc_frequency, graph_folder):
        median_avg_doc = self.find_median(list(avg_doc_frequency.values())) #x축, 평균 단어 빈도
        median_avg_DoD = self.find_median(list(avg_DoD_increase_rate.values())) #y축, 평균 증가율
        
        coordinates = {}
        coordinates['axis'] = [median_avg_doc, median_avg_DoD]
        
        for key in avg_DoD_increase_rate:
            if key not in self.exception_word_list:
                coordinates[key] = (avg_doc_frequency[key], avg_DoD_increase_rate[key])
        
        plt.figure(figsize = (100, 100))
        plt.axvline(x=median_avg_doc, color='k', linestyle='--')  # x축 중앙값 수직선
        plt.axhline(y=median_avg_DoD, color='k', linestyle='--')  # y축 중앙값 수평선
        
        strong_signal = [word for word in coordinates if coordinates[word][0] > median_avg_doc and coordinates[word][1] > median_avg_DoD]
        weak_signal = [word for word in coordinates if coordinates[word][0] < median_avg_doc and coordinates[word][1] > median_avg_DoD]
        latent_signal = [word for word in coordinates if coordinates[word][0] < median_avg_doc and coordinates[word][1] < median_avg_DoD]
        well_known_signal = [word for word in coordinates if coordinates[word][0] > median_avg_doc and coordinates[word][1] < median_avg_DoD]
        
        strong_signal = [word for word in strong_signal if word not in self.exception_word_list]
        weak_signal = [word for word in weak_signal if word not in self.exception_word_list]
        latent_signal = [word for word in latent_signal if word not in self.exception_word_list]
        well_known_signal = [word for word in well_known_signal if word not in self.exception_word_list]
        
        # 각 좌표와 해당 키를 표시
        for key, value in coordinates.items():
            if key != 'axis':
                plt.scatter(value[0], value[1])
                plt.text(value[0], value[1], key, fontsize=50)

        # 그래프 제목 및 레이블 설정
        plt.title("Keyword Issue Map", fontsize=50)
        plt.xlabel("Average Document Frequency(TF)", fontsize=50)
        plt.ylabel("Time-Weighted increasing rate", fontsize=50)
        
        # 그래프 표시
        plt.savefig(graph_folder + "/" + "TF_DOD_graph (size=100 font=50).png")
        
        coordinates_df =  pd.DataFrame([(k, v) for k, v in coordinates.items()], columns=['key', 'value'])
        coordinates_df.to_csv(graph_folder + "/" + "DOD_coordinates.csv", index = False, encoding = 'utf-8-sig')
        
        return strong_signal, weak_signal, latent_signal, well_known_signal

    def coordinates_draw_graph(self):
        kimkem_folder_path = filedialog.askdirectory(initialdir = self.kimkem_data_path, title="Select folder")
        DOV_coordinates_csv = kimkem_folder_path + "/" + 'graph' + "/" + "DOV_coordinates.csv"
        DOD_coordinates_csv = kimkem_folder_path + "/" + 'graph' + "/" + "DOD_coordinates.csv"
        
        DOV_coordinates_csv = pd.read_csv(DOV_coordinates_csv)
        DOD_coordinates_csv = pd.read_csv(DOD_coordinates_csv)
        
        DOV_coordinates = DOV_coordinates_csv.set_index('key')['value'].to_dict()
        DOD_coordinates = DOD_coordinates_csv.set_index('key')['value'].to_dict()
    
        DOV_median_avg_term = int(eval(DOV_coordinates['axis'])[0])
        DOV_median_avg_DoV = int(eval(DOV_coordinates['axis'])[1])
        
        DOD_median_avg_doc = int(eval(DOD_coordinates['axis'])[0])
        DoD_median_avg_DoD = int(eval(DOD_coordinates['axis'])[1])
        
        print("=================KIM KEM 그래프 그리기=================")
        size = int(input("그래프 사이즈를 입력하세요: "))
        font = int(input("폰트 사이즈를 입력하세요: "))
        
        print("\n처리 중...")
        
        ############################## DOV ####################################
        plt.figure(figsize = (size, size))
        plt.axvline(x=DOV_median_avg_term, color='k', linestyle='--')  # x축 중앙값 수직선
        plt.axhline(y=DOV_median_avg_DoV, color='k', linestyle='--')  # y축 중앙값 수평선
        
        for key, value in DOV_coordinates.items():
            value = eval(value)
            if key != 'axis':
                plt.scatter(value[0], value[1])
                plt.text(value[0], value[1], key, fontsize=font)
        
        plt.title("Keyword Emergence Map", fontsize=50)
        plt.xlabel("Average Term Frequency(TF)", fontsize=50)
        plt.ylabel("Time-Weighted increasing rate", fontsize=50)
        
        # 그래프 표시
        plt.savefig(f"{kimkem_folder_path}/graph/TF_DOV_graph(size={size} font={font}).png")
        
        ############################## DOD ####################################
        plt.figure(figsize = (size, size))
        plt.axvline(x=DOD_median_avg_doc, color='k', linestyle='--')  # x축 중앙값 수직선
        plt.axhline(y=DoD_median_avg_DoD, color='k', linestyle='--')  # y축 중앙값 수평선
        
        for key, value in DOD_coordinates.items():
            value = eval(value)
            if key != 'axis':
                plt.scatter(value[0], value[1])
                plt.text(value[0], value[1], key, fontsize=font)
        
        plt.title("Keyword Issue Map", fontsize=50)
        plt.xlabel("Average Document Frequency(TF)", fontsize=50)
        plt.ylabel("Time-Weighted increasing rate", fontsize=50)
        
        # 그래프 표시
        plt.savefig(f"{kimkem_folder_path}/graph/TF_DOD_graph(size={size} font={font}).png")
        print("\n완료")
        
        

    def make_exception(self):
        while True:
            except_option = input("제외어 사전을 추가하시겠습니까(Y/N)? ")  
            if except_option.lower() == "y":
                exception_file_path = filedialog.askopenfilename(initialdir = self.exception_list, title="제외어 사전을 고르시오", filetypes=(("CSV files", "*.csv"), ("All files", "*.*")))
                exception_word_list = pd.read_csv(exception_file_path, encoding='cp949', sep='\t').values.flatten().tolist()
                exception_word_list = [word.replace(",,", '') for word in exception_word_list]
                return exception_word_list, "Y"
            elif except_option.lower() == "n":
                return [], "N"
            else:
                print("다시 입력하세요")
            
    def clear_screen(self):
        if platform.system() == "Windows":
            os.system("cls")
        else:
            os.system("clear")

kimkem = kimkem()