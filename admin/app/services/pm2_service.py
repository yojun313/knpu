import subprocess
import json
import shutil

class PM2Service:
    @staticmethod
    def get_processes():
        pm2_path = shutil.which("pm2")
        if not pm2_path:
            return []
        try:
            result = subprocess.run([pm2_path, "jlist"], capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except Exception as e:
            print(f"PM2 get_processes Error: {e}")
            return []

    @staticmethod
    def run_command(action: str, name: str):
        pm2_path = shutil.which("pm2")
        if not pm2_path:
            return False
        try:
            subprocess.run([pm2_path, action, name], check=True)
            return True
        except Exception as e:
            print(f"PM2 run_command Error: {e}")
            return False