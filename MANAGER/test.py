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
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )

    def run_function_in_console(self, message):
        """콘솔 창에 메시지를 전달하는 함수"""
        self.open_console()  # 콘솔이 열려있지 않으면 열기

        # 콘솔에 메시지 출력 명령 전달
        if self.console_process is not None:
            self.console_process.stdin.write(f'echo {message}\n')
            self.console_process.stdin.flush()  # 파이프에 강제로 보내기

console = Console()  # Console 객체 생성
console.run_function_in_console('Hello from PyQt')  # 콘솔 창에 메시지 출력
