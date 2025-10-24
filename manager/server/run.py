# gunicorn app.main:app -c run.py
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1       
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 0
loglevel = "warning"
accesslog = None          
keepalive = 86400