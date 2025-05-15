from PyQt5.QtCore import QCoreApplication, QEventLoop

def printStatus(parent, msg=''):
    for i in range(3):
        parent.rightLabel.setText(msg)
        QCoreApplication.processEvents(QEventLoop.AllEvents, 0)