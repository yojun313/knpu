import os
import sys
import warnings
import traceback
from datetime import datetime
from PyQt5.QtCore import QStringListModel, Qt
from PyQt5.QtWidgets import (
    QMessageBox, QFileDialog, QHBoxLayout, QTableWidgetItem,
    QWidget, QToolBox,
    QListView, QVBoxLayout,
    QPushButton, QDialog, QLabel, QCheckBox
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
        self.userMailList = [email for _, email, key in user_data]

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
                    QMessageBox.information(self.main, "Information", f"'{self.userNameList[selected_row]}'님이 삭제되었습니다")
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
                    QMessageBox.information(self.main, "Information", f"'{self.device_list[selected_row]}'가 삭제되었습니다")
                    self.device_list.pop(selected_row)
                    self.main.user_tablewidget.removeRow(selected_row)
                    self.device_init_table()


        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def user_settings(self):
        class SettingsDialog(QDialog):
            def __init__(self, setting):
                super().__init__()
                self.setting_path = setting['path']
                self.setWindowTitle("Settings")
                self.resize(400, 200)

                # 단일 레이아웃 생성
                main_layout = QVBoxLayout()

                # 앱 테마 설정 섹션
                theme_label = QLabel("앱 테마 설정:")
                self.light_mode_radio = QCheckBox("라이트 모드")
                self.dark_mode_radio = QCheckBox("다크 모드")
                if setting['Theme'] == 'default':
                    self.light_mode_radio.setChecked(True)  # 기본값
                else:
                    self.dark_mode_radio.setChecked(True)
                    # 서로 배타적으로 선택되도록 설정
                self.light_mode_radio.toggled.connect(lambda: self.dark_mode_radio.setChecked(False) if self.light_mode_radio.isChecked() else None)
                self.dark_mode_radio.toggled.connect(lambda: self.light_mode_radio.setChecked(False) if self.dark_mode_radio.isChecked() else None)

                main_layout.addWidget(theme_label)
                main_layout.addWidget(self.light_mode_radio)
                main_layout.addWidget(self.dark_mode_radio)

                # 부팅 스크린 사이즈 설정 섹션
                screen_size_label = QLabel("부팅 시 창 크기:")
                self.default_size_radio = QCheckBox("기본값")
                self.maximized_radio = QCheckBox("최대화")
                if setting['ScreenSize'] == 'default':
                    self.default_size_radio.setChecked(True)  # 기본값
                else:
                    self.maximized_radio.setChecked(True)
                self.default_size_radio.toggled.connect(lambda: self.maximized_radio.setChecked(False) if self.default_size_radio.isChecked() else None)
                self.maximized_radio.toggled.connect(lambda: self.default_size_radio.setChecked(False) if self.maximized_radio.isChecked() else None)

                main_layout.addWidget(screen_size_label)
                main_layout.addWidget(self.default_size_radio)
                main_layout.addWidget(self.maximized_radio)

                # 확인 및 취소 버튼 섹션
                save_button = QPushButton("Save")
                save_button.clicked.connect(self.save_settings)  # 저장 버튼 클릭 이벤트 연결
                cancel_button = QPushButton("Cancel")
                cancel_button.clicked.connect(self.reject)  # 취소 버튼 클릭 이벤트 연결

                # 버튼을 하나의 가로 레이아웃으로 추가
                button_layout = QHBoxLayout()
                button_layout.addWidget(save_button)
                button_layout.addWidget(cancel_button)

                main_layout.addLayout(button_layout)

                # 메인 레이아웃을 창에 설정
                self.setLayout(main_layout)

            def save_settings(self):
                # 선택된 설정 가져오기
                self.theme = "default" if self.light_mode_radio.isChecked() else "dark"
                self.screen_size = "default" if self.default_size_radio.isChecked() else "max"

                # 설정 저장 로직 (예: .env 파일 업데이트)
                self.update_env_file()
                self.accept()

            def update_env_file(self):
                """
                .env 파일에 설정 업데이트
                """
                # 설정 키-값 딕셔너리 관리
                options = {
                    "theme": {"key": "OPTION_1", "value": self.theme},  # 테마 설정
                    "screensize": {"key": "OPTION_2", "value": self.screen_size}  # 스크린 사이즈 설정
                }

                # .env 파일 읽기 및 쓰기
                if not options:
                    return

                lines = []
                if self.setting_path and os.path.exists(self.setting_path):
                    with open(self.setting_path, "r") as file:
                        lines = file.readlines()

                with open(self.setting_path, "w") as file:
                    keys_updated = set()

                    # 기존 파일 수정
                    for line in lines:
                        key, sep, value = line.partition("=")
                        key = key.strip()

                        # 기존 키 업데이트
                        for option in options.values():
                            if key == option["key"]:
                                file.write(f"{key}={option['value']}\n")
                                keys_updated.add(key)
                                break
                        else:
                            file.write(line)

                    # 새 설정 추가
                    for option in options.values():
                        if option["key"] not in keys_updated:
                            file.write(f"{option['key']}={option['value']}\n")

        try:
            dialog = SettingsDialog(self.main.SETTING)
            if dialog.exec_() == QDialog.Accepted:
                QMessageBox.information(self.main, "Information", f"설정이 완료되었습니다\n\n프로그램 재부팅 시 설정이 반영됩니다")

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

    def toolbox_DBlistItem_view(self, row=False):
        popupsize=None
        if row != False:
            row = self.main.user_tablewidget.currentRow()
            self.selected_DBlistItems = ['manager_record']
            self.selected_userDB = self.userNameList[row] + '_db'
            popupsize = 'max'

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

            self.main.table_view(self.selected_userDB, self.selected_DBlistItems[0], popupsize)

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
        self.main.user_setting_button.clicked.connect(self.user_settings)
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

            self.main.cmdd.activated.connect(self.user_delete_user)
            self.main.cmdl.activated.connect(lambda: self.toolbox_DBlistItem_view(True))
            self.main.cmda.activated.connect(lambda: self.toolbox_DBlistItem_view(True))

        # User DB
        if index == 1:
            self.main.ctrld.activated.connect(self.toolbox_DBlistItem_delete)
            self.main.ctrlv.activated.connect(self.toolbox_DBlistItem_view)
            self.main.ctrla.activated.connect(self.toolbox_DBlistItem_add)
            self.main.ctrls.activated.connect(self.toolbox_DBlistItem_save)

            self.main.cmdd.activated.connect(self.toolbox_DBlistItem_delete)
            self.main.cmdv.activated.connect(self.toolbox_DBlistItem_view)
            self.main.cmda.activated.connect(self.toolbox_DBlistItem_add)
            self.main.cmds.activated.connect(self.toolbox_DBlistItem_save)

        # Device List
        if index == 2:
            self.main.ctrld.activated.connect(self.user_delete_device)

            self.main.cmdd.activated.connect(self.user_delete_device)