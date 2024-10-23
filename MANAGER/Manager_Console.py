import platform
import sys
import ctypes
import os
from colorama import init, Fore, Style

# colorama 초기화
init(autoreset=True)

def open_console(msg=''):
    if platform.system() == 'Windows':
        """콘솔 창을 열어 print 출력을 가능하게"""
        ctypes.windll.kernel32.AllocConsole()  # 새로운 콘솔 창 할당
        sys.stdout = open("CONOUT$", "w")  # 표준 출력을 콘솔로 리다이렉트

        # 콘솔 창 크기 설정
        hConsole = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE = -11

        # 콘솔 창 크기 설정 (가로 80, 세로 30)
        rect = ctypes.wintypes.SMALL_RECT(0, 0, 79, 29)  # 왼쪽, 위쪽, 오른쪽, 아래쪽
        ctypes.windll.kernel32.SetConsoleWindowInfo(hConsole, True, ctypes.byref(rect))

        # 컬러와 스타일 적용
        print(Fore.GREEN + Style.BRIGHT + "[ BIGMACLAB MANAGER ]")
        print(Fore.YELLOW + f'\n< {msg} >\n')  # 테스트 출력

def close_console():
    if platform.system() == 'Windows':
        """콘솔 창을 닫음"""
        sys.stdout.close()  # 콘솔 창 출력 닫기
        ctypes.windll.kernel32.FreeConsole()  # 콘솔 창 해제

def clear_console():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")
