from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QFileDialog, QDialog, QCheckBox, QComboBox, QRadioButton, QLabel, QDialogButtonBox, QVBoxLayout
import copy
import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns
import platform

# 운영체제에 따라 한글 폰트를 설정
if platform.system() == 'Darwin':  # macOS
    plt.rcParams['font.family'] = 'AppleGothic'
elif platform.system() == 'Windows':  # Windows
    plt.rcParams['font.family'] = 'Malgun Gothic'  # 맑은 고딕 폰트 사용

# 폰트 설정 후 음수 기호가 깨지는 것을 방지
plt.rcParams['axes.unicode_minus'] = False

class Manager_Dataprocess:
    def __init__(self, main_window):
        self.main = main_window
        self.dataprocess_obj = DataProcess(self.main)
        self.DB = copy.deepcopy(self.main.DB)
        self.DB_table_column = ['Name', 'Type', 'Keyword', 'Period', 'Option', 'Crawl Start', 'Crawl End', 'Requester']
        self.main.table_maker(self.main.dataprocess_tab1_tablewidget, self.DB['DBdata'], self.DB_table_column)
        self.dataprocess_filefinder_maker()
        self.dataprocess_buttonMatch()

    def dataprocess_buttonMatch(self):
        self.main.dataprocess_tab1_refreshDB_button.clicked.connect(self.dataprocess_refresh_DB)
        self.main.dataprocess_tab1_searchDB_lineinput.returnPressed.connect(self.dataprocess_search_DB)
        self.main.dataprocess_tab1_searchDB_button.clicked.connect(self.dataprocess_search_DB)
        self.main.dataprocess_tab1_timesplit_button.clicked.connect(self.dataprocess_timesplit_DB)
        self.main.dataprocess_tab1_analysis_button.clicked.connect(self.dataprocess_analysis_DB)

        self.main.dataprocess_tab2_timesplit_button.clicked.connect(self.dataprocess_timesplit_file)
        self.main.dataprocess_tab2_analysis_button.clicked.connect(self.dataprocess_analysis_file)
        self.main.dataprocess_tab2_merge_button.clicked.connect(self.dataprocess_merge_file)

    def dataprocess_search_DB(self):
        search_text = self.main.dataprocess_tab1_searchDB_lineinput.text().lower()
        if not search_text:
            return

        # 현재 선택된 행의 다음 행부터 검색 시작
        start_row = self.main.dataprocess_tab1_tablewidget.currentRow() + 1 if self.main.dataprocess_tab1_tablewidget.currentRow() != -1 else 0

        for row in range(start_row, self.main.dataprocess_tab1_tablewidget.rowCount()):
            match = False
            for col in range(self.main.dataprocess_tab1_tablewidget.columnCount()):
                item = self.main.dataprocess_tab1_tablewidget.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            if match:
                self.main.dataprocess_tab1_tablewidget.selectRow(row)
                return

        # 검색어가 처음부터 검색되도록 반복
        for row in range(0, start_row):
            match = False
            for col in range(self.main.dataprocess_tab1_tablewidget.columnCount()):
                item = self.main.dataprocess_tab1_tablewidget.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            if match:
                self.main.dataprocess_tab1_tablewidget.selectRow(row)
                return

    def dataprocess_refresh_DB(self):
        self.main.printStatus("새로고침 중...")

        def refresh_database():
            self.DB = self.main.update_DB(self.DB)
            self.main.table_maker(self.main.dataprocess_tab1_tablewidget, self.DB['DBdata'], self.DB_table_column)

        QTimer.singleShot(1, refresh_database)
        QTimer.singleShot(1, self.main.printStatus)

    def dataprocess_timesplit_DB(self):
        def selectDB():
            selected_row = self.main.dataprocess_tab1_tablewidget.currentRow()
            if not selected_row >= 0:
                return 0 ,0, 0
            target_db = self.DB['DBlist'][selected_row]

            folder_path  = QFileDialog.getExistingDirectory(self.main, "분할 데이터를 저장할 폴더를 선택하세요", self.main.default_directory)
            if folder_path:
                try:
                    splitdata_path = os.path.join(folder_path, target_db + '_split')

                    while True:
                        try:
                            os.mkdir(splitdata_path)
                            break
                        except:
                            splitdata_path += "_copy"

                    self.main.mySQL_obj.connectDB(target_db)
                    tableList = self.main.mySQL_obj.showAllTable(target_db)
                    tableList = [table for table in tableList if 'info' not in table]

                    return target_db, tableList, splitdata_path

                except Exception as e:
                    QMessageBox.critical(self.main, "Error", f"Failed to save splited database: {str(e)}")
            else:
                QMessageBox.warning(self.main, "Warning", "No directory selected.")
                return 0,0,0
        def splitTable(table, splitdata_path):
            table_path = os.path.join(splitdata_path, table + '_split')
            try:
                os.mkdir(table_path)
            except:
                table_path += "_copy"
                os.mkdir(table_path)

            table_df = self.main.mySQL_obj.TableToDataframe(table)
            table_df = self.dataprocess_obj.TimeSplitter(table_df)

            self.year_divided_group = table_df.groupby('year')
            self.month_divided_group = table_df.groupby('year_month')
            self.week_divided_group = table_df.groupby('week')

            return table_path
        def saveTable(tablename, table_path):
            self.dataprocess_obj.TimeSplitToCSV(1, self.year_divided_group, table_path, tablename)
            self.dataprocess_obj.TimeSplitToCSV(2, self.month_divided_group, table_path, tablename)
        def main(tableList, splitdata_path):
            for table in tableList:
                table_path = splitTable(table, splitdata_path)
                saveTable(table, table_path)

        self.main.printStatus("분할 데이터를 저장할 위치를 선택하세요...")
        targetDB, tableList, splitdata_path = selectDB()
        if targetDB == 0:
            self.main.printStatus()
            return
        QTimer.singleShot(1, lambda: self.main.printStatus(f"{targetDB} 변환 및 저장 중..."))
        self.main.openFileExplorer(splitdata_path)
        QTimer.singleShot(1000, lambda: main(tableList, splitdata_path))
        QTimer.singleShot(1000, self.main.printStatus)

    def dataprocess_analysis_DB(self):
        def selectDB():
            selected_row = self.main.dataprocess_tab1_tablewidget.currentRow()
            if not selected_row >= 0:
                return 0 ,0, 0
            target_db = self.DB['DBlist'][selected_row]

            folder_path  = QFileDialog.getExistingDirectory(self.main, "분석 데이터를 저장할 폴더를 선택하세요", self.main.default_directory)
            if folder_path:
                try:
                    analysisdata_path = os.path.join(folder_path, target_db + '_analysis')

                    while True:
                        try:
                            os.mkdir(analysisdata_path)
                            break
                        except:
                            analysisdata_path += "_copy"

                    self.main.mySQL_obj.connectDB(target_db)
                    tableList = self.main.mySQL_obj.showAllTable(target_db)
                    tableList = [table for table in tableList if 'info' not in table]

                    return target_db, tableList, analysisdata_path

                except Exception as e:
                    QMessageBox.critical(self.main, "Error", f"Failed to save splited database: {str(e)}")
            else:
                QMessageBox.warning(self.main, "Warning", "No directory selected.")
                return 0,0,0
        def main(tableList, analysisdata_path):

            for index, table in enumerate(tableList):
                tablename = table.split('_')
                tabledf = self.main.mySQL_obj.TableToDataframe(table)

                match tablename[0]:
                    case 'navernews':
                        match tablename[6]:
                            case 'article':
                                self.dataprocess_obj.NaverNewsArticleAnalysis(tabledf,
                                                                              os.path.join(analysisdata_path, table))
                            case 'statistics':
                                statisticsURL = tabledf['Article URL'].tolist()
                                self.dataprocess_obj.NaverNewsStatisticsAnalysis(tabledf,
                                                                                 os.path.join(analysisdata_path, table))
                            case 'reply' | 'rereply':
                                self.dataprocess_obj.NaverNewsReplyAnalysis(tabledf,
                                                                            os.path.join(analysisdata_path, table))

                    case 'navercafe':
                        match tablename[6]:
                            case 'article':
                                self.dataprocess_obj.NaverCafeArticleAnalysis(tabledf,
                                                                              os.path.join(analysisdata_path, table))
                            case 'reply':
                                self.dataprocess_obj.NaverCafeReplyAnalysis(tabledf,
                                                                            os.path.join(analysisdata_path, table))

                    case _:
                            QMessageBox.warning(self.main, "Warning", f"{tablename[0]} {tablename[6]} 분석은 지원되지 않는 기능입니다")


        self.main.printStatus("분석 데이터를 저장할 위치를 선택하세요...")
        targetDB, tableList, analysisdata_path = selectDB()
        if targetDB == 0:
            self.main.printStatus()
            return
        QTimer.singleShot(1, lambda: self.main.printStatus(f"{targetDB} 분석 및 저장 중..."))
        self.main.openFileExplorer(analysisdata_path)
        QTimer.singleShot(1000, lambda: main(tableList, analysisdata_path))
        QTimer.singleShot(1000, self.main.printStatus)


    def dataprocess_filefinder_maker(self):
        self.file_dialog = self.main.filefinder_maker()
        self.main.tab2_fileexplorer_layout.addWidget(self.file_dialog)

    def dataprocess_getfiledirectory(self):
        selected_directory = self.file_dialog.selectedFiles()
        if selected_directory == []:
            return selected_directory
        selected_directory = selected_directory[0].split(', ')

        for directory in selected_directory:
            if not directory.endswith('.csv'):
                return [False, directory]

        for index, directory in enumerate(selected_directory):
            if index != 0:
                selected_directory[index] = os.path.join(os.path.dirname(selected_directory[0]), directory)

        return selected_directory

    def dataprocess_timesplit_file(self):
        selected_directory = self.dataprocess_getfiledirectory()
        if len(selected_directory) == 0:
            return
        elif selected_directory[0] == False:
            QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
            return
        def split_table(csv_path):
            table_path = os.path.join(os.path.dirname(csv_path), os.path.basename(csv_path).replace('.csv', '') + '_split')
            while True:
                try:
                    os.mkdir(table_path)
                    break
                except:
                    table_path += "_copy"

            table_df = self.main.csvReader(csv_path)
            table_df = self.dataprocess_obj.TimeSplitter(table_df)

            self.year_divided_group = table_df.groupby('year')
            self.month_divided_group = table_df.groupby('year_month')
            self.week_divided_group = table_df.groupby('week')

            return table_path
        def saveTable(tablename, table_path):
            self.dataprocess_obj.TimeSplitToCSV(1, self.year_divided_group, table_path, tablename)
            self.dataprocess_obj.TimeSplitToCSV(2, self.month_divided_group, table_path, tablename)
        def main(directory_list):
            for csv_path in directory_list:
                table_path = split_table(csv_path)
                saveTable(os.path.basename(csv_path).replace('.csv', ''), table_path)

        QTimer.singleShot(1, lambda: self.main.printStatus("변환 및 저장 중..."))
        self.main.openFileExplorer(os.path.dirname(selected_directory[0]))
        QTimer.singleShot(1000, lambda: main(selected_directory))
        QTimer.singleShot(1000, self.main.printStatus)

    def dataprocess_merge_file(self):
        def find_different_element_index(lst):
            # 리스트가 비어있으면 None을 반환
            if not lst:
                return None

            # 첫 번째 요소와 나머지 요소가 다르면 첫 번째 요소의 인덱스 반환
            if lst.count(lst[0]) == 1:
                return 0

            # 그렇지 않으면 첫 번째 요소와 다른 첫 번째 요소의 인덱스 반환
            for i in range(1, len(lst)):
                if lst[i] != lst[0]:
                    return i

            return None  # 모든 요소가 같다면 None을 반환

        selected_directory = self.dataprocess_getfiledirectory()
        if len(selected_directory) == 0:
            return
        elif selected_directory[0] == False:
            QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
            return
        elif len(selected_directory) < 2:
            QMessageBox.warning(self.main, f"Warning", "2개 이상의 CSV 파일 선택이 필요합니다.")
            return


        all_df = [self.main.csvReader(directory) for directory in selected_directory]
        all_columns = [df.columns.tolist() for df in all_df]
        same_check_result = find_different_element_index(all_columns)
        if same_check_result != None:
            QMessageBox.warning(self.main, f"Warning", f"{os.path.basename(selected_directory[same_check_result])}의 CSV 형태가 다른 파일의 형태와 다릅니다.")
            return

        mergedfilename, ok = QInputDialog.getText(None, '파일명 입력', '병합 파일명을 입력하세요:', text='merged_file')
        mergedfiledir      = os.path.dirname(selected_directory[0])
        if ok and mergedfilename:
            merged_df = pd.DataFrame()

            for df in all_df:
                merged_df = pd.concat([merged_df, df], ignore_index=True)

            merged_df.to_csv(os.path.join(mergedfiledir, mergedfilename)+'.csv', index=False, encoding='utf-8-sig')
            self.main.openFileExplorer(mergedfiledir)

    def dataprocess_analysis_file(self):
        selected_directory = self.dataprocess_getfiledirectory()
        if len(selected_directory) == 0:
            return
        elif selected_directory[0] == False:
            QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
            return
        elif len(selected_directory) != 1:
            QMessageBox.warning(self.main, f"Warning", "한 개의 CSV 파일만 선택하여 주십시오")
            return

        csv_path = selected_directory[0]
        csv_data = pd.read_csv(csv_path, low_memory=False)

        selected_options = []
        dialog = OptionDialog()
        if dialog.exec_() == QDialog.Accepted:
            selected_options = []

            # 선택된 체크박스 옵션 추가
            for checkbox in dialog.checkbox_group:
                if checkbox.isChecked():
                    selected_options.append(checkbox.text())

            # 콤보박스에서 선택된 옵션 추가
            selected_options.append(dialog.combobox.currentText())

        match selected_options:
            case ['article 분석', 'Naver News']:
                self.dataprocess_obj.NaverNewsArticleAnalysis(csv_data, csv_path)
            case ['statistics 분석', 'Naver News']:
                self.dataprocess_obj.NaverNewsStatisticsAnalysis(csv_data, csv_path)
            case ['reply 분석', 'Naver News'] | ['rereply 분석', 'Naver News']:
                self.dataprocess_obj.NaverNewsReplyAnalysis(csv_data, csv_path)
            case ['article 분석', 'Naver Cafe']:
                self.dataprocess_obj.NaverCafeArticleAnalysis(csv_data, csv_path)
            case ['reply 분석', 'Naver Cafe']:
                self.dataprocess_obj.NaverCafeReplyAnalysis(csv_data, csv_path)
            case []:
                QMessageBox.warning(self.main, "Warning", "CSV 파일 클릭 -> Open버튼 클릭 -> 옵션을 선택하세요")
            case _:
                QMessageBox.warning(self.main, "Warning", f"{selected_options[1]} {selected_options[0]} 분석은 지원되지 않는 기능입니다")

        self.main.openFileExplorer(os.path.dirname(csv_path))


class DataProcess:
    def __init__(self, main_window):
        self.main = main_window

    def TimeSplitter(self, data):
        # data 형태: DataFrame
        data_columns = data.columns.tolist()

        for i in data_columns:
            if 'Date' in i:
                word = i
                break

        data[word] = pd.to_datetime(data[word], format='%Y-%m-%d', errors='coerce')

        data['year'] = data[word].dt.year
        data['month'] = data[word].dt.month
        data['year_month'] = data[word].dt.to_period('M')
        data['week'] = data[word].dt.to_period('W')

        return data

    def TimeSplitToCSV(self, option, divided_group, data_path, tablename):
        # 폴더 이름과 데이터 그룹 설정
        data_group = divided_group
        if option == 1:
            folder_name = "Year Data"
            info_label = 'Year'
        elif option == 2:
            folder_name = "Month Data"
            info_label = 'Month'
        elif option == 3:
            folder_name = "Week Data"
            info_label = 'Week'

        info = {}

        # 디렉토리 생성
        os.mkdir(data_path + "/" + folder_name)

        # 데이터 그룹을 순회하며 파일 저장 및 정보 수집
        for group_name, group_data in data_group:
            info[str(group_name)] = len(group_data)
            group_data.to_csv(f"{data_path}/{folder_name}/{tablename+'_'+str(group_name)}.csv", index=False,
                              encoding='utf-8-sig', header=True)

        # 정보 파일 생성
        info_df = pd.DataFrame(list(info.items()), columns=[info_label, 'Count'])
        info_df.to_csv(f"{data_path}/{folder_name}/{folder_name} Count.csv", index=False,
                       encoding='utf-8-sig', header=True)

        info_df.set_index(info_label, inplace=True)
        keys = list(info_df.index)
        values = info_df['Count'].tolist()

        # 데이터의 수에 따라 그래프 크기 자동 조정
        num_data_points = len(keys)
        width_per_data_point = 0.5  # 데이터 포인트 하나당 가로 크기 (조정 가능)
        base_width = 10  # 최소 가로 크기
        height = 6  # 고정된 세로 크기

        fig_width = max(base_width, num_data_points * width_per_data_point)

        plt.figure(figsize=(fig_width, height))

        # 그래프 그리기
        sns.lineplot(x=keys, y=values, marker='o')

        # 그래프 설정
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()

        plt.title(f'{info_label} Data Visualization')
        plt.xlabel(info_label)
        plt.ylabel('Values')

        # 그래프 저장
        plt.savefig(f"{data_path}/{folder_name}/{folder_name} Graph.png", bbox_inches='tight')

    def calculate_figsize(self, data_length, base_width=12, height=6, max_width=50):
        # Increase width proportionally to the number of data points, but limit the maximum width
        width = min(base_width + (data_length / 20), max_width)
        return (width, height)

    def NaverNewsArticleAnalysis(self, data, file_path):
        if 'Article Press' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverNews Article CSV 형태와 일치하지 않습니다")
            return

        # 'Article Date'를 datetime 형식으로 변환
        data['Article Date'] = pd.to_datetime(data['Article Date'])

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 시간에 따른 기사 및 댓글 수 분석
        time_analysis = data.groupby(data['Article Date'].dt.to_period("M")).agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 기사 유형별 분석
        article_type_analysis = data.groupby('Article Type').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 언론사별 분석 (상위 10개 언론사만)
        top_10_press = data['Article Press'].value_counts().head(10).index
        press_analysis = data[data['Article Press'].isin(top_10_press)].groupby('Article Press').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 상관관계 분석
        correlation_matrix = data[['Article ReplyCnt']].corr()

        # 시각화 및 분석 결과 저장 디렉토리 설정
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))
        article_type_analysis.to_csv(os.path.join(csv_output_dir, "article_type_analysis.csv"))
        press_analysis.to_csv(os.path.join(csv_output_dir, "press_analysis.csv"))
        #correlation_matrix.to_csv(os.path.join(output_dir, "correlation_matrix.csv"))

        # For time_analysis graph
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Article Count', label='Article Count')
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Article ReplyCnt',
                     label='Reply Count')
        plt.title('Monthly Article and Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.yticks([])
        plt.ylabel('')
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_article_reply_count.png"))
        plt.close()

        # For article_type_analysis graph
        data_length = len(article_type_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        article_type_analysis = article_type_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x=article_type_analysis.index, y=article_type_analysis['Article Count'], palette="viridis")
        plt.title('Article Count by Type')
        plt.xlabel('Article Type')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "article_type_count.png"))
        plt.close()

        # For press_analysis graph
        data_length = len(press_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        press_analysis = press_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x=press_analysis.index, y=press_analysis['Article Count'], palette="plasma")
        plt.title('Top 10 Press by Article Count')
        plt.xlabel('Press')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "press_article_count.png"))
        plt.close()

        '''
        # 4. 상관관계 행렬 히트맵 (현재는 댓글 수에 대한 상관관계만 존재)
        plt.figure(figsize=(8, 6))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "correlation_matrix.png"))
        plt.close()
        '''
    def NaverNewsStatisticsAnalysis(self, data, file_path):
        if 'Male' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverNews Statistics CSV 형태와 일치하지 않습니다")
            return

        # 'Article Date'를 datetime 형식으로 변환
        data['Article Date'] = pd.to_datetime(data['Article Date'])
        data['Article ReplyCnt'] = pd.to_numeric(data['Article ReplyCnt'], errors='coerce')

        # 백분율 값을 실제 댓글 수로 변환하기 전에 숫자(float)로 변환
        for col in ['Male', 'Female', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y']:
            data[col] = pd.to_numeric(data[col], errors='coerce')  # 각 열을 숫자로 변환
            data[col] = (data[col] / 100.0) * data['Article ReplyCnt']

        # 분석 결과 저장 디렉토리 설정
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 시간에 따른 기사 및 댓글 수 분석
        time_analysis = data.groupby(data['Article Date'].dt.to_period("M")).agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 기사 유형별 분석
        article_type_analysis = data.groupby('Article Type').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 언론사별 분석 (상위 10개 언론사만)
        top_10_press = data['Article Press'].value_counts().head(10).index
        press_analysis = data[data['Article Press'].isin(top_10_press)].groupby(
            'Article Press').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 상관관계 분석
        correlation_matrix = data[
            ['Article ReplyCnt', 'Male', 'Female', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y']].corr()

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))
        article_type_analysis.to_csv(os.path.join(csv_output_dir, "article_type_analysis.csv"))
        press_analysis.to_csv(os.path.join(csv_output_dir, "press_analysis.csv"))
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"))

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 월별 기사 및 댓글 수 추세
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Article Count', label='Article Count')
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Article ReplyCnt',
                     label='Reply Count')
        plt.title('Monthly Article and Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_article_reply_count.png"))
        plt.close()

        # 2. 기사 유형별 기사 및 댓글 수
        data_length = len(article_type_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        article_type_analysis = article_type_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x=article_type_analysis.index, y=article_type_analysis['Article Count'], palette="viridis")
        plt.title('Article Count by Type')
        plt.xlabel('Article Type')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "article_type_count.png"))
        plt.close()

        # 3. 상위 10개 언론사별 기사 및 댓글 수
        data_length = len(press_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        press_analysis = press_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x=press_analysis.index, y=press_analysis['Article Count'], palette="plasma")
        plt.title('Top 10 Press by Article Count')
        plt.xlabel('Press')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "press_article_count.png"))
        plt.close()

        # 4. 상관관계 행렬 히트맵
        data_length = len(correlation_matrix)
        plt.figure(figsize=self.calculate_figsize(data_length, height=8))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 5. 성별 댓글 수 분석 및 시각화
        gender_reply_count = {
            'Male': data['Male'].sum(),
            'Female': data['Female'].sum()
        }
        gender_reply_df = pd.DataFrame(list(gender_reply_count.items()), columns=['Gender', 'Reply Count'])
        data_length = len(gender_reply_df)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=8))
        sns.barplot(x='Gender', y='Reply Count', data=gender_reply_df, palette="pastel")
        plt.title('Total Number of Replies by Gender')
        plt.xlabel('Gender')
        plt.ylabel('Reply Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "gender_reply_count.png"))
        plt.close()
        gender_reply_df.to_csv(os.path.join(csv_output_dir, "gender_reply_count.csv"), index=False)

        # 6. 연령대별 댓글 수 분석 및 시각화
        age_group_reply_count = {
            '10Y': data['10Y'].sum(),
            '20Y': data['20Y'].sum(),
            '30Y': data['30Y'].sum(),
            '40Y': data['40Y'].sum(),
            '50Y': data['50Y'].sum(),
            '60Y': data['60Y'].sum()
        }
        age_group_reply_df = pd.DataFrame(list(age_group_reply_count.items()), columns=['Age Group', 'Reply Count'])
        data_length = len(age_group_reply_df)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=10))
        sns.barplot(x='Age Group', y='Reply Count', data=age_group_reply_df, palette="coolwarm")
        plt.title('Total Number of Replies by Age Group')
        plt.xlabel('Age Group')
        plt.ylabel('Reply Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "age_group_reply_count.png"))
        plt.close()
        age_group_reply_df.to_csv(os.path.join(csv_output_dir, "age_group_reply_count.csv"), index=False)

        # 7. 연령대별 성별 댓글 비율 분석
        age_gender_df = data.groupby(['Article Date', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y'])[
            ['Male', 'Female']].sum().reset_index()
        age_gender_df = age_gender_df.melt(id_vars=['Article Date', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y'],
                                           value_vars=['Male', 'Female'],
                                           var_name='Gender',
                                           value_name='Reply Count')
        data_length = len(age_gender_df)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=12, height=8))
        sns.lineplot(data=age_gender_df, x='Article Date', y='Reply Count', hue='Gender')
        plt.title('Reply Count by Gender Over Time')
        plt.xlabel('Date')
        plt.ylabel('Reply Count')
        plt.legend(title='Gender')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "age_gender_reply_count.png"))
        plt.close()
        age_gender_df.to_csv(os.path.join(csv_output_dir, "age_gender_reply_count.csv"), index=False)
    def NaverNewsReplyAnalysis(self, data, file_path):
        if 'Reply Sentiment' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverNews Reply CSV 형태와 일치하지 않습니다")
            return
        # 'Reply Date'를 datetime 형식으로 변환
        data['Reply Date'] = pd.to_datetime(data['Reply Date'])

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 댓글 길이 추가
        data['Reply Length'] = data['Reply Text'].apply(len)

        # 날짜별 댓글 수 분석
        time_analysis = data.groupby(data['Reply Date'].dt.date).agg({
            'id': 'count',
            'Reply Like': 'sum',
            'Reply Bad': 'sum'
        }).rename(columns={'id': 'Reply Count'})

        # 댓글 감성 분석 결과 빈도
        sentiment_counts = data['Reply Sentiment'].value_counts()

        # 상관관계 분석
        correlation_matrix = data[['Reply Like', 'Reply Bad', 'Rereply Count', 'Reply LikeRatio', 'Reply Sentiment',
                                   'Reply Length']].corr()

        # 작성자별 댓글 수 계산
        writer_reply_count = data['Reply Writer'].value_counts()

        # 결과를 저장할 디렉토리 생성
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))
        sentiment_counts.to_csv(os.path.join(csv_output_dir, "sentiment_counts.csv"))
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"))
        writer_reply_count.to_csv(os.path.join(csv_output_dir, "writer_reply_count.csv"))

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 날짜별 댓글 수 추세
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index, y='Reply Count')
        plt.title('Daily Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Number of Replies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "daily_reply_count.png"))
        plt.close()

        # 2. 댓글 감성 분석 결과 분포
        data_length = len(sentiment_counts)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=8))
        sns.countplot(x='Reply Sentiment', data=data)
        plt.title('Reply Sentiment Distribution')
        plt.xlabel('Sentiment')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "reply_sentiment_distribution.png"))
        plt.close()

        # 4. 상관관계 행렬 히트맵
        data_length = len(correlation_matrix)
        plt.figure(figsize=self.calculate_figsize(data_length, height=8))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 5. 작성자별 댓글 수 분포 (상위 10명)
        top_10_writers = writer_reply_count.head(10)  # 상위 10명 작성자 선택
        data_length = len(top_10_writers)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.barplot(x=top_10_writers.index, y=top_10_writers.values, palette="viridis")
        plt.title('Top 10 Writers by Number of Replies')
        plt.xlabel('Writer')
        plt.ylabel('Number of Replies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "writer_reply_count.png"))
        plt.close()

    def NaverCafeArticleAnalysis(self, data, file_path):
        if 'NaverCafe Name' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverCafe Article CSV 형태와 일치하지 않습니다")
            return
        # 'Article Date'를 datetime 형식으로 변환
        data['Article Date'] = pd.to_datetime(data['Article Date'])
        # 특정 열들에 대해 pd.to_numeric을 적용하여 숫자형으로 변환
        cols_to_convert = ['NaverCafe MemberCount', 'Article ReadCount', 'Article ReplyCount']
        data[cols_to_convert] = data[cols_to_convert].apply(pd.to_numeric, errors='coerce')

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 카페별 분석
        cafe_analysis = data.groupby('NaverCafe Name').agg({
            'id': 'count',
            'Article ReadCount': 'mean',
            'Article ReplyCount': 'mean',
            'NaverCafe MemberCount': 'mean'
        }).rename(columns={'id': 'Article Count', 'Article ReadCount': 'Avg ReadCount',
                           'Article ReplyCount': 'Avg ReplyCount'})

        # 작성자별 분석
        writer_analysis = data.groupby('Article Writer').agg({
            'id': 'count',
            'Article ReadCount': 'mean',
            'Article ReplyCount': 'mean'
        }).rename(columns={'id': 'Article Count', 'Article ReadCount': 'Avg ReadCount',
                           'Article ReplyCount': 'Avg ReplyCount'})

        # 시간별 분석 (연도, 월별)
        time_analysis = data.groupby(data['Article Date'].dt.to_period("M")).agg({
            'id': 'count',
            'Article ReadCount': 'sum',
            'Article ReplyCount': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 상관관계 분석
        numerical_cols = ['NaverCafe MemberCount', 'Article ReadCount', 'Article ReplyCount']
        correlation_matrix = data[numerical_cols].corr()

        # 결과를 저장할 디렉토리 생성
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"))
        cafe_analysis.to_csv(os.path.join(csv_output_dir, "cafe_analysis.csv"))
        writer_analysis.to_csv(os.path.join(csv_output_dir, "writer_analysis.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"))

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 카페별 게시글 수 분포
        data_length = len(cafe_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.barplot(x=cafe_analysis.index, y=cafe_analysis['Article Count'])
        plt.title('Number of Articles by NaverCafe')
        plt.xlabel('NaverCafe')
        plt.ylabel('Number of Articles')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "cafe_article_count.png"))
        plt.close()

        # 2. 시간별 게시글 수 추세
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Article Count')
        plt.title('Monthly Article Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Number of Articles')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_article_count.png"))
        plt.close()


        # 4. 작성자별 게시글 수 분포 (상위 10명)
        top_10_writers = writer_analysis.sort_values('Article Count', ascending=False).head(10)
        data_length = len(top_10_writers)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.barplot(x=top_10_writers.index, y=top_10_writers['Article Count'])
        plt.title('Top 10 Writers by Number of Articles')
        plt.xlabel('Writer')
        plt.ylabel('Number of Articles')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "top_10_writers.png"))
        plt.close()
    def NaverCafeReplyAnalysis(self, data, file_path):
        # 'Article URL' 열이 있는지 확인
        if 'Article URL' not in list(data.columns):
            QMessageBox.warning(self.main, "Warning", "NaverCafe Reply CSV 형태와 일치하지 않습니다")
            return

        # 'Reply Date'를 datetime 형식으로 변환
        data['Reply Date'] = pd.to_datetime(data['Reply Date'])

        # 작성자별 분석 (상위 10명)
        writer_analysis = data.groupby('Reply Writer').agg({
            'id': 'count'
        }).rename(columns={'id': 'Reply Count'}).sort_values(by='Reply Count', ascending=False).head(100)

        # 시간별 분석 (연도, 월별)
        time_analysis = data.groupby(data['Reply Date'].dt.to_period("M")).agg({
            'id': 'count'
        }).rename(columns={'id': 'Reply Count'})

        # 결과를 저장할 디렉토리 생성
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        writer_analysis.to_csv(os.path.join(csv_output_dir, "writer_analysis.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 작성자별 댓글 수 분포 (상위 10명)
        data_length = len(writer_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.barplot(x=writer_analysis.index, y=writer_analysis['Reply Count'])
        plt.title('Number of Replies by Top 100 Writers')
        plt.xlabel('Writer')
        plt.ylabel('Number of Replies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "writer_reply_count.png"))
        plt.close()

        # 2. 시간별 댓글 수 추세
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Reply Count')
        plt.title('Monthly Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Number of Replies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_reply_count.png"))
        plt.close()

class OptionDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Select Options')

        # 다이얼로그 레이아웃
        layout = QVBoxLayout()

        # 여러 옵션 추가 (예: 체크박스, 라디오 버튼, 콤보박스)
        # 여러 옵션 추가 (예: 체크박스, 라디오 버튼, 콤보박스)
        self.checkbox_group = []

        self.combobox = QComboBox()
        self.combobox.addItems(['Naver News', 'Naver Blog', 'Naver Cafe', 'YouTube'])
        self.combobox.currentIndexChanged.connect(self.update_checkboxes)

        layout.addWidget(QLabel('Choose Data Type:'))
        layout.addWidget(self.combobox)

        # 다이얼로그의 OK/Cancel 버튼
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout.addWidget(self.button_box)

        self.setLayout(layout)
        self.update_checkboxes()

    def update_checkboxes(self):
        # 기존 체크박스 제거
        for checkbox in self.checkbox_group:
            checkbox.setParent(None)
        self.checkbox_group.clear()

        # 콤보박스 선택에 따라 다른 체크박스 표시
        if self.combobox.currentText() == 'Naver News':
            options = ['article 분석', 'statistics 분석', 'reply 분석', 'rereply 분석']
        elif self.combobox.currentText() == 'Naver Blog':
            options = ['article 분석', 'reply 분석']
        elif self.combobox.currentText() == 'Naver Cafe':
            options = ['article 분석', 'reply 분석']
        elif self.combobox.currentText() == 'YouTube':
            options = ['article 분석', 'reply 분석', 'rereply 분석']

        for option in options:
            checkbox = QCheckBox(option)
            checkbox.setAutoExclusive(True)  # 중복 체크 불가
            self.checkbox_group.append(checkbox)
            self.layout().insertWidget(self.layout().count() - 1, checkbox)  # 버튼 위에 체크박스 추가


