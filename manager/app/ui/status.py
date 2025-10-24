from PyQt5.QtCore import QCoreApplication, QEventLoop
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut

active_threads = []  

def register_thread(thread):
    active_threads.append(thread)  

def unregister_thread(thread):
    try:
        active_threads.remove(thread)  
    except ValueError:
        pass  # 등록되지 않은 스레드일 경우 무시

def get_active_thread_count():
    return len(active_threads)

def showActiveThreadsDialog():

    dialog = QDialog()
    dialog.setWindowTitle("실행 중인 작업")
    dialog.resize(400, 300)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(10)

    info_label = QLabel(f"현재 실행 중인 작업 {len(active_threads)}개")
    layout.addWidget(info_label)

    # 스크롤 가능한 리스트
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setSpacing(5)

    for t in active_threads:
        lbl = QLabel(t)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)  # 복사 가능
        container_layout.addWidget(lbl)

    container_layout.addStretch()
    scroll.setWidget(container)
    layout.addWidget(scroll)

    close_btn = QPushButton("닫기")
    close_btn.clicked.connect(dialog.accept)
    layout.addWidget(close_btn)
    
    QShortcut(QKeySequence("Ctrl+W"), dialog).activated.connect(dialog.reject)
    QShortcut(QKeySequence("Ctrl+ㅈ"), dialog).activated.connect(dialog.reject)

    dialog.exec_()
 
def printStatus(parent, msg=''):
    if len(active_threads) > 0:
        add_msg = f"{len(active_threads)}개의 작업 진행 중"
        if msg:
            msg += f" | {add_msg}"
        else: 
            msg = add_msg
        
        tooltipMsg = "\n".join(active_threads)
        parent.rightLabel.setToolTip(tooltipMsg)


    for i in range(3):
        parent.rightLabel.setText(msg)
        QCoreApplication.processEvents(QEventLoop.AllEvents, 0)
