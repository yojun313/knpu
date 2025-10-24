# gunicorn app.main:app -c run.py

bind = "0.0.0.0:8000"
workers = 10
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 0
loglevel = "warning"
accesslog = None          
keepalive = 86400