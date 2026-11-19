from fastapi import APIRouter, UploadFile, File, Form, Body
from fastapi.responses import StreamingResponse, JSONResponse
from app.services.analysis_service import (
    measure_hate,
    transcribe_audio,
    transcribe_audio_stream,
    cancel_whisper_job,
    get_yolo_model_list,
    yolo_detect_videos,
    yolo_detect_images,
    grounding_dino_detect_images,
    grounding_dino_detect_videos,
    generate_embeddings,
)
from app.libs.progress import send_message
from app.libs.exceptions import BadRequestException
from app.services.analysis_service import (
    WHISPER_MODEL_MAP,
    EMBED_BATCH_MIN,
    EMBED_BATCH_MAX,
    resolve_yolo_model_name,
)
import pandas as pd
import json
import io
import os
from dotenv import load_dotenv
from app.models.analysis_model import HateOption
import tempfile
from urllib.parse import quote
import platform
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from typing import List


if platform.system() == "Linux":
    font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
    fm.fontManager.addfont(font_path)
    plt.rcParams["font.family"] = "NanumGothic"
    plt.rcParams["axes.unicode_minus"] = False

router = APIRouter()

load_dotenv()


@router.post("/hate")
async def hate_measure_route(
    option: str = Form(...),
    file: UploadFile = File(...),
):
    # 옵션 파싱 → HateOption + 부가 파라미터(text_col 등)
    option_dict = _parse_option(option)
    try:
        hate_option = HateOption(
            pid=option_dict["pid"],
            option_num=option_dict["option_num"],
        )
    except (KeyError, ValueError) as e:
        raise BadRequestException(f"hate 옵션이 올바르지 않습니다: {e}")
    text_col = option_dict.get("text_col", "Text")

    # CSV → DataFrame
    content = await file.read()
    df = pd.read_csv(io.StringIO(content.decode("utf-8")))

    # 혐오도 분석
    result_df = measure_hate(
        option=hate_option,
        data=df,
        text_col=text_col,
        update_interval=1000,
    )

    # DataFrame → CSV Bytes
    buffer = io.BytesIO()
    result_df.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)

    # 스트리밍 응답
    filename = f"hate_result_opt{hate_option.option_num}.csv"
    media_type = "text/csv"
    cd_header = f"attachment; filename*=UTF-8''{quote(filename)}"

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": cd_header},
    )


def _parse_option(option: str) -> dict:
    """option JSON 을 dict 로. 잘못된 JSON 은 400(예전엔 일부 경로가 예외 객체를 반환만 했다)."""
    try:
        value = json.loads(option or "{}")
    except (TypeError, ValueError):
        raise BadRequestException("option JSON 파싱 실패")
    if not isinstance(value, dict):
        raise BadRequestException("option 은 JSON 객체여야 합니다")
    return value


def _whisper_level(option_dict: dict) -> int:
    try:
        level = int(option_dict.get("model", 2))
    except (TypeError, ValueError):
        raise BadRequestException("model 단계는 정수여야 합니다")
    if level not in WHISPER_MODEL_MAP:
        raise BadRequestException(
            f"지원하지 않는 model 단계입니다: {level} (허용: {sorted(WHISPER_MODEL_MAP)})"
        )
    return level


def _batch_size(option_dict: dict) -> int:
    try:
        size = int(option_dict.get("batch_size", 12))
    except (TypeError, ValueError):
        raise BadRequestException("batch_size는 정수여야 합니다")
    if not (EMBED_BATCH_MIN <= size <= EMBED_BATCH_MAX):
        raise BadRequestException(
            f"batch_size는 {EMBED_BATCH_MIN}~{EMBED_BATCH_MAX} 사이여야 합니다"
        )
    return size


@router.post("/whisper")
async def whisper_route(option: str = Form("{}"), file: UploadFile = File(...)):
    option_dict = _parse_option(option)

    language = option_dict.get("language", "ko")
    model_level = _whisper_level(option_dict)
    pid = option_dict.get("pid", None)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await file.read())
        audio_path = tmp.name

    try:
        result = transcribe_audio(
            audio_path=audio_path,
            language=language,
            model_level=model_level,
            pid=pid,
        )
        return JSONResponse(result)
    finally:
        os.remove(audio_path)


@router.post("/whisper/stream")
def whisper_stream_route(option: str = Form("{}"), file: UploadFile = File(...)):
    """whisper 웹사이트용 실시간 전사. 진행 이벤트를 NDJSON 한 줄씩 스트리밍한다:
    {"type":"status",...} → {"type":"info","duration":..} → {"type":"segment",..}* → {"type":"done"}
    (동기 라우트 + 동기 제너레이터라서 FastAPI가 threadpool에서 돌린다)

    option.language: 생략 / null / "auto" 이면 언어 자동 감지(기본값), 그 외는 ISO-639-1 코드(ko/en/ja/...)로 고정."""
    option_dict = _parse_option(option)
    language = option_dict.get("language")
    if not language or str(language).strip().lower() == "auto":
        language = None  # None = faster-whisper 자동 감지
    model_level = _whisper_level(option_dict)
    job_id = option_dict.get("job_id")  # 있으면 /whisper/cancel/{job_id}로 중단 가능

    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        audio_path = tmp.name

    def event_stream():
        try:
            for event in transcribe_audio_stream(
                audio_path=audio_path,
                language=language,
                model_level=model_level,
                job_id=job_id,
            ):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as e:
            yield (
                json.dumps(
                    {"type": "error", "message": f"{type(e).__name__}: {e}"},
                    ensure_ascii=False,
                )
                + "\n"
            )
        finally:
            try:
                os.remove(audio_path)
            except OSError:
                pass

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.get("/gpu/stats")
def gpu_stats_route():
    """nvidia-smi 기반 실시간 GPU 사용량. whisper 웹사이트들의 모니터 위젯이 폴링한다."""
    import subprocess

    fields = [
        "index",
        "name",
        "utilization.gpu",
        "utilization.memory",
        "memory.total",
        "memory.used",
        "memory.free",
        "temperature.gpu",
        "power.draw",
        "power.limit",
        "fan.speed",
        "clocks.sm",
        "pstate",
    ]
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                f"--query-gpu={','.join(fields)}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip() or "nvidia-smi failed")
    except Exception as e:
        return JSONResponse(status_code=503, content={"error": str(e), "gpus": []})

    def num(v):
        v = v.strip()
        if not v or v.startswith("[") or v.lower() in ("n/a", "na"):
            return None
        try:
            return float(v) if "." in v else int(v)
        except ValueError:
            return v

    gpus = []
    for line in out.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(", ")]
        if len(parts) < len(fields):
            continue
        gpus.append(
            {
                "index": num(parts[0]),
                "name": parts[1],
                "util": num(parts[2]),  # GPU 사용률 %
                "mem_util": num(parts[3]),  # 메모리 컨트롤러 사용률 %
                "mem_total": num(parts[4]),  # MiB
                "mem_used": num(parts[5]),  # MiB
                "mem_free": num(parts[6]),  # MiB
                "temp": num(parts[7]),  # °C
                "power": num(parts[8]),  # W
                "power_limit": num(parts[9]),  # W
                "fan": num(parts[10]),  # %
                "clock_sm": num(parts[11]),  # MHz
                "pstate": parts[12],
            }
        )
    return JSONResponse({"gpus": gpus})


@router.post("/whisper/cancel/{job_id}")
def whisper_cancel_route(job_id: str):
    """진행 중인 스트림 전사를 중단한다. 세그먼트 루프가 다음 반복에서 빠져나가며
    faster-whisper 디코딩(GPU 연산)이 즉시 멈춘다. 해당 job이 없으면 cancelled=false."""
    cancelled = cancel_whisper_job(job_id)
    return JSONResponse({"cancelled": cancelled, "job_id": job_id})


@router.get("/yolo/models")
async def get_yolo_models():
    try:
        models = get_yolo_model_list()
        return JSONResponse(content={"models": models})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"모델 리스트를 가져오는 중 오류 발생: {str(e)}"},
        )


@router.post("/yolo")
async def yolo_detect_route(
    files: List[UploadFile] = File(...),
    option: str = Form("{}"),
    conf_thres: float = Form(0.25),
):
    option_dict = _parse_option(option)

    pid = option_dict.get("pid")
    media = option_dict.get("media", "image")
    if media not in ("image", "video"):
        raise BadRequestException(f"지원하지 않는 media 타입: {media}")

    # 모델명은 허용 목록(모델 폴더의 .pt + 공식 기본 모델)으로만 — 경로 문자 거절
    try:
        model_name = resolve_yolo_model_name(option_dict.get("model", "yolo11n"))
    except ValueError as e:
        raise BadRequestException(str(e))

    if media == "video":
        zip_buffer = await yolo_detect_videos(
            files=files,
            conf_thres=float(conf_thres),
            pid=pid,
            model_name=model_name,  # [추가] 인자 전달
        )
        out_name = "yolo_video_results.zip"

    elif media == "image":
        zip_buffer = await yolo_detect_images(
            files=files,
            conf_thres=float(conf_thres),
            pid=pid,
            model_name=model_name,  # [추가] 인자 전달
        )
        out_name = "yolo_image_results.zip"

    else:  # 위에서 걸렀으므로 오지 않는다
        raise BadRequestException(f"지원하지 않는 media 타입: {media}")

    cd_header = f"attachment; filename*=UTF-8''{quote(out_name)}"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": cd_header},
    )


@router.post("/dino")
async def grounding_dino_route(
    files: List[UploadFile] = File(...),
    prompt: str = Form(...),
    option: str = Form("{}"),
):
    option_dict = _parse_option(option)
    pid = option_dict.get("pid")
    media = option_dict.get("media", "image")

    try:
        box_threshold = float(option_dict.get("box_threshold", 0.4))
    except (TypeError, ValueError):
        raise BadRequestException("box_threshold는 숫자여야 합니다")
    if not (0.0 <= box_threshold <= 1.0):
        raise BadRequestException("box_threshold는 0~1 사이여야 합니다")

    if media == "image":
        zip_buffer = await grounding_dino_detect_images(
            files=files,
            prompt=prompt,
            box_threshold=box_threshold,
            pid=pid,
        )
        filename = "grounding_dino_images.zip"

    elif media == "video":
        zip_buffer = await grounding_dino_detect_videos(
            files=files,
            prompt=prompt,
            box_threshold=box_threshold,
            pid=pid,
        )
        filename = "grounding_dino_videos.zip"

    else:
        raise BadRequestException(f"지원하지 않는 media 타입: {media}")

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.post("/embed")
async def embed_text_route(
    sentences: List[str] = Body(..., description="임베딩할 문장 리스트"),
    option: str = Form("{}"),
):
    option_dict = _parse_option(option)
    batch_size = _batch_size(option_dict)
    try:
        embeddings = generate_embeddings(sentences, batch_size=batch_size)

        return JSONResponse(
            content={
                "model": "BAAI/bge-m3",
                "dim": len(embeddings[0]) if embeddings else 0,
                "count": len(embeddings),
                "embeddings": embeddings,
            }
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})


@router.post("/embed/csv")
async def embed_csv_route(file: UploadFile = File(...), option: str = Form("{}")):
    option_dict = _parse_option(option)

    pid = option_dict.get("pid")
    text_col = option_dict.get("text_col", "Text")
    batch_size = _batch_size(option_dict)

    content = await file.read()
    df = None
    for enc in ("utf-8-sig", "cp949"):
        try:
            df = pd.read_csv(io.StringIO(content.decode(enc)))
            break
        except UnicodeDecodeError:
            continue
        except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
            raise BadRequestException(f"CSV 파일을 읽지 못했습니다: {e}")
    if df is None:
        raise BadRequestException(
            "CSV 인코딩을 읽지 못했습니다(UTF-8 또는 CP949만 지원)"
        )

    if text_col not in df.columns:
        for c in df.columns:
            if "text" in c.lower():
                text_col = c
                break
        else:
            raise BadRequestException(f"Column '{text_col}' not found in CSV")

    if pid:
        send_message(pid, f"[임베딩] '{text_col}' 열 데이터 추출 중...")

    sentences = df[text_col].fillna("").astype(str).tolist()

    if pid:
        send_message(
            pid, f"[임베딩] BGE-M3 모델로 {len(sentences):,}개 문장 벡터화 시작"
        )

    embeddings = generate_embeddings(sentences, batch_size=batch_size)

    df["embedding"] = [json.dumps(e) for e in embeddings]

    if pid:
        send_message(pid, "[임베딩] 분석 완료 및 결과 생성 중")

    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)

    filename = f"embed_result_{pid if pid else 'data'}.csv"
    cd_header = f"attachment; filename*=UTF-8''{quote(filename)}"

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": cd_header},
    )
