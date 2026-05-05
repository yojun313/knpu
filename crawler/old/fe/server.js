const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const path = require('path');
const { Worker } = require('worker_threads');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);
let PORT = 3001;

const python_CRAWLER_WEB = path.join(__dirname, '..', '..', 'knpu/crawler/main_web.py');
const crawlWorker_path   = path.join(__dirname, 'crawler_worker.js');

app.use(express.static(path.join(__dirname, 'public')));

app.get('/', (req, res) => {
    const theme = req.query.theme || "";
    res.sendFile(path.join(__dirname, 'public', 'crawl_dashboard.html'), {
        headers: {
            'X-Theme': theme   // 기본 테마 설정
        }
    });
});

app.get('/add', (req, res) => {
    const theme = req.query.theme || ""; // dark 또는 light

    res.sendFile(path.join(__dirname, 'public', 'crawl_add.html'), {
        headers: {
            'X-Theme': theme   // HTML에서 읽을 수 있게 전달
        }
    });
});



let processes = {};

io.on('connection', (socket) => {
    socket.on('crawlInfo_submit', (data) => {
        const processId = Date.now().toString();
        const { name, crawl_object, start_day, end_day, option_select, keyword, uploadToDrive } = data;
        socket.emit('redirect', '/');

        // 예시 venv 경로 (절대경로로 정확히 입력)
        const venvPath = path.join(__dirname, '..', '..', 'knpu/venv'); // 가상환경 경로

        const worker = new Worker(crawlWorker_path, {
            workerData: {
                scriptPath: python_CRAWLER_WEB,
                args: [name, crawl_object, start_day, end_day, option_select, keyword, uploadToDrive],
                venvPath: venvPath  // ✅ 가상환경 경로 전달
            }
        });

        processes[processId] = worker;

        worker.on('message', (output) => {
            io.emit('crawl_progress', {
                processId,
                output,
                name,
                crawl_object,
                start_day,
                end_day,
                option_select,
                keyword,
                uploadToDrive
            });
        });

        worker.on('error', error => {
            console.error(`Worker error: ${error}`);
        });

        worker.on('exit', (code) => {
            console.log(`Worker exited with code ${code}`);
        });
    });
});


server.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
