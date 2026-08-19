const path = require("path");

const py = path.join(__dirname, ".venv", "bin", "python");
const app = (name, dir, port, extra = {}) => ({
  name,
  cwd: path.join(__dirname, dir),
  script: "run.py",
  interpreter: py,
  watch: false,
  time: true,
  env: { MODE: "0", ...(port ? { PORT: String(port) } : {}) },
  ...extra,
});

module.exports = {
  apps: [
    app("homepage-dev", "homepage/server", 18000),
    app("manager-dev", "manager/server", 18001),
    app("network-dev", "network", 18003),
    app("kemkim-dev", "kemkim", 18008),
    app("statistics-dev", "statistics", 18004),
    app("manager_web-dev", "manager/web", 18006),
    app("ahp-dev", "ahp", 18007),
    app("complaint-dev", "complaint/server", 18010),
    app("dashboard-dev", "admin", 18009),
  ],
};
