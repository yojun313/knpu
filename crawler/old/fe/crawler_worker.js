const { workerData, parentPort } = require('worker_threads');
const { spawn } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

const { scriptPath, args, venvPath } = workerData; // venvPath 추가

// 플랫폼에 따라 Python 실행 파일 경로 설정
const pythonExecutable = os.platform() === 'win32'
    ? path.join(venvPath, 'Scripts', 'python.exe')   // Windows
    : path.join(venvPath, 'bin', 'python');          // macOS/Linux

const pythonProcess = spawn(pythonExecutable, ['-u', scriptPath, ...args]);

pythonProcess.stdout.on('data', (data) => {
    parentPort.postMessage(data.toString());
});

pythonProcess.stderr.on('data', (data) => {
    parentPort.postMessage(`Error: ${data}`);
});

parentPort.on('message', (message) => {
    if (message === 'terminate') {
        terminationReason = 'terminated';
        pythonProcess.kill('SIGINT');
    }
});
