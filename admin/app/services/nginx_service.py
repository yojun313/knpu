import subprocess
import os

class NginxService:
    SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))

    @staticmethod
    def get_domains():
        """view_nginx.sh 로직을 파이썬에서 실행하여 리스트 반환"""
        domains = []
        enabled_path = "/etc/nginx/sites-enabled"
        
        if not os.path.exists(enabled_path):
            return domains

        for filename in os.listdir(enabled_path):
            file_path = os.path.join(enabled_path, filename)
            if os.path.isfile(file_path):
                try:
                    # 간단한 파싱 로직
                    with open(file_path, 'r') as f:
                        content = f.read()
                        import re
                        domain_match = re.search(r'server_name\s+([^;]+);', content)
                        port_match = re.search(r'proxy_pass\s+http://localhost:(\d+);', content)
                        
                        domains.append({
                            "domain": domain_match.group(1).strip() if domain_match else "N/A",
                            "port": port_match.group(1) if port_match else "N/A",
                            "filename": filename
                        })
                except Exception:
                    continue
        
        domains.sort(key=lambda x: int(x['port']) if x['port'].isdigit() else 99999)
        return domains

    @classmethod
    def add_domain(cls, domain: str, email: str, port: str):
        """add_nginx.sh 실행 (입력값을 순서대로 주입)"""
        script_path = os.path.join(cls.SCRIPT_DIR, "add_nginx.sh")
        inputs = f"{domain}\n{email}\n{port}\n"
        process = subprocess.Popen(['sudo', 'bash', script_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(input=inputs)
        return process.returncode == 0, stdout + stderr

    @classmethod
    def delete_domain(cls, domain_name: str):
        try:
            # 1. Certbot 인증서 삭제
            subprocess.run(['sudo', 'certbot', 'delete', '--cert-name', domain_name, '--non-interactive'], check=False)
            # 2. Nginx 설정 파일 삭제
            subprocess.run(['sudo', 'rm', f'/etc/nginx/sites-enabled/{domain_name}'], check=False)
            subprocess.run(['sudo', 'rm', f'/etc/nginx/sites-available/{domain_name}'], check=False)
            # 3. Nginx Reload
            subprocess.run(['sudo', 'nginx', '-t'], check=True)
            subprocess.run(['sudo', 'systemctl', 'reload', 'nginx'], check=True)
            return True, "Success"
        except Exception as e:
            return False, str(e)