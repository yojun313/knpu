import platform
import sys
import ctypes
import os
import psutil
import time

def open_console(msg=''):
    if platform.system() != 'Windows':
        return
    """콘솔 창을 열어 print 출력을 가능하게"""
    ctypes.windll.kernel32.AllocConsole()  # 새로운 콘솔 창 할당
    sys.stdout = open("CONOUT$", "w")  # 표준 출력을 콘솔로 리다이렉트

    # 콘솔 창 크기 설정
    hConsole = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE = -11

    # 콘솔 창 크기 설정 (가로 80, 세로 30)
    rect = ctypes.wintypes.SMALL_RECT(0, 0, 79, 29)  # 왼쪽, 위쪽, 오른쪽, 아래쪽
    ctypes.windll.kernel32.SetConsoleWindowInfo(hConsole, True, ctypes.byref(rect))

    print("[ BIGMACLAB MANAGER ]")
    print(f'\n< {msg} >\n')  # 테스트 출력

def close_console():
    if platform.system() != 'Windows':
        return
    """콘솔 창을 닫음"""
    sys.stdout.close()  # 콘솔 창 출력 닫기
    ctypes.windll.kernel32.FreeConsole()  # 콘솔 창 해제

def open_resource_console():
    if platform.system() != 'Windows':
        return
    """리소스 모니터링용 별도 콘솔 창을 열어 시스템 리소스를 출력."""
    ctypes.windll.kernel32.AllocConsole()  # 새로운 콘솔 창 할당
    resource_console_out = open("CONOUT$", "w")  # 리소스 전용 콘솔 출력으로 리다이렉트

    def resource_monitor():
        """주기적으로 CPU와 메모리 사용량을 리소스 전용 콘솔에 출력."""
        while True:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_info = psutil.virtual_memory()
            memory_usage = memory_info.percent
            print(f"CPU Usage: {cpu_usage}% | Memory Usage: {memory_usage}%", file=resource_console_out)
            time.sleep(1)  # 매초 업데이트

    # 리소스 모니터링 쓰레드 시작
    monitoring_thread = threading.Thread(target=resource_monitor)
    monitoring_thread.daemon = True
    monitoring_thread.start()


def clear_console():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")