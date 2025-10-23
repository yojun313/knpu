from PyQt5.QtCore import QCoreApplication, QEventLoop

_active_threads = set()

def register_thread(thread):
    _active_threads.add(thread)

def unregister_thread(thread):
    _active_threads.discard(thread)

def get_active_thread_count():
    return len(_active_threads)

def printStatus(parent, msg=''):
    if len(_active_threads) > 0:
        
        add_msg = f"{_active_threads.__len__()}개의 작업 진행 중"
        if msg:
            msg += f" | {add_msg}"
        else:
            msg = add_msg
        
        tooltipMsg = "\n".join(_active_threads)        
        parent.rightLabel.setToolTip(tooltipMsg)
        
    for i in range(3):
        parent.rightLabel.setText(msg)
        QCoreApplication.processEvents(QEventLoop.AllEvents, 0)

