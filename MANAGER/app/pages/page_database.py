import os
import sys
import gc
import copy
import json
import re
import warnings
import traceback
import pandas as pd
from tqdm import tqdm
from datetime import datetime, timedelta
import subprocess
import shutil
import platform
from PyQt5.QtCore import QDate, QSize
from PyQt5.QtGui import QKeySequence, QIcon
from PyQt5.QtWidgets import (
    QWidget, QMainWindow, QDialog, QVBoxLayout, QFormLayout, QTableWidget, QInputDialog,
    QButtonGroup, QPushButton, QDialogButtonBox, QRadioButton, QLabel, QTabWidget,
    QLineEdit, QFileDialog, QMessageBox, QSizePolicy, QSpacerItem, QHBoxLayout, QShortcut
)
import requests
import zipfile
from libs.console import openConsole, closeConsole
from urllib.parse import unquote

warnings.filterwarnings("ignore")


class Manager_Database:
    def __init__(self, main_window):
        self.main = main_window
        self.DB = copy.deepcopy(self.main.DB)

        self.DBTableColumn = ['Database', 'Type', 'Keyword',
                              'StartDate', 'EndDate', 'Option', 'Status', 'User', 'Size']
        self.main.makeTable(self.main.database_tablewidget,
                            self.DB['DBtable'], self.DBTableColumn, self.viewDBinfo)
        self.matchButton()
        self.chatgpt_mode = False
        self.console_open = False

    def deleteDB(self):
        try:
            selectedRow = self.main.database_tablewidget.currentRow()
            if selectedRow >= 0:
                DBdata = self.DB['DBdata'][selectedRow]
                DBuid = DBdata['uid']
                DBname = DBdata['name']
                status = DBdata['status']
                owner = DBdata['requester']

                if owner != self.main.user and self.main.user != 'admin':
                    QMessageBox.warning(
                        self.main, "Information", f"DB와 사용자 정보가 일치하지 않습니다")
                    return

                if status == 'Working':
                    confirm_msg = f"현재 크롤링이 진행 중입니다.\n\n'{DBname}' 크롤링을 중단하고 DB를 삭제하시겠습니까?"
                else:
                    confirm_msg = f"'{DBname}'를 삭제하시겠습니까?"

                reply = QMessageBox.question(
                    self.main, 'Confirm Delete', confirm_msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.main.Request('delete', f'crawls/{DBuid}')

                    if status == 'Working':
                        self.main.activeCrawl -= 1
                        QMessageBox.information(
                            self.main, "Information", f"크롤러 서버에 중단 요청을 전송했습니다")
                    else:
                        QMessageBox.information(
                            self.main, "Information", f"'{DBname}'가 삭제되었습니다")
                    self.main.userLogging(f'DATABASE -> delete_DB({DBname})')
                    self.refreshDB()

            self.main.printStatus(f"{self.main.fullStorage} GB / 2 TB")
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def viewDB(self):

        class TableWindow(QMainWindow):
            def __init__(self, parent=None, targetDB=None):
                super(TableWindow, self).__init__(parent)
                self.setWindowTitle(targetDB)
                self.resize(1600, 1200)

                self.parent = parent  # 부모 객체를 저장하여 나중에 사용
                self.targetDB = targetDB  # targetDB를 저장하여 나중에 사용

                self.centralWidget = QWidget(self)
                self.setCentralWidget(self.centralWidget)

                self.layout = QVBoxLayout(self.centralWidget)

                # 상단 버튼 레이아웃
                self.button_layout = QHBoxLayout()

                # spacer 아이템 추가 (버튼들을 오른쪽 끝에 배치하기 위해 앞에 추가)
                spacer = QSpacerItem(
                    40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
                self.button_layout.addItem(spacer)

                # 새로고침 버튼 추가
                self.refreshButton = QPushButton("새로고침", self)
                self.refreshButton.setFixedWidth(80)  # 가로 길이 조정
                self.refreshButton.clicked.connect(self.refresh_table)
                self.button_layout.addWidget(self.refreshButton)

                # 닫기 버튼 추가
                self.close_button = QPushButton("닫기", self)
                self.close_button.setFixedWidth(80)  # 가로 길이 조정
                self.close_button.clicked.connect(self.closeWindow)
                self.button_layout.addWidget(self.close_button)

                # 버튼 레이아웃을 메인 레이아웃에 추가
                self.layout.addLayout(self.button_layout)

                self.tabWidget_tables = QTabWidget(self)
                self.layout.addWidget(self.tabWidget_tables)

                # targetDB가 주어지면 테이블 뷰를 초기화
                if targetDB is not None:
                    self.init_viewTable(parent.mySQLObj, targetDB)

            def closeWindow(self):
                self.tabWidget_tables.clear()  # 탭 위젯 내용 삭제
                self.close()  # 창 닫기
                self.deleteLater()  # 객체 삭제
                gc.collect()

            def closeEvent(self, event):
                # 윈도우 창이 닫힐 때 closeWindow 메서드 호출
                self.closeWindow()
                event.accept()  # 창 닫기 이벤트를 허용

            def init_viewTable(self, mySQLObj, targetDB):
                # targetDB에 연결
                mySQLObj.connectDB(targetDB)

                tableNameList = mySQLObj.showAllTable(targetDB)
                self.tabWidget_tables.clear()  # 기존 탭 내용 초기화

                for tableName in tableNameList:
                    if 'info' in tableName or 'token' in tableName:
                        continue
                    tableDF_begin = mySQLObj.TableToDataframe(tableName, ':50')
                    tableDF_end = mySQLObj.TableToDataframe(tableName, ':-50')
                    tableDF = pd.concat([tableDF_begin, tableDF_end], axis=0)
                    tableDF = tableDF.drop(columns=['id'])

                    # 데이터프레임 값을 튜플 형태의 리스트로 변환
                    self.tuple_list = [
                        tuple(row) for row in tableDF.itertuples(index=False, name=None)]

                    # 새로운 탭 생성
                    new_tab = QWidget()
                    new_tab_layout = QVBoxLayout(new_tab)
                    new_table = QTableWidget(new_tab)
                    new_tab_layout.addWidget(new_table)

                    # makeTable 함수를 호출하여 테이블 설정
                    self.parent.makeTable(
                        new_table, self.tuple_list, list(tableDF.columns))

                    # 탭 위젯에 추가
                    self.tabWidget_tables.addTab(
                        new_tab, tableName.split('_')[-1])

                    # 메모리 해제
                    new_tab = None
                    new_table = None

            def refresh_table(self):
                # 테이블 뷰를 다시 초기화하여 데이터를 새로 로드
                self.init_viewTable(self.parent.mySQLObj, self.targetDB)

        try:
            reply = QMessageBox.question(
                self.main, 'Confirm View', 'DB 조회는 데이터의 처음과 마지막 50개의 행만 불러옵니다\n\n진행하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.main.printStatus("불러오는 중...")

                def destory_table():
                    del self.DBtable_window
                    gc.collect()

                selectedRow = self.main.database_tablewidget.currentRow()
                if selectedRow >= 0:
                    targetDB = self.DB['DBnames'][selectedRow]
                    self.main.userLogging(f'DATABASE -> view_DB({targetDB})')
                    self.DBtable_window = TableWindow(self.main, targetDB)
                    self.DBtable_window.destroyed.connect(destory_table)
                    self.DBtable_window.show()

                self.main.printStatus(f"{self.main.fullStorage} GB / 2 TB")

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def viewDBinfo(self, row):
        try:
            self.main.printStatus("불러오는 중...")
            DBdata = self.DB['DBdata'][row]

            self.main.userLogging(
                f'DATABASE -> dbinfo_viewer({DBdata['name']})')

            # 다이얼로그 생성
            dialog = QDialog(self.main)
            dialog.setWindowTitle(f'{DBdata['name']}_Info')
            dialog.resize(540, 600)

            layout = QVBoxLayout()

            crawlType = DBdata['crawlType']
            crawlOption_int = int(DBdata['crawlOption'])

            CountText = DBdata['dataInfo']
            if CountText['totalArticleCnt'] == '0' and CountText['totalReplyCnt'] == '0' and CountText['totalRereplyCnt'] == '0':
                CountText = DBdata['status']
            else:
                CountText = f"Aricle: {CountText['totalArticleCnt']}\nReply: {CountText['totalReplyCnt']}\nRereply: {CountText['totalRereplyCnt']}"

            match crawlType:
                case 'Naver News':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '기사 + 댓글'
                        case 2:
                            crawlOption = '기사 + 댓글/대댓글'
                        case 3:
                            crawlOption = '기사'
                        case 4:
                            crawlOption = '기사 + 댓글(추가 정보)'

                case 'Naver Blog':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '블로그 본문'
                        case 2:
                            crawlOption = '블로그 본문 + 댓글/대댓글'

                case 'Naver Cafe':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '카페 본문'
                        case 2:
                            crawlOption = '카페 본문 + 댓글/대댓글'

                case 'YouTube':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '영상 정보 + 댓글/대댓글 (100개 제한)'
                        case 2:
                            crawlOption = '영상 정보 + 댓글/대댓글(무제한)'

                case 'ChinaDaily':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '기사 + 댓글'

                case 'ChinaSina':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '기사'
                        case 2:
                            crawlOption = '기사 + 댓글'

                case 'dcinside':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '게시글'
                        case 2:
                            crawlOption = '게시글 + 댓글'
                case _:
                    crawlOption = crawlOption_int

            starttime = DBdata['startTime']
            endtime = DBdata['endTime']

            try:
                ElapsedTime = datetime.strptime(
                    endtime, "%Y-%m-%d %H:%M") - datetime.strptime(starttime, "%Y-%m-%d %H:%M")
            except:
                ElapsedTime = str(
                    datetime.now() - datetime.strptime(starttime, "%Y-%m-%d %H:%M"))[:-7]
                if endtime == '오류 중단':
                    ElapsedTime = '오류 중단'

            if endtime != '오류 중단':
                endtime = endtime.replace(
                    '/', '-') if endtime != '크롤링 중' else endtime

            details_html = self.main.style_html + f"""
                <div class="version-details">
                    <table>
                        <tr>
                            <th>Item</th>
                            <th>Details</th>
                        </tr>
                        <tr>
                            <td><b>DB Name:</b></td>
                            <td>{DBdata['name']}</td>
                        </tr>
                        <tr>
                            <td><b>DB Size:</b></td>
                            <td>{DBdata['dbSize']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Type:</b></td>
                            <td>{DBdata['crawlType']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Keyword:</b></td>
                            <td>{DBdata['keyword']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Period:</b></td>
                            <td>{DBdata['startDate']} ~ {DBdata['endDate']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Option:</b></td>
                            <td>{crawlOption}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Start:</b></td>
                            <td>{starttime}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl End:</b></td>
                            <td>{endtime}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl ElapsedTime:</b></td>
                            <td>{ElapsedTime}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Requester:</b></td>
                            <td>{DBdata['requester']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Server:</b></td>
                            <td>{DBdata['crawlCom']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Speed:</b></td>
                            <td>{DBdata['crawlSpeed']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Result:</b></td>
                            <td class="detail-content">{CountText}</td>
                        </tr>
                    </table>
                </div>
            """

            detail_label = QLabel(details_html)
            detail_label.setWordWrap(True)

            layout.addWidget(detail_label)

            # 닫기 버튼 추가
            close_button = QPushButton('Close')
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button)

            ctrlw = QShortcut(QKeySequence("Ctrl+W"), dialog)
            ctrlw.activated.connect(dialog.accept)

            cmdw = QShortcut(QKeySequence("Ctrl+ㅈ"), dialog)
            cmdw.activated.connect(dialog.accept)

            dialog.setLayout(layout)
            self.main.printStatus(f"{self.main.fullStorage} GB / 2 TB")
            # 다이얼로그 실행
            dialog.show()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def searchDB(self):
        try:
            search_text = self.main.database_searchDB_lineinput.text().lower()
            if not search_text or search_text == "":
                if self.main.SETTING['DBKeywordSort'] == 'default':
                    self.main.SETTING['DBKeywordSort'] = 'on'
                    self.main.updateSettings(10, 'on')
                    QMessageBox.information(
                        self.main, "Information", "DB 정렬 기준이 '키워드순'으로 변경되었습니다")
                    self.refreshDB()
                else:
                    self.main.SETTING['DBKeywordSort'] = 'default'
                    self.main.updateSettings(10, 'default')
                    QMessageBox.information(
                        self.main, "Information", "DB 정렬 기준이 '최신순'으로 변경되었습니다")
                    self.refreshDB()
                return

            self.searchAdminMode(search_text)
            # 현재 선택된 행의 다음 행부터 검색 시작
            start_row = self.main.database_tablewidget.currentRow(
            ) + 1 if self.main.database_tablewidget.currentRow() != -1 else 0

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
            self.main.programBugLog(traceback.format_exc())

    def mergeDB(self):
        try:
            selectedRow = self.main.database_tablewidget.currentRow()
            if selectedRow < 0:
                return

            # 대상 DB 정보 가져오기
            targetDB_name = self.DB['DBnames'][selectedRow]
            targetDB_data = self.DB['DBdata'][selectedRow]

            owner = targetDB_data['requester']

            if owner != self.main.user and self.main.user != 'admin':
                QMessageBox.warning(self.main, "Information",
                                    f"DB와 사용자 정보가 일치하지 않습니다")
                return

            target_keyword = targetDB_data['keyword']
            target_crawl_type = targetDB_data['crawlType']
            target_count_data = eval(
                targetDB_data['dataInfo'])  # 통계 데이터 (딕셔너리 형태)
            target_start_date = targetDB_data['startDate']
            target_end_date = targetDB_data['endDate']

            # 다음 시작 날짜 계산
            target_end_date_dt = datetime.strptime(target_end_date, '%Y%m%d')
            next_start_date_dt = target_end_date_dt + timedelta(days=1)
            next_start_date = next_start_date_dt.strftime('%Y%m%d')

            # 병합 가능한 DB 필터링
            merge_candidates = [
                db_data['name'] for db_data in self.DB['DBdata']
                if db_data['keyword'] == target_keyword
                and db_data['crawlType'] == target_crawl_type
                and db_data['startDate'] == next_start_date
                and db_data['status'] != "Working"
            ]

            if not merge_candidates:
                QMessageBox.information(self.main, "Information",
                                        "병합 가능한 DB가 없습니다\n\n<병합 가능 조건>\n\n1. 키워드 동일\n2. 크롤링 옵션 동일\n3. 크롤링 기간 연속적\n(ex. 12/01~12/14 & 12/15~12/31)"
                                        )
                return

            # 병합할 DB 선택
            selected_db_name, ok = QInputDialog.getItem(
                self.main,
                "DB 선택",
                "병합할 DB를 선택하세요:",
                merge_candidates,
                0,
                False
            )

            if not ok or not selected_db_name:
                return

            # 선택된 DB 정보 가져오기

            selected_db_data = self.DB['DBdata'][self.DB['DBnames'].index(
                selected_db_name)]
            selected_db_end_date = selected_db_name.split('_')[3]
            selected_count_data = eval(
                selected_db_data['dataInfo'])  # 통계 데이터 (딕셔너리 형태)

            # 대상 DB 이름 업데이트 및 병합된 통계 데이터 계산
            targetDB_parts = targetDB_name.split('_')
            targetDB_parts[3] = selected_db_end_date
            updated_targetDB_name = '_'.join(targetDB_parts)

            merged_count_data = {
                'UrlCnt': target_count_data['UrlCnt'] + selected_count_data['UrlCnt'],
                'totalArticleCnt': target_count_data['totalArticleCnt'] + selected_count_data['totalArticleCnt'],
                'totalReplyCnt': target_count_data['totalReplyCnt'] + selected_count_data['totalReplyCnt'],
                'totalRereplyCnt': target_count_data['totalRereplyCnt'] + selected_count_data['totalRereplyCnt']
            }

            # 병합 여부 확인
            reply = QMessageBox.question(
                self.main,
                'DB 병합',
                f"'{updated_targetDB_name[:-10]}'로 병합하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply != QMessageBox.Yes:
                return

            self.main.userLogging(
                f'DATABASE -> Merge_DB({targetDB_name} + {selected_db_name} = {updated_targetDB_name})')
            if self.main.SETTING['ProcessConsole'] == 'default':
                openConsole("DB 병합")

            print('\n실행 중 프로그램 종료되면 DB 시스템에 큰 문제를 일으킬 수 있습니다')
            print("프로그램이 종료될 때까지 대기해주시기 바랍니다\n\n")

            target_tables = sorted(
                self.main.mySQLObj.showAllTable(targetDB_name))
            selected_tables = sorted(
                self.main.mySQLObj.showAllTable(selected_db_name))

            self.main.printStatus(f"병합 DB 생성 중...")
            print("\n병합 DB 생성 중...")
            self.main.mySQLObj.copyDB(targetDB_name, updated_targetDB_name)

            if self.main.SETTING['ProcessConsole'] == 'default':
                iterator = tqdm(list(zip(target_tables, selected_tables)), desc="Merging",
                                file=sys.stdout, bar_format="{l_bar}{bar}|", ascii=' =')
            else:
                iterator = list(zip(target_tables, selected_tables))

            for target_table, selected_table in iterator:
                self.main.printStatus(f"{target_table} 병합 중...")
                # 테이블 병합
                self.main.mySQLObj.mergeTable(
                    updated_targetDB_name, target_table, selected_db_name, selected_table)

                # 테이블 이름 업데이트
                target_table_parts = target_table.split('_')
                if 'token' in target_table:
                    target_table_parts[4] = selected_db_end_date
                else:
                    target_table_parts[3] = selected_db_end_date

                new_target_table = '_'.join(target_table_parts)
                self.main.mySQLObj.renameTable(
                    updated_targetDB_name, target_table, new_target_table)

            self.main.printStatus(f"DB 목록 업데이트 중...")
            print("\nDB 목록 업데이트 중...")
            self.main.mySQLObj.connectDB('crawler_db')
            self.main.mySQLObj.insertToTable('db_list', [[
                updated_targetDB_name, targetDB_data['crawlOption'],
                targetDB_data['startTime'], selected_db_data['endTime'],
                targetDB_data['requester'], targetDB_data['keyword'],
                self.main.mySQLObj.showDBSize(updated_targetDB_name)[0],
                targetDB_data['crawlCom'], targetDB_data['crawlSpeed'],
                str(merged_count_data)
            ]])
            self.main.mySQLObj.commit()
            self.main.printStatus()

            # DB 새로고침
            self.refreshDB()
            print("\nDB 병합 완료")
            if self.main.SETTING['ProcessConsole'] == 'default':
                closeConsole()

            reply = QMessageBox.question(
                self.main, 'Merge Finished', f"DB 병합이 완료되었습니다\n\n기존 DB를 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.main.printStatus("기존 DB 삭제 중...")
                self.main.mySQLObj.connectDB()
                self.main.mySQLObj.dropDB(targetDB_name)
                self.main.mySQLObj.dropDB(selected_db_name)
                self.main.mySQLObj.connectDB('crawler_db')
                self.main.mySQLObj.deleteTableRowByColumn(
                    'db_list', targetDB_name, 'DBname')
                self.main.mySQLObj.deleteTableRowByColumn(
                    'db_list', selected_db_name, 'DBname')
                self.main.printStatus(f"{self.main.fullStorage} GB / 2 TB")
                self.refreshDB()
                QMessageBox.information(
                    self.main, "Information", "삭제가 완료되었습니다")
            else:
                return

        except Exception:
            self.main.programBugLog(traceback.format_exc())

    def searchAdminMode(self, search_text):
        # ADMIN MODE
        try:
            if search_text == '/remove':
                reply = QMessageBox.question(self.main, 'Program Delete',
                                             f"'C:/BIGMACLAB_MANAGER'를 비롯한 모든 구성요소가 제거됩니다\n\nMANAGER를 완전히 삭제하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:

                    if os.path.exists(self.main.localDirectory):
                        shutil.rmtree(self.main.localDirectory)
                    exe_file_path = os.path.join(
                        os.environ['LOCALAPPDATA'], 'MANAGER', 'unins000.exe')
                    subprocess.Popen([exe_file_path], shell=True)
                    os._exit(0)

            if search_text == '/admin-mode' and self.main.user != 'admin':
                ok, password = self.main.checkPassword(True)
                if ok or password == self.main.admin_password:
                    self.main.user = 'admin'
                    QMessageBox.information(
                        self.main, "Admin Mode", f"관리자 권한이 부여되었습니다")
                else:
                    QMessageBox.warning(
                        self.main, 'Wrong Password', "비밀번호가 올바르지 않습니다")

            if search_text == '/toggle-logging':
                mode_changed = 'On' if self.main.CONFIG['Logging'] == 'Off' else 'Off'
                self.main.mySQLObj.connectDB('bigmaclab_manager_db')
                self.main.mySQLObj.updateTableCellByCondition(
                    'configuration', 'Setting', 'Logging', 'Config', mode_changed)
                self.main.mySQLObj.commit()
                self.main.CONFIG['Logging'] = 'On' if self.main.CONFIG['Logging'] == 'Off' else 'Off'
                QMessageBox.information(
                    self.main, "Information", f"Logging 설정을 '{mode_changed}'으로 변경했습니다")
                return
            if './user_change' in search_text:
                selectedRow = self.main.database_tablewidget.currentRow()
                if selectedRow < 0:
                    return
                # 대상 DB 정보 가져오기
                targetDB_name = self.DB['DBnames'][selectedRow]
                new = search_text.split()[1]

                self.main.mySQLObj.connectDB('crawler_db')
                self.main.mySQLObj.updateTableCellByCondition(
                    'db_list', "DBname", {targetDB_name}, 'Requester', new)
                QMessageBox.information(
                    self.main, "Information", f"요청자가 {new}로 변경했습니다")
                self.refreshDB()

            if search_text == '/update':
                self.main.updateProgram(sc=True)
                return
            if search_text == '/crawllog':
                self.main.viewTable('crawler_db', 'crawl_log', 'max')
                return
            if search_text == '/dblist':
                self.main.viewTable('crawler_db', 'db_list')
                return
            if search_text == '/config':
                self.main.viewTable('bigmaclab_manager_db', 'configuration')
                return
            if search_text == '/add_llm_model':
                llm_models = ''
                for index, (key, value) in enumerate(self.main.LLM_list.items(), start=1):
                    llm_models += f'{index}. {key} - {value}\n'

                reply = QMessageBox.question(self.main, 'Notification', f"현재 LLM 모델 목록은 다음과 같습니다\n\n{llm_models}\n모델을 추가하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    # 첫 번째 입력 받기 (표시 이름)
                    model_name, ok1 = QInputDialog.getText(
                        self.main, 'LLM 모델 추가', '모델의 표시 이름을 입력하세요:')

                    if ok1 and model_name:
                        # 두 번째 입력 받기 (실제 값)
                        model_value, ok2 = QInputDialog.getText(
                            self.main, 'LLM 모델 추가', '모델의 실제 값을 입력하세요:')

                        if ok2 and model_value:
                            # 입력된 값을 리스트에 추가
                            self.main.LLM_list[model_value] = model_name
                            self.main.mySQLObj.connectDB(
                                'bigmaclab_manager_db')
                            self.main.mySQLObj.updateTableCellByCondition(
                                'configuration', "Setting", 'LLM_model', 'Config', json.dumps(self.main.LLM_list))
                            self.main.mySQLObj.commit()
                            QMessageBox.information(
                                self.main, '성공', f'LLM 모델 "{model_name}"이(가) 추가되었습니다')

            if search_text == '/del_llm_model':
                llm_models = ''
                for index, (key, value) in enumerate(self.main.LLM_list.items(), start=1):
                    llm_models += f'{index}. {key} - {value}\n'

                reply = QMessageBox.question(self.main, 'Notification',
                                             f"현재 LLM 모델 목록은 다음과 같습니다\n\n{llm_models}\n삭제할 모델의 번호를 입력하십시오",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    # 첫 번째 입력 받기 (표시 이름)
                    num, ok1 = QInputDialog.getText(
                        self.main, 'LLM 모델 삭제', '모델의 번호를 입력하세요:')

                    if ok1 and num:
                        key_to_delete = list(self.main.LLM_list.keys())[
                            int(num)-1]
                        value_to_delete = list(self.main.LLM_list.values())[
                            int(num)-1]
                        del self.main.LLM_list[key_to_delete]
                        self.main.mySQLObj.connectDB('bigmaclab_manager_db')
                        self.main.mySQLObj.updateTableCellByCondition('configuration', "Setting", 'LLM_model',
                                                                      'Config', json.dumps(self.main.LLM_list))
                        self.main.mySQLObj.commit()
                        QMessageBox.information(
                            self.main, '성공', f'LLM 모델 {key_to_delete}이(가) 삭제되었습니다')

            if 'log' in search_text:
                match = re.match(r'\/(.+)_log', search_text)
                name = match.group(1)
                self.main.viewTable(f'{name}_db', 'manager_record', 'max')
                return
            if 'error' in search_text:  # ./error_db 이름
                # 패턴 매칭
                match = re.search(r"(?<=/error_)(.*)", search_text)
                dbname = match.group(1)
                self.main.mySQLObj.connectDB('crawler_db')
                self.main.mySQLObj.updateTableCellByCondition(
                    'db_list', 'DBname', dbname, 'Endtime', '오류 중단')
                self.main.mySQLObj.updateTableCellByCondition(
                    'db_list', 'DBname', dbname, 'Datainfo', '오류 중단')
                self.main.mySQLObj.commit()
                QMessageBox.information(
                    self.main, "Information", f"{dbname} 상태를 변경했습니다")
                self.refreshDB()
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def initLLMChat(self):
        try:
            self.main.printStatus("LLM Chat 실행 중")
            if platform.system() == "Darwin":  # macOS인지 확인
                osascript_cmd = '''
                    tell application "iTerm"
                        activate
                        set newWindow to (create window with default profile)
                        tell current session of newWindow
                            write text "cd /Users/yojunsmacbookprp/Documents/GitHub/BIGMACLAB && source venv/bin/activate && cd .. && cd LLM_API && python3 LLM_Chat.py"
                        end tell
                    end tell
                '''
                subprocess.Popen(["osascript", "-e", osascript_cmd])
            else:
                script_path = os.path.join(os.path.dirname(
                    __file__), 'assets', "LLM_Chat.exe")
                subprocess.Popen([script_path])

            self.main.userLogging(f'LLM Chat ON')
            self.main.printStatus(f"{self.main.fullStorage} GB / 2 TB")
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def saveDB(self):
        try:
            class OptionDialog(QDialog):
                def __init__(self):
                    super().__init__()
                    self.setWindowTitle('Select Options')
                    self.resize(250, 150)  # 초기 크기 설정

                    self.incl_word_list = []
                    self.excl_word_list = []
                    self.include_all_option = False

                    # 다이얼로그 레이아웃
                    self.layout = QVBoxLayout()

                    # 라디오 버튼 그룹 생성
                    self.radio_all = QRadioButton('전체 기간')
                    self.radio_custom = QRadioButton('기간 설정')
                    self.radio_all.setChecked(True)  # 기본으로 "전체 저장" 선택

                    self.layout.addWidget(QLabel('Choose Date Option:'))
                    self.layout.addWidget(self.radio_all)
                    self.layout.addWidget(self.radio_custom)

                    # 기간 입력 폼 (처음엔 숨김)
                    self.date_input_form = QWidget()
                    self.date_input_form_layout = QFormLayout()

                    self.start_date_input = QLineEdit()
                    self.start_date_input.setPlaceholderText('YYYYMMDD')
                    self.end_date_input = QLineEdit()
                    self.end_date_input.setPlaceholderText('YYYYMMDD')

                    self.date_input_form_layout.addRow(
                        '시작 날짜:', self.start_date_input)
                    self.date_input_form_layout.addRow(
                        '종료 날짜:', self.end_date_input)
                    self.date_input_form.setLayout(self.date_input_form_layout)
                    self.date_input_form.setVisible(False)

                    self.layout.addWidget(self.date_input_form)

                    # 라디오 버튼 그룹 생성
                    self.radio_nofliter = QRadioButton('필터링 안함')
                    self.radio_filter = QRadioButton('필터링 설정')
                    self.radio_nofliter.setChecked(True)  # 기본으로 "전체 저장" 선택

                    self.layout.addWidget(QLabel('Choose Filter Option:'))
                    self.layout.addWidget(self.radio_nofliter)
                    self.layout.addWidget(self.radio_filter)

                    # QButtonGroup 생성하여 라디오 버튼 그룹화
                    self.filter_group = QButtonGroup()
                    self.filter_group.addButton(self.radio_nofliter)
                    self.filter_group.addButton(self.radio_filter)

                    # 단어 입력 폼 (처음엔 숨김)
                    self.word_input_form = QWidget()
                    self.word_input_form_layout = QFormLayout()

                    self.incl_word_input = QLineEdit()
                    self.incl_word_input.setPlaceholderText('ex) 사과, 바나나')
                    self.excl_word_input = QLineEdit()
                    self.excl_word_input.setPlaceholderText('ex) 당근, 오이')

                    self.word_input_form_layout.addRow(
                        '포함 문자:', self.incl_word_input)
                    self.word_input_form_layout.addRow(
                        '제외 문자:', self.excl_word_input)
                    self.word_input_form.setLayout(self.word_input_form_layout)
                    self.word_input_form.setVisible(False)

                    # 포함 옵션 선택 (All 포함 vs Any 포함)
                    self.include_option_group = QButtonGroup()
                    self.include_all = QRadioButton('모두 포함/제외 (All)')
                    self.include_any = QRadioButton('개별 포함/제외 (Any)')
                    self.include_all.setToolTip("입력한 단어를 모두 포함/제외한 행을 선택")
                    self.include_any.setToolTip("입력한 단어를 개별 포함/제외한 행을 선택")
                    self.include_all.setChecked(True)  # 기본 선택: Any 포함

                    self.word_input_form_layout.addRow(QLabel('포함 옵션:'))
                    self.word_input_form_layout.addWidget(self.include_all)
                    self.word_input_form_layout.addWidget(self.include_any)

                    # 이름에 필터링 설정 포함할지
                    self.radio_name = QRadioButton('포함 설정')
                    self.radio_name.setToolTip("예) (+사과,바나나 _ -당근,오이 _all)")
                    self.radio_noname = QRadioButton('포함 안함')
                    self.radio_name.setChecked(True)  # 기본으로 "전체 저장" 선택

                    self.word_input_form_layout.addRow(QLabel('폴더명에 필터링 항목:'))
                    self.word_input_form_layout.addWidget(self.radio_name)
                    self.word_input_form_layout.addWidget(self.radio_noname)

                    # QButtonGroup 생성하여 라디오 버튼 그룹화
                    self.filter_name_group = QButtonGroup()
                    self.filter_name_group.addButton(self.radio_name)
                    self.filter_name_group.addButton(self.radio_noname)
                    self.word_input_form_layout.addWidget(self.radio_name)
                    self.word_input_form_layout.addWidget(self.radio_noname)

                    self.word_input_form.setLayout(self.word_input_form_layout)
                    self.word_input_form.setVisible(False)

                    self.layout.addWidget(self.word_input_form)

                    # 다이얼로그의 OK/Cancel 버튼
                    self.button_box = QDialogButtonBox(
                        QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    self.button_box.accepted.connect(self.accept)
                    self.button_box.rejected.connect(self.reject)

                    self.layout.addWidget(self.button_box)

                    self.setLayout(self.layout)

                    # 신호 연결
                    self.radio_custom.toggled.connect(self.toggle_date_input)
                    self.radio_filter.toggled.connect(self.toggle_word_input)

                def toggle_date_input(self, checked):
                    # "기간 설정" 라디오 버튼이 선택되면 날짜 입력 필드 표시
                    self.date_input_form.setVisible(checked)
                    self.adjust_dialog_size()

                def toggle_word_input(self, checked):
                    # "필터링 설정" 라디오 버튼이 선택되면 단어 입력 필드 표시
                    self.word_input_form.setVisible(checked)
                    self.adjust_dialog_size()

                def adjust_dialog_size(self):
                    """다이얼로그 크기를 현재 내용에 맞게 조정"""
                    self.adjustSize()  # 다이얼로그 크기를 내용에 맞게 자동 조정

                def accept(self):
                    # 확인 버튼을 눌렀을 때 데이터 유효성 검사
                    self.start_date = None
                    self.end_date = None

                    if self.radio_custom.isChecked():
                        date_format = "yyyyMMdd"
                        self.start_date = QDate.fromString(
                            self.start_date_input.text(), date_format)
                        self.end_date = QDate.fromString(
                            self.end_date_input.text(), date_format)

                        if not (self.start_date.isValid() and self.end_date.isValid()):
                            QMessageBox.warning(
                                self, 'Wrong Form', '잘못된 날짜 형식입니다.')
                            return  # 확인 동작을 취소함

                        self.start_date = self.start_date.toString(date_format)
                        self.end_date = self.end_date.toString(date_format)

                    if self.radio_filter.isChecked():
                        try:
                            incl_word_str = self.incl_word_input.text()
                            excl_word_str = self.excl_word_input.text()

                            if incl_word_str == '':
                                self.incl_word_list = []
                            else:
                                self.incl_word_list = incl_word_str.split(', ')

                            if excl_word_str == '':
                                self.excl_word_list = []
                            else:
                                self.excl_word_list = excl_word_str.split(', ')

                            if self.include_all.isChecked():
                                self.include_all_option = True
                            else:
                                self.include_all_option = False

                            if self.radio_name.isChecked():
                                self.include = True

                        except:
                            QMessageBox.warning(
                                self, 'Wrong Input', '잘못된 필터링 입력입니다')
                            return  # 확인 동작을 취소함

                    super().accept()  # 정상적인 경우에만 다이얼로그를 종료함

            selectedRow = self.main.database_tablewidget.currentRow()
            if not selectedRow >= 0:
                return
            self.main.printStatus("DB를 저장할 위치를 선택하여 주십시오")

            targetUid = self.DB['DBuids'][selectedRow]

            folder_path = QFileDialog.getExistingDirectory(
                self.main, "DB를 저장할 위치를 선택하여 주십시오", self.main.localDirectory)
            if folder_path == '':
                self.main.printStatus(f"{self.main.fullStorage} GB / 2 TB")
                return
            self.main.printStatus("DB 저장 옵션을 설정하여 주십시오")
            dialog = OptionDialog()
            option = {}

            if dialog.exec_() == QDialog.Accepted:

                if self.main.SETTING['ProcessConsole'] == 'default':
                    openConsole("DB 저장")

                option['dateOption'] = 'all' if dialog.radio_all.isChecked() else 'part'
                option['start_date'] = dialog.start_date if dialog.start_date else ""
                option['end_date'] = dialog.end_date if dialog.end_date else ""
                incl_words = dialog.incl_word_list
                excl_words = dialog.excl_word_list
                option['filterOption'] = bool(incl_words or excl_words)
                option['incl_words'] = dialog.incl_word_list
                option['excl_words'] = dialog.excl_word_list
                option['include_all'] = dialog.include_all_option
                option['filename_edit'] = dialog.radio_name.isChecked()

            self.main.printStatus("서버에서 파일 준비 중...")
            print("\n서버에서 파일 준비 중...\n")

            download_url = self.main.server_api + f"/crawls/{targetUid}/save"
            response = requests.post(
                download_url,
                json=option,
                stream=True,
                headers=self.main.api_headers,
                timeout=3600
            )
            response.raise_for_status()

            # 1) Content-Disposition 헤더에서 파일명 파싱
            content_disp = response.headers.get("Content-Disposition", "")

            # 2) 우선 filename="…" 시도
            m = re.search(r'filename="(?P<fname>[^"]+)"', content_disp)
            if m:
                zip_name = m.group("fname")
            else:
                # 3) 없으면 filename*=utf-8''… 로 시도
                m2 = re.search(
                    r"filename\*=utf-8''(?P<fname>[^;]+)", content_disp)
                if m2:
                    zip_name = unquote(m2.group("fname"))
                else:
                    zip_name = f"{targetUid}.zip"

            # 4) 이제 다운로드 & 압축 해제
            local_zip = os.path.join(folder_path, zip_name)
            total_size = int(response.headers.get("Content-Length", 0))

            with open(local_zip, "wb") as f, tqdm(
                total=total_size,
                file=sys.stdout,
                unit="B", unit_scale=True, unit_divisor=1024,
                desc="Downloading DB",
                ascii=True, ncols=80,
                bar_format="{desc}: |{bar}| {percentage:3.0f}% [{n_fmt}/{total_fmt} {unit}] @ {rate_fmt}",
                dynamic_ncols=True
            ) as pbar:
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

            self.main.printStatus("다운로드 완료, 압축 해제 중…")
            print("\n다운로드 완료, 압축 해제 중...\n")

            # 압축 풀 폴더 이름은 zip 파일 이름(확장자 제외)
            base_folder = os.path.splitext(zip_name)[0]
            extract_path = os.path.join(folder_path, base_folder)
            os.makedirs(extract_path, exist_ok=True)

            with zipfile.ZipFile(local_zip, "r") as zf:
                zf.extractall(extract_path)

            os.remove(local_zip)

            self.main.printStatus()
            closeConsole()

            reply = QMessageBox.question(self.main, 'Notification', f"DB 저장이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.main.openFileExplorer(extract_path)

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def refreshDB(self):
        try:
            self.main.printStatus("새로고침 중...")

            self.DB = self.main.updateDB()
            self.main.makeTable(self.main.database_tablewidget,
                                self.DB['DBtable'], self.DBTableColumn)

            self.main.printStatus(f"{self.main.fullStorage} GB / 2 TB")
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def matchButton(self):
        self.main.database_searchDB_button.clicked.connect(self.searchDB)
        self.main.database_chatgpt_button.clicked.connect(self.initLLMChat)
        self.main.database_searchDB_lineinput.returnPressed.connect(
            self.searchDB)
        self.main.database_searchDB_lineinput.setPlaceholderText(
            "검색어를 입력하고 Enter키나 검색 버튼을 누르세요...")

        self.main.database_saveDB_button.clicked.connect(self.saveDB)
        self.main.database_deleteDB_button.clicked.connect(self.deleteDB)
        self.main.database_viewDB_button.clicked.connect(self.viewDB)
        self.main.database_mergeDB_button.clicked.connect(self.mergeDB)

        self.main.database_chatgpt_button.setToolTip("LLM ChatBot")
        self.main.database_saveDB_button.setToolTip("Ctrl+S")
        self.main.database_viewDB_button.setToolTip("Ctrl+V")
        self.main.database_deleteDB_button.setToolTip("Ctrl+D")

        self.main.database_searchDB_button.setText("")  # 텍스트 제거
        self.main.database_searchDB_button.setIcon(QIcon(os.path.join(
            # 아이콘 설정 (이미지 경로 지정)
            os.path.dirname(__file__), '..', 'assets', 'search.png')))
        self.main.database_searchDB_button.setIconSize(
            QSize(18, 18))  # 아이콘 크기 조정 (원하는 크기로 설정)

        self.main.database_chatgpt_button.setText("")  # 텍스트 제거
        self.main.database_chatgpt_button.setIcon(QIcon(os.path.join(os.path.dirname(
            # 아이콘 설정 (이미지 경로 지정)
            __file__), '..', 'assets', 'chatgpt_logo.png')))
        self.main.database_chatgpt_button.setIconSize(
            QSize(19, 19))  # 아이콘 크기 조정 (원하는 크기로 설정)

    def setDatabaseShortcut(self):
        self.main.initShortcutialize()
        self.main.ctrld.activated.connect(self.deleteDB)
        self.main.ctrls.activated.connect(self.saveDB)
        self.main.ctrlm.activated.connect(self.mergeDB)
        self.main.ctrlv.activated.connect(self.viewDB)
        self.main.ctrlr.activated.connect(self.refreshDB)
        self.main.ctrlc.activated.connect(self.initLLMChat)

        self.main.cmdd.activated.connect(self.deleteDB)
        self.main.cmds.activated.connect(self.saveDB)
        self.main.cmdm.activated.connect(self.mergeDB)
        self.main.cmdv.activated.connect(self.viewDB)
        self.main.cmdr.activated.connect(self.refreshDB)
        self.main.cmdc.activated.connect(self.initLLMChat)
