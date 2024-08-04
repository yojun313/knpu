from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox

class Manager_User:
    def __init__(self, main_window):
        self.main = main_window
        self.user_init_table()
        self.user_buttonMatch()

    def user_init_table(self):
        self.main.mySQL_obj.connectDB('user_db')

        self.userNameList = []
        userDF = self.main.mySQL_obj.TableToDataframe('user_info')
        user_data = [tuple(row) for row in userDF.itertuples(index=False, name=None)]

        self.main.user_tablewidget.setRowCount(len(user_data))
        self.main.user_tablewidget.setColumnCount(3)
        self.main.user_tablewidget.setHorizontalHeaderLabels(['Name', 'Email', 'PushOverKey'])
        self.main.user_tablewidget.setSelectionBehavior(QTableWidget.SelectRows)
        self.main.user_tablewidget.setSelectionMode(QTableWidget.SingleSelection)

        header = self.main.user_tablewidget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        for i, (id, name, email, key) in enumerate(user_data):
            self.main.user_tablewidget.setItem(i, 0, QTableWidgetItem(name))
            self.main.user_tablewidget.setItem(i, 1, QTableWidgetItem(email))
            self.main.user_tablewidget.setItem(i, 2, QTableWidgetItem(key))
            self.userNameList.append(name)

    def user_add_user(self):
        name = self.main.user_name_lineinput.text()
        email = self.main.user_email_lineinput.text()
        key = self.main.user_key_lineinput.text()

        self.main.mySQL_obj.connectDB('user_db')

        reply = QMessageBox.question(self.main, 'Confirm Add', f"{name}님을 추가하시겠습니까?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.main.mySQL_obj.insertToTable(tableName='user_info', data_list=[name, email, key])
            self.main.mySQL_obj.commit()
            self.userNameList.append(name)

            row_position = self.main.user_tablewidget.rowCount()
            self.main.user_tablewidget.insertRow(row_position)
            self.main.user_tablewidget.setItem(row_position, 0, QTableWidgetItem(name))
            self.main.user_tablewidget.setItem(row_position, 1, QTableWidgetItem(email))
            self.main.user_tablewidget.setItem(row_position, 2, QTableWidgetItem(key))
            self.main.user_name_lineinput.clear()
            self.main.user_email_lineinput.clear()
            self.main.user_key_lineinput.clear()

    def user_delete_user(self):
        selected_row = self.main.user_tablewidget.currentRow()
        if selected_row >= 0:
            reply = QMessageBox.question(self.main, 'Confirm Delete', f"{self.userNameList[selected_row]}님을 삭제하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.main.mySQL_obj.connectDB('user_db')
                self.main.mySQL_obj.deleteTableRowByColumn('user_info', self.userNameList[selected_row], 'Name')
                self.userNameList.pop(selected_row)
                self.main.user_tablewidget.removeRow(selected_row)

    def user_buttonMatch(self):
        self.main.user_adduser_button.clicked.connect(self.user_add_user)
        self.main.user_deleteuser_button.clicked.connect(self.user_delete_user)