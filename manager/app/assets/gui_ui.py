# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gui.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (
    QCoreApplication,
    QDate,
    QDateTime,
    QLocale,
    QMetaObject,
    QObject,
    QPoint,
    QRect,
    QSize,
    QTime,
    QUrl,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QCursor,
    QFont,
    QFontDatabase,
    QGradient,
    QIcon,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPalette,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenuBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1069, 787)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout_main = QHBoxLayout(self.centralwidget)
        self.horizontalLayout_main.setObjectName("horizontalLayout_main")
        self.listWidget = QListWidget(self.centralwidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        QListWidgetItem(self.listWidget)
        self.listWidget.setObjectName("listWidget")
        self.listWidget.setMinimumSize(QSize(75, 0))
        self.listWidget.setMaximumSize(QSize(150, 16777215))

        self.horizontalLayout_main.addWidget(self.listWidget)

        self.stackedWidget = QStackedWidget(self.centralwidget)
        self.stackedWidget.setObjectName("stackedWidget")
        self.page_database = QWidget()
        self.page_database.setObjectName("page_database")
        self.verticalLayout_2 = QVBoxLayout(self.page_database)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.database_tablewidget = QTableWidget(self.page_database)
        self.database_tablewidget.setObjectName("database_tablewidget")

        self.verticalLayout_2.addWidget(self.database_tablewidget)

        self.horizontalLayout_search = QHBoxLayout()
        self.horizontalLayout_search.setObjectName("horizontalLayout_search")
        self.database_searchDB_lineinput = QLineEdit(self.page_database)
        self.database_searchDB_lineinput.setObjectName("database_searchDB_lineinput")

        self.horizontalLayout_search.addWidget(self.database_searchDB_lineinput)

        self.database_searchDB_button = QPushButton(self.page_database)
        self.database_searchDB_button.setObjectName("database_searchDB_button")

        self.horizontalLayout_search.addWidget(self.database_searchDB_button)

        self.database_chatgpt_button = QPushButton(self.page_database)
        self.database_chatgpt_button.setObjectName("database_chatgpt_button")

        self.horizontalLayout_search.addWidget(self.database_chatgpt_button)

        self.verticalLayout_2.addLayout(self.horizontalLayout_search)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.horizontalLayout_2.setSizeConstraint(QLayout.SetNoConstraint)
        self.database_deleteDB_button = QPushButton(self.page_database)
        self.database_deleteDB_button.setObjectName("database_deleteDB_button")

        self.horizontalLayout_2.addWidget(self.database_deleteDB_button)

        self.database_viewDB_button = QPushButton(self.page_database)
        self.database_viewDB_button.setObjectName("database_viewDB_button")

        self.horizontalLayout_2.addWidget(self.database_viewDB_button)

        self.database_saveDB_button = QPushButton(self.page_database)
        self.database_saveDB_button.setObjectName("database_saveDB_button")

        self.horizontalLayout_2.addWidget(self.database_saveDB_button)

        self.verticalLayout_2.addLayout(self.horizontalLayout_2)

        self.stackedWidget.addWidget(self.page_database)
        self.page_crawler = QWidget()
        self.page_crawler.setObjectName("page_crawler")
        self.verticalLayout_4 = QVBoxLayout(self.page_crawler)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.tab_webview = QWidget(self.page_crawler)
        self.tab_webview.setObjectName("tab_webview")

        self.verticalLayout_4.addWidget(self.tab_webview)

        self.stackedWidget.addWidget(self.page_crawler)
        self.page_data_process = QWidget()
        self.page_data_process.setObjectName("page_data_process")
        self.verticalLayout_data_process = QVBoxLayout(self.page_data_process)
        self.verticalLayout_data_process.setObjectName("verticalLayout_data_process")
        self.tabWidget_data_process = QTabWidget(self.page_data_process)
        self.tabWidget_data_process.setObjectName("tabWidget_data_process")
        self.tabWidget_data_process.setTabPosition(QTabWidget.North)
        self.tab_file = QWidget()
        self.tab_file.setObjectName("tab_file")
        self.verticalLayout_tab_1 = QVBoxLayout(self.tab_file)
        self.verticalLayout_tab_1.setObjectName("verticalLayout_tab_1")
        self.horizontalLayout_9 = QHBoxLayout()
        self.horizontalLayout_9.setObjectName("horizontalLayout_9")
        self.analysis_filefinder_layout = QHBoxLayout()
        self.analysis_filefinder_layout.setObjectName("analysis_filefinder_layout")

        self.horizontalLayout_9.addLayout(self.analysis_filefinder_layout)

        self.verticalLayout_5 = QVBoxLayout()
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.analysis_timesplitfile_btn = QPushButton(self.tab_file)
        self.analysis_timesplitfile_btn.setObjectName("analysis_timesplitfile_btn")

        self.verticalLayout_5.addWidget(self.analysis_timesplitfile_btn)

        self.analysis_mergefile_btn = QPushButton(self.tab_file)
        self.analysis_mergefile_btn.setObjectName("analysis_mergefile_btn")

        self.verticalLayout_5.addWidget(self.analysis_mergefile_btn)

        self.analysis_dataanalysisfile_btn = QPushButton(self.tab_file)
        self.analysis_dataanalysisfile_btn.setObjectName(
            "analysis_dataanalysisfile_btn"
        )

        self.verticalLayout_5.addWidget(self.analysis_dataanalysisfile_btn)

        self.analysis_wordcloud_btn = QPushButton(self.tab_file)
        self.analysis_wordcloud_btn.setObjectName("analysis_wordcloud_btn")

        self.verticalLayout_5.addWidget(self.analysis_wordcloud_btn)

        self.analysis_tokenization_btn = QPushButton(self.tab_file)
        self.analysis_tokenization_btn.setObjectName("analysis_tokenization_btn")

        self.verticalLayout_5.addWidget(self.analysis_tokenization_btn)

        self.analysis_kemkim_btn = QPushButton(self.tab_file)
        self.analysis_kemkim_btn.setObjectName("analysis_kemkim_btn")

        self.verticalLayout_5.addWidget(self.analysis_kemkim_btn)

        self.analysis_hate_btn = QPushButton(self.tab_file)
        self.analysis_hate_btn.setObjectName("analysis_hate_btn")

        self.verticalLayout_5.addWidget(self.analysis_hate_btn)

        self.analysis_network_btn = QPushButton(self.tab_file)
        self.analysis_network_btn.setObjectName("analysis_network_btn")

        self.verticalLayout_5.addWidget(self.analysis_network_btn)

        self.analysis_etc_btn = QPushButton(self.tab_file)
        self.analysis_etc_btn.setObjectName("analysis_etc_btn")

        self.verticalLayout_5.addWidget(self.analysis_etc_btn)

        self.verticalSpacer_2 = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )

        self.verticalLayout_5.addItem(self.verticalSpacer_2)

        self.horizontalLayout_9.addLayout(self.verticalLayout_5)

        self.verticalLayout_tab_1.addLayout(self.horizontalLayout_9)

        self.tabWidget_data_process.addTab(self.tab_file, "")

        self.verticalLayout_data_process.addWidget(self.tabWidget_data_process)

        self.stackedWidget.addWidget(self.page_data_process)
        self.page_board = QWidget()
        self.page_board.setObjectName("page_board")
        self.verticalLayout_data_process1 = QVBoxLayout(self.page_board)
        self.verticalLayout_data_process1.setObjectName("verticalLayout_data_process1")
        self.tabWidget_board = QTabWidget(self.page_board)
        self.tabWidget_board.setObjectName("tabWidget_board")
        self.tabWidget_board.setTabPosition(QTabWidget.North)
        self.tab_version = QWidget()
        self.tab_version.setObjectName("tab_version")
        self.verticalLayout_tab_11 = QVBoxLayout(self.tab_version)
        self.verticalLayout_tab_11.setObjectName("verticalLayout_tab_11")
        self.board_version_tableWidget = QTableWidget(self.tab_version)
        self.board_version_tableWidget.setObjectName("board_version_tableWidget")

        self.verticalLayout_tab_11.addWidget(self.board_version_tableWidget)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.board_addversion_button = QPushButton(self.tab_version)
        self.board_addversion_button.setObjectName("board_addversion_button")

        self.horizontalLayout_5.addWidget(self.board_addversion_button)

        self.board_editversion_button = QPushButton(self.tab_version)
        self.board_editversion_button.setObjectName("board_editversion_button")

        self.horizontalLayout_5.addWidget(self.board_editversion_button)

        self.board_deleteversion_button = QPushButton(self.tab_version)
        self.board_deleteversion_button.setObjectName("board_deleteversion_button")

        self.horizontalLayout_5.addWidget(self.board_deleteversion_button)

        self.board_detailversion_button = QPushButton(self.tab_version)
        self.board_detailversion_button.setObjectName("board_detailversion_button")

        self.horizontalLayout_5.addWidget(self.board_detailversion_button)

        self.verticalLayout_tab_11.addLayout(self.horizontalLayout_5)

        self.tabWidget_board.addTab(self.tab_version, "")
        self.tab_bugreport = QWidget()
        self.tab_bugreport.setObjectName("tab_bugreport")
        self.verticalLayout_tab_12 = QVBoxLayout(self.tab_bugreport)
        self.verticalLayout_tab_12.setObjectName("verticalLayout_tab_12")
        self.board_bug_tableWidget = QTableWidget(self.tab_bugreport)
        self.board_bug_tableWidget.setObjectName("board_bug_tableWidget")

        self.verticalLayout_tab_12.addWidget(self.board_bug_tableWidget)

        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.board_addbug_button = QPushButton(self.tab_bugreport)
        self.board_addbug_button.setObjectName("board_addbug_button")

        self.horizontalLayout_8.addWidget(self.board_addbug_button)

        self.board_deletebug_button = QPushButton(self.tab_bugreport)
        self.board_deletebug_button.setObjectName("board_deletebug_button")

        self.horizontalLayout_8.addWidget(self.board_deletebug_button)

        self.board_detailbug_button = QPushButton(self.tab_bugreport)
        self.board_detailbug_button.setObjectName("board_detailbug_button")

        self.horizontalLayout_8.addWidget(self.board_detailbug_button)

        self.verticalLayout_tab_12.addLayout(self.horizontalLayout_8)

        self.tabWidget_board.addTab(self.tab_bugreport, "")
        self.tab_post = QWidget()
        self.tab_post.setObjectName("tab_post")
        self.verticalLayout_tab_13 = QVBoxLayout(self.tab_post)
        self.verticalLayout_tab_13.setObjectName("verticalLayout_tab_13")
        self.board_post_tableWidget = QTableWidget(self.tab_post)
        self.board_post_tableWidget.setObjectName("board_post_tableWidget")

        self.verticalLayout_tab_13.addWidget(self.board_post_tableWidget)

        self.horizontalLayout_51 = QHBoxLayout()
        self.horizontalLayout_51.setObjectName("horizontalLayout_51")
        self.board_addpost_button = QPushButton(self.tab_post)
        self.board_addpost_button.setObjectName("board_addpost_button")

        self.horizontalLayout_51.addWidget(self.board_addpost_button)

        self.board_deletepost_button = QPushButton(self.tab_post)
        self.board_deletepost_button.setObjectName("board_deletepost_button")

        self.horizontalLayout_51.addWidget(self.board_deletepost_button)

        self.board_detailpost_button = QPushButton(self.tab_post)
        self.board_detailpost_button.setObjectName("board_detailpost_button")

        self.horizontalLayout_51.addWidget(self.board_detailpost_button)

        self.board_editpost_button = QPushButton(self.tab_post)
        self.board_editpost_button.setObjectName("board_editpost_button")

        self.horizontalLayout_51.addWidget(self.board_editpost_button)

        self.verticalLayout_tab_13.addLayout(self.horizontalLayout_51)

        self.tabWidget_board.addTab(self.tab_post, "")

        self.verticalLayout_data_process1.addWidget(self.tabWidget_board)

        self.stackedWidget.addWidget(self.page_board)
        self.page_web = QWidget()
        self.page_web.setObjectName("page_web")
        self.verticalLayout_data_process2 = QVBoxLayout(self.page_web)
        self.verticalLayout_data_process2.setObjectName("verticalLayout_data_process2")
        self.tabWidget_web = QTabWidget(self.page_web)
        self.tabWidget_web.setObjectName("tabWidget_web")
        self.tabWidget_web.setTabPosition(QTabWidget.North)
        self.tab_papers = QWidget()
        self.tab_papers.setObjectName("tab_papers")
        self.verticalLayout_tab_14 = QVBoxLayout(self.tab_papers)
        self.verticalLayout_tab_14.setObjectName("verticalLayout_tab_14")
        self.web_papers_tableWidget = QTableWidget(self.tab_papers)
        self.web_papers_tableWidget.setObjectName("web_papers_tableWidget")

        self.verticalLayout_tab_14.addWidget(self.web_papers_tableWidget)

        self.horizontalLayout_52 = QHBoxLayout()
        self.horizontalLayout_52.setObjectName("horizontalLayout_52")
        self.web_addpaper_button = QPushButton(self.tab_papers)
        self.web_addpaper_button.setObjectName("web_addpaper_button")

        self.horizontalLayout_52.addWidget(self.web_addpaper_button)

        self.web_deletepaper_button = QPushButton(self.tab_papers)
        self.web_deletepaper_button.setObjectName("web_deletepaper_button")

        self.horizontalLayout_52.addWidget(self.web_deletepaper_button)

        self.web_editpaper_button = QPushButton(self.tab_papers)
        self.web_editpaper_button.setObjectName("web_editpaper_button")

        self.horizontalLayout_52.addWidget(self.web_editpaper_button)

        self.web_viewpaper_button = QPushButton(self.tab_papers)
        self.web_viewpaper_button.setObjectName("web_viewpaper_button")

        self.horizontalLayout_52.addWidget(self.web_viewpaper_button)

        self.verticalLayout_tab_14.addLayout(self.horizontalLayout_52)

        self.tabWidget_web.addTab(self.tab_papers, "")
        self.tab_groupphotos = QWidget()
        self.tab_groupphotos.setObjectName("tab_groupphotos")
        self.verticalLayout_tab_15 = QVBoxLayout(self.tab_groupphotos)
        self.verticalLayout_tab_15.setObjectName("verticalLayout_tab_15")
        self.web_groupphotos_tableWidget = QTableWidget(self.tab_groupphotos)
        self.web_groupphotos_tableWidget.setObjectName("web_groupphotos_tableWidget")

        self.verticalLayout_tab_15.addWidget(self.web_groupphotos_tableWidget)

        self.horizontalLayout_53 = QHBoxLayout()
        self.horizontalLayout_53.setObjectName("horizontalLayout_53")
        self.web_addgroupphoto_button = QPushButton(self.tab_groupphotos)
        self.web_addgroupphoto_button.setObjectName("web_addgroupphoto_button")

        self.horizontalLayout_53.addWidget(self.web_addgroupphoto_button)

        self.web_deletegroupphoto_button = QPushButton(self.tab_groupphotos)
        self.web_deletegroupphoto_button.setObjectName("web_deletegroupphoto_button")

        self.horizontalLayout_53.addWidget(self.web_deletegroupphoto_button)

        self.web_editgroupphoto_button = QPushButton(self.tab_groupphotos)
        self.web_editgroupphoto_button.setObjectName("web_editgroupphoto_button")

        self.horizontalLayout_53.addWidget(self.web_editgroupphoto_button)

        self.web_viewgroupphoto_button = QPushButton(self.tab_groupphotos)
        self.web_viewgroupphoto_button.setObjectName("web_viewgroupphoto_button")

        self.horizontalLayout_53.addWidget(self.web_viewgroupphoto_button)

        self.verticalLayout_tab_15.addLayout(self.horizontalLayout_53)

        self.tabWidget_web.addTab(self.tab_groupphotos, "")
        self.tab_members = QWidget()
        self.tab_members.setObjectName("tab_members")
        self.verticalLayout_tab_16 = QVBoxLayout(self.tab_members)
        self.verticalLayout_tab_16.setObjectName("verticalLayout_tab_16")
        self.web_members_tableWidget = QTableWidget(self.tab_members)
        self.web_members_tableWidget.setObjectName("web_members_tableWidget")

        self.verticalLayout_tab_16.addWidget(self.web_members_tableWidget)

        self.horizontalLayout_54 = QHBoxLayout()
        self.horizontalLayout_54.setObjectName("horizontalLayout_54")
        self.web_addmember_button = QPushButton(self.tab_members)
        self.web_addmember_button.setObjectName("web_addmember_button")

        self.horizontalLayout_54.addWidget(self.web_addmember_button)

        self.web_deletemember_button = QPushButton(self.tab_members)
        self.web_deletemember_button.setObjectName("web_deletemember_button")

        self.horizontalLayout_54.addWidget(self.web_deletemember_button)

        self.web_editmember_button = QPushButton(self.tab_members)
        self.web_editmember_button.setObjectName("web_editmember_button")

        self.horizontalLayout_54.addWidget(self.web_editmember_button)

        self.web_viewmember_button = QPushButton(self.tab_members)
        self.web_viewmember_button.setObjectName("web_viewmember_button")

        self.horizontalLayout_54.addWidget(self.web_viewmember_button)

        self.verticalLayout_tab_16.addLayout(self.horizontalLayout_54)

        self.tabWidget_web.addTab(self.tab_members, "")
        self.tab_news = QWidget()
        self.tab_news.setObjectName("tab_news")
        self.verticalLayout_tab_17 = QVBoxLayout(self.tab_news)
        self.verticalLayout_tab_17.setObjectName("verticalLayout_tab_17")
        self.web_news_tableWidget = QTableWidget(self.tab_news)
        self.web_news_tableWidget.setObjectName("web_news_tableWidget")

        self.verticalLayout_tab_17.addWidget(self.web_news_tableWidget)

        self.horizontalLayout_55 = QHBoxLayout()
        self.horizontalLayout_55.setObjectName("horizontalLayout_55")
        self.web_addnews_button = QPushButton(self.tab_news)
        self.web_addnews_button.setObjectName("web_addnews_button")

        self.horizontalLayout_55.addWidget(self.web_addnews_button)

        self.web_deletenews_button = QPushButton(self.tab_news)
        self.web_deletenews_button.setObjectName("web_deletenews_button")

        self.horizontalLayout_55.addWidget(self.web_deletenews_button)

        self.web_editnews_button = QPushButton(self.tab_news)
        self.web_editnews_button.setObjectName("web_editnews_button")

        self.horizontalLayout_55.addWidget(self.web_editnews_button)

        self.web_viewnews_button = QPushButton(self.tab_news)
        self.web_viewnews_button.setObjectName("web_viewnews_button")

        self.horizontalLayout_55.addWidget(self.web_viewnews_button)

        self.verticalLayout_tab_17.addLayout(self.horizontalLayout_55)

        self.tabWidget_web.addTab(self.tab_news, "")
        self.tab_popup = QWidget()
        self.tab_popup.setObjectName("tab_popup")
        self.verticalLayout_tab_18 = QVBoxLayout(self.tab_popup)
        self.verticalLayout_tab_18.setObjectName("verticalLayout_tab_18")
        self.web_popup_tableWidget = QTableWidget(self.tab_popup)
        self.web_popup_tableWidget.setObjectName("web_popup_tableWidget")

        self.verticalLayout_tab_18.addWidget(self.web_popup_tableWidget)

        self.horizontalLayout_56 = QHBoxLayout()
        self.horizontalLayout_56.setObjectName("horizontalLayout_56")
        self.web_addpopup_button = QPushButton(self.tab_popup)
        self.web_addpopup_button.setObjectName("web_addpopup_button")

        self.horizontalLayout_56.addWidget(self.web_addpopup_button)

        self.web_deletepopup_button = QPushButton(self.tab_popup)
        self.web_deletepopup_button.setObjectName("web_deletepopup_button")

        self.horizontalLayout_56.addWidget(self.web_deletepopup_button)

        self.web_editpopup_button = QPushButton(self.tab_popup)
        self.web_editpopup_button.setObjectName("web_editpopup_button")

        self.horizontalLayout_56.addWidget(self.web_editpopup_button)

        self.web_viewpopup_button = QPushButton(self.tab_popup)
        self.web_viewpopup_button.setObjectName("web_viewpopup_button")

        self.horizontalLayout_56.addWidget(self.web_viewpopup_button)

        self.verticalLayout_tab_18.addLayout(self.horizontalLayout_56)

        self.tabWidget_web.addTab(self.tab_popup, "")

        self.verticalLayout_data_process2.addWidget(self.tabWidget_web)

        self.stackedWidget.addWidget(self.page_web)
        self.page_info = QWidget()
        self.page_info.setObjectName("page_info")
        self.verticalLayout = QVBoxLayout(self.page_info)
        self.verticalLayout.setObjectName("verticalLayout")
        self.stackedWidget.addWidget(self.page_info)

        self.horizontalLayout_main.addWidget(self.stackedWidget)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        self.menubar.setGeometry(QRect(0, 0, 1069, 22))
        MainWindow.setMenuBar(self.menubar)

        self.retranslateUi(MainWindow)

        self.stackedWidget.setCurrentIndex(0)
        self.tabWidget_data_process.setCurrentIndex(0)
        self.tabWidget_board.setCurrentIndex(0)
        self.tabWidget_web.setCurrentIndex(0)

        QMetaObject.connectSlotsByName(MainWindow)

    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(
            QCoreApplication.translate("MainWindow", "MainWindow", None)
        )

        __sortingEnabled = self.listWidget.isSortingEnabled()
        self.listWidget.setSortingEnabled(False)
        ___qlistwidgetitem = self.listWidget.item(0)
        ___qlistwidgetitem.setText(
            QCoreApplication.translate("MainWindow", "DATABASE", None)
        )
        ___qlistwidgetitem1 = self.listWidget.item(1)
        ___qlistwidgetitem1.setText(
            QCoreApplication.translate("MainWindow", "CRAWLER", None)
        )
        ___qlistwidgetitem2 = self.listWidget.item(2)
        ___qlistwidgetitem2.setText(
            QCoreApplication.translate("MainWindow", "ANALYSIS", None)
        )
        ___qlistwidgetitem3 = self.listWidget.item(3)
        ___qlistwidgetitem3.setText(
            QCoreApplication.translate("MainWindow", "BOARD", None)
        )
        ___qlistwidgetitem4 = self.listWidget.item(4)
        ___qlistwidgetitem4.setText(
            QCoreApplication.translate("MainWindow", "WEB", None)
        )
        ___qlistwidgetitem5 = self.listWidget.item(5)
        ___qlistwidgetitem5.setText(
            QCoreApplication.translate("MainWindow", "SETTING", None)
        )
        self.listWidget.setSortingEnabled(__sortingEnabled)

        self.database_searchDB_button.setText(
            QCoreApplication.translate("MainWindow", "\uac80\uc0c9", None)
        )
        self.database_chatgpt_button.setText(
            QCoreApplication.translate("MainWindow", "ChatGPT", None)
        )
        self.database_deleteDB_button.setText(
            QCoreApplication.translate("MainWindow", "DB \uc0ad\uc81c", None)
        )
        self.database_viewDB_button.setText(
            QCoreApplication.translate("MainWindow", "DB \uc870\ud68c", None)
        )
        self.database_saveDB_button.setText(
            QCoreApplication.translate("MainWindow", "CSV\ub85c \uc800\uc7a5", None)
        )
        self.page_crawler.setWindowTitle(
            QCoreApplication.translate("MainWindow", "CRAWLER", None)
        )
        self.page_data_process.setWindowTitle(
            QCoreApplication.translate("MainWindow", "ANALYSIS", None)
        )
        self.analysis_timesplitfile_btn.setText(
            QCoreApplication.translate(
                "MainWindow", "\uc2dc\uacc4\uc5f4 \ubd84\ud560", None
            )
        )
        self.analysis_mergefile_btn.setText(
            QCoreApplication.translate("MainWindow", "CSV \ubcd1\ud569", None)
        )
        self.analysis_dataanalysisfile_btn.setText(
            QCoreApplication.translate("MainWindow", "\ud1b5\uacc4 \ubd84\uc11d", None)
        )
        self.analysis_wordcloud_btn.setText(
            QCoreApplication.translate(
                "MainWindow", "\uc6cc\ub4dc\ud074\ub77c\uc6b0\ub4dc", None
            )
        )
        self.analysis_tokenization_btn.setText(
            QCoreApplication.translate("MainWindow", "\ud1a0\ud070\ud654", None)
        )
        self.analysis_kemkim_btn.setText(
            QCoreApplication.translate("MainWindow", "KEM KIM", None)
        )
        self.analysis_hate_btn.setText(
            QCoreApplication.translate(
                "MainWindow", "\ud610\uc624\ub3c4 \ubd84\uc11d", None
            )
        )
        self.analysis_network_btn.setText(
            QCoreApplication.translate(
                "MainWindow", "\ub124\ud2b8\uc6cc\ud06c \ubd84\uc11d", None
            )
        )
        self.analysis_etc_btn.setText(
            QCoreApplication.translate("MainWindow", "\uae30\ud0c0 \ubd84\uc11d", None)
        )
        self.tabWidget_data_process.setTabText(
            self.tabWidget_data_process.indexOf(self.tab_file),
            QCoreApplication.translate(
                "MainWindow", "\ud30c\uc77c \ubd88\ub7ec\uc624\uae30", None
            ),
        )
        self.board_addversion_button.setText(
            QCoreApplication.translate("MainWindow", "\ucd94\uac00", None)
        )
        self.board_editversion_button.setText(
            QCoreApplication.translate("MainWindow", "\uc218\uc815", None)
        )
        self.board_deleteversion_button.setText(
            QCoreApplication.translate("MainWindow", "\uc0ad\uc81c", None)
        )
        self.board_detailversion_button.setText(
            QCoreApplication.translate("MainWindow", "\uc790\uc138\ud788", None)
        )
        self.tabWidget_board.setTabText(
            self.tabWidget_board.indexOf(self.tab_version),
            QCoreApplication.translate("MainWindow", "\ud328\uce58 \ub178\ud2b8", None),
        )
        self.board_addbug_button.setText(
            QCoreApplication.translate("MainWindow", "\ucd94\uac00", None)
        )
        self.board_deletebug_button.setText(
            QCoreApplication.translate("MainWindow", "\uc0ad\uc81c", None)
        )
        self.board_detailbug_button.setText(
            QCoreApplication.translate("MainWindow", "\uc790\uc138\ud788", None)
        )
        self.tabWidget_board.setTabText(
            self.tabWidget_board.indexOf(self.tab_bugreport),
            QCoreApplication.translate(
                "MainWindow", "\ubc84\uadf8 \ub9ac\ud3ec\ud2b8", None
            ),
        )
        self.board_addpost_button.setText(
            QCoreApplication.translate("MainWindow", "\ucd94\uac00", None)
        )
        self.board_deletepost_button.setText(
            QCoreApplication.translate("MainWindow", "\uc0ad\uc81c", None)
        )
        self.board_detailpost_button.setText(
            QCoreApplication.translate("MainWindow", "\uc790\uc138\ud788", None)
        )
        self.board_editpost_button.setText(
            QCoreApplication.translate("MainWindow", "\uc218\uc815", None)
        )
        self.tabWidget_board.setTabText(
            self.tabWidget_board.indexOf(self.tab_post),
            QCoreApplication.translate(
                "MainWindow", "\uc790\uc720\uac8c\uc2dc\ud310", None
            ),
        )
        self.web_addpaper_button.setText(
            QCoreApplication.translate("MainWindow", "\ucd94\uac00", None)
        )
        self.web_deletepaper_button.setText(
            QCoreApplication.translate("MainWindow", "\uc0ad\uc81c", None)
        )
        self.web_editpaper_button.setText(
            QCoreApplication.translate("MainWindow", "\uc218\uc815", None)
        )
        self.web_viewpaper_button.setText(
            QCoreApplication.translate("MainWindow", "\uc790\uc138\ud788", None)
        )
        self.tabWidget_web.setTabText(
            self.tabWidget_web.indexOf(self.tab_papers),
            QCoreApplication.translate("MainWindow", "\ub17c\ubb38 \ubaa9\ub85d", None),
        )
        self.web_addgroupphoto_button.setText(
            QCoreApplication.translate("MainWindow", "\ucd94\uac00", None)
        )
        self.web_deletegroupphoto_button.setText(
            QCoreApplication.translate("MainWindow", "\uc0ad\uc81c", None)
        )
        self.web_editgroupphoto_button.setText(
            QCoreApplication.translate("MainWindow", "\uc218\uc815", None)
        )
        self.web_viewgroupphoto_button.setText(
            QCoreApplication.translate("MainWindow", "\uc790\uc138\ud788", None)
        )
        self.tabWidget_web.setTabText(
            self.tabWidget_web.indexOf(self.tab_groupphotos),
            QCoreApplication.translate("MainWindow", "\uac24\ub7ec\ub9ac", None),
        )
        self.web_addmember_button.setText(
            QCoreApplication.translate("MainWindow", "\ucd94\uac00", None)
        )
        self.web_deletemember_button.setText(
            QCoreApplication.translate("MainWindow", "\uc0ad\uc81c", None)
        )
        self.web_editmember_button.setText(
            QCoreApplication.translate("MainWindow", "\uc218\uc815", None)
        )
        self.web_viewmember_button.setText(
            QCoreApplication.translate("MainWindow", "\uc790\uc138\ud788", None)
        )
        self.tabWidget_web.setTabText(
            self.tabWidget_web.indexOf(self.tab_members),
            QCoreApplication.translate("MainWindow", "\uba64\ubc84 \ubaa9\ub85d", None),
        )
        self.web_addnews_button.setText(
            QCoreApplication.translate("MainWindow", "\ucd94\uac00", None)
        )
        self.web_deletenews_button.setText(
            QCoreApplication.translate("MainWindow", "\uc0ad\uc81c", None)
        )
        self.web_editnews_button.setText(
            QCoreApplication.translate("MainWindow", "\uc218\uc815", None)
        )
        self.web_viewnews_button.setText(
            QCoreApplication.translate("MainWindow", "\uc790\uc138\ud788", None)
        )
        self.tabWidget_web.setTabText(
            self.tabWidget_web.indexOf(self.tab_news),
            QCoreApplication.translate("MainWindow", "\ub274\uc2a4 \ubaa9\ub85d", None),
        )
        self.web_addpopup_button.setText(
            QCoreApplication.translate("MainWindow", "\ucd94\uac00", None)
        )
        self.web_deletepopup_button.setText(
            QCoreApplication.translate("MainWindow", "\uc0ad\uc81c", None)
        )
        self.web_editpopup_button.setText(
            QCoreApplication.translate("MainWindow", "\uc218\uc815", None)
        )
        self.web_viewpopup_button.setText(
            QCoreApplication.translate("MainWindow", "\uc790\uc138\ud788", None)
        )
        self.tabWidget_web.setTabText(
            self.tabWidget_web.indexOf(self.tab_popup),
            QCoreApplication.translate("MainWindow", "\ud31d\uc5c5 \uad00\ub9ac", None),
        )

    # retranslateUi
