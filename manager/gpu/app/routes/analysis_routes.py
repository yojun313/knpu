from fastapi import APIRouter, UploadFile, File, Form, Body
from fastapi.responses import StreamingResponse, JSONResponse
from app.services.analysis_service import (
    measure_hate,
    transcribe_audio,
    get_yolo_model_list,
    yolo_detect_videos,
    yolo_detect_images,
    grounding_dino_detect_images,
    grounding_dino_detect_videos,
    generate_embeddings,
)
from app.libs.progress import send_message
from app.libs.exceptions import BadRequestException
import pandas as pd
import json
import io
import os
from dotenv import load_dotenv
from app.models.analysis_model import HateOption
import tempfile
from urllib.parse import quote
from itertools import combinations
from collections import Counter
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx
import zipfile
import platform
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from multiprocessing import Pool, cpu_count
from typing import List
from app.services.network_service import run_network_analysis
from io import StringIO


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
    option_dict = json.loads(option)
    hate_option = HateOption(
        pid=option_dict["pid"],
        option_num=option_dict["option_num"],
    )
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


@router.post("/whisper")
async def whisper_route(option: str = Form("{}"), file: UploadFile = File(...)):
    option_dict = json.loads(option)

    language = option_dict.get("language", "ko")
    model_level = int(option_dict.get("model", 2))
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


@router.get("/yolo/models")
async def get_yolo_models():
    """
    현재 서버에서 사용 가능한 YOLO 모델 리스트를 반환합니다.
    """
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
    try:
        option_dict = json.loads(option)
    except json.JSONDecodeError:
        return BadRequestException("option JSON 파싱 실패")

    pid = option_dict.get("pid")
    media = option_dict.get("media", "image")

    # [추가] 모델명 추출 (기본값: yolo11n)
    model_name = option_dict.get("model", "yolo11n")

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

    else:
        return BadRequestException(
            detail=f"지원하지 않는 media 타입: {media}",
        )

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
    option_dict = json.loads(option)
    pid = option_dict.get("pid")
    media = option_dict.get("media", "image")

    box_threshold = float(option_dict.get("box_threshold", 0.4))

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
    try:
        option_dict = json.loads(option)
        batch_size = int(option_dict.get("batch_size", 12))

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
    try:
        option_dict = json.loads(option)
    except json.JSONDecodeError:
        return BadRequestException("option JSON 파싱 실패")

    pid = option_dict.get("pid")
    text_col = option_dict.get("text_col", "Text")
    batch_size = int(option_dict.get("batch_size", 12))

    content = await file.read()
    try:
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except:
        df = pd.read_csv(io.StringIO(content.decode("cp949")))

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


@router.post("/graph-network")
async def graph_network(option: str = Form(...), file: UploadFile = File(...)):
    option = json.loads(option)
    content = await file.read()
    df = pd.read_csv(StringIO(content.decode("utf-8")))
    return run_network_analysis(option.get("pid", "network"), df, option)
