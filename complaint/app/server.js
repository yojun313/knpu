const path = require('path');
require('dotenv').config();
const express = require('express');
const session = require("express-session");
const bodyParser = require('body-parser');
const fs = require('fs');
const { URL } = require('url');
const http = require('http');
const https = require('https');

const app = express();
const port = 3003;

app.use(session({
  secret: 'complaint-secret',   // 실제 서비스에선 env로
  resave: false,
  saveUninitialized: true,
}));

const result_page_html = './public/result_page.html';

function postJson(url, data) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const lib = parsed.protocol === 'https:' ? https : http;
    const body = JSON.stringify(data);

    const options = {
      hostname: parsed.hostname,
      port: parsed.port,
      path: parsed.pathname + (parsed.search || ''),
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
      }
    };

    const req = lib.request(options, (res) => {
      let resp = '';
      res.on('data', (chunk) => resp += chunk);
      res.on('end', () => {
        let parsedResp = resp;
        try { parsedResp = JSON.parse(resp); } catch {}

        if (res.statusCode >= 400) {
          reject({
            status: res.statusCode,
            body: parsedResp
          });
        } else {
          resolve(parsedResp);
        }
      });
    });

    req.on('error', reject);
    req.write(body);
    req.end();
  });
}


app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());app.use(express.static(path.join(__dirname, 'public')));

app.get('/', (req, res) => {
  // HTML 파일을 렌더링합니다.
  res.sendFile(path.join(__dirname, 'public', 'first_page.html'));
});

app.get('/basic_info', (req, res) => {
  // HTML 파일을 렌더링합니다.
  res.sendFile(path.join(__dirname, 'public', 'forms', 'basic_info.html'));
});

// 첫 번째 페이지 작성 후 제출
app.post('/submit', (req, res) => {
  const first_formData = req.body;
  const redirect_page_name = first_formData['고소 죄명'];

  if (redirect_page_name) {
    req.session.first_formData = first_formData;
    req.session.redirect_page_name = redirect_page_name;
    res.redirect(`/forms/${redirect_page_name}.html`);
  } else {
    // redirect_page_name이 없는 경우 처리
    res.redirect("/error"); // 오류 페이지로 리디렉션, 또는 다른 처리
  }
});


// 결과창으로 이동(로딩창)
app.post('/loading', (req, res) => {
  if (Object.keys(req.body).length > 0) {
    req.session.second_formData = req.body;
  }
  res.sendFile(path.join(__dirname, 'public', 'loading.html'));
});

// 결과창으로 이동
app.get('/llm', async (req, res) => {

  const fastapiBase = process.env.SERVER_URL || 'http://localhost:8000/api';
  console.log("FastAPI Base URL:", fastapiBase);
  const second_formData = req.session.second_formData;
  const first_formData = req.session.first_formData;

  const combined_data = {
    first_formData,
    second_formData
  };
  try {
      const apiResp = await postJson(`${fastapiBase}/complaint/generate`, { combined_data });
      
      if (apiResp && typeof apiResp === 'object') {
        req.session.file_id = apiResp.file_id;
        req.session.preview_pdf = apiResp.preview_pdf;
        req.session.download_word = apiResp.download_word;
        req.session.download_pdf = apiResp.download_pdf;
        req.session.model_name = apiResp.model_name;
        req.session.model_url = apiResp.model_url;
      }        
    } catch (err) {
      console.error("AI 고소장 생성 실패:", err);

      return res.sendFile(
        path.join(__dirname, 'public', 'llm_failed.html')
      );
    }

  fs.readFile(result_page_html, 'utf8', (err, html) => {
    if (err) {
      console.error(err);
      return;
    }
    // HTML 수정
    const word_url = `${fastapiBase}${req.session.download_word}`;
    const pdf_url  = `${fastapiBase}${req.session.download_pdf}`;
    const preview  = `${fastapiBase}${req.session.preview_pdf}`;

    const modelName = req.session.model_name
    const modelUrl = req.session.model_url 

    let modifiedHtml = html
      .replace('pdf_url', preview)
      .replace('word_download_url', word_url)
      .replace('pdf_download_url', pdf_url)
      .replace('MODEL_NAME', modelName)
      .replace('MODEL_URL', modelUrl);

    res.send(modifiedHtml);
  });
});

const server = app.listen(port, '0.0.0.0', () => {
  console.log(`Server is running at http://localhost:${port}`);
});

server.timeout = 0;
server.keepAliveTimeout = 0;
server.headersTimeout = 0;