// 배포용(prod) pm2 설정.
// 포트는 여기서만 관리한다 — 각 서비스 run.py는 PORT 환경변수를 읽어서 뜬다.
// 규칙: prod는 8000번대, dev(ecosystem.dev.config.js)는 8000번대+10000 = 18000번대.
// 서비스 중요도 순으로 8000부터 채운다(홈페이지가 8000).
// 켜고 끄기: pm2 start/stop/delete ecosystem.prod.config.js
module.exports = {
  apps: [
    {
      name: "homepage",
      cwd: "/home/lab/knpu/homepage/server",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: true,
      time: true,
      env: { MODE: "1", PORT: "8000" },
    },
    {
      name: "manager",
      cwd: "/home/lab/knpu/manager/server",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: false,
      time: true,
      env: { MODE: "1", PORT: "8001" },
    },
    {
      name: "network",
      cwd: "/home/lab/knpu/network",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: false,
      time: true,
      env: { MODE: "1", PORT: "8002" },
    },
    {
      name: "kemkim",
      cwd: "/home/lab/knpu/kemkim",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: false,
      time: true,
      env: { MODE: "1", PORT: "8003" },
    },
    {
      name: "statistics",
      cwd: "/home/lab/knpu/statistics",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: false,
      time: true,
      env: { MODE: "1", PORT: "8004" },
    },
    // 참고: crawler는 지금 pm2가 아니라 별도(nohup 등)로 떠 있음.
    // 포트/코드는 새 체계에 맞춰 8005로 바꿔뒀지만, pm2 등록 여부는 요청하신 적 없어서
    // 이 항목은 아직 pm2 start를 걸지 않았습니다 — 넣어드릴지 확인 후 진행하겠습니다.
    {
      name: "crawler",
      cwd: "/home/lab/knpu/crawler",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: false,
      time: true,
      env: { MODE: "1", PORT: "8005" },
    },
    {
      name: "manager_web",
      cwd: "/home/lab/knpu/manager/web",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: true,
      time: true,
      env: { MODE: "1", PORT: "8006" },
    },
    {
      name: "ahp",
      cwd: "/home/lab/knpu/ahp",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: false,
      time: true,
      env: { MODE: "1", PORT: "8007" },
    },
    {
      name: "complaint",
      cwd: "/home/lab/knpu/complaint/server",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: true,
      time: true,
      env: { MODE: "1", PORT: "8008" },
    },
    {
      name: "dashboard",
      cwd: "/home/lab/knpu/admin",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: true,
      time: true,
      env: { MODE: "1", PORT: "8009" },
    },
    // 아래 두 개는 포트로 운영되는 웹 서비스가 아니라서(디스코드 봇 / SSH 터널)
    // dev 사본을 두지 않는다 — 봇 토큰이 같아 이중 기동하면 메시지가 중복 처리된다.
    {
      name: "bot",
      cwd: "/home/lab/knpu/system/bot",
      script: "run.py",
      interpreter: "/home/lab/knpu/.venv/bin/python",
      watch: true,
      time: true,
      env: { MODE: "1" },
    },
    {
      name: "gpu-tunnel",
      script: "/home/lab/bash/gpu_tunnel.sh",
      watch: true,
      time: true,
    },
  ],
};
