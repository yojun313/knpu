import hashlib
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

from app.services.ecosystem_service import child_env
from app.services.repo_git_service import GitService

UV_SYNC_TIMEOUT_SECONDS = 600
_uv_sync_running: set[str] = set()
_uv_sync_lock = threading.Lock()


def _uv_project(cwd: str | None) -> Path | None:
    """uv 프로젝트 폴더 (pyproject.toml + uv.lock). 작업 폴더부터 위로 찾는다 (knpu 처럼 uv 워크스페이스 루트).

    git 저장소 루트나 홈 폴더 밖으로는 올라가지 않는다.
    """
    if not cwd:
        return None
    path = Path(cwd)
    for folder in (path, *path.parents):
        if (folder / "pyproject.toml").is_file() and (folder / "uv.lock").is_file():
            return folder
        if (folder / ".git").exists() or folder == Path.home():
            return None
    return None


def _git_root(cwd: str | None) -> Path | None:
    """앱 작업 폴더가 들어 있는 git 저장소 폴더 (.git 이 있는 가장 가까운 상위)."""
    if not cwd:
        return None
    path = Path(cwd)
    for folder in (path, *path.parents):
        if (folder / ".git").exists():
            return folder
    return None


def _uv_binary() -> str | None:
    # pm2 로 뜬 서버는 PATH 에 ~/.local/bin 이 없을 수 있다
    found = shutil.which("uv")
    if found:
        return found
    for candidate in (Path.home() / ".local/bin/uv", Path.home() / ".cargo/bin/uv"):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def process_flags(processes: list[dict]) -> dict[str, dict]:
    """앱 이름 → {uv, git}: 화면에 uv sync · git pull 버튼을 보일지."""
    flags = {}
    for proc in processes:
        cwd = (proc.get("pm2_env") or {}).get("pm_cwd")
        flags[proc.get("name")] = {
            "uv": _uv_project(cwd) is not None,
            "git": _git_root(cwd) is not None,
        }
    return flags


class PM2Service:
    @staticmethod
    def get_processes():
        pm2_path = shutil.which("pm2")
        if not pm2_path:
            return []
        try:
            # jlist 호출
            result = subprocess.run(
                [pm2_path, "jlist"],
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
    def app_cwd(name: str) -> str | None:
        proc = next(
            (p for p in PM2Service.get_processes() if p.get("name") == name), None
        )
        if proc is None:
            raise KeyError("프로세스를 찾을 수 없습니다.")
        return (proc.get("pm2_env") or {}).get("pm_cwd")

    @staticmethod
    def uv_sync(name: str) -> tuple[bool, str]:
        """pm2 앱의 uv 프로젝트(워크스페이스 루트) 폴더에서 `uv sync`. 반환: (성공 여부, 출력)."""
        project = _uv_project(PM2Service.app_cwd(name))
        if project is None:
            raise ValueError("uv 프로젝트(pyproject.toml + uv.lock)가 아닙니다.")
        uv = _uv_binary()
        if not uv:
            raise RuntimeError("uv 를 찾을 수 없습니다.")
        key = str(project)
        with _uv_sync_lock:
            if key in _uv_sync_running:
                raise RuntimeError("이미 uv sync 가 실행 중입니다.")
            _uv_sync_running.add(key)
        # 대시보드의 .env 값 · 가상환경이 섞이지 않게 기본 변수만 넘긴다
        env = {**child_env(), "NO_COLOR": "1"}
        try:
            result = subprocess.run(
                [uv, "sync"],
                cwd=project,
                capture_output=True,
                text=True,
                timeout=UV_SYNC_TIMEOUT_SECONDS,
                check=False,
                env=env,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return False, f"{UV_SYNC_TIMEOUT_SECONDS}초 안에 끝나지 않았습니다."
        except OSError as error:
            return False, str(error)
        finally:
            with _uv_sync_lock:
                _uv_sync_running.discard(key)
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, f"$ cd {project} && uv sync\n{output}"[-20000:]

    @staticmethod
    def git_pull(name: str) -> dict:
        """pm2 앱이 들어 있는 저장소에서 `git pull --ff-only`. 서버에서 머지 커밋은 만들지 않는다.

        Git 페이지와 같은 저장소 잠금을 써서 두 곳에서 동시에 Git 작업이 돌지 않게 한다.
        """
        cwd = PM2Service.app_cwd(name)
        if _git_root(cwd) is None:
            raise ValueError("git 저장소가 아닙니다.")
        top = GitService._run(Path(cwd), "rev-parse", "--show-toplevel", timeout=10)
        if top.returncode != 0:
            raise ValueError("git 저장소가 아닙니다.")
        repo = Path(top.stdout.strip()).resolve()
        repo_id = hashlib.sha256(str(repo).encode("utf-8")).hexdigest()[:16]
        lock = GitService._lock_for(repo_id)
        if not lock.acquire(blocking=False):
            raise RuntimeError("이 저장소에서 다른 Git 작업이 실행 중입니다.")
        try:
            before = GitService._text(repo, "rev-parse", "HEAD")
            branch = GitService._text(repo, "branch", "--show-current")
            try:
                result = GitService._run(repo, "pull", "--ff-only")
            except subprocess.TimeoutExpired:
                return {
                    "ok": False,
                    "output": "시간 안에 끝나지 않아 중단했습니다.",
                    "changed": [],
                }
            after = GitService._text(repo, "rev-parse", "HEAD")
            changed = []
            if result.returncode == 0 and before and after and before != after:
                diff = GitService._text(
                    repo, "diff", "--name-only", "-z", before, after
                )
                changed = [f for f in diff.split("\0") if f]
        finally:
            lock.release()
        output = "\n".join(
            part for part in (result.stdout.strip(), result.stderr.strip()) if part
        )
        project = _uv_project(cwd)
        deps = set()
        if project is not None:
            rel = project.resolve().relative_to(repo)
            deps = {
                f if str(rel) == "." else str(rel / f)
                for f in ("uv.lock", "pyproject.toml")
            }
        return {
            "ok": result.returncode == 0,
            "repo": str(repo),
            "branch": branch,
            "updated": before != after,
            "changed": changed[:500],
            # 워크스페이스 멤버의 pyproject.toml 이 바뀌어도 uv.lock 이 같이 바뀐다
            "deps_changed": bool(deps & set(changed)),
            "output": GitService._mask(output)[-20000:] or "(출력 없음)",
        }

    @staticmethod
    def save_processes():
        pm2_path = shutil.which("pm2")
        try:
            subprocess.run([pm2_path, "save"], check=True)
            return True
        except:
            return False

    @staticmethod
    def get_startup_status():
        pm2_path = shutil.which("pm2")
        try:
            result = subprocess.run(
                [pm2_path, "startup"], capture_output=True, text=True
            )
            return (
                "already configured" in result.stdout.lower()
                or "sudo" in result.stdout.lower()
            )
        except:
            return False
