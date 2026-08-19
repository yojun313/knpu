# uvicorn app.main:app --host 0.0.0.0 --port 8003

import os
import uvicorn
import warnings
from requests.exceptions import RequestsDependencyWarning

warnings.filterwarnings("ignore", category=RequestsDependencyWarning)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8008)),
        workers=1,
        log_level="warning",
        access_log=True,
        reload=True,
        timeout_keep_alive=86400,
    )
