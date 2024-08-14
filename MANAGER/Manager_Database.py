import os
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout, QMainWindow, QHeaderView, QMessageBox, QFileDialog, QDialog, QInputDialog, QDialogButtonBox, QRadioButton, QLabel, QFormLayout, QLineEdit
from PyQt5.QtCore import QTimer, QDate
import pandas as pd
import copy
import re
class TableWindow(QMainWindow):
    def __init__(self, parent=None, target_db=None):
        super(TableWindow, self).__init__(parent)
        self.setWindowTitle(target_db)
        self.setGeometry(100, 100, 1600, 1200)

        self.parent = parent  # 부모 객체를 저장하여 나중에 사용
        self.target_db = target_db  # target_db를 저장하여 나중에 사용

        self.central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        # 상단 버튼 레이아웃
        self.button_layout = QtWidgets.QHBoxLayout()

        # spacer 아이템 추가 (버튼들을 오른쪽 끝에 배치하기 위해 앞에 추가)
        spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.button_layout.addItem(spacer)

        # 새로고침 버튼 추가
        self.refresh_button = QtWidgets.QPushButton("새로고침", self)
        self.refresh_button.setFixedWidth(80)  # 가로 길이 조정
        self.refresh_button.clicked.connect(self.refresh_table)
        self.button_layout.addWidget(self.refresh_button)

        # 닫기 버튼 추가
        self.close_button = QtWidgets.QPushButton("닫기", self)
        self.close_button.setFixedWidth(80)  # 가로 길이 조정
        self.close_button.clicked.connect(self.close)
        self.button_layout.addWidget(self.close_button)

        # 버튼 레이아웃을 메인 레이아웃에 추가
        self.layout.addLayout(self.button_layout)

        self.tabWidget_tables = QtWidgets.QTabWidget(self)
        self.layout.addWidget(self.tabWidget_tables)

        # target_db가 주어지면 테이블 뷰를 초기화
        if target_db is not None:
            self.init_table_view(parent.mySQL_obj, target_db)

    def init_table_view(self, mySQL_obj, target_db):
        # target_db에 연결
        mySQL_obj.connectDB(target_db)

        tableNameList = mySQL_obj.showAllTable(target_db)
        self.tabWidget_tables.clear()  # 기존 탭 내용 초기화

        for tableName in tableNameList:
            if 'info' in tableName or 'token' in tableName:
                continue
            tableDF = mySQL_obj.TableToDataframe(tableName)

            # 데이터프레임 값을 튜플 형태의 리스트로 변환
            tuple_list = [tuple(row) for row in tableDF.itertuples(index=False, name=None)]

            # 새로운 탭 생성
            new_tab = QWidget()
            new_tab_layout = QVBoxLayout(new_tab)
            new_table = QTableWidget(new_tab)
            new_tab_layout.addWidget(new_table)

            # 테이블 데이터 설정
            new_table.setRowCount(len(tuple_list))
            new_table.setColumnCount(len(tableDF.columns))
            new_table.setHorizontalHeaderLabels(tableDF.columns)

            # 열 너비 조정
            header = new_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)

            # 행 전체 선택 설정 및 단일 선택 모드
            new_table.setSelectionBehavior(QTableWidget.SelectRows)
            new_table.setSelectionMode(QTableWidget.SingleSelection)

            for row_idx, row_data in enumerate(tuple_list):
                for col_idx, col_data in enumerate(row_data):
                    new_table.setItem(row_idx, col_idx, QTableWidgetItem(str(col_data)))

            self.tabWidget_tables.addTab(new_tab, tableName.split('_')[-1])

    def refresh_table(self):
        # 테이블 뷰를 다시 초기화하여 데이터를 새로 로드
        self.init_table_view(self.parent.mySQL_obj, self.target_db)

class Manager_Database:
    def __init__(self, main_window):
        self.main = main_window
        self.DB = copy.deepcopy(self.main.DB)
        self.DB_table_column = ['Name', 'Type', 'Keyword', 'Period', 'Option', 'Crawl Start', 'Crawl End', 'Requester']
        self.main.table_maker(self.main.database_tablewidget, self.DB['DBdata'], self.DB_table_column)
        self.database_buttonMatch()

    def database_delete_DB(self):
        try:
            self.main.printStatus("삭제 중...")
            def delete_database():
                selected_row = self.main.database_tablewidget.currentRow()
                if selected_row >= 0:
                    target_db = self.DB['DBlist'][selected_row]
                    self.main.mySQL_obj.connectDB(target_db)
                    db_info_df = self.main.mySQL_obj.TableToDataframe(target_db + '_info')
                    db_info = db_info_df.iloc[-1].tolist()
                    endtime = db_info[3]

                    if endtime == '-':
                        confirm_msg = f"현재 크롤링이 진행 중입니다.\n\n'{target_db}' 크롤링을 중단하시겠습니까?"
                    else:
                        confirm_msg = f"'{target_db}'를 삭제하시겠습니까?"

                    reply = QMessageBox.question(self.main, 'Confirm Delete', confirm_msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        self.main.mySQL_obj.dropDB(target_db)
                        self.database_refresh_DB()

            QTimer.singleShot(1, delete_database)
            QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def database_view_DB(self):
        try:
            reply = QMessageBox.question(self.main, 'Confirm Delete', 'DB 조회는 로딩 시 많은 시간이 소요됩니다\n\n진행하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.main.printStatus("불러오는 중...")
                def load_database():
                    selected_row = self.main.database_tablewidget.currentRow()
                    if selected_row >= 0:
                        target_DB = self.DB['DBlist'][selected_row]
                        self.DBtable_window = TableWindow(self.main, target_DB)
                        self.DBtable_window.show()

                QTimer.singleShot(1, load_database)
                QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def database_search_DB(self):
        try:
            search_text = self.main.database_searchDB_lineinput.text().lower()
            if not search_text:
                return

            # 현재 선택된 행의 다음 행부터 검색 시작
            start_row = self.main.database_tablewidget.currentRow() + 1 if self.main.database_tablewidget.currentRow() != -1 else 0

            for row in range(start_row, self.main.database_tablewidget.rowCount()):
                match = False
                for col in range(self.main.database_tablewidget.columnCount()):
                    item = self.main.database_tablewidget.item(row, col)
                    if item and search_text in item.text().lower():
                        match = True
                        break

                if match:
                    self.main.database_tablewidget.selectRow(row)
                    return

            # 검색어가 처음부터 검색되도록 반복
            for row in range(0, start_row):
                match = False
                for col in range(self.main.database_tablewidget.columnCount()):
                    item = self.main.database_tablewidget.item(row, col)
                    if item and search_text in item.text().lower():
                        match = True
                        break

                if match:
                    self.main.database_tablewidget.selectRow(row)
                    return
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def database_save_DB(self):
        try:
            class OptionDialog(QDialog):
                def __init__(self):
                    super().__init__()
                    self.setWindowTitle('Select Options')
                    self.resize(250, 150)  # 너비 400, 높이 300

                    # 다이얼로그 레이아웃
                    self.layout = QVBoxLayout()

                    # 라디오 버튼 그룹 생성
                    self.radio_all = QRadioButton('전체 기간')
                    self.radio_custom = QRadioButton('기간 설정')
                    self.radio_all.setChecked(True)  # 기본으로 "전체 저장" 선택

                    self.layout.addWidget(QLabel('Choose Option:'))
                    self.layout.addWidget(self.radio_all)
                    self.layout.addWidget(self.radio_custom)

                    # 기간 입력 폼 (처음엔 숨김)
                    self.date_input_form = QWidget()
                    self.date_input_form_layout = QFormLayout()

                    self.start_date_input = QLineEdit()
                    self.start_date_input.setPlaceholderText('YYYYMMDD')
                    self.end_date_input = QLineEdit()
                    self.end_date_input.setPlaceholderText('YYYYMMDD')

                    self.date_input_form_layout.addRow('시작 날짜:', self.start_date_input)
                    self.date_input_form_layout.addRow('종료 날짜:', self.end_date_input)
                    self.date_input_form.setLayout(self.date_input_form_layout)
                    self.date_input_form.setVisible(False)

                    self.layout.addWidget(self.date_input_form)

                    # 다이얼로그의 OK/Cancel 버튼
                    self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    self.button_box.accepted.connect(self.accept)
                    self.button_box.rejected.connect(self.reject)

                    self.layout.addWidget(self.button_box)

                    self.setLayout(self.layout)

                    # 신호 연결
                    self.radio_custom.toggled.connect(self.toggle_date_input)

                def toggle_date_input(self, checked):
                    # "기간 설정" 라디오 버튼이 선택되면 날짜 입력 필드 표시
                    self.date_input_form.setVisible(checked)

                def accept(self):
                    # 확인 버튼을 눌렀을 때 데이터 유효성 검사
                    if self.radio_custom.isChecked():
                        date_format = "yyyyMMdd"
                        start_date = QDate.fromString(self.start_date_input.text(), date_format)
                        end_date = QDate.fromString(self.end_date_input.text(), date_format)

                        if not (start_date.isValid() and end_date.isValid()):
                            QMessageBox.warning(self, '날짜 오류', '잘못된 날짜 형식입니다.')
                            return  # 확인 동작을 취소함

                    super().accept()  # 정상적인 경우에만 다이얼로그를 종료함

            def replace_dates_in_filename(filename, new_start_date, new_end_date):
                pattern = r"_(\d{8})_(\d{8})_"
                new_filename = re.sub(pattern, f"_{new_start_date}_{new_end_date}_", filename)
                return new_filename

            def select_database():
                selected_row = self.main.database_tablewidget.currentRow()
                if not selected_row >= 0:
                    return
                self.main.printStatus("데이터를 저장할 위치를 선택하세요...")
                target_db = self.DB['DBlist'][selected_row]
                folder_path = QFileDialog.getExistingDirectory(self.main, "Select Directory", self.main.default_directory)
                if folder_path == '':
                    self.main.printStatus()
                    return
                if folder_path:
                    dialog = OptionDialog()
                    selected_options = {}
                    if dialog.exec_() == QDialog.Accepted:
                        # 선택된 라디오 버튼 확인
                        if dialog.radio_all.isChecked():
                            selected_options['option'] = 'all'
                        elif dialog.radio_custom.isChecked():
                            selected_options['option'] = 'part'

                        # 기간 설정이 선택된 경우, 입력된 날짜 가져오기
                        if selected_options['option'] == 'part':
                            date_format = "yyyyMMdd"
                            start_date = QDate.fromString(dialog.start_date_input.text(), date_format)
                            end_date = QDate.fromString(dialog.end_date_input.text(), date_format)

                            if start_date.isValid() and end_date.isValid():
                                selected_options['start_date'] = start_date.toString(date_format)
                                selected_options['end_date'] = end_date.toString(date_format)
                            else:
                                QMessageBox.warning(dialog, '날짜 오류', '잘못된 날짜 형식입니다.')
                                selected_options['option'] = None  # 잘못된 날짜가 입력된 경우 선택 옵션을 None으로 설정

                    if selected_options == {}:
                        self.main.printStatus()
                        return
                    if selected_options['option'] == 'part':
                        self.main.printStatus(f"{replace_dates_in_filename(target_db, selected_options['start_date'], selected_options['end_date'])} 저장 중...")
                    else:
                        self.main.printStatus(f"{target_db} 저장 중...")
                    QTimer.singleShot(1000, lambda: save_database(target_db, folder_path, selected_options))
                    QTimer.singleShot(1000, self.main.printStatus)

            def save_database(target_db, folder_path, selected_options):

                dbpath = os.path.join(folder_path, target_db)
                if selected_options['option'] == 'part':
                    start_date = selected_options['start_date']
                    end_date = selected_options['end_date']

                    start_date_formed = pd.to_datetime(start_date, format='%Y%m%d')
                    end_date_formed = pd.to_datetime(end_date, format='%Y%m%d')
                    dbpath = os.path.join(folder_path, replace_dates_in_filename(target_db, start_date, end_date))

                try:
                    while True:
                        try:
                            os.mkdir(dbpath)
                            os.mkdir(os.path.join(dbpath, 'token_data'))
                            break
                        except:
                            dbpath += "_copy"

                    statisticsURL = []

                    self.main.mySQL_obj.connectDB(target_db)
                    tableList = self.main.mySQL_obj.showAllTable(target_db)
                    tableList = [table for table in tableList if 'info' not in table]
                    tableList = sorted(tableList, key=lambda x: ('statistics' not in x, x))

                    self.main.openFileExplorer(dbpath)
                    for tableName in tableList:
                        edited_tableName = replace_dates_in_filename(tableName, start_date, end_date) if selected_options['option'] == 'part' else tableName

                        # 테이블 데이터를 DataFrame으로 변환
                        tableDF = self.main.mySQL_obj.TableToDataframe(tableName)
                        target = next((column for column in tableDF.columns if 'Date' in column), None)
                        tableDF[target] = pd.to_datetime(tableDF[target])

                        # 기간 저장 옵션이 선택된 경우, 날짜 범위로 필터링
                        if selected_options['option'] == 'part':
                            tableDF = tableDF[(tableDF[target] >= start_date_formed) & (tableDF[target] <= end_date_formed)]

                        # statistics 테이블 처리
                        if 'statistics' in tableName:
                            statisticsURL = tableDF['Article URL'].tolist()
                            save_path = os.path.join(dbpath, 'token_data' if 'token' in tableName else '', f"{edited_tableName}.csv")
                            tableDF.to_csv(save_path, index=False, encoding='utf-8-sig', header=True)
                            continue

                        # reply 테이블 처리
                        if 'reply' in tableName and 'statisticsURL' in locals():
                            filteredDF = tableDF[tableDF['Article URL'].isin(statisticsURL)]
                            save_path = os.path.join(dbpath, 'token_data' if 'token' in tableName else '', f"{edited_tableName + '_statistics'}.csv")
                            filteredDF.to_csv(save_path, index=False, encoding='utf-8-sig', header=True)

                        # 기타 테이블 처리
                        save_dir = os.path.join(dbpath, 'token_data' if 'token' in tableName else '')
                        tableDF.to_csv(os.path.join(save_dir, f"{edited_tableName}.csv"), index=False, encoding='utf-8-sig', header=True)

                    QMessageBox.information(self.main, "Information", f"{edited_tableName}가 성공적으로 저장되었습니다")

                except Exception as e:
                    QMessageBox.critical(self.main, "Error", f"Failed to save database: {str(e)}")

            select_database()
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def database_refresh_DB(self):
        try:
            self.main.printStatus("새로고침 중")
            def refresh_database():
                self.DB = self.main.update_DB(self.DB)
                self.main.table_maker(self.main.database_tablewidget, self.DB['DBdata'], self.DB_table_column)

            QTimer.singleShot(1, refresh_database)
            QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def database_buttonMatch(self):
        self.main.database_refreshDB_button.clicked.connect(self.database_refresh_DB)
        self.main.database_searchDB_button.clicked.connect(self.database_search_DB)
        self.main.database_searchDB_lineinput.returnPressed.connect(self.database_search_DB)

        self.main.database_saveDB_button.clicked.connect(self.database_save_DB)
        self.main.database_deleteDB_button.clicked.connect(self.database_delete_DB)
        self.main.database_viewDB_button.clicked.connect(self.database_view_DB)
