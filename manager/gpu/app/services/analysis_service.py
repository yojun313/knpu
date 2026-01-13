import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
from app.models.analysis_model import *
from app.libs.progress import *
import pandas as pd
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TextClassificationPipeline,
    logging
)
logging.set_verbosity_error()
from faster_whisper import WhisperModel
from dotenv import load_dotenv
import gc
from ultralytics import YOLO
import io
import zipfile
import cv2
from typing import List, Dict, Any
import json
from fastapi import UploadFile
import tempfile
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
from PIL import Image, ImageDraw

load_dotenv() 
MODEL_DIR = os.getenv("MODEL_PATH")


# ---- Hate Analysis ----
kor_unsmile_pipe = None

def unload_hate_model():
    global kor_unsmile_pipe
    kor_unsmile_pipe = None
    torch.cuda.empty_cache()
    gc.collect()

def measure_hate(
    option: HateOption,
    data: pd.DataFrame,
    text_col: str | None = "Text",
    update_interval: int = 1_000,
    batch_size: int = 64,
) -> pd.DataFrame:
    """
    option.option_num
      1 → clean 제외 레이블 중 최대값 → Hate 열
      2 → 10개 레이블 모두         → 레이블명별 열
      3 → clean 확률               → Clean 열
    """

    def batch_scores(texts: list[str]) -> list[dict[str, float]]:
        """문장 리스트 → [{label: prob}, ...] (둘째 자리 반올림)"""
        pipe = get_hate_model()
        outs = pipe(
            texts,
            truncation=True,
            batch_size=batch_size,
        )
        return [
            {o["label"]: round(o["score"], 2) for o in each}
            for each in outs
        ]


    pid, mode = option.pid, option.option_num

    # 대상 열 탐색 
    if text_col not in data.columns:
        for c in data.columns:
            if "text" in c.lower():
                text_col = c
                send_message(pid, f"🔍 '{text_col}' 열 자동 선택")
                break
        else:
            raise ValueError("'Text'라는 글자를 포함한 열을 찾을 수 없습니다")

    texts = data[text_col].fillna("").astype(str).tolist()
    total = len(texts)
    pipe = get_hate_model()
    labels = list(pipe.model.config.id2label.values())
    
    send_message(pid, f"[혐오도 분석] '{text_col}' 처리 시작 (총 {total:,} rows)")

    # 결과 버퍼 
    if mode == 1:
        results = [0.0] * total
    elif mode == 2:
        # dict 대신 numpy array를 쓰는 것도 성능 향상에 좋음
        results = {lbl: [0.0] * total for lbl in labels}
    elif mode == 3:
        results = [0.0] * total
    else:
        raise ValueError("option_num must be 1, 2, 또는 3 이어야 합니다")

    # 미리 비어있지 않은 인덱스 필터링 
    non_empty_indices = [i for i, t in enumerate(texts) if t.strip()]
    non_empty_texts = [texts[i].strip() for i in non_empty_indices]
    total_non_empty = len(non_empty_indices)

    # 배치 추론 
    for batch_start in range(0, total_non_empty, batch_size):
        batch_end = min(batch_start + batch_size, total_non_empty)
        batch_idx = non_empty_indices[batch_start:batch_end]
        batch_txt = non_empty_texts[batch_start:batch_end]

        # 모델 한 번 호출
        scored = batch_scores(batch_txt)

        # 결과 채우기
        if mode == 1:
            for idx, sc in zip(batch_idx, scored):
                results[idx] = max(v for k, v in sc.items() if k != "clean")
        elif mode == 2:
            for idx, sc in zip(batch_idx, scored):
                for lbl in labels:
                    results[lbl][idx] = sc.get(lbl, 0.0)
        else:  # mode == 3
            for idx, sc in zip(batch_idx, scored):
                results[idx] = sc.get("clean", 0.0)

        if (batch_end % update_interval == 0) or (batch_end == total_non_empty):
            pct = round(batch_end / total_non_empty * 100, 2)
            send_message(pid, f"[혐오도 분석] {pct}% 완료 ({batch_end:,}/{total_non_empty:,})")

    # 결과 열 붙이기
    if mode == 1:
        data["Hate"] = results
    elif mode == 2:
        for lbl, vals in results.items():
            data[lbl] = vals
    else:
        data["Clean"] = results

    send_message(pid, "[혐오도 분석] 완료")
    unload_hate_model()
    return data


# ---- Whisper ----
_whisper_models = {}

WHISPER_MODEL_MAP = {
    1: {
        "name": "faster-whisper-small",
        "compute": "int8_float16",
    },
    2: {
        "name": "faster-whisper-medium",
        "compute": "int8_float16",
    },
    3: {
        "name": "faster-whisper-large-v3",
        "compute": "float16",
    },
}

whisper_model = WhisperModel(
    os.path.join(MODEL_DIR, "faster-whisper-large-v3"),
    device="cuda",
    compute_type="float16",
    local_files_only=True,
)

def get_hate_model():
    global kor_unsmile_pipe
    
    if kor_unsmile_pipe is None:
        tokenizer = AutoTokenizer.from_pretrained(os.path.join(MODEL_DIR, "kor_unsmile"), local_files_only=True)
        kor_unsmile_model = AutoModelForSequenceClassification.from_pretrained(os.path.join(MODEL_DIR, "kor_unsmile"), local_files_only=True)
        kor_unsmile_pipe = TextClassificationPipeline(
            model=kor_unsmile_model,
            tokenizer=tokenizer,
            function_to_apply="sigmoid",
            top_k=None,
            device=1 if torch.cuda.is_available() else -1,
        )

    return kor_unsmile_pipe

def get_whisper_model(level: int):
    if level not in WHISPER_MODEL_MAP:
        level = 2  # 기본값 medium

    cfg = WHISPER_MODEL_MAP[level]

    key = f"{cfg['name']}::{cfg['compute']}"

    if key not in _whisper_models:
        _whisper_models[key] = WhisperModel(
            os.path.join(MODEL_DIR, cfg["name"]),
            device="cuda",
            compute_type=cfg["compute"],
            local_files_only=True,
        )

    return _whisper_models[key]

def get_yolo_model():
    global _yolo_model, _yolo_names

    if _yolo_model is None:
        _yolo_model = YOLO(os.path.join(MODEL_DIR, "yolo11n.pt"), verbose=False)
        _yolo_names = _yolo_model.names

    return _yolo_model, _yolo_names


# ---- YOLO ----
_yolo_model = None
_yolo_names = None

def transcribe_audio(
    audio_path: str,
    language: str = "ko",
    model_level: int = 2,
    pid = None,
):
    def format_paragraphs(segments, max_len=120):
        paragraphs = []
        buf = ""

        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue

            if len(buf) + len(text) <= max_len:
                buf += " " + text
            else:
                paragraphs.append(buf.strip())
                buf = text

        if buf:
            paragraphs.append(buf.strip())

        return "\n\n".join(paragraphs)

    def format_with_timestamps(segments):
        def ts(t):
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t - int(t)) * 1000)
            return f"{h:02}:{m:02}:{s:02},{ms:03}"

        lines = []
        for seg in segments:
            line = f"[{ts(seg.start)} - {ts(seg.end)}] {seg.text.strip()}"
            lines.append(line)

        return "\n".join(lines)

    send_message(pid, f"[음성 인식] {WHISPER_MODEL_MAP[model_level]['name']} 모델 로드 중")
    model = get_whisper_model(model_level)

    send_message(pid, "[음성 인식] Audio -> Text 변환 중")
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=1 if model_level < 3 else 5,
        vad_filter=True,
    )

    segments = list(segments)

    text_paragraph = format_paragraphs(segments)
    text_with_time = format_with_timestamps(segments)
    
    send_message(pid, "[음성 인식] 완료")
    return {
        "language": info.language,
        "duration": info.duration,
        "model_level": model_level,
        "text": text_paragraph,
        "text_with_time": text_with_time,
        "segments": [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            }
            for seg in segments
        ],
    }

async def yolo_detect_images_to_zip(
    files: List[UploadFile],
    conf_thres: float = 0.25,
    pid=None,
) -> io.BytesIO:
    """
    여러 이미지를 받아 YOLO 객체검출 후
    - bbox 그려진 이미지
    - detections json
    을 zip(BytesIO)로 묶어 반환
    zip 내부:
      images/{stem}.jpg
      json/{stem}.json
    """
    model, names = get_yolo_model()

    # 파일 리스트 정리 (확장자 필터링)
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    valid_files = []
    skipped = 0
    for f in files:
        fname = f.filename or "image"
        ext = os.path.splitext(fname)[1].lower()
        if ext in valid_exts:
            valid_files.append(f)
        else:
            skipped += 1

    total = len(valid_files)
    if pid is not None:
        send_message(pid, f"[YOLO] 이미지 처리 시작 (총 {total}개, conf={conf_thres})"
                         + (f", 스킵 {skipped}개" if skipped else ""))

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, up in enumerate(valid_files, start=1):
            filename = up.filename or f"image_{i}"
            ext = os.path.splitext(filename)[1].lower()

            if pid is not None:
                send_message(pid, f"[YOLO] ({i}/{total}) '{filename}' 로드/추론 중...")

            data = await up.read()
            if not data:
                if pid is not None:
                    send_message(pid, f"[YOLO] ({i}/{total}) '{filename}' 읽기 실패(빈 파일) - 스킵")
                continue

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            try:
                img = cv2.imread(tmp_path)
                if img is None:
                    if pid is not None:
                        send_message(pid, f"[YOLO] ({i}/{total}) '{filename}' 이미지 디코딩 실패 - 스킵")
                    continue

                h, w = img.shape[:2]
                results = model(tmp_path, conf=conf_thres, verbose=False)

                detections: List[Dict[str, Any]] = []

                for r in results:
                    for box in r.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        conf = float(box.conf[0].item())
                        cls = int(box.cls[0].item())

                        # draw bbox
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        label = f"{names.get(cls, str(cls))} {conf:.2f}"
                        cv2.putText(
                            img,
                            label,
                            (x1, max(0, y1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 255, 0),
                            1,
                        )

                        detections.append({
                            "class_id": cls,
                            "class_name": names.get(cls, str(cls)),
                            "confidence": round(conf, 4),
                            "bbox_xyxy": [x1, y1, x2, y2],
                        })

                # encode annotated image -> jpg bytes
                encode_ext = ".jpg"
                ok, enc = cv2.imencode(encode_ext, img)
                if not ok:
                    if pid is not None:
                        send_message(pid, f"[YOLO] ({i}/{total}) '{filename}' 인코딩 실패 - 스킵")
                    continue
                annotated_bytes = enc.tobytes()

                json_obj = {
                    "image": filename,
                    "width": w,
                    "height": h,
                    "detections": detections,
                }
                json_bytes = json.dumps(json_obj, ensure_ascii=False, indent=2).encode("utf-8")

                stem = os.path.splitext(os.path.basename(filename))[0]
                zf.writestr(f"images/{stem}{encode_ext}", annotated_bytes)
                zf.writestr(f"json/{stem}.json", json_bytes)

                if pid is not None:
                    pct = round(i / total * 100, 2) if total else 100.0
                    send_message(pid, f"[YOLO] ({i}/{total}) '{filename}' 완료 "
                                      f"(det={len(detections)}개) / {pct}%")

            except Exception as e:
                if pid is not None:
                    send_message(pid, f"[YOLO] ({i}/{total}) '{filename}' 처리 중 오류: {type(e).__name__}: {e}")
                # 에러난 파일은 스킵하고 계속 진행
                continue

            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    zip_buffer.seek(0)

    if pid is not None:
        send_message(pid, "[YOLO] 전체 완료: 결과 zip 생성 완료")

    return zip_buffer

async def yolo_detect_videos_to_zip(
    files: List[UploadFile],
    conf_thres: float = 0.25,
    pid=None,
) -> io.BytesIO:
    """
    여러 비디오를 받아 YOLO 객체검출 후
    - bbox가 그려진 비디오(mp4)
    - 프레임별 detections json
    을 zip(BytesIO)로 묶어 반환

    zip 내부:
      videos/{stem}.mp4
      json/{stem}.json
    """
    model, names = get_yolo_model()

    valid_exts = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    valid_files = []
    skipped = 0

    for f in files:
        fname = f.filename or "video"
        ext = os.path.splitext(fname)[1].lower()
        if ext in valid_exts:
            valid_files.append(f)
        else:
            skipped += 1

    total = len(valid_files)
    if pid is not None:
        send_message(
            pid,
            f"[YOLO] 비디오 처리 시작 (총 {total}개, conf={conf_thres})"
            + (f", 스킵 {skipped}개" if skipped else "")
        )

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, up in enumerate(valid_files, start=1):
            filename = up.filename or f"video_{i}"
            stem, ext = os.path.splitext(os.path.basename(filename))

            if pid is not None:
                send_message(pid, f"[YOLO] ({i}/{total}) '{filename}' 로드 중...")

            data = await up.read()
            if not data:
                if pid is not None:
                    send_message(pid, f"[YOLO] ({i}/{total}) '{filename}' 빈 파일 - 스킵")
                continue

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            out_video_path = None

            try:
                cap = cv2.VideoCapture(tmp_path)
                if not cap.isOpened():
                    raise RuntimeError("VideoCapture open 실패")

                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                out_video_path = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".mp4"
                ).name
                writer = cv2.VideoWriter(out_video_path, fourcc, fps, (width, height))

                detections_by_frame = []

                frame_idx = 0
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    results = model(frame, conf=conf_thres, verbose=False)

                    frame_dets = []
                    for r in results:
                        for box in r.boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            conf = float(box.conf[0].item())
                            cls = int(box.cls[0].item())

                            # draw bbox
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            label = f"{names.get(cls, str(cls))} {conf:.2f}"
                            cv2.putText(
                                frame,
                                label,
                                (x1, max(0, y1 - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                (0, 255, 0),
                                1,
                            )

                            frame_dets.append({
                                "class_id": cls,
                                "class_name": names.get(cls, str(cls)),
                                "confidence": round(conf, 4),
                                "bbox_xyxy": [x1, y1, x2, y2],
                            })

                    detections_by_frame.append({
                        "frame_index": frame_idx,
                        "detections": frame_dets,
                    })

                    writer.write(frame)
                    frame_idx += 1

                    if pid is not None and frame_idx % 30 == 0:
                        pct = round(frame_idx / frame_count * 100, 2) if frame_count else 0
                        send_message(
                            pid,
                            f"[YOLO] ({i}/{total}) '{filename}' "
                            f"frame {frame_idx}/{frame_count} ({pct}%)"
                        )

                cap.release()
                writer.release()

                # zip write
                with open(out_video_path, "rb") as vf:
                    zf.writestr(f"videos/{stem}.mp4", vf.read())

                json_obj = {
                    "video": filename,
                    "fps": fps,
                    "width": width,
                    "height": height,
                    "frame_count": frame_idx,
                    "detections": detections_by_frame,
                }

                zf.writestr(
                    f"json/{stem}.json",
                    json.dumps(json_obj, ensure_ascii=False, indent=2).encode("utf-8"),
                )

                if pid is not None:
                    send_message(
                        pid,
                        f"[YOLO] ({i}/{total}) '{filename}' 완료 "
                        f"(총 {frame_idx} 프레임)"
                    )

            except Exception as e:
                if pid is not None:
                    send_message(
                        pid,
                        f"[YOLO] ({i}/{total}) '{filename}' 오류: "
                        f"{type(e).__name__}: {e}"
                    )
                continue

            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                if out_video_path:
                    try:
                        os.remove(out_video_path)
                    except Exception:
                        pass

    zip_buffer.seek(0)

    if pid is not None:
        send_message(pid, "[YOLO] 전체 완료: 비디오 결과 zip 생성 완료")

    return zip_buffer


# ---- Grounding Dino ----
_grounding_processor = None
_grounding_model = None

def get_grounding_dino_model():
    global _grounding_processor, _grounding_model

    if _grounding_processor is None or _grounding_model is None:
        model_path = os.path.join(
            MODEL_DIR,
            "grounding_dino",
            "grounding-dino-base",
        )

        if not os.path.isdir(model_path):
            raise FileNotFoundError(f"Grounding DINO model path not found: {model_path}")

        _grounding_processor = AutoProcessor.from_pretrained(
            model_path,
            local_files_only=True,
        )

        _grounding_model = AutoModelForZeroShotObjectDetection.from_pretrained(
            model_path,
            local_files_only=True,
        ).to("cuda" if torch.cuda.is_available() else "cpu")

        _grounding_model.eval()

    return _grounding_processor, _grounding_model

async def grounding_dino_detect_images_zip(
    files: List[UploadFile],
    prompt: str,
    box_threshold: float = 0.4,
    text_threshold: float = 0.3,
    pid=None,
) -> io.BytesIO:
    """
    여러 이미지 + 텍스트 프롬프트를 받아
    Grounding DINO로 bbox를 그리고
    결과들을 zip(BytesIO)로 반환
    """

    if pid is not None:
        send_message(pid, "[GroundingDINO] 모델 로드 중")

    processor, model = get_grounding_dino_model()
    device = model.device

    # prompt 규칙 (중요)
    prompt = prompt.lower().strip()
    if not prompt.endswith("."):
        prompt += "."

    if pid is not None:
        send_message(pid, f"[GroundingDINO] 배치 처리 시작 (count={len(files)})")

    zip_bytes = io.BytesIO()
    # ZIP_STORED(무압축) 또는 ZIP_DEFLATED(압축). 이미지 PNG는 압축 효율 낮지만 보통 DEFLATED 사용.
    with zipfile.ZipFile(zip_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, file in enumerate(files, start=1):
            # 원본 파일명 기반 결과명
            orig_name = file.filename or f"image_{idx}.png"
            base, _ext = os.path.splitext(orig_name)
            out_name = f"grounding_dino_{base}.png"

            if pid is not None:
                send_message(pid, f"[GroundingDINO] ({idx}/{len(files)}) {orig_name} 추론 시작")

            # 이미지 로드
            image_bytes = await file.read()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            inputs = processor(
                images=image,
                text=prompt,
                return_tensors="pt",
            ).to(device)

            with torch.no_grad():
                outputs = model(**inputs)

            results = processor.post_process_grounded_object_detection(
                outputs=outputs,
                input_ids=inputs.input_ids,
                target_sizes=[image.size[::-1]],
            )[0]

            keep = [i for i, s in enumerate(results["scores"]) if float(s) >= box_threshold]

            results = {
                "boxes": results["boxes"][keep],
                "labels": [results["labels"][i] for i in keep],
                "scores": results["scores"][keep],
            }

            # bbox draw
            draw_img = image.copy()
            drawer = ImageDraw.Draw(draw_img)

            for box, label, score in zip(results["boxes"], results["labels"], results["scores"]):
                x1, y1, x2, y2 = box.tolist()
                drawer.rectangle([(x1, y1), (x2, y2)], outline="red", width=3)
                drawer.text((x1, y1), f"{label} {float(score):.2f}", fill="red")

            # 결과 PNG → bytes
            out_buf = io.BytesIO()
            draw_img.save(out_buf, format="PNG")
            out_buf.seek(0)

            # zip에 기록
            zf.writestr(out_name, out_buf.getvalue())

            if pid is not None:
                send_message(pid, f"[GroundingDINO] ({idx}/{len(files)}) 완료 (det={len(results['boxes'])}개)")

    zip_bytes.seek(0)

    if pid is not None:
        send_message(pid, "[GroundingDINO] 전체 완료")

    return zip_bytes

