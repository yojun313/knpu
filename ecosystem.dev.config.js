const fs = require("fs");
const path = require("path");

const MODE = "0";
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
    watch: true,
    time: true,
    env,
    ...extra,
  };
};

module.exports = {
  apps: [
    app("homepage-dev", "homepage/server", "homepage"),
    app("manager-dev", "manager/server", "manager"),
    app("network-dev", "network", "network"),
    app("kemkim-dev", "kemkim", "kemkim"),
    app("statistics-dev", "statistics", "statistics"),
    app("manager_web-dev", "manager/web", "progress"),
    app("ahp-dev", "ahp", "ahp"),
    app("complaint-dev", "complaint/server", "complaint"),
    app("dashboard-dev", "admin", "dashboard"),
  ],
};
