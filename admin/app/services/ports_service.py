import psutil
from app.services.pm2_service import PM2Service
from app.services.nginx_service import NginxService


class PortsService:
    @staticmethod
    def _pm2_pid_map():
        pid_map = {}
        for proc in PM2Service.get_processes():
            pid = proc.get("pid") or proc.get("monit", {}).get("pid")
            if pid:
                pid_map[pid] = proc.get("name")
        return pid_map

    @staticmethod
    def _nginx_port_map():
        port_map = {}
        for domain_info in NginxService.get_domains():
            for p in domain_info.get("paths", []):
                port = p.get("port")
                if not port or port == "N/A":
                    continue
                port_map.setdefault(port, []).append(
                    {"domain": domain_info["domain"], "path": p["path"]}
                )
        return port_map

    @staticmethod
    def _process_label(pid):
        if not pid:
            return None
        try:
            p = psutil.Process(pid)
            name = p.name()
            try:
                cwd = p.cwd()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                cwd = None
            return {"name": name, "cwd": cwd, "user": p.username()}
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    @staticmethod
    def _find_pm2_name(pid, pm2_pid_map, max_depth=4):
        if not pid:
            return None
        if pid in pm2_pid_map:
            return pm2_pid_map[pid]
        try:
            proc = psutil.Process(pid)
            for _ in range(max_depth):
                proc = proc.parent()
                if proc is None:
                    return None
                if proc.pid in pm2_pid_map:
                    return pm2_pid_map[proc.pid]
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
        return None

    @classmethod
    def get_listening_ports(cls):
        pm2_pid_map = cls._pm2_pid_map()
        nginx_port_map = cls._nginx_port_map()

        seen = {}  # port -> entry  (같은 포트를 IPv4/IPv6 등 여러 주소로 바인딩한 경우 병합)
        try:
            conns = psutil.net_connections(kind="tcp")
        except (psutil.AccessDenied, PermissionError):
            conns = []

        for c in conns:
            if c.status != psutil.CONN_LISTEN or not c.laddr:
                continue

            port = c.laddr.port
            key = port
            if key in seen:
                # 같은 포트를 IPv4/IPv6 양쪽으로 바인딩한 경우 — 주소만 추가
                addrs = seen[key]["addresses"]
                if c.laddr.ip not in addrs:
                    addrs.append(c.laddr.ip)
                continue

            proc_info = cls._process_label(c.pid)
            pm2_name = cls._find_pm2_name(c.pid, pm2_pid_map)
            domains = nginx_port_map.get(str(port), [])

            seen[key] = {
                "port": port,
                "proto": "tcp",
                "addresses": [c.laddr.ip],
                "pid": c.pid,
                "process_name": proc_info["name"] if proc_info else None,
                "process_user": proc_info["user"] if proc_info else None,
                "process_cwd": proc_info["cwd"] if proc_info else None,
                "pm2_name": pm2_name,
                "domains": domains,
            }

        ports = sorted(seen.values(), key=lambda e: e["port"])

        # nginx가 특정 포트로 proxy_pass 하도록 설정돼 있는데, 정작 해당 포트가 지금 아무도
        # LISTEN 하고 있지 않은 경우(서비스가 안 떠 있음) — 눈에 띄게 별도로 표시한다.
        listening_ports = {str(e["port"]) for e in ports}
        dangling = []
        for port_str, domain_list in nginx_port_map.items():
            if port_str not in listening_ports:
                dangling.append({"port": port_str, "domains": domain_list})
        dangling.sort(key=lambda d: int(d["port"]) if d["port"].isdigit() else 0)

        return ports, dangling
