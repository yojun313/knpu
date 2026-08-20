// pm2 ecosystem — prod (MODE=1)
//
// 포트는 여기에 적지 않는다 — knpu/services.json 한 곳에서 읽는다.
// cwd/interpreter는 이 파일이 있는 위치(__dirname) 기준이라 어느 계정의 체크아웃에서도 동작한다.
const fs = require("fs");
const path = require("path");

const MODE = "1";
const PORT_KEY = MODE === "0" ? "dev_port" : "prod_port";
const SERVICES = JSON.parse(
  fs.readFileSync(path.join(__dirname, "services.json"), "utf8")
).services;

const py = path.join(__dirname, ".venv", "bin", "python");

// service: services.json의 키. null이면 포트를 쓰지 않는 앱(봇 등).
const app = (name, dir, service, extra = {}) => {
  const env = { MODE };
  if (service) {
    const port = SERVICES[service]?.[PORT_KEY];
    if (port == null) {
      throw new Error(
        `services.json에 '${service}'의 ${PORT_KEY}가 없습니다 (pm2 앱: ${name})`
      );
    }
    env.PORT = String(port);
  }
  return {
    name,
    cwd: path.join(__dirname, dir),
    script: "run.py",
    interpreter: py,
    watch: false,
    time: true,
    env,
    ...extra,
  };
};

module.exports = {
  apps: [
    app("homepage", "homepage/server", "homepage", { watch: true }),
    app("manager", "manager/server", "manager"),
    app("network", "network", "network"),
    app("kemkim", "kemkim", "kemkim"),
    app("statistics", "statistics", "statistics"),
    app("manager_web", "manager/web", "progress", { watch: true }),
    app("ahp", "ahp", "ahp"),
    app("complaint", "complaint/server", "complaint", { watch: true }),
    app("dashboard", "admin", "dashboard", { watch: true }),
    app("bot", "system/bot", null, { watch: true }),
    {
      name: "gpu-tunnel",
      script: "/home/lab/bash/gpu_tunnel.sh",
      watch: true,
      time: true,
    },
  ],
};
