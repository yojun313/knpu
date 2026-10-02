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

// 분석 서비스: 종료 신호 → uvicorn 정리(최대 5초) → 작업 러너가 분석 프로세스 그룹을
// SIGTERM/SIGKILL 로 정리할 시간을 준다. 기본 1.6초면 그 전에 SIGKILL 돼 손자 프로세스가 남는다.
const ANALYSIS = { kill_timeout: 20000, treekill: true };

module.exports = {
  apps: [
    app("homepage-dev", "homepage/server", "homepage"),
    app("manager-dev", "manager/server", "manager"),
    app("network-dev", "network", "network", ANALYSIS),
    app("kemkim-dev", "kemkim", "kemkim", ANALYSIS),
    app("statistics-dev", "statistics", "statistics", ANALYSIS),
    app("manager_web-dev", "manager/web", "progress"),
    app("mcdm-dev", "mcdm", "mcdm"),
    app("complaint-dev", "complaint/server", "complaint"),
    app("dashboard-dev", "admin", "dashboard"),
    app("whisper-dev", "whisper", "whisper"),
  ],
};
