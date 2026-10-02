"""오래 걸리는 분석(KEMKIM·네트워크·통계·혐오도 …)을 '작업'으로 관리한다.

서비스 main.py 에서:

    from system.jobs import install_jobs
    install_jobs(app, service="statistics", entry="app.services.analyze_service:run_job")

* /api/jobs/* API(목록·상세·중단·다시 실행·예약 변경·삭제)를 붙이고
* 기동 때 러너 스레드를 띄우며, 종료 때 실행 중인 프로세스 그룹을 정리한다.
분석 시작 라우트는 system.jobs.submit(...) 으로 작업을 등록한다.

이 패키지는 감독 프로세스가 가볍게 import 하므로 여기서 무거운 모듈을 불러오지 않는다.
"""


def install_jobs(
    app,
    *,
    service: str,
    entry: str,
    cwd: str | None = None,
    max_concurrent: int | None = None,
):
    """cwd: 서비스 루트(app/ 가 있는 폴더). 워커가 여기서 entry 를 import 한다."""
    import os

    from system.jobs.routes import register
    from system.jobs.runner import Runner

    cwd = cwd or os.getcwd()
    limit = max_concurrent or int(os.getenv("JOBS_MAX_CONCURRENT", "2") or 2)
    runner = Runner(service, entry, cwd, limit)
    register(app, service, runner)

    @app.on_event("startup")
    def _jobs_startup():
        runner.start()

    @app.on_event("shutdown")
    def _jobs_shutdown():
        runner.shutdown()

    app.state.jobs_runner = runner
    return runner


def submit(**kwargs):
    from system.jobs.store import create

    return create(**kwargs)
