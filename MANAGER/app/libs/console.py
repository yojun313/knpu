import platform
import sys
import ctypes
import os


class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", ctypes.c_short),
                ("Top", ctypes.c_short),
                ("Right", ctypes.c_short),
                ("Bottom", ctypes.c_short)]


original_stdout = sys.stdout  # 기존 stdout 저장


def openConsole(msg=''):
    global original_stdout
    try:
        if platform.system() != 'Windows':
            return
        ctypes.windll.kernel32.AllocConsole()  # 새로운 콘솔 창 할당
        sys.stdout = open("CONOUT$", "w")  # 표준 출력을 콘솔로 리다이렉트

        # 콘솔 창 크기 설정
        # STD_OUTPUT_HANDLE = -11
        hConsole = ctypes.windll.kernel32.GetStdHandle(-11)
        rect = SMALL_RECT(0, 0, 79, 29)  # 콘솔 창 크기 설정 (가로 80, 세로 30)
        ctypes.windll.kernel32.SetConsoleWindowInfo(
            hConsole, True, ctypes.byref(rect))

        print("[ BIGMACLAB MANAGER ]")
        print(f'\n< {msg} >\n')  # 테스트 출력
    except Exception as e:
        sys.stdout = original_stdout  # 에러 발생 시 stdout 복구
        print(e)


def closeConsole():
    global original_stdout
    try:
        if platform.system() != 'Windows':
            return
        sys.stdout.close()  # 콘솔 창 출력 닫기
        sys.stdout = original_stdout  # stdout 복구
        ctypes.windll.kernel32.FreeConsole()  # 콘솔 창 해제
    except Exception as e:
        sys.stdout = original_stdout  # 에러 발생 시 stdout 복구
        print(e)


def clear_console():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")
