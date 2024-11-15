import os
import gc
import warnings
import traceback
from datetime import datetime
from PyQt5.QtCore import QTimer, QStringListModel, Qt
from PyQt5.QtWidgets import (
    QMessageBox, QFileDialog, QHBoxLayout, QTableWidgetItem,
    QWidget, QToolBox, QHeaderView,
    QListView, QMainWindow, QVBoxLayout, QTableWidget,
    QPushButton, QSpacerItem, QSizePolicy
)
warnings.filterwarnings("ignore")

class Manager_User:
    def __init__(self, main_window):
        self.main = main_window
        self.user_init_table()
        self.device_init_table()
        self.user_buttonMatch()

    def user_init_table(self):
        # 데이터베이스 연결 및 데이터 가져오기
        self.main.mySQL_obj.connectDB('user_db')
        userDF = self.main.mySQL_obj.TableToDataframe('user_info')
        user_data = [(name, email, key) for _, name, email, key in userDF.itertuples(index=False, name=None)]

        # userNameList 및 userKeyList 업데이트
        self.userNameList = [name for name, _, key in user_data]
        self.userKeyList = [key for _, _, key in user_data if key != 'n']

        # 테이블 설정
        columns = ['Name', 'Email', 'PushOverKey']
        self.main.table_maker(
            widgetname=self.main.user_tablewidget,
            data=user_data,
            column=columns,
        )

    def device_init_table(self):
        # 데이터베이스 연결 및 데이터 가져오기
        self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
        userDF = self.main.mySQL_obj.TableToDataframe('device_list')
        device_data = [(user, device) for _, device, user in userDF.itertuples(index=False, name=None)]
        device_data = sorted(device_data, key=lambda x: (not x[0][0].isalpha(), x[0]))

        # userNameList 및 userKeyList 업데이트
        self.device_list = [device for name, device in device_data]
        self.user_list = [name for name, device in device_data]

        # 테이블 설정
        columns = ['User', 'Device']
        self.main.table_maker(
            widgetname=self.main.device_tablewidget,
            data=device_data,
            column=columns,
        )

    def user_add_user(self):
        try:
            name = self.main.user_name_lineinput.text()
            email = self.main.user_email_lineinput.text()
            key = self.main.user_key_lineinput.text()

            if self.main.user != 'admin':
                ok, password = self.main.pw_check(True)
                if not ok or password != self.main.admin_password:
                    return

            self.main.mySQL_obj.connectDB('user_db')

            reply = QMessageBox.question(self.main, 'Confirm Add', f"{name}님을 추가하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.main.mySQL_obj.connectDB('user_db')
                self.main.mySQL_obj.insertToTable(tableName='user_info', data_list=[[name, email, key]])
                self.userNameList.append(name)
                self.main.mySQL_obj.newDB(name+'_db')
                self.main.mySQL_obj.newTable('manager_record', ['Date', 'Log', 'Bug', 'D_Log'])
                self.main.mySQL_obj.commit()

                row_position = self.main.user_tablewidget.rowCount()
                self.main.user_tablewidget.insertRow(row_position)

                name_item = QTableWidgetItem(name)
                email_item = QTableWidgetItem(email)
                key_item = QTableWidgetItem(key)

                name_item.setTextAlignment(Qt.AlignCenter)
                email_item.setTextAlignment(Qt.AlignCenter)
                key_item.setTextAlignment(Qt.AlignCenter)

                self.main.user_tablewidget.setItem(row_position, 0, name_item)
                self.main.user_tablewidget.setItem(row_position, 1, email_item)
                self.main.user_tablewidget.setItem(row_position, 2, key_item)

                self.main.user_name_lineinput.clear()
                self.main.user_email_lineinput.clear()
                self.main.user_key_lineinput.clear()

        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def user_delete_user(self):
        try:
            if self.main.user != 'admin':
                ok, password = self.main.pw_check(True)
                if not ok or password != self.main.admin_password:
                    return

            selected_row = self.main.user_tablewidget.currentRow()
            if selected_row >= 0:
                reply = QMessageBox.question(self.main, 'Confirm Delete', f"{self.userNameList[selected_row]}님을 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.main.mySQL_obj.connectDB('user_db')
                    self.main.mySQL_obj.deleteTableRowByColumn('user_info', self.userNameList[selected_row], 'Name')
                    self.main.mySQL_obj.dropDB(self.userNameList[selected_row]+'_db')
                    self.userNameList.pop(selected_row)
                    self.main.user_tablewidget.removeRow(selected_row)

        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def user_delete_device(self):
        try:
            if self.main.user != 'admin':
                ok, password = self.main.pw_check(True)
                if not ok or password != self.main.admin_password:
                    return

            selected_row = self.main.device_tablewidget.currentRow()
            if selected_row >= 0:
                reply = QMessageBox.question(self.main, 'Confirm Delete', f"{self.device_list[selected_row]}를 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                    self.main.mySQL_obj.deleteTableRowByColumn('device_list', self.device_list[selected_row], 'device_name')
                    self.device_list.pop(selected_row)
                    self.main.user_tablewidget.removeRow(selected_row)
                    self.device_init_table()

        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def userDB_layout_maker(self):
        # File Explorer를 탭 레이아웃에 추가
        self.userDBfiledialog = self.main.filefinder_maker(self.main)
        self.main.tab3_userDB_fileexplorerlayout.addWidget(self.userDBfiledialog)

        # QToolBox 생성
        self.tool_box = QToolBox()
        self.main.tab3_userDB_buttonlayout.addWidget(self.tool_box)

        # QListView들을 저장할 딕셔너리 생성
        self.list_views = {}

        def create_list(DBname):
            # 데이터베이스에서 테이블 목록 가져오기
            data = self.main.mySQL_obj.showAllTable(database_name=DBname)
            if self.main.user != 'admin':
                data.remove('manager_record')

            # QListView 생성
            list_view = QListView()

            # 여러 항목을 선택할 수 있도록 MultiSelection 모드로 설정
            list_view.setSelectionMode(QListView.MultiSelection)

            # 데이터를 QListView와 연결하기 위한 모델 설정
            model = QStringListModel(data)
            list_view.setModel(model)

            # QListView 항목이 클릭될 때 발생하는 시그널 연결
            list_view.clicked.connect(self.toolbox_DBlistItem_selected)

            # QListView를 포함하는 QWidget 생성
            section = QWidget()
            layout = QVBoxLayout(section)
            layout.addWidget(list_view)

            # 생성된 QListView를 딕셔너리에 저장
            self.list_views[DBname] = list_view

            return section

        for userName in self.userNameList:
            DBname = userName + '_db'
            section = create_list(DBname)
            self.tool_box.addItem(section, DBname.replace('_db', ' DB'))

        self.tool_box.setCurrentIndex(-1)
        self.tool_box.currentChanged.connect(self.toolbox_DB_selected)

    def toolbox_DB_selected(self, index):
        self.selected_userDB = self.tool_box.itemText(index)
        self.selected_userDB = self.selected_userDB.replace(' DB', '_db')

    def toolbox_DBlistItem_selected(self, index):
        self.selected_DBlistItems = [item.data() for item in self.list_views[self.selected_userDB].selectedIndexes()]
        self.main.printStatus(f"Table {len(self.selected_DBlistItems)}개 선택됨")

    def toolbox_DBlistItem_delete(self):
        try:
            if not self.selected_DBlistItems or self.selected_DBlistItems == []:
                self.main.printStatus()
                return
            if 'manager_record' in self.selected_DBlistItems:
                ok, password = self.main.pw_check(True)
                if not ok or password != self.main.admin_password:
                    return

            reply = QMessageBox.question(self.main, 'Confirm Delete', "테이블을 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

            if reply == QMessageBox.Yes:
                self.main.printStatus(f"Table {len(self.selected_DBlistItems)}개 삭제 중...")
                self.main.mySQL_obj.connectDB(self.selected_userDB)

                for item in self.selected_DBlistItems:
                    self.main.mySQL_obj.dropTable(item)

                # QListView에서 해당 항목 삭제 및 업데이트
                list_view = self.list_views[self.selected_userDB]
                model = list_view.model()

                for item in self.selected_DBlistItems:
                    row = model.stringList().index(item)
                    model.removeRow(row)

                # 선택된 항목 초기화
                self.selected_DBlistItems = []

                # 리스트 갱신 (이 작업을 통해 UI에 즉각 반영됨)
                list_view.setModel(model)
                self.main.printStatus()
        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def toolbox_DBlistItem_add(self):
        try:
            selected_directory = self.toolbox_getfiledirectory(self.userDBfiledialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format", f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return
            self.main.printStatus()

            def update_list_view(DBname):
                # 데이터베이스에서 테이블 목록 다시 가져오기
                updated_data = self.main.mySQL_obj.showAllTable(database_name=DBname)

                # 해당 DB의 QListView 가져오기
                list_view = self.list_views[DBname]
                model = QStringListModel(updated_data)

                # 모델 업데이트 (QListView 갱신)
                list_view.setModel(model)

            self.main.mySQL_obj.connectDB(self.selected_userDB)

            self.main.printStatus(f'{self.selected_userDB}에 Table {len(selected_directory)}개 추가 중...')
            for csv_path in selected_directory:
                self.main.mySQL_obj.CSVToTable(csv_path, os.path.basename(csv_path).replace('.csv', ''))
            update_list_view(self.selected_userDB)
            self.main.printStatus()
        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def toolbox_DBlistItem_view(self, row=False, name=''):
        if row != False:
            row = self.main.user_tablewidget.currentRow()
            self.selected_DBlistItems = ['manager_record']
            self.selected_userDB = self.userNameList[row] + '_db'
        if name != '':
            self.selected_DBlistItems = ['manager_record']
            self.selected_userDB = name + '_db'

        class SingleTableWindow(QMainWindow):
            def __init__(self, parent=None, target_db=None, target_table=None):
                super(SingleTableWindow, self).__init__(parent)
                self.setWindowTitle(f"{target_db[:-3]}의 {target_table}")
                self.setGeometry(100, 100, 1600, 1200)

                self.parent = parent  # 부모 객체 저장
                self.target_db = target_db  # 대상 데이터베이스 이름 저장
                self.target_table = target_table  # 대상 테이블 이름 저장

                self.central_widget = QWidget(self)
                self.setCentralWidget(self.central_widget)

                self.layout = QVBoxLayout(self.central_widget)

                # 상단 버튼 레이아웃
                self.button_layout = QHBoxLayout()

                # spacer 아이템 추가 (버튼을 오른쪽 끝에 배치)
                spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
                self.button_layout.addItem(spacer)

                # 닫기 버튼 추가
                self.close_button = QPushButton("닫기", self)
                self.close_button.setFixedWidth(80)
                self.close_button.clicked.connect(self.closeWindow)
                self.button_layout.addWidget(self.close_button)

                # 버튼 레이아웃을 메인 레이아웃에 추가
                self.layout.addLayout(self.button_layout)

                # target_db와 target_table이 주어지면 테이블 뷰를 초기화
                if target_db is not None and target_table is not None:
                    self.init_table_view(parent.mySQL_obj, target_db, target_table)

            def closeWindow(self):
                self.close()  # 창 닫기
                self.deleteLater()  # 객체 삭제
                gc.collect()

            def closeEvent(self, event):
                # 윈도우 창이 닫힐 때 closeWindow 메서드 호출
                self.closeWindow()
                event.accept()  # 창 닫기 이벤트 허용

            def init_table_view(self, mySQL_obj, target_db, target_table):
                # target_db에 연결
                mySQL_obj.connectDB(target_db)
                tableDF = mySQL_obj.TableToDataframe(target_table)
                if target_table == 'manager_record':
                    tableDF = tableDF.iloc[::-1].reset_index(drop=True)

                # 데이터프레임 값을 문자열로 변환하여 튜플 형태의 리스트로 저장
                self.tuple_list = [tuple(str(cell) for cell in row[1:]) for row in
                                   tableDF.itertuples(index=False, name=None)]

                # 테이블 위젯 생성
                new_table = QTableWidget(self.central_widget)
                self.layout.addWidget(new_table)

                # column 정보를 리스트로 저장
                columns = list(tableDF.columns)
                columns.pop(0)
                
                # table_maker 함수를 호출하여 테이블 설정
                self.parent.table_maker(new_table, self.tuple_list, columns)

        try:
            if not self.selected_DBlistItems or self.selected_DBlistItems == []:
                self.main.printStatus()
                return
            if len(self.selected_DBlistItems) > 1:
                QMessageBox.warning(self.main, "Wrong Selection", f"선택 가능한 테이블 수는 1개입니다")
                return
            if self.selected_DBlistItems[0] == 'manager_record':
                if self.main.user != 'admin':
                    ok, password = self.main.pw_check(True)
                    if not ok or password != self.main.admin_password:
                        return

            def destory_table():
                del self.DBtable_window
                gc.collect()

            def load_database():
                self.DBtable_window = SingleTableWindow(self.main, self.selected_userDB, self.selected_DBlistItems[0])
                self.DBtable_window.destroyed.connect(destory_table)
                self.DBtable_window.show()

            self.main.printStatus(f"{self.selected_DBlistItems[0]} 조회 중...")
            QTimer.singleShot(1, load_database)
            QTimer.singleShot(1, self.main.printStatus)

        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def toolbox_DBlistItem_save(self):
        try:
            if not self.selected_DBlistItems or self.selected_DBlistItems == []:
                self.main.printStatus()
                return

            self.main.printStatus("데이터를 저장할 위치를 선택하세요...")
            folder_path = QFileDialog.getExistingDirectory(self.main, "데이터를 저장할 위치를 선택하세요", self.main.default_directory)
            if folder_path == '':
                self.main.printStatus()
                return

            folder_path = os.path.join(folder_path, f'{self.selected_userDB}_download_{datetime.now().strftime('%m%d_%H%M')}')
            os.makedirs(folder_path, exist_ok=True)

            self.main.printStatus(f"Table {len(self.selected_DBlistItems)}개 저장 중...")
            self.main.mySQL_obj.connectDB(self.selected_userDB)

            self.main.openFileExplorer(folder_path)
            for item in self.selected_DBlistItems:
                self.main.mySQL_obj.TableToCSV(item, folder_path)

            self.main.printStatus()
        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def toolbox_getfiledirectory(self, file_dialog):
        selected_directory = file_dialog.selectedFiles()
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

    def user_buttonMatch(self):
        self.main.user_adduser_button.clicked.connect(self.user_add_user)
        self.main.user_deleteuser_button.clicked.connect(self.user_delete_user)
        self.main.user_log_button.clicked.connect(lambda: self.toolbox_DBlistItem_view(row=True))

        self.selected_userDB = 'admin_db'
        self.selected_DBlistItem = None
        self.selected_DBlistItems = []
        self.main.userDB_list_delete_button.clicked.connect(self.toolbox_DBlistItem_delete)
        self.main.userDB_list_add_button.clicked.connect(self.toolbox_DBlistItem_add)
        self.main.userDB_list_view_button.clicked.connect(self.toolbox_DBlistItem_view)
        self.main.userDB_list_save_button.clicked.connect(self.toolbox_DBlistItem_save)
        self.main.device_delete_button.clicked.connect(self.user_delete_device)

        self.main.user_adduser_button.setToolTip("Ctrl+A")
        self.main.user_deleteuser_button.setToolTip("Ctrl+D")
        self.main.user_log_button.setToolTip("Ctrl+L")
        self.main.userDB_list_delete_button.setToolTip("Ctrl+D")
        self.main.userDB_list_add_button.setToolTip("Ctrl+A")
        self.main.userDB_list_view_button.setToolTip("Ctrl+V")
        self.main.userDB_list_save_button.setToolTip("Ctrl+S")
        self.main.device_delete_button.setToolTip("Ctrl+D")

    def user_shortcut_setting(self):
        self.update_shortcuts_based_on_tab(0)
        self.main.tabWidget_user.currentChanged.connect(self.update_shortcuts_based_on_tab)

    def update_shortcuts_based_on_tab(self, index):
        self.main.shortcut_initialize()

        # User List
        if index == 0:
            self.main.ctrld.activated.connect(self.user_delete_user)
            self.main.ctrll.activated.connect(lambda: self.toolbox_DBlistItem_view(True))
            self.main.ctrla.activated.connect(lambda: self.toolbox_DBlistItem_view(True))

        # User DB
        if index == 1:
            self.main.ctrld.activated.connect(self.toolbox_DBlistItem_delete)
            self.main.ctrlv.activated.connect(self.toolbox_DBlistItem_view)
            self.main.ctrla.activated.connect(self.toolbox_DBlistItem_add)
            self.main.ctrls.activated.connect(self.toolbox_DBlistItem_save)

        # Device List
        if index == 2:
            self.main.ctrld.activated.connect(self.user_delete_device)