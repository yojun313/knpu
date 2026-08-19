const path = require("path");

const py = path.join(__dirname, ".venv", "bin", "python");
const app = (name, dir, port, extra = {}) => ({
  name,
  cwd: path.join(__dirname, dir),
  script: "run.py",
  interpreter: py,
  watch: false,
  time: true,
  env: { MODE: "1", ...(port ? { PORT: String(port) } : {}) },
  ...extra,
});

module.exports = {
  apps: [
    app("homepage", "homepage/server", 8000, { watch: true }),
    app("manager", "manager/server", 8001),
    app("network", "network", 8003),
    app("kemkim", "kemkim", 8008),
    app("statistics", "statistics", 8004),
    app("manager_web", "manager/web", 8006, { watch: true }),
    app("ahp", "ahp", 8007),
    app("complaint", "complaint/server", 8010, { watch: true }),
    app("dashboard", "admin", 8009, { watch: true }),
    app("bot", "system/bot", null, { watch: true }),
    {
      name: "gpu-tunnel",
      script: "/home/lab/bash/gpu_tunnel.sh",
      watch: true,
      time: true,
    },
  ],
};
