from PyQt5.QtCore import QCoreApplication, QEventLoop

_active_threads = []  

def register_thread(thread):
    _active_threads.append(thread)  

def unregister_thread(thread):
    try:
        _active_threads.remove(thread)  
    except ValueError:
        pass  # 등록되지 않은 스레드일 경우 무시

def get_active_thread_count():
    return len(_active_threads)

def printStatus(parent, msg=''):
    if len(_active_threads) > 0:
        add_msg = f"{len(_active_threads)}개의 작업 진행 중"
        if msg:
            msg += f" | {add_msg}"
        else:
            msg = add_msg
        
        tooltipMsg = "\n".join(_active_threads)
        parent.rightLabel.setToolTip(tooltipMsg)

    for i in range(3):
        parent.rightLabel.setText(msg)
        QCoreApplication.processEvents(QEventLoop.AllEvents, 0)
