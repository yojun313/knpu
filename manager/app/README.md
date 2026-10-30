# KNPU MANAGER App

PyInstaller로 빌드하는 데스크톱 클라이언트입니다. 루트 uv 워크스페이스의 멤버이므로 의존성은 저장소 루트의 `uv.lock`으로 관리합니다(이 폴더에는 별도 lock 파일이 없습니다).

## 컴파일 머신 환경 구성

컴파일 머신에서는 반드시 **저장소 루트에서** 아래 명령으로 동기화합니다.

```bash
uv sync --package manager-app
```

이 명령은 가상환경을 manager 앱에 필요한 패키지만 남도록 맞춥니다. 빌드 스크립트(`compile/config.py`의 `VENV_PYTHON`)는 `C:/GitHub/knpu/venv`를 사용하므로, 그 위치에 설치하려면 경로를 지정합니다.

```powershell
$env:UV_PROJECT_ENVIRONMENT="venv"; uv sync --package manager-app
```

> 서버처럼 다른 서비스와 루트 `.venv`를 함께 쓰는 환경에서는 위 명령을 그대로 실행하지 않습니다. 다른 서비스의 패키지가 삭제되므로 `uv sync --package manager-app --inexact`를 사용합니다.
