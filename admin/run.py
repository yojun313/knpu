# uvicorn app.main:app --host 0.0.0.0 --port 3004 --reload

import uvicorn
import warnings
from requests.exceptions import RequestsDependencyWarning

warnings.filterwarnings("ignore", category=RequestsDependencyWarning)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=3004,
        log_level="warning",
        access_log=True,
        timeout_keep_alive=86400,
    )