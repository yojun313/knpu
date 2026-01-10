from app.models.analysis_model import *
from app.libs.kemkim import KimKem
from app.libs.progress import *
import os
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import shutil
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask
from kiwipiepy import Kiwi
import time
import pandas as pd
import re
from kiwipiepy import Kiwi
from transformers import (
    logging
)
logging.set_verbosity_error()
import os
from app.utils.zip import fast_zip
from typing import Literal
import asyncio
from yt_dlp import YoutubeDL
from datetime import datetime
import httpx
import json
from urllib.parse import urlparse, parse_qs, urlunparse

GPU_SERVER_URL = os.getenv("GPU_SERVER_URL")

kiwi_instance = None

def get_kiwi():
    global kiwi_instance
    if kiwi_instance is None:
        kiwi_instance = Kiwi(num_workers=-1)
    return kiwi_instance

def start_kemkim(option: KemKimOption, token_data):

    def cleanup_folder_and_zip(folder_path: str, zip_path: str):
        shutil.rmtree(folder_path, ignore_errors=True)
        try:
            os.remove(zip_path)
        except OSError:
            pass

    option = option.model_dump()
    save_path = os.path.join(os.path.dirname(__file__), '..', 'temp')

    kemkim_obj = KimKem(
        pid=option["pid"],
        token_data=token_data,
        csv_name=option["tokenfile_name"],
        save_path=save_path,
        startdate=option["startdate"],
        enddate=option["enddate"],
        period=option["period"],
        topword=option["topword"],
        weight=option["weight"],
        graph_wordcnt=option["graph_wordcnt"],
        split_option=option["split_option"],
        split_custom=option["split_custom"],
        filter_option=option["filter_option"],
        trace_standard=option["trace_standard"],
        ani_option=option["ani_option"],
        exception_word_list=option["exception_word_list"],
        exception_filename=option["exception_filename"],
        modify_kemkim=False
    )
    try:
        result_path = kemkim_obj.make_kimkem()
        
        if type(result_path) == str:
            zip_path = f"{result_path}.zip"
            fast_zip(result_path, zip_path)   
            filename = os.path.basename(zip_path)

            background_task = BackgroundTask(
                cleanup_folder_and_zip, result_path, zip_path)

            # 4) FileResponse에 filename= 으로 넘기기
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename=filename,
                background=background_task,
            )
        elif result_path == 2:
            # 예외 상황 메시지 응답
            return JSONResponse(
                status_code=400,
                content={"error": "KEMKIM 분석 중 오류 발생",
                         "message": "시간 가중치 오류가 발생했습니다"}
            )
        elif result_path == 3:
            # 예외 상황 메시지 응답
            return JSONResponse(
                status_code=400,
                content={"error": "KEMKIM 분석 중 오류 발생",
                         "message": "키워드가 없어 분석이 종료되었습니다"}
            )

    except Exception as e:
        # 예외 상황 메시지 응답
        return JSONResponse(
            status_code=500,
            content={"error": "KEMKIM 분석 중 오류 발생", "message": str(e)}
        )

def tokenization(
    pid: str,
    data: pd.DataFrame,
    columns,
    include_words: list = None,
    update_interval: int = 3000,
) -> pd.DataFrame:
    """
    ▸ pid            : 진행 상황을 send_message(pid, …)로 전달할 때 사용
    ▸ data           : 원본 DataFrame (in-place 수정)
    ▸ columns        : 토큰화할 열 이름 또는 이름 리스트
    ▸ update_interval: 이 개수마다 진행률 메시지 전송
    """
    # Kiwi 한 번만 초기화
    kiwi = get_kiwi()
    for word in include_words:
        kiwi.add_user_word(word, 'NNP', score=10)

    # 단일 str → list
    if isinstance(columns, str):
        columns = [columns]

    # 각 열을 순회
    for col in columns:
        if col not in data.columns:
            send_message(pid, f"⚠️  열 '{col}'이(가) 존재하지 않습니다 → 건너뜀")
            continue

        texts        = data[col].tolist()
        total        = len(texts)
        tokenized_col = []

        send_message(pid, f"[{col}] 토큰화 시작 (총 {total:,} rows)")

        total_time = 0.0
        for idx, text in enumerate(texts, 1):
            start = time.time()

            if isinstance(text, str):
                # 전처리
                cleaned = re.sub(r"[^가-힣a-zA-Z\s]", "", text)
                # splitComplex=False → 복합어를 분해하지 않고 처리
                tokens   = kiwi.tokenize(cleaned, split_complex=False)
                nouns    = [t.form for t in tokens if t.tag in ("NNG", "NNP")]
                tokenized_col.append(", ".join(nouns))
            else:
                tokenized_col.append("")

            # 진행률 계산
            total_time += time.time() - start
            if idx % update_interval == 0 or idx == total:
                pct   = round(idx / total * 100, 2)
                avg   = total_time / idx
                remain_sec = avg * (total - idx)
                m, s  = divmod(int(remain_sec), 60)
                send_message(
                    pid,
                    f"[{col}] 진행률 {pct}% ({idx:,}/{total:,}) • 예상 남은 시간 {m}분 {s}초"
                )

        # 열 덮어쓰기
        data[col] = tokenized_col
        send_message(pid, f"[{col}] 토큰화 완료")

    return data

async def start_youtube_download(option: dict):
    """
    option 예시:
    {
      "pid": "xxx",
      "urls": ["https://youtu.be/...", "https://www.youtube.com/watch?v=..."],
      "format": "mp3",          # "mp3" | "mp4"
      "save_whisper": true,     # true면 whisper 결과(txt)도 저장
      "quality": "1080p"        # 선택사항
    }
    """

    pid: str = option["pid"]
    raw_urls = option.get("urls", [])
    fmt: Literal["mp3", "mp4"] = option.get("format", "mp3")
    save_whisper: bool = bool(option.get("save_whisper", False))
    quality: str = option.get("quality", "최고 화질 (자동)")

    urls = []
    for url in raw_urls:
        parsed_url = urlparse(url)
        if "youtube.com" in parsed_url.netloc:
            query_params = parse_qs(parsed_url.query)
            video_id = query_params.get("v")
            if video_id:
                new_query = f"v={video_id[0]}"
                clean_url = urlunparse(parsed_url._replace(query=new_query, fragment=""))
                urls.append(clean_url)
            else:
                urls.append(url)
        elif "youtu.be" in parsed_url.netloc:
            clean_url = urlunparse(parsed_url._replace(query="", fragment=""))
            urls.append(clean_url)
        else:
            urls.append(url)

    if not urls:
        return JSONResponse(status_code=400, content={"error": "urls가 비어있습니다"})
    
    if not urls:
        return JSONResponse(status_code=400, content={"error": "urls가 비어있습니다"})

    # ───────────────────────
    # 출력 디렉토리 준비
    # ───────────────────────
    base_temp = os.path.join(os.path.dirname(__file__), "..", "temp")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(base_temp, f"youtube_{pid}_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    outtmpl = os.path.join(out_dir, "%(title).200s [%(id)s].%(ext)s")

    # ───────────────────────
    # 유틸 함수들
    # ───────────────────────
    def cleanup_folder_and_zip(folder_path: str, zip_path: str):
        shutil.rmtree(folder_path, ignore_errors=True)
        try:
            os.remove(zip_path)
        except OSError:
            pass

    def _format_by_quality(q: str) -> str:
        return {
            "최고 화질 (자동)": "bv*+ba/best",
            "1080p": "bv*[height<=1080]+ba/best",
            "720p": "bv*[height<=720]+ba/best",
            "480p": "bv*[height<=480]+ba/best",
            "360p": "bv*[height<=360]+ba/best",
        }.get(q, "bv*+ba/best")

    def _ytdlp_opts(format_: str, q: str) -> dict:
        opts = {
            "outtmpl": outtmpl,
            "quiet": False,  # 에러 디버깅을 위해 잠시 False로 권장
            "no_warnings": False,
            # 최신 유튜브 차단 정책 우회를 위한 인자 추가
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                    "skip": ["dash", "hls"]
                }
            },
            "nocheckcertificate": True,
        }

        if format_ == "mp3":
            opts.update({
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            })
        else:
            opts.update({
                "format": _format_by_quality(q),
                "merge_output_format": "mp4",
            })
        
        return opts

    def _download_one(url: str, format_: str, q: str) -> str:
        with YoutubeDL(_ytdlp_opts(format_, q)) as ydl:
            info = ydl.extract_info(url, download=True)
            base_path = ydl.prepare_filename(info)
            root, _ = os.path.splitext(base_path)

            if format_ == "mp3":
                mp3_path = root + ".mp3"
                return mp3_path if os.path.exists(mp3_path) else base_path

            mp4_path = root + ".mp4"
            return mp4_path if os.path.exists(mp4_path) else base_path

    def _fallback_pick_latest_file() -> str | None:
        files = [
            os.path.join(out_dir, p)
            for p in os.listdir(out_dir)
            if os.path.isfile(os.path.join(out_dir, p))
        ]
        if not files:
            return None
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return files[0]

    async def _whisper_to_txt(media_path: str) -> str:
        filename = os.path.basename(media_path)
        txt_path = os.path.join(out_dir, os.path.splitext(filename)[0] + ".txt")

        async with httpx.AsyncClient(timeout=None) as client:
            with open(media_path, "rb") as f:
                files = {"file": (filename, f, "application/octet-stream")}
                data = {"option": "{}"}
                resp = await client.post(
                    f"{GPU_SERVER_URL}/analysis/whisper",
                    data=data,
                    files=files,
                )
                resp.raise_for_status()
                content = await resp.aread()

        ctype = resp.headers.get("content-type", "")
        try:
            if "application/json" in ctype:
                obj = json.loads(content.decode("utf-8", errors="ignore"))
                with open(txt_path, "w", encoding="utf-8") as wf:
                    wf.write(obj['text_with_time'])
            else:
                with open(txt_path, "wb") as wf:
                    wf.write(content)
        except Exception:
            with open(txt_path, "wb") as wf:
                wf.write(content)

        return txt_path

    # ───────────────────────
    # 메인 로직
    # ───────────────────────
    try:
        send_message(
            pid,
            f"유튜브 다운로드 시작 (총 {len(urls)}개, format={fmt}, quality={quality}, whisper={save_whisper})"
        )

        for i, url in enumerate(urls, 1):
            send_message(pid, f"[{i}/{len(urls)}] 다운로드 중: {url}")

            media_path = await asyncio.to_thread(
                _download_one, url, fmt, quality
            )

            if not os.path.exists(media_path):
                picked = _fallback_pick_latest_file()
                if picked:
                    media_path = picked

            send_message(
                pid,
                f"[{i}/{len(urls)}] 다운로드 완료: {os.path.basename(media_path)}"
            )

            if save_whisper:
                send_message(
                    pid,
                    f"[{i}/{len(urls)}] whisper 변환 중: {os.path.basename(media_path)}"
                )
                try:
                    await _whisper_to_txt(media_path)
                    send_message(pid, f"[{i}/{len(urls)}] whisper 저장 완료")
                except Exception as e:
                    send_message(pid, f"[{i}/{len(urls)}] whisper 실패: {str(e)}")

        zip_path = out_dir + ".zip"
        fast_zip(out_dir, zip_path)

        background_task = BackgroundTask(
            cleanup_folder_and_zip, out_dir, zip_path
        )

        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=os.path.basename(zip_path),
            background=background_task,
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "유튜브 다운로드 중 오류",
                "message": str(e),
            },
        )
 
