import subprocess
import json
import shutil
import os

class PM2Service:
    @staticmethod
    def get_processes():
        pm2_path = shutil.which("pm2")
        if not pm2_path:
            return []
        try:
            # jlist 호출
            result = subprocess.run(f"{pm2_path} jlist", shell=True, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except Exception as e:
            print(f"PM2 get_processes Error: {e}")
            return []

    @staticmethod
    def run_command(action: str, name: str, extra_args: list = None):
        pm2_path = shutil.which("pm2")
        if not pm2_path:
            return False
        
        args_str = " ".join(extra_args) if extra_args else ""
        command = f"{pm2_path} {action} {name} {args_str}"
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"PM2 Command Failed: {command}")
                print(f"Error Message: {result.stderr}")
                return False
                
            return True
        except Exception as e:
            print(f"General Error: {e}")
            return False
    
    @staticmethod
    def save_processes():
        pm2_path = shutil.which("pm2")
        try:
            subprocess.run(f"{pm2_path} save", shell=True, check=True)
            return True
        except:
            return False

    @staticmethod
    def get_startup_status():
        pm2_path = shutil.which("pm2")
        try:
            result = subprocess.run(f"{pm2_path} startup", shell=True, capture_output=True, text=True)
            return "already configured" in result.stdout.lower() or "sudo" in result.stdout.lower()
        except:
            return False