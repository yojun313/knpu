import os
import warnings
import traceback
from datetime import datetime
from PyQt5.QtCore import QStringListModel, Qt
from PyQt5.QtWidgets import (
    QMessageBox, QFileDialog, QTableWidgetItem,
    QWidget, QToolBox,
    QListView, QVBoxLayout,
)
warnings.filterwarnings("ignore")


class Manager_User:
    def __init__(self, main_window):
        self.main = main_window
        self.refreshUserTable()
        self.initDeviceTable()
        self.matchButton()

    def refreshUserTable(self):
        # 데이터베이스 연결 및 데이터 가져오기

        self.user_list = self.main.Request('get', '/users').json()['data']
        user_data = [(user['name'], user['email'], user['pushoverKey'])
                     for user in self.user_list]
        self.userNameList = [user['name'] for user in self.user_list]
        # userNameList 및 userKeyList 업데이트
        self.userKeyList = [user['pushoverKey']
                            for user in self.user_list if user['pushoverKey'] != 'n']

        # 테이블 설정
        columns = ['Name', 'Email', 'PushOverKey']
        self.main.makeTable(
            widgetname=self.main.user_tablewidget,
            data=user_data,
            column=columns,
        )

    def initDeviceTable(self):
        # 데이터베이스 연결 및 데이터 가져오기
        self.main.mySQLObj.connectDB('bigmaclab_manager_db')
        userDF = self.main.mySQLObj.TableToDataframe('device_list')
        device_data = [(user, device, mac) for _, device, user,
                       mac in userDF.itertuples(index=False, name=None)]
        device_data = sorted(device_data, key=lambda x: (
            not x[0][0].isalpha(), x[0]))

        # userNameList 및 userKeyList 업데이트
        self.deviceList = [device for name, device, mac in device_data]
        self.userList = [name for name, device, mac in device_data]
        self.macList = [mac for name, device, mac in device_data]

        # 테이블 설정
        columns = ['User', 'Device', 'Mac']
        self.main.makeTable(
            widgetname=self.main.device_tablewidget,
            data=device_data,
            column=columns,
        )

    def addUser(self):
        try:
            name = self.main.userName_lineinput.text()
            email = self.main.user_email_lineinput.text()
            key = self.main.user_key_lineinput.text()

            if self.main.user != 'admin':
                ok, password = self.main.checkPassword(True)
                if not ok or password != self.main.admin_password:
                    return

            reply = QMessageBox.question(
                self.main, 'Confirm Add', f"{name}님을 추가하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                data = {
                    'name': name,
                    'email': email,
                    'pushoverKey': key
                }
                response = self.main.Request('post', '/users/add', json=data)
                self.refreshUserTable()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def deleteUser(self):
        try:
            if self.main.user != 'admin':
                ok, password = self.main.checkPassword(True)
                if not ok or password != self.main.admin_password:
                    return

            selectedRow = self.main.user_tablewidget.currentRow()
            if selectedRow >= 0:
                selectedUser = self.user_list[selectedRow]
                reply = QMessageBox.question(
                    self.main, 'Confirm Delete', f"{selectedUser['name']}님을 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    response = self.main.Request(
                        'delete', f'/users/{selectedUser['uid']}')
                    if response.status_code == 200:
                        QMessageBox.information(
                            self.main, "Information", f"'{selectedUser['name']}'님이 삭제되었습니다")
                        self.refreshUserTable()
                    else:
                        QMessageBox.warning(
                            self.main, "Error", f"'{selectedUser['name']}'님을 삭제할 수 없습니다")

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def deleteDevice(self):
        try:
            if self.main.user != 'admin':
                ok, password = self.main.checkPassword(True)
                if not ok or password != self.main.admin_password:
                    return

            selectedRow = self.main.device_tablewidget.currentRow()
            if selectedRow >= 0:
                reply = QMessageBox.question(
                    self.main, 'Confirm Delete', f"{self.deviceList[selectedRow]}를 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.main.mySQLObj.connectDB('bigmaclab_manager_db')
                    self.main.mySQLObj.deleteTableRowByColumn(
                        'deviceList', self.deviceList[selectedRow], 'device_name')
                    QMessageBox.information(
                        self.main, "Information", f"'{self.deviceList[selectedRow]}'가 삭제되었습니다")
                    self.deviceList.pop(selectedRow)
                    self.main.user_tablewidget.removeRow(selectedRow)
                    self.initDeviceTable()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def makeUserDBLayout(self):
        # File Explorer를 탭 레이아웃에 추가
        self.userDBfiledialog = self.main.makeFileFinder(self.main)
        self.main.tab3_userDB_fileexplorerlayout.addWidget(
            self.userDBfiledialog)

        # QToolBox 생성
        self.tool_box = QToolBox()
        self.main.tab3_userDB_buttonlayout.addWidget(self.tool_box)

        # QListView들을 저장할 딕셔너리 생성
        self.list_views = {}

        def create_list(DBname):
            # 데이터베이스에서 테이블 목록 가져오기
            data = self.main.mySQLObj.showAllTable(database_name=DBname)
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
        self.selected_DBlistItems = [
            item.data() for item in self.list_views[self.selected_userDB].selectedIndexes()]
        self.main.printStatus(f"Table {len(self.selected_DBlistItems)}개 선택됨")

    def toolbox_DBlistItem_delete(self):
        try:
            if not self.selected_DBlistItems or self.selected_DBlistItems == []:
                self.main.printStatus()
                return
            if 'manager_record' in self.selected_DBlistItems:
                ok, password = self.main.checkPassword(True)
                if not ok or password != self.main.admin_password:
                    return

            reply = QMessageBox.question(
                self.main, 'Confirm Delete', "테이블을 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

            if reply == QMessageBox.Yes:
                self.main.printStatus(
                    f"Table {len(self.selected_DBlistItems)}개 삭제 중...")
                self.main.mySQLObj.connectDB(self.selected_userDB)

                for item in self.selected_DBlistItems:
                    self.main.mySQLObj.dropTable(item)

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
            self.main.programBugLog(traceback.format_exc())

    def toolbox_DBlistItem_add(self):
        try:
            selected_directory = self.toolbox_getfiledirectory(
                self.userDBfiledialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format",
                                    f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return
            self.main.printStatus()

            def update_list_view(DBname):
                # 데이터베이스에서 테이블 목록 다시 가져오기
                updated_data = self.main.mySQLObj.showAllTable(
                    database_name=DBname)

                # 해당 DB의 QListView 가져오기
                list_view = self.list_views[DBname]
                model = QStringListModel(updated_data)

                # 모델 업데이트 (QListView 갱신)
                list_view.setModel(model)

            self.main.mySQLObj.connectDB(self.selected_userDB)

            self.main.printStatus(
                f'{self.selected_userDB}에 Table {len(selected_directory)}개 추가 중...')
            for csv_path in selected_directory:
                self.main.mySQLObj.CSVToTable(
                    csv_path, os.path.basename(csv_path).replace('.csv', ''))
            update_list_view(self.selected_userDB)
            self.main.printStatus()
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def toolbox_DBlistItem_view(self, row=False):
        popupsize = None
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
                QMessageBox.warning(
                    self.main, "Wrong Selection", f"선택 가능한 테이블 수는 1개입니다")
                return
            if self.selected_DBlistItems[0] == 'manager_record':
                if self.main.user != 'admin':
                    ok, password = self.main.checkPassword(True)
                    if not ok or password != self.main.admin_password:
                        return

            self.main.viewTable(self.selected_userDB,
                                self.selected_DBlistItems[0], popupsize)

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def toolbox_DBlistItem_save(self):
        try:
            if not self.selected_DBlistItems or self.selected_DBlistItems == []:
                self.main.printStatus()
                return

            self.main.printStatus("데이터를 저장할 위치를 선택하세요...")
            folder_path = QFileDialog.getExistingDirectory(
                self.main, "데이터를 저장할 위치를 선택하세요", self.main.localDirectory)
            if folder_path == '':
                self.main.printStatus()
                return

            folder_path = os.path.join(
                folder_path, f'{self.selected_userDB}_download_{datetime.now().strftime('%m%d_%H%M')}')
            os.makedirs(folder_path, exist_ok=True)

            self.main.printStatus(
                f"Table {len(self.selected_DBlistItems)}개 저장 중...")
            self.main.mySQLObj.connectDB(self.selected_userDB)

            self.main.openFileExplorer(folder_path)
            for item in self.selected_DBlistItems:
                self.main.mySQLObj.TableToCSV(item, folder_path)

            self.main.printStatus()
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

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
                selected_directory[index] = os.path.join(
                    os.path.dirname(selected_directory[0]), directory)

        return selected_directory

    def matchButton(self):
        self.main.user_adduser_button.clicked.connect(self.addUser)
        self.main.user_deleteuser_button.clicked.connect(self.deleteUser)
        self.main.user_log_button.clicked.connect(
            lambda: self.toolbox_DBlistItem_view(row=True))

        self.selected_userDB = 'admin_db'
        self.selected_DBlistItem = None
        self.selected_DBlistItems = []
        self.main.userDB_list_delete_button.clicked.connect(
            self.toolbox_DBlistItem_delete)
        self.main.userDB_list_add_button.clicked.connect(
            self.toolbox_DBlistItem_add)
        self.main.userDB_list_view_button.clicked.connect(
            self.toolbox_DBlistItem_view)
        self.main.userDB_list_save_button.clicked.connect(
            self.toolbox_DBlistItem_save)
        self.main.device_delete_button.clicked.connect(self.deleteDevice)

        self.main.user_adduser_button.setToolTip("Ctrl+A")
        self.main.user_deleteuser_button.setToolTip("Ctrl+D")
        self.main.user_log_button.setToolTip("Ctrl+L")
        self.main.userDB_list_delete_button.setToolTip("Ctrl+D")
        self.main.userDB_list_add_button.setToolTip("Ctrl+A")
        self.main.userDB_list_view_button.setToolTip("Ctrl+V")
        self.main.userDB_list_save_button.setToolTip("Ctrl+S")
        self.main.device_delete_button.setToolTip("Ctrl+D")

    def user_shortcut_setting(self):
        self.updateShortcut(0)
        self.main.tabWidget_user.currentChanged.connect(self.updateShortcut)

    def updateShortcut(self, index):
        self.main.initShortcutialize()

        # User List
        if index == 0:
            self.main.ctrld.activated.connect(self.deleteUser)
            self.main.ctrll.activated.connect(
                lambda: self.toolbox_DBlistItem_view(True))
            self.main.ctrla.activated.connect(
                lambda: self.toolbox_DBlistItem_view(True))

            self.main.cmdd.activated.connect(self.deleteUser)
            self.main.cmdl.activated.connect(
                lambda: self.toolbox_DBlistItem_view(True))
            self.main.cmda.activated.connect(
                lambda: self.toolbox_DBlistItem_view(True))

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
            self.main.ctrld.activated.connect(self.deleteDevice)

            self.main.cmdd.activated.connect(self.deleteDevice)
