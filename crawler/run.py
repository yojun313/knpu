import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

MODE = int(os.getenv("MODE", 1))
DEFAULT_PORT = 18002 if MODE == 0 else 8002

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", DEFAULT_PORT)),
        workers=1,
    )
