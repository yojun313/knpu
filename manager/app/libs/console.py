import platform, sys, os, ctypes, subprocess, tempfile, textwrap, shlex

class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", ctypes.c_short),
                ("Top",  ctypes.c_short),
                ("Right", ctypes.c_short),
                ("Bottom", ctypes.c_short)]

_original_stdout = sys.stdout
_log_file = None          # macOS용 로그 파일 핸들
_log_path   = None
_term_win_id = None  


def _open_console_windows(msg: str):
    global _original_stdout
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

        print("[ MANAGER ]")
        print(f'\n< {msg} >\n')  # 테스트 출력
    except Exception as e:
        sys.stdout = _original_stdout  # 에러 발생 시 stdout 복구
        print(e)

def _close_console_windows():
    global _original_stdout
    try:
        if platform.system() != 'Windows':
            return
        sys.stdout.close()  # 콘솔 창 출력 닫기
        sys.stdout = _original_stdout  # stdout 복구
        ctypes.windll.kernel32.FreeConsole()  # 콘솔 창 해제
    except Exception as e:
        sys.stdout = _original_stdout  # 에러 발생 시 stdout 복구
        print(e)

def _open_console_macos(msg: str = ""):
    global _log_file, _log_path, _term_win_id

    # 터미널에서 직접 실행된 경우 → 그냥 출력
    if sys.stdout.isatty():
        print("[ MANAGER ]")
        if msg: print(f"< {msg} >")
        return

    # 1) 로그 파일 준비
    _log_path = os.path.join(tempfile.gettempdir(),
                             f"pyqt_console_{os.getpid()}.log")
    _log_file = open(_log_path, "w", buffering=1, encoding="utf-8")
    sys.stdout = sys.stderr = _log_file

    # 2) AppleScript : 빈 창을 재활용하거나 하나만 새로 열어 tail 실행
    tail_cmd = f"tail -f {shlex.quote(_log_path)}"
    osa = textwrap.dedent(f"""
        tell application "Terminal"
            if not running then
                -- Terminal이 꺼져 있었으면 do script 가 '창 1개'를 자동 생성
                do script "{tail_cmd}"
            else
                -- 이미 켜져 있다면 새 탭 대신 '새 창' 하나만 열기
                do script "{tail_cmd}" in (make new window)
            end if
            delay 0.05
            set win_id to id of front window
            activate
            return win_id
        end tell
    """).strip()

    try:
        _term_win_id = int(subprocess.check_output(
            ["osascript", "-e", osa], text=True).strip())
    except Exception as e:
        _term_win_id = None
        print(f"[WARN] 창 ID 획득 실패: {e}", file=_original_stdout)

    print("[ MANAGER ]")
    if msg: print(f"< {msg} >")

def _close_console_macos():
    global _log_file, _log_path

    # 1) 로그 파일 핸들 닫기
    if _log_file and not _log_file.closed:
        _log_file.close()

    # 2) AppleScript 로 창 닫고 Terminal 강제 종료
    osa_close = textwrap.dedent(f"""
        tell application "Terminal"
            try
                if {_term_win_id or 0} ≠ 0 then
                    close (every window whose id is {_term_win_id})
                else
                    close (every window whose name contains "tail -f")
                end if
            end try
            quit saving no        -- 확인 없이 즉시 종료
        end tell
    """).strip()
    subprocess.Popen(["osascript", "-e", osa_close])

    # 3) 로그 파일 삭제
    if _log_path and os.path.exists(_log_path):
        try: os.remove(_log_path)
        except Exception as e:
            print(f"[WARN] 로그 파일 삭제 실패: {e}", file=_original_stdout)

    sys.stdout = sys.stderr = _original_stdout

def openConsole(msg: str = ""):
    """필요하면 콘솔(터미널) 창을 열고 stdout/stderr을 그쪽으로 보낸다."""
    if platform.system() == "Windows":
        _open_console_windows(msg)
    elif platform.system() == "Darwin":
        _open_console_macos(msg)
    # Linux 등 그 외 OS 는 생략했지만, gnome-terminal / xterm 호출 방식으로 확장 가능

def closeConsole():
    """열어 둔 콘솔 자원을 해제한다."""
    if platform.system() == "Windows":
        _close_console_windows()
    elif platform.system() == "Darwin":
        _close_console_macos()

# ===== 편의 함수 =====
def clear_console():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")

# ===== 예시 =====
if __name__ == "__main__":
    openConsole("콘솔/터미널 창이 열렸습니다!")
    print("여기에 PyQt 내부 print 도 함께 찍힙니다.")
    input("엔터를 누르면 창을 닫습니다…")
    closeConsole()
