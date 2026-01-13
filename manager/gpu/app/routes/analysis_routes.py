from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from app.services.analysis_service import *
import pandas as pd
import json
import io
import os
from dotenv import load_dotenv
from app.models.analysis_model import HateOption
import tempfile
from urllib.parse import quote  
from ultralytics import YOLO
from app.libs.exceptions import BadRequestException

router = APIRouter()

load_dotenv()

@router.post("/hate")
async def hate_measure_route(
    option: str = Form(...),
    file: UploadFile = File(...),
):
    # 옵션 파싱 → HateOption + 부가 파라미터(text_col 등)
    option_dict  = json.loads(option)
    hate_option  = HateOption(
        pid        = option_dict["pid"],
        option_num = option_dict["option_num"],
    )
    text_col     = option_dict.get("text_col", "Text")           

    # CSV → DataFrame
    content  = await file.read()
    df       = pd.read_csv(io.StringIO(content.decode("utf-8")))

    # 혐오도 분석
    result_df = measure_hate(
        option         = hate_option,
        data           = df,
        text_col       = text_col,
        update_interval= 1000,     
    )

    # DataFrame → CSV Bytes
    buffer = io.BytesIO()
    result_df.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)

    # 스트리밍 응답
    filename   = f"hate_result_opt{hate_option.option_num}.csv"
    media_type = "text/csv"
    cd_header  = f"attachment; filename*=UTF-8''{quote(filename)}"

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": cd_header},
    )
    
@router.post("/whisper")
async def whisper_route(
    option: str = Form("{}"),
    file: UploadFile = File(...)
):
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
            pid = pid,
        )
        return JSONResponse(result)
    finally:
        os.remove(audio_path)

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
    media = option_dict.get("media", "image")  # image | video

    if media == "video":
        zip_buffer = await yolo_detect_videos_to_zip(
            files=files,
            conf_thres=float(conf_thres),
            pid=pid,
        )
        out_name = "yolo_video_results.zip"

    elif media == "image":
        zip_buffer = await yolo_detect_images_to_zip(
            files=files,
            conf_thres=float(conf_thres),
            pid=pid,
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
    file: UploadFile = File(...),
    prompt: str = Form(...),
    option: str = Form("{}"),
):
    """
    Grounding DINO
    - image + prompt → bounding box 그린 이미지 반환
    """

    try:
        option_dict = json.loads(option)
    except json.JSONDecodeError:
        option_dict = {}

    pid = option_dict.get("pid")
    box_threshold = float(option_dict.get("box_threshold", 0.4))
    text_threshold = float(option_dict.get("text_threshold", 0.3))

    # analysis_service 쪽 함수 호출
    img_buffer = await grounding_dino_detect_image(
        file=file,
        prompt=prompt,
        box_threshold=box_threshold,
        text_threshold=text_threshold,
        pid=pid,
    )

    filename = "grounding_dino_result.png"
    cd_header = f"inline; filename*=UTF-8''{quote(filename)}"

    return StreamingResponse(
        img_buffer,
        media_type="image/png",
        headers={"Content-Disposition": cd_header},
    )
