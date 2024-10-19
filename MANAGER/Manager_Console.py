import subprocess

class Console():
    def __init__(self):
        self.console_process = None

    def open_console(self):
        """콘솔 창을 열고 프로세스를 유지"""
        if self.console_process is None:  # 콘솔이 열려있지 않다면
            # /K 옵션을 사용해서 명령어가 실행된 후에도 콘솔 창을 유지
            self.console_process = subprocess.Popen(
                ['cmd.exe', '/K'],  # /K를 통해 콘솔이 종료되지 않도록 유지
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )

    def run_function_in_console(self, message):
        """콘솔 창에 메시지를 전달하는 함수"""
        self.open_console()  # 콘솔이 열려있지 않으면 열기

        # 명령어를 전달하여 메시지를 콘솔 창에 출력
        if self.console_process is not None:
            # /C 옵션으로 echo 명령어를 실행
            subprocess.run(f'echo {message}', shell=True)