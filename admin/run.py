# gunicorn app.main:app -c run.py
# uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

import warnings
from requests.exceptions import RequestsDependencyWarning
warnings.filterwarnings("ignore", category=RequestsDependencyWarning)

bind = "0.0.0.0:3004"
workers = 5
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 0
loglevel = "warning"
accesslog = None          
keepalive = 86400
