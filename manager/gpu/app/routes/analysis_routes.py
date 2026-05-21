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
            pid, f"[임베딩] BGE-M3 모델로 {len(sentences):, Joyce}개 문장 벡터화 시작"
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


def process_text_chunk(texts):
    """
    할당받은 텍스트 리스트에서 단어 조합(Counter)을 추출합니다.
    """
    local_counter = Counter()
    for text in texts:
        # 콤마로 구분된 토큰 추출 및 정렬
        tokens = [t.strip() for t in text.split(",") if t.strip()]
        unique_tokens = sorted(list(set(tokens)))

        # 조합 생성 후 카운터 업데이트 (메모리 절약을 위해 바로 업데이트)
        if len(unique_tokens) >= 2:
            local_counter.update(combinations(unique_tokens, 2))
    return local_counter


@router.post("/graph-network")
async def graph_network_route(file: UploadFile = File(...), option: str = Form("{}")):
    try:
        option_dict = json.loads(option)
        mode = option_dict.get("mode", "keyword")
        text_col = option_dict.get("text_col", "Article Text")
        threshold = float(option_dict.get("threshold", 0.8))

        content = await file.read()
        try:
            df = pd.read_csv(io.StringIO(content.decode("utf-8-sig")))
        except:
            df = pd.read_csv(io.StringIO(content.decode("cp949")))

        G = nx.Graph()

        if mode == "keyword":
            # 1. 병렬 처리를 위한 데이터 분할
            texts = df[text_col].fillna("").astype(str).tolist()
            num_cores = cpu_count()  # 현재 서버의 CPU 코어 수

            # 데이터를 코어 수에 맞춰 덩어리(chunk)로 나눔
            chunk_size = len(texts) // num_cores if len(texts) > num_cores else 1
            chunks = [
                texts[i : i + chunk_size] for i in range(0, len(texts), chunk_size)
            ]

            # 2. Multiprocessing Pool 가동
            # process_text_chunk 함수를 병렬로 실행
            with Pool(processes=num_cores) as pool:
                results = pool.map(process_text_chunk, chunks)

            # 3. 각 프로세스의 결과(Counter)를 하나로 병합
            pair_counts = Counter()
            for res in results:
                pair_counts.update(res)

            # 4. 임계값(Threshold) 필터링 및 그래프 생성
            min_freq = int(threshold) if threshold >= 1 else 1

            for (u, v), w in pair_counts.items():
                if w >= min_freq:
                    G.add_edge(u, v, weight=w)

        elif mode == "semantic":
            # (Semantic 모드는 기존과 동일하게 유지하되, 모든 문서를 대상으로 분석)
            if "embedding" not in df.columns:
                sentences = df[text_col].fillna("").astype(str).tolist()
                embeddings = generate_embeddings(sentences, batch_size=12)
            else:
                embeddings = [json.loads(e) for e in df["embedding"]]

            sim_matrix = cosine_similarity(embeddings)

            for i in range(len(df)):
                label = (
                    df.iloc[i]["Article Title"]
                    if "Article Title" in df.columns
                    else f"Doc_{i}"
                )
                G.add_node(i, label=label)

            for i in range(len(sim_matrix)):
                for j in range(i + 1, len(sim_matrix)):
                    if sim_matrix[i][j] >= threshold:
                        G.add_edge(i, j, weight=float(sim_matrix[i][j]))

        # 1. 중심성 및 레이아웃 계산
        deg_cent = nx.degree_centrality(G)
        bet_cent = nx.betweenness_centrality(G)
        pos = nx.spring_layout(G, k=0.5, iterations=50)  # 그래프 형태 결정

        # 2. 시각화 이미지 생성 (Matplotlib)
        plt.figure(figsize=(12, 12))

        # 노드 크기를 중심성에 비례하게 설정
        node_sizes = [v * 5000 for v in deg_cent.values()]

        # 연결선 두께를 가중치(Weight)에 비례하게 설정
        edges = G.edges(data=True)
        weights = [d["weight"] for u, v, d in edges]
        # 가중치 정규화 (선이 너무 굵어지는 것 방지)
        max_weight = max(weights) if weights else 1
        edge_widths = [(w / max_weight) * 5 for w in weights]

        nx.draw_networkx_nodes(
            G, pos, node_size=node_sizes, node_color="skyblue", alpha=0.7
        )
        nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color="gray", alpha=0.4)
        nx.draw_networkx_labels(
            G, pos, font_family=plt.rcParams["font.family"], font_size=10
        )

        plt.title(f"Network Analysis ({mode} mode)", size=15)
        plt.axis("off")

        # 이미지를 버퍼에 저장
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", bbox_inches="tight")
        img_buffer.seek(0)
        plt.close()  # 메모리 해제

        nodes_df = pd.DataFrame(
            [
                {
                    "ID": n,
                    "Label": G.nodes[n].get("label", n),
                    "DegreeCentrality": deg_cent.get(n, 0),
                    "BetweennessCentrality": bet_cent.get(n, 0),
                }
                for n in G.nodes()
            ]
        )

        edges_df = pd.DataFrame(
            [
                {"Source": u, "Target": v, "Weight": d["weight"]}
                for u, v, d in G.edges(data=True)
            ]
        )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("nodes.csv", nodes_df.to_csv(index=False, encoding="utf-8-sig"))
            zf.writestr("edges.csv", edges_df.to_csv(index=False, encoding="utf-8-sig"))
            zf.writestr(
                "network_graph.png", img_buffer.getvalue()
            )  # 시각화 이미지 추가

        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=network_analysis_result.zip"
            },
        )

    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})
