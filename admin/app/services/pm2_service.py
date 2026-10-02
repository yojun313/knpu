import subprocess
import json
import shutil
import os

from app.services.ecosystem_service import child_env


class PM2Service:
    @staticmethod
    def get_processes():
        pm2_path = shutil.which("pm2")
        if not pm2_path:
            return []
        try:
            # jlist 호출
            result = subprocess.run(
                f"{pm2_path} jlist",
                shell=True,
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except Exception as e:
            print(f"PM2 get_processes Error: {e}")
            return []

    @staticmethod
    def run_command(action: str, name: str, extra_args: list = None):
        pm2_path = shutil.which("pm2")
        if not pm2_path:
            return False

        # 셸을 거치지 않고 인자 목록으로 실행한다(이름에 ; $() 등이 있어도 명령이 되지 않게).
        command = [pm2_path, action, name, *(extra_args or [])]

        try:
            # 대시보드의 환경(PORT=8009 등)이 대상 앱에 섞이지 않게 깨끗한 환경으로 실행한다.
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=120, env=child_env()
            )

            if result.returncode != 0:
                print(f"PM2 Command Failed: {command}")
                print(f"Error Message: {result.stderr}")
                return False

            return True
        except Exception as e:
            print(f"General Error: {e}")
            return False

    @staticmethod
    def self_name() -> str | None:
        """이 대시보드가 pm2 로 실행 중이면 그 앱 이름(pm2 가 name 환경 변수로 넣어 준다)."""
        if os.environ.get("pm_id") is None:
            return None
        return os.environ.get("name") or None

    @staticmethod
    def restart_command(name: str) -> tuple[list[str], str | None]:
        """재시작 명령. ecosystem 파일에 있는 앱이면 그 파일 기준으로 재시작해
        파일의 env(PORT·MODE 등)를 다시 적용한다 — 예전 버그로 다른 앱의 PORT 가 저장돼
        있어도 이걸로 바로잡힌다. 없는 앱이면 저장된 설정 그대로 재시작한다."""
        pm2_path = shutil.which("pm2") or "pm2"
        try:
            from app.services import ecosystem_service

            path = ecosystem_service.ecosystem_path()
            apps = {a.get("name") for a in ecosystem_service.load_apps(path)}
        except Exception:
            path, apps = None, set()
        if path is not None and name in apps:
            return (
                [pm2_path, "restart", str(path), "--only", name, "--update-env"],
                str(path.parent),
            )
        return [pm2_path, "restart", name], None

    @staticmethod
    def restart(name: str) -> tuple[bool, str]:
        command, cwd = PM2Service.restart_command(name)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=cwd,
                env=child_env(),
            )
        except Exception as e:
            return False, str(e)
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            print(f"PM2 Command Failed: {command}\n{output[-2000:]}")
        return result.returncode == 0, output[-2000:]

    @staticmethod
    def restart_detached(name: str) -> bool:
        """대시보드 자기 자신 재시작. pm2 는 재시작할 때 프로세스 트리를 통째로 죽이므로
        대시보드의 자식으로 pm2 를 돌리면 명령이 중간에 같이 죽는다. setsid -f 로
        대시보드와 무관한 프로세스로 떼어 내 실행한다."""
        command, cwd = PM2Service.restart_command(name)
        setsid = shutil.which("setsid")
        try:
            subprocess.Popen(
                ([setsid, "-f"] if setsid else []) + command,
                cwd=cwd,
                env=child_env(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
            return True
        except Exception as e:
            print(f"PM2 detached restart failed: {e}")
            return False

    @staticmethod
    def save_processes():
        pm2_path = shutil.which("pm2")
        try:
            subprocess.run(f"{pm2_path} save", shell=True, check=True)
            return True
        except:
            return False

    @staticmethod
    def get_startup_status():
        pm2_path = shutil.which("pm2")
        try:
            result = subprocess.run(
                f"{pm2_path} startup", shell=True, capture_output=True, text=True
            )
            return (
                "already configured" in result.stdout.lower()
                or "sudo" in result.stdout.lower()
            )
        except:
            return False
