const express = require('express');
const path = require('path');
const fs = require('fs');
const bodyParser = require('body-parser');
const jwt = require('jsonwebtoken');
const favicon = require('serve-favicon');
const cookieParser = require('cookie-parser');
const http = require('http');
const dotenv = require('dotenv');
const { S3Client, ListObjectsV2Command } = require('@aws-sdk/client-s3');

dotenv.config(); // .env 불러오기

const app = express();
const PORT = 3000;
const SECRET_KEY = process.env.JWT_SECRET || '1234';

// R2 환경 변수 불러오기
const ACCESS_KEY_ID = process.env.ACCESS_KEY_ID;
const SECRET_ACCESS_KEY = process.env.SECRET_ACCESS_KEY;
const ACCOUNT_ID = process.env.ACCOUNT_ID;
const BUCKET_NAME = process.env.BUCKET_NAME;
const R2_ENDPOINT = `https://${ACCOUNT_ID}.r2.cloudflarestorage.com`;

// R2 S3 클라이언트 (AWS SDK v3)
const s3 = new S3Client({
    region: 'auto',
    endpoint: R2_ENDPOINT,
    credentials: {
        accessKeyId: ACCESS_KEY_ID,
        secretAccessKey: SECRET_ACCESS_KEY
    }
});

// 파비콘 설정
app.use(favicon(path.join(__dirname, 'public', 'assets', 'img', 'pailab_logo_favicon.ico')));
app.use(express.static('public'));
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(cookieParser());

// 정적 페이지 라우팅
app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'public', 'homepage.html')));
app.get('/team', (req, res) => res.sendFile(path.join(__dirname, 'public', 'team.html')));
app.get('/publications', (req, res) => res.sendFile(path.join(__dirname, 'public', 'publications.html')));
app.get('/login', (req, res) => res.sendFile(path.join(__dirname, 'public', 'homepage_login.html')));
app.get('/manager', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manager.html')));
app.get('/terms', (req, res) => res.sendFile(path.join(__dirname, 'public', 'terms.html')));

app.get('/tool', (req, res) => res.sendFile(path.join(__dirname, 'public', 'tool.html')));
app.get('/manual/kemkim', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manual_kemkim.html')));
app.get('/manual/hate_analysis', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manual_hateanalysis.html')));
app.get('/manual/whisper', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manual_whisper.html')));
app.get('/manual/yolo', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manual_detection.html')));
app.get('/download_manager', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manager_download.html')));

// 파일 목록 API (R2)
app.get('/files', async (req, res) => {
    try {
        const command = new ListObjectsV2Command({ Bucket: BUCKET_NAME });
        const response = await s3.send(command);

        const files = (response.Contents || []).map(obj => ({
            name: obj.Key,
            size: `${(obj.Size / 1024 / 1024).toFixed(1)} MB`,
            created: new Date(obj.LastModified.getTime() + 9 * 60 * 60 * 1000)
                .toISOString()
                .slice(0, 16)
                .replace('T', ' ')
        }));

        files.sort((a, b) => new Date(b.created) - new Date(a.created));
        res.json(files);
    } catch (err) {
        console.error('Failed to list R2 files:', err);
        res.status(500).json({ error: 'Failed to retrieve file list' });
    }
});

// 파일 다운로드 리디렉션
app.get('/download/:filename', (req, res) => {
    const R2_PUBLIC_URL = process.env.R2_PUBLIC_URL;
    const filename = req.params.filename;
    const fileUrl = `${R2_PUBLIC_URL}/${encodeURIComponent(filename)}`;
    res.redirect(fileUrl);
});

// 인증 미들웨어
function ensureAuthenticated(req, res, next) {
    const token = req.cookies.authToken;
    if (!token) return res.status(401).send('Access Denied: No token provided.');
    jwt.verify(token, SECRET_KEY, (err, decoded) => {
        if (err) return res.status(403).send('Access Denied: Invalid token.');
        req.user = decoded;
        next();
    });
}

// 서버 시작
http.createServer(app).listen(PORT, () => {
    console.log(`HTTP server running on port ${PORT}`);
});
