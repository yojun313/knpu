from PyQt6.QtGui import QKeySequence, QShortcut
from services.update import updateProgram

def initShortcut(parent):
    parent.ctrld = QShortcut(QKeySequence("Ctrl+D"), parent)
    parent.ctrls = QShortcut(QKeySequence("Ctrl+S"), parent)
    parent.ctrlv = QShortcut(QKeySequence("Ctrl+V"), parent)
    parent.ctrlu = QShortcut(QKeySequence("Ctrl+U"), parent)
    parent.ctrll = QShortcut(QKeySequence("Ctrl+L"), parent)
    parent.ctrla = QShortcut(QKeySequence("Ctrl+A"), parent)
    parent.ctrli = QShortcut(QKeySequence("Ctrl+I"), parent)
    parent.ctrle = QShortcut(QKeySequence("Ctrl+E"), parent)
    parent.ctrlr = QShortcut(QKeySequence("Ctrl+R"), parent)
    parent.ctrlk = QShortcut(QKeySequence("Ctrl+K"), parent)
    parent.ctrlm = QShortcut(QKeySequence("Ctrl+M"), parent)
    parent.ctrlp = QShortcut(QKeySequence("Ctrl+P"), parent)
    parent.ctrlc = QShortcut(QKeySequence("Ctrl+C"), parent)
    parent.ctrlq = QShortcut(QKeySequence("Ctrl+Q"), parent)
    parent.ctrlpp = QShortcut(QKeySequence("Ctrl+Shift+P"), parent)

    parent.cmdd = QShortcut(QKeySequence("Ctrl+ㅇ"), parent)
    parent.cmds = QShortcut(QKeySequence("Ctrl+ㄴ"), parent)
    parent.cmdv = QShortcut(QKeySequence("Ctrl+ㅍ"), parent)
    parent.cmdu = QShortcut(QKeySequence("Ctrl+ㅕ"), parent)
    parent.cmdl = QShortcut(QKeySequence("Ctrl+ㅣ"), parent)
    parent.cmda = QShortcut(QKeySequence("Ctrl+ㅁ"), parent)
    parent.cmdi = QShortcut(QKeySequence("Ctrl+ㅑ"), parent)
    parent.cmde = QShortcut(QKeySequence("Ctrl+ㄷ"), parent)
    parent.cmdr = QShortcut(QKeySequence("Ctrl+ㄱ"), parent)
    parent.cmdk = QShortcut(QKeySequence("Ctrl+ㅏ"), parent)
    parent.cmdm = QShortcut(QKeySequence("Ctrl+ㅡ"), parent)
    parent.cmdp = QShortcut(QKeySequence("Ctrl+ㅔ"), parent)
    parent.cmdc = QShortcut(QKeySequence("Ctrl+ㅊ"), parent)
    parent.cmdq = QShortcut(QKeySequence("Ctrl+ㅂ"), parent)
    parent.cmdpp = QShortcut(QKeySequence("Ctrl+Shift+ㅔ"), parent)

    parent.ctrlu.activated.connect(lambda: updateProgram(parent, sc=True))
    parent.ctrlq.activated.connect(lambda: parent.close())

    parent.cmdu.activated.connect(lambda: updateProgram(parent, sc=True))
    parent.cmdq.activated.connect(lambda: parent.close())


def resetShortcuts(parent):
    shortcuts = [parent.ctrld, parent.ctrls, parent.ctrlv, parent.ctrla, parent.ctrll, parent.ctrle, parent.ctrlr, parent.ctrlk, parent.ctrlm, parent.ctrlc,
                 parent.cmdd, parent.cmds, parent.cmdv, parent.cmda, parent.cmdl, parent.cmde, parent.cmdr, parent.cmdk, parent.cmdm, parent.cmdc]
    for shortcut in shortcuts:
        try:
            shortcut.activated.disconnect()
        except TypeError:
            # 연결된 슬롯이 없는 경우 발생하는 에러를 무시
            pass
