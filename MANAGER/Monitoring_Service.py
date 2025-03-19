import time
import requests
from mySQL import mySQL
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

class Monitoring:
    def __init__(self):
        self.console = Console()  # Rich Console 인스턴스 생성
        self.app_key = "a2x6qmtaup9a3upmupiftv2fqfu8sz"
        self.user_keys = ['uvz7oczixno7daxvgxmq65g2gbnsd5']
        self.z8_status = {"db": True, "crawler": True}
        self.omen_status = True

    def main(self):
        with Live(refresh_per_second=1, console=self.console) as live:
            while True:
                status = self.check_servers(live)
                if status is not True:
                    error_num, computer, server_type = status
                    msg = self.create_error_message(error_num, computer, server_type)

                    for key in self.user_keys:
                        self.sendPushOver(msg, key)

                time.sleep(60)

    def create_error_message(self, error_num, computer, server_type):
        return (
            f"PROBLEMS DETECTED IN SERVER\n\n"
            f"DateTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Computer: {computer}\n"
            f"Object: {server_type.upper()}\n"
            f"Solution:\n"
            f"1. Check {computer} if it is online\n"
            f"2. Check {computer} network"
        )

    def sendPushOver(self, msg, user_key):
        url = 'https://api.pushover.net/1/messages.json'
        message = {
            'token': self.app_key,
            'user': user_key,
            'message': msg
        }

        while True:
            try:
                requests.post(url, data=message)
                return
            except:
                continue

    def check_servers(self, live):
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Component", justify="left", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center", style="green")

        z8_db_status = "Online" if self.check_z8_db() else "Offline"
        z8_crawler_status = "Online" if self.check_z8_crawler() else "Offline"
        omen_crawler_status = "Online" if self.check_omen_crawler() else "Offline"

        table.add_row("Z8 Database", 'Online' if self.z8_status['db'] == True else 'Offline')
        table.add_row("Z8 Crawler", 'Online' if self.z8_status['crawler'] == True else 'Offline')
        table.add_row("OMEN Crawler", 'Online' if self.omen_status == True else 'Offline')

        live.update(Panel(table, title=f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))

        if "Offline" in [z8_db_status, z8_crawler_status, omen_crawler_status]:
            if z8_db_status == "Offline":
                return (1, 'Z8', 'DB SERVER')
            elif z8_crawler_status == "Offline":
                return (1, 'Z8', 'CRAWLER')
            else:
                return (1, 'OMEN', 'CRAWLER')
        return True

    def check_z8_db(self):
        try:
            mySQLObj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306)
        except:
            return False
        if mySQLObj.showAllDB() == []:
            if self.z8_status["db"]:
                self.z8_status["db"] = False
                return False
        else:
            if not self.z8_status["db"]:
                self.notify_recovery("Z8", "DB Server")
                self.z8_status["db"] = True
        return True

    def check_z8_crawler(self):
        return self.check_crawler_server("Z8", "http://bigmaclab-crawler.kro.kr:81", "crawler")

    def check_omen_crawler(self):
        return self.check_crawler_server("OMEN", "http://bigmaclab-crawler.kro.kr:80", "crawler")

    def check_crawler_server(self, computer, url, server_type):
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                if computer == "Z8" and not self.z8_status[server_type]:
                    self.notify_recovery(computer, server_type)
                    self.z8_status[server_type] = True
                elif computer == "OMEN" and not self.omen_status:
                    self.notify_recovery(computer, server_type)
                    self.omen_status = True
            else:
                if computer == "Z8" and self.z8_status[server_type]:
                    self.z8_status[server_type] = False
                    return False
                elif computer == "OMEN" and self.omen_status:
                    self.omen_status = False
                    return False
        except requests.exceptions.RequestException:
            if computer == "Z8" and self.z8_status[server_type]:
                self.z8_status[server_type] = False
                return False
            elif computer == "OMEN" and self.omen_status:
                self.omen_status = False
                return False
        return True

    def notify_recovery(self, computer, server_type):
        recovery_msg = (
            f"SERVER RECOVERED\n\n"
            f"DateTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"{computer} {server_type.upper()} server is stable now"
        )
        for key in self.user_keys:
            self.sendPushOver(recovery_msg, key)


monitoring_obj = Monitoring()
monitoring_obj.main()