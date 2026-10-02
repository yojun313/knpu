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
