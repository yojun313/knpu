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
const MANAGER_BUCKET_NAME = process.env.MANAGER_BUCKET_NAME;
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
app.use(favicon(path.join(__dirname, 'public', 'assets', 'imgs', 'fpei_logo_favicon.ico')));
app.use(express.static('public'));
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(cookieParser());

// 정적 페이지 라우팅
app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'public', 'homepage.html')));
app.get('/people', (req, res) => res.sendFile(path.join(__dirname, 'public', 'people.html')));
app.get('/publications', (req, res) => res.sendFile(path.join(__dirname, 'public', 'publications.html')));
app.get('/news', (req, res) => res.sendFile(path.join(__dirname, 'public', 'news.html')));
app.get('/login', (req, res) => res.sendFile(path.join(__dirname, 'public', 'login.html')));
app.get('/signup', (req, res) => res.sendFile(path.join(__dirname, 'public', 'signup.html')));
app.get('/verify-email', (req, res) => res.sendFile(path.join(__dirname, 'public', 'verify-email.html')));
app.get('/account', ensureAuthenticated, (req, res) => res.sendFile(path.join(__dirname, 'public', 'account.html')));
app.get('/terms', (req, res) => res.sendFile(path.join(__dirname, 'public', 'terms.html')));
app.get('/gallery', (req, res) => res.sendFile(path.join(__dirname, 'public', 'gallery.html')));
app.get('/systems', (req, res) => res.sendFile(path.join(__dirname, 'public', 'systems.html')));
app.get('/about', (req, res) => res.sendFile(path.join(__dirname, 'public', 'about.html')));
app.get('/admission', (req, res) => res.sendFile(path.join(__dirname, 'public', 'admission.html')));

app.get('/manager', (req, res) => res.redirect(301, 'https://manager.knpu.re.kr'));
app.get('/manual/kemkim', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manuals', 'manual_kemkim.html')));
app.get('/manual/hate_analysis', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manuals', 'manual_hateanalysis.html')));
app.get('/manual/whisper', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manuals', 'manual_whisper.html')));
app.get('/manual/yolo', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manuals', 'manual_detection.html')));
app.get('/manual/network', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manuals', 'manual_network.html')));
app.get('/manager/download', (req, res) => res.sendFile(path.join(__dirname, 'public', 'manager_download.html')));

// 파일 목록 API (R2)
app.get('/files', async (req, res) => {
    try {
        const command = new ListObjectsV2Command({ Bucket: MANAGER_BUCKET_NAME });
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
    const R2_MANAGER_PUBLIC_URL = process.env.R2_MANAGER_PUBLIC_URL;
    const filename = req.params.filename;
    const fileUrl = `${R2_MANAGER_PUBLIC_URL}/${encodeURIComponent(filename)}`;
    res.redirect(fileUrl);
});

// 인증 미들웨어 — knpu.re.kr 중앙 로그인이 발급한 session 쿠키(JWT)를 검증한다
function ensureAuthenticated(req, res, next) {
    const token = req.cookies.session;
    if (!token) {
        return res.redirect('/login?redirect=' + encodeURIComponent(req.originalUrl));
    }
    jwt.verify(token, SECRET_KEY, (err, decoded) => {
        if (err) {
            return res.redirect('/login?redirect=' + encodeURIComponent(req.originalUrl));
        }
        req.user = decoded;
        next();
    });
}

// 서버 시작
http.createServer(app).listen(PORT, () => {
    console.log(`HTTP server running on port ${PORT}`);
});
