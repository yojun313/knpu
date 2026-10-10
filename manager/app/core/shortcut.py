from PySide6.QtGui import QKeySequence, QShortcut
from services.update import updateProgram
from libs.console import openConsole, closeConsole


SHORTCUT_KEYS = {
    "ctrld": "Ctrl+D",
    "ctrls": "Ctrl+S",
    "ctrlv": "Ctrl+V",
    "ctrlu": "Ctrl+U",
    "ctrll": "Ctrl+L",
    "ctrla": "Ctrl+A",
    "ctrli": "Ctrl+I",
    "ctrle": "Ctrl+E",
    "ctrlr": "Ctrl+R",
    "ctrlk": "Ctrl+K",
    "ctrlm": "Ctrl+M",
    "ctrlp": "Ctrl+P",
    "ctrlc": "Ctrl+C",
    "ctrlq": "Ctrl+Q",
    "ctrlpp": "Ctrl+Shift+P",
    "cmdd": "Ctrl+ㅇ",
    "cmds": "Ctrl+ㄴ",
    "cmdv": "Ctrl+ㅍ",
    "cmdu": "Ctrl+ㅕ",
    "cmdl": "Ctrl+ㅣ",
    "cmda": "Ctrl+ㅁ",
    "cmdi": "Ctrl+ㅑ",
    "cmde": "Ctrl+ㄷ",
    "cmdr": "Ctrl+ㄱ",
    "cmdk": "Ctrl+ㅏ",
    "cmdm": "Ctrl+ㅡ",
    "cmdp": "Ctrl+ㅔ",
    "cmdc": "Ctrl+ㅊ",
    "cmdq": "Ctrl+ㅂ",
    "cmdpp": "Ctrl+Shift+ㅔ",
}


def initShortcut(parent):
    # 화면별 재등록이 먼저 호출되어도 모든 단축키 객체를 한 번만 만든다.
    for name, key in SHORTCUT_KEYS.items():
        if getattr(parent, name, None) is None:
            setattr(parent, name, QShortcut(QKeySequence(key), parent))

    if getattr(parent, "_global_shortcuts_initialized", False):
        return

    parent.ctrlu.activated.connect(lambda: updateProgram(parent, sc=True))
    parent.ctrlq.activated.connect(lambda: parent.close())
    parent.ctrlp.activated.connect(lambda: openConsole("Developer Mode"))
    parent.ctrlpp.activated.connect(lambda: closeConsole())

    parent.cmdu.activated.connect(lambda: updateProgram(parent, sc=True))
    parent.cmdq.activated.connect(lambda: parent.close())
    parent.cmdp.activated.connect(lambda: openConsole("Developer Mode"))
    parent.cmdpp.activated.connect(lambda: closeConsole())
    parent._global_shortcuts_initialized = True


def resetShortcuts(parent):
    initShortcut(parent)
    shortcuts = [
        parent.ctrld,
        parent.ctrls,
        parent.ctrlv,
        parent.ctrla,
        parent.ctrll,
        parent.ctrle,
        parent.ctrlr,
        parent.ctrlk,
        parent.ctrlm,
        parent.ctrlc,
        parent.ctrli,
        parent.cmdd,
        parent.cmds,
        parent.cmdv,
        parent.cmda,
        parent.cmdl,
        parent.cmde,
        parent.cmdr,
        parent.cmdk,
        parent.cmdm,
        parent.cmdc,
        parent.cmdi,
    ]
    for shortcut in shortcuts:
        try:
            shortcut.activated.disconnect()
        except TypeError:
            pass
