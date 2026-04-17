# gunicorn app.main:app -c run.py
# uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
bind = "0.0.0.0:8002"
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 0
loglevel = "warning"
accesslog = None          
keepalive = 86400
