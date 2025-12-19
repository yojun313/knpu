# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gui.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QHeaderView, QLabel,
    QLayout, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenuBar, QPushButton, QSizePolicy,
    QSpacerItem, QStackedWidget, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1069, 787)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout_main = QHBoxLayout(self.centralwidget)
        self.horizontalLayout_main.setObjectName(u"horizontalLayout_main")
        self.listWidget = QListWidget(self.centralwidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        self.listWidget.setObjectName(u"listWidget")
        self.listWidget.setMinimumSize(QSize(75, 0))
        self.listWidget.setMaximumSize(QSize(150, 16777215))

        self.horizontalLayout_main.addWidget(self.listWidget)

        self.stackedWidget = QStackedWidget(self.centralwidget)
        self.stackedWidget.setObjectName(u"stackedWidget")
        self.page_database = QWidget()
        self.page_database.setObjectName(u"page_database")
        self.verticalLayout_2 = QVBoxLayout(self.page_database)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.database_tablewidget = QTableWidget(self.page_database)
        self.database_tablewidget.setObjectName(u"database_tablewidget")

        self.verticalLayout_2.addWidget(self.database_tablewidget)

        self.horizontalLayout_search = QHBoxLayout()
        self.horizontalLayout_search.setObjectName(u"horizontalLayout_search")
        self.database_searchDB_lineinput = QLineEdit(self.page_database)
        self.database_searchDB_lineinput.setObjectName(u"database_searchDB_lineinput")

        self.horizontalLayout_search.addWidget(self.database_searchDB_lineinput)

        self.database_searchDB_button = QPushButton(self.page_database)
        self.database_searchDB_button.setObjectName(u"database_searchDB_button")

        self.horizontalLayout_search.addWidget(self.database_searchDB_button)

        self.database_chatgpt_button = QPushButton(self.page_database)
        self.database_chatgpt_button.setObjectName(u"database_chatgpt_button")

        self.horizontalLayout_search.addWidget(self.database_chatgpt_button)


        self.verticalLayout_2.addLayout(self.horizontalLayout_search)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setSizeConstraint(QLayout.SetNoConstraint)
        self.database_deleteDB_button = QPushButton(self.page_database)
        self.database_deleteDB_button.setObjectName(u"database_deleteDB_button")

        self.horizontalLayout_2.addWidget(self.database_deleteDB_button)

        self.database_viewDB_button = QPushButton(self.page_database)
        self.database_viewDB_button.setObjectName(u"database_viewDB_button")

        self.horizontalLayout_2.addWidget(self.database_viewDB_button)

        self.database_saveDB_button = QPushButton(self.page_database)
        self.database_saveDB_button.setObjectName(u"database_saveDB_button")

        self.horizontalLayout_2.addWidget(self.database_saveDB_button)


        self.verticalLayout_2.addLayout(self.horizontalLayout_2)

        self.stackedWidget.addWidget(self.page_database)
        self.page_crawler = QWidget()
        self.page_crawler.setObjectName(u"page_crawler")
        self.verticalLayout_4 = QVBoxLayout(self.page_crawler)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.tab_webview = QWidget(self.page_crawler)
        self.tab_webview.setObjectName(u"tab_webview")

        self.verticalLayout_4.addWidget(self.tab_webview)

        self.stackedWidget.addWidget(self.page_crawler)
        self.page_data_process = QWidget()
        self.page_data_process.setObjectName(u"page_data_process")
        self.verticalLayout_data_process = QVBoxLayout(self.page_data_process)
        self.verticalLayout_data_process.setObjectName(u"verticalLayout_data_process")
        self.tabWidget_data_process = QTabWidget(self.page_data_process)
        self.tabWidget_data_process.setObjectName(u"tabWidget_data_process")
        self.tabWidget_data_process.setTabPosition(QTabWidget.North)
        self.tab_file = QWidget()
        self.tab_file.setObjectName(u"tab_file")
        self.verticalLayout_tab_1 = QVBoxLayout(self.tab_file)
        self.verticalLayout_tab_1.setObjectName(u"verticalLayout_tab_1")
        self.horizontalLayout_9 = QHBoxLayout()
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")
        self.analysis_filefinder_layout = QHBoxLayout()
        self.analysis_filefinder_layout.setObjectName(u"analysis_filefinder_layout")

        self.horizontalLayout_9.addLayout(self.analysis_filefinder_layout)

        self.verticalLayout_5 = QVBoxLayout()
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.analysis_timesplitfile_btn = QPushButton(self.tab_file)
        self.analysis_timesplitfile_btn.setObjectName(u"analysis_timesplitfile_btn")

        self.verticalLayout_5.addWidget(self.analysis_timesplitfile_btn)

        self.analysis_mergefile_btn = QPushButton(self.tab_file)
        self.analysis_mergefile_btn.setObjectName(u"analysis_mergefile_btn")

        self.verticalLayout_5.addWidget(self.analysis_mergefile_btn)

        self.analysis_dataanalysisfile_btn = QPushButton(self.tab_file)
        self.analysis_dataanalysisfile_btn.setObjectName(u"analysis_dataanalysisfile_btn")

        self.verticalLayout_5.addWidget(self.analysis_dataanalysisfile_btn)

        self.analysis_wordcloud_btn = QPushButton(self.tab_file)
        self.analysis_wordcloud_btn.setObjectName(u"analysis_wordcloud_btn")

        self.verticalLayout_5.addWidget(self.analysis_wordcloud_btn)

        self.analysis_tokenization_btn = QPushButton(self.tab_file)
        self.analysis_tokenization_btn.setObjectName(u"analysis_tokenization_btn")

        self.verticalLayout_5.addWidget(self.analysis_tokenization_btn)

        self.analysis_kemkim_btn = QPushButton(self.tab_file)
        self.analysis_kemkim_btn.setObjectName(u"analysis_kemkim_btn")

        self.verticalLayout_5.addWidget(self.analysis_kemkim_btn)

        self.analysis_etc_btn = QPushButton(self.tab_file)
        self.analysis_etc_btn.setObjectName(u"analysis_etc_btn")

        self.verticalLayout_5.addWidget(self.analysis_etc_btn)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_5.addItem(self.verticalSpacer_2)


        self.horizontalLayout_9.addLayout(self.verticalLayout_5)


        self.verticalLayout_tab_1.addLayout(self.horizontalLayout_9)

        self.tabWidget_data_process.addTab(self.tab_file, "")

        self.verticalLayout_data_process.addWidget(self.tabWidget_data_process)

        self.stackedWidget.addWidget(self.page_data_process)
        self.page_board = QWidget()
        self.page_board.setObjectName(u"page_board")
        self.verticalLayout_data_process1 = QVBoxLayout(self.page_board)
        self.verticalLayout_data_process1.setObjectName(u"verticalLayout_data_process1")
        self.tabWidget_board = QTabWidget(self.page_board)
        self.tabWidget_board.setObjectName(u"tabWidget_board")
        self.tabWidget_board.setTabPosition(QTabWidget.North)
        self.tab_version = QWidget()
        self.tab_version.setObjectName(u"tab_version")
        self.verticalLayout_tab_11 = QVBoxLayout(self.tab_version)
        self.verticalLayout_tab_11.setObjectName(u"verticalLayout_tab_11")
        self.board_version_tableWidget = QTableWidget(self.tab_version)
        self.board_version_tableWidget.setObjectName(u"board_version_tableWidget")

        self.verticalLayout_tab_11.addWidget(self.board_version_tableWidget)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.board_addversion_button = QPushButton(self.tab_version)
        self.board_addversion_button.setObjectName(u"board_addversion_button")

        self.horizontalLayout_5.addWidget(self.board_addversion_button)

        self.board_editversion_button = QPushButton(self.tab_version)
        self.board_editversion_button.setObjectName(u"board_editversion_button")

        self.horizontalLayout_5.addWidget(self.board_editversion_button)

        self.board_deleteversion_button = QPushButton(self.tab_version)
        self.board_deleteversion_button.setObjectName(u"board_deleteversion_button")

        self.horizontalLayout_5.addWidget(self.board_deleteversion_button)

        self.board_detailversion_button = QPushButton(self.tab_version)
        self.board_detailversion_button.setObjectName(u"board_detailversion_button")

        self.horizontalLayout_5.addWidget(self.board_detailversion_button)


        self.verticalLayout_tab_11.addLayout(self.horizontalLayout_5)

        self.tabWidget_board.addTab(self.tab_version, "")
        self.tab_bugreport = QWidget()
        self.tab_bugreport.setObjectName(u"tab_bugreport")
        self.verticalLayout_tab_12 = QVBoxLayout(self.tab_bugreport)
        self.verticalLayout_tab_12.setObjectName(u"verticalLayout_tab_12")
        self.board_bug_tableWidget = QTableWidget(self.tab_bugreport)
        self.board_bug_tableWidget.setObjectName(u"board_bug_tableWidget")

        self.verticalLayout_tab_12.addWidget(self.board_bug_tableWidget)

        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.board_addbug_button = QPushButton(self.tab_bugreport)
        self.board_addbug_button.setObjectName(u"board_addbug_button")

        self.horizontalLayout_8.addWidget(self.board_addbug_button)

        self.board_deletebug_button = QPushButton(self.tab_bugreport)
        self.board_deletebug_button.setObjectName(u"board_deletebug_button")

        self.horizontalLayout_8.addWidget(self.board_deletebug_button)

        self.board_detailbug_button = QPushButton(self.tab_bugreport)
        self.board_detailbug_button.setObjectName(u"board_detailbug_button")

        self.horizontalLayout_8.addWidget(self.board_detailbug_button)


        self.verticalLayout_tab_12.addLayout(self.horizontalLayout_8)

        self.tabWidget_board.addTab(self.tab_bugreport, "")
        self.tab_post = QWidget()
        self.tab_post.setObjectName(u"tab_post")
        self.verticalLayout_tab_13 = QVBoxLayout(self.tab_post)
        self.verticalLayout_tab_13.setObjectName(u"verticalLayout_tab_13")
        self.board_post_tableWidget = QTableWidget(self.tab_post)
        self.board_post_tableWidget.setObjectName(u"board_post_tableWidget")

        self.verticalLayout_tab_13.addWidget(self.board_post_tableWidget)

        self.horizontalLayout_51 = QHBoxLayout()
        self.horizontalLayout_51.setObjectName(u"horizontalLayout_51")
        self.board_addpost_button = QPushButton(self.tab_post)
        self.board_addpost_button.setObjectName(u"board_addpost_button")

        self.horizontalLayout_51.addWidget(self.board_addpost_button)

        self.board_deletepost_button = QPushButton(self.tab_post)
        self.board_deletepost_button.setObjectName(u"board_deletepost_button")

        self.horizontalLayout_51.addWidget(self.board_deletepost_button)

        self.board_detailpost_button = QPushButton(self.tab_post)
        self.board_detailpost_button.setObjectName(u"board_detailpost_button")

        self.horizontalLayout_51.addWidget(self.board_detailpost_button)

        self.board_editpost_button = QPushButton(self.tab_post)
        self.board_editpost_button.setObjectName(u"board_editpost_button")

        self.horizontalLayout_51.addWidget(self.board_editpost_button)


        self.verticalLayout_tab_13.addLayout(self.horizontalLayout_51)

        self.tabWidget_board.addTab(self.tab_post, "")

        self.verticalLayout_data_process1.addWidget(self.tabWidget_board)

        self.stackedWidget.addWidget(self.page_board)
        self.page_web = QWidget()
        self.page_web.setObjectName(u"page_web")
        self.verticalLayout_data_process2 = QVBoxLayout(self.page_web)
        self.verticalLayout_data_process2.setObjectName(u"verticalLayout_data_process2")
        self.tabWidget_web = QTabWidget(self.page_web)
        self.tabWidget_web.setObjectName(u"tabWidget_web")
        self.tabWidget_web.setTabPosition(QTabWidget.North)
        self.tab_papers = QWidget()
        self.tab_papers.setObjectName(u"tab_papers")
        self.verticalLayout_tab_14 = QVBoxLayout(self.tab_papers)
        self.verticalLayout_tab_14.setObjectName(u"verticalLayout_tab_14")
        self.web_papers_tableWidget = QTableWidget(self.tab_papers)
        self.web_papers_tableWidget.setObjectName(u"web_papers_tableWidget")

        self.verticalLayout_tab_14.addWidget(self.web_papers_tableWidget)

        self.horizontalLayout_52 = QHBoxLayout()
        self.horizontalLayout_52.setObjectName(u"horizontalLayout_52")
        self.web_addpaper_button = QPushButton(self.tab_papers)
        self.web_addpaper_button.setObjectName(u"web_addpaper_button")

        self.horizontalLayout_52.addWidget(self.web_addpaper_button)

        self.web_deletepaper_button = QPushButton(self.tab_papers)
        self.web_deletepaper_button.setObjectName(u"web_deletepaper_button")

        self.horizontalLayout_52.addWidget(self.web_deletepaper_button)

        self.web_editpaper_button = QPushButton(self.tab_papers)
        self.web_editpaper_button.setObjectName(u"web_editpaper_button")

        self.horizontalLayout_52.addWidget(self.web_editpaper_button)

        self.web_viewpaper_button = QPushButton(self.tab_papers)
        self.web_viewpaper_button.setObjectName(u"web_viewpaper_button")

        self.horizontalLayout_52.addWidget(self.web_viewpaper_button)


        self.verticalLayout_tab_14.addLayout(self.horizontalLayout_52)

        self.tabWidget_web.addTab(self.tab_papers, "")
        self.tab_members = QWidget()
        self.tab_members.setObjectName(u"tab_members")
        self.verticalLayout_tab_15 = QVBoxLayout(self.tab_members)
        self.verticalLayout_tab_15.setObjectName(u"verticalLayout_tab_15")
        self.web_members_tableWidget = QTableWidget(self.tab_members)
        self.web_members_tableWidget.setObjectName(u"web_members_tableWidget")

        self.verticalLayout_tab_15.addWidget(self.web_members_tableWidget)

        self.horizontalLayout_53 = QHBoxLayout()
        self.horizontalLayout_53.setObjectName(u"horizontalLayout_53")
        self.web_addmember_button = QPushButton(self.tab_members)
        self.web_addmember_button.setObjectName(u"web_addmember_button")

        self.horizontalLayout_53.addWidget(self.web_addmember_button)

        self.web_deletemember_button = QPushButton(self.tab_members)
        self.web_deletemember_button.setObjectName(u"web_deletemember_button")

        self.horizontalLayout_53.addWidget(self.web_deletemember_button)

        self.web_editmember_button = QPushButton(self.tab_members)
        self.web_editmember_button.setObjectName(u"web_editmember_button")

        self.horizontalLayout_53.addWidget(self.web_editmember_button)

        self.web_viewmember_button = QPushButton(self.tab_members)
        self.web_viewmember_button.setObjectName(u"web_viewmember_button")

        self.horizontalLayout_53.addWidget(self.web_viewmember_button)


        self.verticalLayout_tab_15.addLayout(self.horizontalLayout_53)

        self.tabWidget_web.addTab(self.tab_members, "")
        self.tab_news = QWidget()
        self.tab_news.setObjectName(u"tab_news")
        self.verticalLayout_tab_16 = QVBoxLayout(self.tab_news)
        self.verticalLayout_tab_16.setObjectName(u"verticalLayout_tab_16")
        self.web_news_tableWidget = QTableWidget(self.tab_news)
        self.web_news_tableWidget.setObjectName(u"web_news_tableWidget")

        self.verticalLayout_tab_16.addWidget(self.web_news_tableWidget)

        self.horizontalLayout_54 = QHBoxLayout()
        self.horizontalLayout_54.setObjectName(u"horizontalLayout_54")
        self.web_addnews_button = QPushButton(self.tab_news)
        self.web_addnews_button.setObjectName(u"web_addnews_button")

        self.horizontalLayout_54.addWidget(self.web_addnews_button)

        self.web_deletenews_button = QPushButton(self.tab_news)
        self.web_deletenews_button.setObjectName(u"web_deletenews_button")

        self.horizontalLayout_54.addWidget(self.web_deletenews_button)

        self.web_editnews_button = QPushButton(self.tab_news)
        self.web_editnews_button.setObjectName(u"web_editnews_button")

        self.horizontalLayout_54.addWidget(self.web_editnews_button)

        self.web_viewnews_button = QPushButton(self.tab_news)
        self.web_viewnews_button.setObjectName(u"web_viewnews_button")

        self.horizontalLayout_54.addWidget(self.web_viewnews_button)


        self.verticalLayout_tab_16.addLayout(self.horizontalLayout_54)

        self.tabWidget_web.addTab(self.tab_news, "")

        self.verticalLayout_data_process2.addWidget(self.tabWidget_web)

        self.stackedWidget.addWidget(self.page_web)
        self.page_user = QWidget()
        self.page_user.setObjectName(u"page_user")
        self.verticalLayout_user = QVBoxLayout(self.page_user)
        self.verticalLayout_user.setObjectName(u"verticalLayout_user")
        self.tabWidget_user = QTabWidget(self.page_user)
        self.tabWidget_user.setObjectName(u"tabWidget_user")
        self.tabWidget_user.setTabPosition(QTabWidget.North)
        self.tab_userlist = QWidget()
        self.tab_userlist.setObjectName(u"tab_userlist")
        self.verticalLayout = QVBoxLayout(self.tab_userlist)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.user_tablewidget = QTableWidget(self.tab_userlist)
        self.user_tablewidget.setObjectName(u"user_tablewidget")

        self.verticalLayout.addWidget(self.user_tablewidget)

        self.horizontalLayout_input = QHBoxLayout()
        self.horizontalLayout_input.setObjectName(u"horizontalLayout_input")
        self.label_name = QLabel(self.tab_userlist)
        self.label_name.setObjectName(u"label_name")

        self.horizontalLayout_input.addWidget(self.label_name)

        self.userName_lineinput = QLineEdit(self.tab_userlist)
        self.userName_lineinput.setObjectName(u"userName_lineinput")

        self.horizontalLayout_input.addWidget(self.userName_lineinput)

        self.label_email = QLabel(self.tab_userlist)
        self.label_email.setObjectName(u"label_email")

        self.horizontalLayout_input.addWidget(self.label_email)

        self.user_email_lineinput = QLineEdit(self.tab_userlist)
        self.user_email_lineinput.setObjectName(u"user_email_lineinput")

        self.horizontalLayout_input.addWidget(self.user_email_lineinput)

        self.label_key = QLabel(self.tab_userlist)
        self.label_key.setObjectName(u"label_key")

        self.horizontalLayout_input.addWidget(self.label_key)

        self.user_key_lineinput = QLineEdit(self.tab_userlist)
        self.user_key_lineinput.setObjectName(u"user_key_lineinput")

        self.horizontalLayout_input.addWidget(self.user_key_lineinput)


        self.verticalLayout.addLayout(self.horizontalLayout_input)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.user_deleteuser_button = QPushButton(self.tab_userlist)
        self.user_deleteuser_button.setObjectName(u"user_deleteuser_button")

        self.horizontalLayout.addWidget(self.user_deleteuser_button)

        self.user_adduser_button = QPushButton(self.tab_userlist)
        self.user_adduser_button.setObjectName(u"user_adduser_button")

        self.horizontalLayout.addWidget(self.user_adduser_button)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.tabWidget_user.addTab(self.tab_userlist, "")

        self.verticalLayout_user.addWidget(self.tabWidget_user)

        self.stackedWidget.addWidget(self.page_user)
        self.page_info = QWidget()
        self.page_info.setObjectName(u"page_info")
        self.verticalLayout1 = QVBoxLayout(self.page_info)
        self.verticalLayout1.setObjectName(u"verticalLayout1")
        self.stackedWidget.addWidget(self.page_info)

        self.horizontalLayout_main.addWidget(self.stackedWidget)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1069, 22))
        MainWindow.setMenuBar(self.menubar)

        self.retranslateUi(MainWindow)

        self.stackedWidget.setCurrentIndex(0)
        self.tabWidget_data_process.setCurrentIndex(0)
        self.tabWidget_board.setCurrentIndex(0)
        self.tabWidget_web.setCurrentIndex(0)
        self.tabWidget_user.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))

        __sortingEnabled = self.listWidget.isSortingEnabled()
        self.listWidget.setSortingEnabled(False)
        ___qlistwidgetitem = self.listWidget.item(0)
        ___qlistwidgetitem.setText(QCoreApplication.translate("MainWindow", u"DATABASE", None));
        ___qlistwidgetitem1 = self.listWidget.item(1)
        ___qlistwidgetitem1.setText(QCoreApplication.translate("MainWindow", u"CRAWLER", None));
        ___qlistwidgetitem2 = self.listWidget.item(2)
        ___qlistwidgetitem2.setText(QCoreApplication.translate("MainWindow", u"ANALYSIS", None));
        ___qlistwidgetitem3 = self.listWidget.item(3)
        ___qlistwidgetitem3.setText(QCoreApplication.translate("MainWindow", u"BOARD", None));
        ___qlistwidgetitem4 = self.listWidget.item(4)
        ___qlistwidgetitem4.setText(QCoreApplication.translate("MainWindow", u"WEB", None));
        ___qlistwidgetitem5 = self.listWidget.item(5)
        ___qlistwidgetitem5.setText(QCoreApplication.translate("MainWindow", u"USER", None));
        ___qlistwidgetitem6 = self.listWidget.item(6)
        ___qlistwidgetitem6.setText(QCoreApplication.translate("MainWindow", u"SETTING", None));
        self.listWidget.setSortingEnabled(__sortingEnabled)

        self.database_searchDB_button.setText(QCoreApplication.translate("MainWindow", u"\uac80\uc0c9", None))
        self.database_chatgpt_button.setText(QCoreApplication.translate("MainWindow", u"ChatGPT", None))
        self.database_deleteDB_button.setText(QCoreApplication.translate("MainWindow", u"DB \uc0ad\uc81c", None))
        self.database_viewDB_button.setText(QCoreApplication.translate("MainWindow", u"DB \uc870\ud68c", None))
        self.database_saveDB_button.setText(QCoreApplication.translate("MainWindow", u"CSV\ub85c \uc800\uc7a5", None))
        self.page_crawler.setWindowTitle(QCoreApplication.translate("MainWindow", u"CRAWLER", None))
        self.page_data_process.setWindowTitle(QCoreApplication.translate("MainWindow", u"ANALYSIS", None))
        self.analysis_timesplitfile_btn.setText(QCoreApplication.translate("MainWindow", u"\uc2dc\uacc4\uc5f4 \ubd84\ud560", None))
        self.analysis_mergefile_btn.setText(QCoreApplication.translate("MainWindow", u"CSV \ubcd1\ud569", None))
        self.analysis_dataanalysisfile_btn.setText(QCoreApplication.translate("MainWindow", u"\ud1b5\uacc4 \ubd84\uc11d", None))
        self.analysis_wordcloud_btn.setText(QCoreApplication.translate("MainWindow", u"\uc6cc\ub4dc\ud074\ub77c\uc6b0\ub4dc", None))
        self.analysis_tokenization_btn.setText(QCoreApplication.translate("MainWindow", u"\ud1a0\ud070\ud654", None))
        self.analysis_kemkim_btn.setText(QCoreApplication.translate("MainWindow", u"KEM KIM", None))
        self.analysis_etc_btn.setText(QCoreApplication.translate("MainWindow", u"\uae30\ud0c0 \ubd84\uc11d", None))
        self.tabWidget_data_process.setTabText(self.tabWidget_data_process.indexOf(self.tab_file), QCoreApplication.translate("MainWindow", u"\ud30c\uc77c \ubd88\ub7ec\uc624\uae30", None))
        self.board_addversion_button.setText(QCoreApplication.translate("MainWindow", u"\ucd94\uac00", None))
        self.board_editversion_button.setText(QCoreApplication.translate("MainWindow", u"\uc218\uc815", None))
        self.board_deleteversion_button.setText(QCoreApplication.translate("MainWindow", u"\uc0ad\uc81c", None))
        self.board_detailversion_button.setText(QCoreApplication.translate("MainWindow", u"\uc790\uc138\ud788", None))
        self.tabWidget_board.setTabText(self.tabWidget_board.indexOf(self.tab_version), QCoreApplication.translate("MainWindow", u"\ud328\uce58 \ub178\ud2b8", None))
        self.board_addbug_button.setText(QCoreApplication.translate("MainWindow", u"\ucd94\uac00", None))
        self.board_deletebug_button.setText(QCoreApplication.translate("MainWindow", u"\uc0ad\uc81c", None))
        self.board_detailbug_button.setText(QCoreApplication.translate("MainWindow", u"\uc790\uc138\ud788", None))
        self.tabWidget_board.setTabText(self.tabWidget_board.indexOf(self.tab_bugreport), QCoreApplication.translate("MainWindow", u"\ubc84\uadf8 \ub9ac\ud3ec\ud2b8", None))
        self.board_addpost_button.setText(QCoreApplication.translate("MainWindow", u"\ucd94\uac00", None))
        self.board_deletepost_button.setText(QCoreApplication.translate("MainWindow", u"\uc0ad\uc81c", None))
        self.board_detailpost_button.setText(QCoreApplication.translate("MainWindow", u"\uc790\uc138\ud788", None))
        self.board_editpost_button.setText(QCoreApplication.translate("MainWindow", u"\uc218\uc815", None))
        self.tabWidget_board.setTabText(self.tabWidget_board.indexOf(self.tab_post), QCoreApplication.translate("MainWindow", u"\uc790\uc720\uac8c\uc2dc\ud310", None))
        self.web_addpaper_button.setText(QCoreApplication.translate("MainWindow", u"\ucd94\uac00", None))
        self.web_deletepaper_button.setText(QCoreApplication.translate("MainWindow", u"\uc0ad\uc81c", None))
        self.web_editpaper_button.setText(QCoreApplication.translate("MainWindow", u"\uc218\uc815", None))
        self.web_viewpaper_button.setText(QCoreApplication.translate("MainWindow", u"\uc790\uc138\ud788", None))
        self.tabWidget_web.setTabText(self.tabWidget_web.indexOf(self.tab_papers), QCoreApplication.translate("MainWindow", u"\ub17c\ubb38 \ubaa9\ub85d", None))
        self.web_addmember_button.setText(QCoreApplication.translate("MainWindow", u"\ucd94\uac00", None))
        self.web_deletemember_button.setText(QCoreApplication.translate("MainWindow", u"\uc0ad\uc81c", None))
        self.web_editmember_button.setText(QCoreApplication.translate("MainWindow", u"\uc218\uc815", None))
        self.web_viewmember_button.setText(QCoreApplication.translate("MainWindow", u"\uc790\uc138\ud788", None))
        self.tabWidget_web.setTabText(self.tabWidget_web.indexOf(self.tab_members), QCoreApplication.translate("MainWindow", u"\uba64\ubc84 \ubaa9\ub85d", None))
        self.web_addnews_button.setText(QCoreApplication.translate("MainWindow", u"\ucd94\uac00", None))
        self.web_deletenews_button.setText(QCoreApplication.translate("MainWindow", u"\uc0ad\uc81c", None))
        self.web_editnews_button.setText(QCoreApplication.translate("MainWindow", u"\uc218\uc815", None))
        self.web_viewnews_button.setText(QCoreApplication.translate("MainWindow", u"\uc790\uc138\ud788", None))
        self.tabWidget_web.setTabText(self.tabWidget_web.indexOf(self.tab_news), QCoreApplication.translate("MainWindow", u"\ub274\uc2a4 \ubaa9\ub85d", None))
        self.label_name.setText(QCoreApplication.translate("MainWindow", u"\uc774\ub984:", None))
        self.label_email.setText(QCoreApplication.translate("MainWindow", u"\uc774\uba54\uc77c:", None))
        self.label_key.setText(QCoreApplication.translate("MainWindow", u"Key:", None))
        self.user_deleteuser_button.setText(QCoreApplication.translate("MainWindow", u"\uc0ac\uc6a9\uc790 \uc0ad\uc81c", None))
        self.user_adduser_button.setText(QCoreApplication.translate("MainWindow", u"\uc0ac\uc6a9\uc790 \ucd94\uac00", None))
        self.tabWidget_user.setTabText(self.tabWidget_user.indexOf(self.tab_userlist), QCoreApplication.translate("MainWindow", u"\uc0ac\uc6a9\uc790 \ubaa9\ub85d", None))
    # retranslateUi

