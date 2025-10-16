# -*- coding: utf-8 -*-
"""
Plotly Dash CSV Analyzer (Naver News / Cafe / YouTube / Hate Analysis)

드래그앤드랍으로 CSV를 올리면 컬럼을 자동 감지하여 해당 분석을 수행하고
대시보드에 그래프와 테이블을 보여줍니다.

필요 패키지(예시):
    pip install dash==2.* dash-bootstrap-components pandas numpy plotly

실행 방법:
    python plotly_dash_news_youtube_cafe_analyzer_app.py
    → http://127.0.0.1:8050 접속

참고:
- 이 앱은 원본 PyQt 기반 분석 로직(Seaborn/Matplotlib 파일 저장)을 웹용으로 재구성했습니다.
- 그래프는 Plotly(인터랙티브), 테이블은 Dash DataTable로 제공합니다.
- CSV는 클라이언트 메모리에서 처리되며, 로컬 파일 저장 대신 화면 출력/다운로드로 대체합니다.
"""

import base64
import io
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dash import Dash, dcc, html, Input, Output, State, dash_table, callback_context
import dash_bootstrap_components as dbc

# ──────────────────────────────────────────────────────────────────────────────
# 유틸: 필수 컬럼 체크
# ──────────────────────────────────────────────────────────────────────────────

def has_cols(df: pd.DataFrame, cols: List[str]) -> bool:
    return all(c in df.columns for c in cols)


def first_col_contains(df: pd.DataFrame, token: str) -> Optional[str]:
    for c in df.columns:
        if token in c:
            return c
    return None


# ──────────────────────────────────────────────────────────────────────────────
# 스키마 정의(감지)
# ──────────────────────────────────────────────────────────────────────────────

SCHEMAS = {
    # Naver News: Article(본문) 분석
    "naver_news_article": [
        "Article Press", "Article Type", "Article URL", "Article Title",
        "Article Text", "Article Date", "Article ReplyCnt",
    ],
    # Naver News: 댓글 통계 포함 분석
    "naver_news_statistics": [
        "Article Press", "Article Type", "Article URL", "Article Title",
        "Article Text", "Article Date", "Article ReplyCnt",
        "Male", "Female", "10Y", "20Y", "30Y", "40Y", "50Y", "60Y",
    ],
    # Naver News: 댓글 데이터
    "naver_news_reply": [
        "Reply Date", "Reply Text", "Reply Writer", "Rereply Count",
        "Reply Like", "Reply Bad", "Reply LikeRatio", "Reply Sentiment",
    ],
    # Naver News: 대댓글 데이터
    "naver_news_rereply": [
        "Reply_ID", "Rereply Writer", "Rereply Date", "Rereply Text",
        "Rereply Like", "Rereply Bad", "Rereply LikeRatio", "Rereply Sentiment",
        "Article URL", "Article Day",
    ],
    # Naver Cafe: 게시글
    "naver_cafe_article": [
        "NaverCafe Name", "NaverCafe MemberCount", "Article Writer",
        "Article Title", "Article Text", "Article Date", "Article ReadCount",
        "Article ReplyCount", "Article URL",
    ],
    # Naver Cafe: 댓글
    "naver_cafe_reply": [
        "Reply Num", "Reply Writer", "Reply Date", "Reply Text", "Article URL", "Article Day",
    ],
    # YouTube: 영상(게시물)
    "youtube_article": [
        "YouTube Channel", "Article URL", "Article Title", "Article Text",
        "Article Date", "Article ViewCount", "Article Like", "Article ReplyCount",
    ],
    # YouTube: 댓글
    "youtube_reply": [
        "Reply Num", "Reply Writer", "Reply Date", "Reply Text", "Reply Like", "Article URL", "Article Day",
    ],
    # YouTube: 대댓글
    "youtube_rereply": [
        "Rereply Num", "Rereply Writer", "Rereply Date", "Rereply Text", "Rereply Like", "Article URL", "Article Day",
    ],
}

# Hate Analysis: 가변(세 가지 형태)
HATE_DATE_KEY = "Date"
HATE_LABELS = {
    "여성/가족", "남성", "성소수자", "인종/국적", "연령",
    "지역", "종교", "기타 혐오", "악플/욕설", "clean",
}


def detect_schema(df: pd.DataFrame) -> str:
    # Hate 분석(우선) : Date 포함 + Hate/clean/레이블들
    date_like = first_col_contains(df, HATE_DATE_KEY)
    if date_like is not None:
        if "Hate" in df.columns:
            return "hate_hate"
        present = [c for c in HATE_LABELS if c in df.columns]
        if len(present) >= 8:
            return "hate_labels"
        if set(present) == {"clean"}:
            return "hate_clean"

    # 그 외 사전 정의 스키마 탐지 (가장 긴 스키마부터)
    for key in [
        "naver_news_statistics",
        "naver_news_article",
        "naver_news_reply",
        "naver_news_rereply",
        "naver_cafe_article",
        "naver_cafe_reply",
        "youtube_article",
        "youtube_reply",
        "youtube_rereply",
    ]:
        if has_cols(df, SCHEMAS[key]):
            return key

    return "unknown"


# ──────────────────────────────────────────────────────────────────────────────
# 파서: dcc.Upload 컨텐츠 → DataFrame
# ──────────────────────────────────────────────────────────────────────────────

def parse_contents(contents: str, filename: str) -> pd.DataFrame:
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    if filename.lower().endswith('.csv'):
        return pd.read_csv(io.StringIO(decoded.decode('utf-8')), encoding_errors='ignore')
    elif filename.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(io.BytesIO(decoded))
    else:
        # 기본은 CSV로 시도
        try:
            return pd.read_csv(io.StringIO(decoded.decode('utf-8')), encoding_errors='ignore')
        except Exception:
            raise ValueError("지원하지 않는 파일 형식입니다. CSV 또는 Excel을 업로드 해주세요.")


# ──────────────────────────────────────────────────────────────────────────────
# 공통: 날짜파싱, 기간그룹, 보조 유틸
# ──────────────────────────────────────────────────────────────────────────────

def to_datetime_safe(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors='coerce')


def ensure_id(df: pd.DataFrame) -> pd.DataFrame:
    if 'id' not in df.columns:
        df = df.copy()
        df.insert(0, 'id', range(1, len(df) + 1))
    return df


def corr_heatmap_fig(df: pd.DataFrame, title: str) -> go.Figure:
    corr = df.corr(numeric_only=True)
    fig = px.imshow(corr, text_auto=True, color_continuous_scale='RdBu', zmin=-1, zmax=1,
                    title=title, aspect='auto')
    return fig


def long_bar_fig(df: pd.DataFrame, x: str, y: str, title: str) -> go.Figure:
    fig = px.bar(df, x=x, y=y, title=title)
    fig.update_layout(xaxis_tickangle=45)
    return fig


def two_line_fig(df: pd.DataFrame, x: str, y1: str, y2: str, title: str,
                 name1: str, name2: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df[x], y=df[y1], mode='lines+markers', name=name1))
    fig.add_trace(go.Scatter(x=df[x], y=df[y2], mode='lines+markers', name=name2))
    fig.update_layout(title=title, xaxis_title=x, yaxis_title='count')
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# 분석기: 각 스키마별 분석(Plotly용)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AnalysisResult:
    title: str
    description: str
    figures: List[Tuple[str, go.Figure]]  # (subtitle, figure)
    tables: List[Tuple[str, pd.DataFrame]]  # (subtitle, dataframe)


# 1) Naver News Article

def analyze_naver_news_article(df: pd.DataFrame) -> AnalysisResult:
    df = ensure_id(df)
    df = df.copy()
    df['Article Date'] = to_datetime_safe(df['Article Date'])
    df['Article ReplyCnt'] = pd.to_numeric(df['Article ReplyCnt'], errors='coerce').fillna(0)

    # 월/일별 집계
    monthly = df.groupby(df['Article Date'].dt.to_period('M')).agg(
        Article_Count=('id', 'count'),
        Reply_Count=('Article ReplyCnt', 'sum')
    ).reset_index()
    monthly['Article Date'] = monthly['Article Date'].dt.to_timestamp()

    daily = df.groupby(df['Article Date'].dt.to_period('D')).agg(
        Article_Count=('id', 'count'),
        Reply_Count=('Article ReplyCnt', 'sum')
    ).reset_index()
    daily['Article Date'] = daily['Article Date'].dt.to_timestamp()

    # 유형/언론사 Top
    type_agg = df.groupby('Article Type').agg(
        Article_Count=('id', 'count'),
        Reply_Count=('Article ReplyCnt', 'sum')
    ).reset_index().sort_values('Article_Count', ascending=False)

    top10_press = df['Article Press'].value_counts().head(10).index
    press_agg = df[df['Article Press'].isin(top10_press)].groupby('Article Press').agg(
        Article_Count=('id', 'count'),
        Reply_Count=('Article ReplyCnt', 'sum')
    ).reset_index().sort_values('Article_Count', ascending=False)

    figs = []
    figs.append(("월별 기사/댓글 수", two_line_fig(monthly, 'Article Date', 'Article_Count', 'Reply_Count',
                                           '월별 기사/댓글 수 추이', '기사 수', '댓글 수')))
    figs.append(("일별 기사/댓글 수", two_line_fig(daily, 'Article Date', 'Article_Count', 'Reply_Count',
                                           '일별 기사/댓글 수 추이', '기사 수', '댓글 수')))
    figs.append(("기사 유형별 기사 수", long_bar_fig(type_agg, 'Article Type', 'Article_Count', '기사 유형별 기사 수')))
    figs.append(("상위 10개 언론사 기사 수", long_bar_fig(press_agg, 'Article Press', 'Article_Count', '상위 10개 언론사 기사 수')))

    tables = [
        ("월별 집계", monthly),
        ("일별 집계", daily),
        ("기사 유형별 집계", type_agg),
        ("상위 10개 언론사 집계", press_agg),
    ]

    desc = (
        "월/일별 기사 수 및 댓글 수 추이를 확인할 수 있고, 기사 유형과 상위 언론사 분포를 함께 제공합니다."
    )
    return AnalysisResult("Naver News: 기사 분석", desc, figs, tables)


# 2) Naver News Statistics (성별/연령 포함)

def analyze_naver_news_statistics(df: pd.DataFrame) -> AnalysisResult:
    df = ensure_id(df)
    df = df.copy()
    df['Article Date'] = to_datetime_safe(df['Article Date'])
    df['Article ReplyCnt'] = pd.to_numeric(df['Article ReplyCnt'], errors='coerce').fillna(0)

    # 비율 → 실제 수로 변환
    for col in ["Male", "Female", "10Y", "20Y", "30Y", "40Y", "50Y", "60Y"]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df[col] = df[col] / 100.0 * df['Article ReplyCnt']

    # 월/일별
    monthly = df.groupby(df['Article Date'].dt.to_period('M')).agg(
        Article_Count=('id', 'count'),
        Reply_Count=('Article ReplyCnt', 'sum')
    ).reset_index()
    monthly['Article Date'] = monthly['Article Date'].dt.to_timestamp()

    daily = df.groupby(df['Article Date'].dt.to_period('D')).agg(
        Article_Count=('id', 'count'),
        Reply_Count=('Article ReplyCnt', 'sum')
    ).reset_index()
    daily['Article Date'] = daily['Article Date'].dt.to_timestamp()

    # 유형/언론사
    type_agg = df.groupby('Article Type').agg(
        Article_Count=('id', 'count'), Reply_Count=('Article ReplyCnt', 'sum')
    ).reset_index().sort_values('Article_Count', ascending=False)

    top10_press = df['Article Press'].value_counts().head(10).index
    press_agg = df[df['Article Press'].isin(top10_press)].groupby('Article Press').agg(
        Article_Count=('id', 'count'), Reply_Count=('Article ReplyCnt', 'sum')
    ).reset_index().sort_values('Article_Count', ascending=False)

    # 성별/연령 총합
    gender_df = pd.DataFrame({
        'Gender': ['Male', 'Female'],
        'Reply Count': [df['Male'].sum(), df['Female'].sum()]
    })
    age_df = pd.DataFrame({
        'Age Group': ['10Y','20Y','30Y','40Y','50Y','60Y'],
        'Reply Count': [df[a].sum() for a in ['10Y','20Y','30Y','40Y','50Y','60Y']]
    })

    figs = []
    figs.append(("월별 기사/댓글 수", two_line_fig(monthly, 'Article Date', 'Article_Count', 'Reply_Count',
                                           '월별 기사/댓글 수 추이', '기사 수', '댓글 수')))
    figs.append(("일별 기사/댓글 수", two_line_fig(daily, 'Article Date', 'Article_Count', 'Reply_Count',
                                           '일별 기사/댓글 수 추이', '기사 수', '댓글 수')))
    figs.append(("기사 유형별 기사 수", long_bar_fig(type_agg, 'Article Type', 'Article_Count', '기사 유형별 기사 수')))
    figs.append(("상위 10개 언론사 기사 수", long_bar_fig(press_agg, 'Article Press', 'Article_Count', '상위 10개 언론사 기사 수')))

    figs.append(("성별 댓글 수", px.bar(gender_df, x='Gender', y='Reply Count', title='성별 댓글 수 합계')))
    figs.append(("연령대 댓글 수", px.bar(age_df, x='Age Group', y='Reply Count', title='연령대별 댓글 수 합계')))

    corr_fig = corr_heatmap_fig(df[[
        'Article ReplyCnt','Male','Female','10Y','20Y','30Y','40Y','50Y','60Y'
    ]], '상관관계(댓글수/성별/연령)')
    figs.append(("상관관계", corr_fig))

    tables = [
        ("월별 집계", monthly), ("일별 집계", daily),
        ("기사 유형 집계", type_agg), ("상위 10 언론사", press_agg),
        ("성별 합계", gender_df), ("연령대 합계", age_df)
    ]

    return AnalysisResult("Naver News: 댓글 통계 포함 분석",
                          "댓글의 성별/연령 분포와 상관관계를 함께 확인합니다.",
                          figs, tables)


# 3) Naver News Reply

def analyze_naver_news_reply(df: pd.DataFrame) -> AnalysisResult:
    df = ensure_id(df)
    df = df.copy()
    df['Reply Date'] = to_datetime_safe(df['Reply Date'])
    for col in ['Rereply Count','Reply Like','Reply Bad','Reply LikeRatio']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df['Reply Sentiment'] = df['Reply Sentiment'].astype(str)

    df['Reply Length'] = df['Reply Text'].astype(str).str.len()

    daily = df.groupby(df['Reply Date'].dt.to_period('D')).agg(
        Reply_Count=('id','count'), Likes=('Reply Like','sum'), Dislikes=('Reply Bad','sum')
    ).reset_index()
    daily['Reply Date'] = daily['Reply Date'].dt.to_timestamp()

    month = df.groupby(df['Reply Date'].dt.to_period('M')).agg(
        Reply_Count=('id','count'), Likes=('Reply Like','sum'), Dislikes=('Reply Bad','sum')
    ).reset_index()
    month['Reply Date'] = month['Reply Date'].dt.to_timestamp()

    sentiment = df['Reply Sentiment'].value_counts().rename_axis('Sentiment').reset_index(name='Count')

    writer_cnt = df['Reply Writer'].value_counts().head(10).rename_axis('Writer').reset_index(name='Count')

    figs = []
    figs.append(("일별 댓글/좋아요/싫어요", px.line(daily, x='Reply Date', y=['Reply_Count','Likes','Dislikes'],
                                  title='일별 댓글/좋아요/싫어요')))
    figs.append(("월별 댓글/좋아요/싫어요", px.line(month, x='Reply Date', y=['Reply_Count','Likes','Dislikes'],
                                  title='월별 댓글/좋아요/싫어요')))
    figs.append(("감성 분포", px.bar(sentiment, x='Sentiment', y='Count', title='댓글 감성 분포')))
    figs.append(("상위 10 작성자", px.bar(writer_cnt, x='Writer', y='Count', title='작성자별 댓글 수(Top 10)')))

    corr_fig = corr_heatmap_fig(df[[c for c in ['Reply Like','Reply Bad','Rereply Count','Reply LikeRatio','Reply Length'] if c in df.columns]],
                                '상관관계(좋아요/싫어요/대댓글/길이)')
    figs.append(("상관관계", corr_fig))

    tables = [
        ("일별 집계", daily), ("월별 집계", month), ("감성 분포", sentiment), ("Top10 작성자", writer_cnt)
    ]

    return AnalysisResult("Naver News: 댓글 분석",
                          "일/월별 추세, 감성 분포, 작성자 상위 현황과 상관관계를 제공합니다.",
                          figs, tables)


# 4) Naver News Rereply

def analyze_naver_news_rereply(df: pd.DataFrame) -> AnalysisResult:
    df = ensure_id(df)
    df = df.copy()
    df['Rereply Date'] = to_datetime_safe(df['Rereply Date'])
    for col in ['Rereply Like', 'Rereply Bad', 'Rereply LikeRatio', 'Rereply Sentiment']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce') if col != 'Rereply Sentiment' else df[col]

    daily = df.groupby(df['Rereply Date'].dt.to_period('D')).agg(
        Rereply_Count=('id','count'), Likes=('Rereply Like','sum'), Dislikes=('Rereply Bad','sum')
    ).reset_index()
    daily['Rereply Date'] = daily['Rereply Date'].dt.to_timestamp()

    month = df.groupby(df['Rereply Date'].dt.to_period('M')).agg(
        Rereply_Count=('id','count'), Likes=('Rereply Like','sum'), Dislikes=('Rereply Bad','sum')
    ).reset_index()
    month['Rereply Date'] = month['Rereply Date'].dt.to_timestamp()

    sentiment = df['Rereply Sentiment'].value_counts().rename_axis('Sentiment').reset_index(name='Count')
    writer_cnt = df['Rereply Writer'].value_counts().head(10).rename_axis('Writer').reset_index(name='Count')

    figs = []
    figs.append(("일별 대댓글/좋아요/싫어요", px.line(daily, x='Rereply Date', y=['Rereply_Count','Likes','Dislikes'],
                                   title='일별 대댓글/좋아요/싫어요')))
    figs.append(("월별 대댓글/좋아요/싫어요", px.line(month, x='Rereply Date', y=['Rereply_Count','Likes','Dislikes'],
                                   title='월별 대댓글/좋아요/싫어요')))
    figs.append(("감성 분포", px.bar(sentiment, x='Sentiment', y='Count', title='대댓글 감성 분포')))
    figs.append(("상위 10 작성자", px.bar(writer_cnt, x='Writer', y='Count', title='대댓글 작성자 수(Top 10)')))

    corr_fig = corr_heatmap_fig(df[[c for c in ['Rereply Like','Rereply Bad','Rereply LikeRatio'] if c in df.columns]],
                                '상관관계(좋아요/싫어요/비율)')
    figs.append(("상관관계", corr_fig))

    tables = [("일별 집계", daily), ("월별 집계", month), ("감성 분포", sentiment), ("Top10 작성자", writer_cnt)]

    return AnalysisResult("Naver News: 대댓글 분석",
                          "일/월별 추세, 감성 분포, 상위 작성자 및 상관관계를 제공합니다.",
                          figs, tables)


# 5) Naver Cafe Article

def analyze_naver_cafe_article(df: pd.DataFrame) -> AnalysisResult:
    df = ensure_id(df)
    df = df.copy()
    df['Article Date'] = to_datetime_safe(df['Article Date'])
    for col in ['NaverCafe MemberCount','Article ReadCount','Article ReplyCount']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    cafe_agg = df.groupby('NaverCafe Name').agg(
        Article_Count=('id','count'),
        Avg_Read=('Article ReadCount','mean'),
        Avg_Reply=('Article ReplyCount','mean'),
        Avg_Member=('NaverCafe MemberCount','mean')
    ).reset_index().sort_values('Article_Count', ascending=False)

    monthly = df.groupby(df['Article Date'].dt.to_period('M')).agg(
        Article_Count=('id','count'), Read_Sum=('Article ReadCount','sum'), Reply_Sum=('Article ReplyCount','sum')
    ).reset_index()
    monthly['Article Date'] = monthly['Article Date'].dt.to_timestamp()

    writer_agg = df.groupby('Article Writer').agg(
        Article_Count=('id','count'), Avg_Read=('Article ReadCount','mean'), Avg_Reply=('Article ReplyCount','mean')
    ).reset_index().sort_values('Article_Count', ascending=False).head(10)

    figs = []
    figs.append(("카페별 게시글 수", long_bar_fig(cafe_agg, 'NaverCafe Name', 'Article_Count', '카페별 게시글 수')))
    figs.append(("월별 게시글 수", px.line(monthly, x='Article Date', y='Article_Count', title='월별 게시글 수 추이')))
    figs.append(("상위 10 작성자", long_bar_fig(writer_agg, 'Article Writer', 'Article_Count', '상위 10 작성자 게시글 수')))

    corr_fig = corr_heatmap_fig(df[['NaverCafe MemberCount','Article ReadCount','Article ReplyCount']], '상관관계')
    figs.append(("상관관계", corr_fig))

    tables = [("카페별 집계", cafe_agg), ("월별 집계", monthly), ("상위 10 작성자", writer_agg)]

    return AnalysisResult("Naver Cafe: 게시글 분석",
                          "카페/작성자/월별 추세 및 상관관계를 제공합니다.", figs, tables)


# 6) Naver Cafe Reply

def analyze_naver_cafe_reply(df: pd.DataFrame) -> AnalysisResult:
    df = ensure_id(df)
    df = df.copy()
    df['Reply Date'] = to_datetime_safe(df['Reply Date'])

    writer = df.groupby('Reply Writer').agg(Reply_Count=('id','count')).reset_index().sort_values('Reply_Count', ascending=False).head(100)
    monthly = df.groupby(df['Reply Date'].dt.to_period('M')).agg(Reply_Count=('id','count')).reset_index()
    monthly['Reply Date'] = monthly['Reply Date'].dt.to_timestamp()

    figs = []
    figs.append(("상위 100 작성자", long_bar_fig(writer, 'Reply Writer', 'Reply_Count', '작성자별 댓글 수(Top 100)')))
    figs.append(("월별 댓글 수", px.line(monthly, x='Reply Date', y='Reply_Count', title='월별 댓글 수 추이')))

    tables = [("상위 100 작성자", writer), ("월별 집계", monthly)]

    return AnalysisResult("Naver Cafe: 댓글 분석",
                          "작성자 분포와 월별 추세를 제공합니다.", figs, tables)


# 7) YouTube Article

def analyze_youtube_article(df: pd.DataFrame) -> AnalysisResult:
    df = ensure_id(df)
    df = df.copy()
    df['Article Date'] = to_datetime_safe(df['Article Date'])

    df = df.rename(columns={
        'Article ViewCount': 'views',
        'Article Like': 'likes',
        'Article ReplyCount': 'comments_count'
    })
    for col in ['views','likes','comments_count']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    valid = df.dropna(subset=['Article Date']).copy()

    monthly = valid.groupby(valid['Article Date'].dt.to_period('M')).agg(
        video_count=('Article Date','count'), views=('views','sum'), likes=('likes','sum'), comments=('comments_count','sum')
    ).reset_index()
    monthly['Article Date'] = monthly['Article Date'].dt.to_timestamp()

    daily = valid.groupby(valid['Article Date'].dt.to_period('D')).agg(
        video_count=('Article Date','count'), views=('views','sum'), likes=('likes','sum'), comments=('comments_count','sum')
    ).reset_index()
    daily['Article Date'] = daily['Article Date'].dt.to_timestamp()

    weekly = valid.groupby(valid['Article Date'].dt.to_period('W-SUN')).agg(
        video_count=('Article Date','count'), views=('views','sum'), likes=('likes','sum'), comments=('comments_count','sum')
    ).reset_index()
    weekly['Article Date'] = weekly['Article Date'].dt.to_timestamp()

    valid['DayOfWeek'] = valid['Article Date'].dt.day_name()
    dow = valid.groupby('DayOfWeek').agg(
        video_count=('Article Date','count'), views=('views','sum'), likes=('likes','sum'), comments=('comments_count','sum')
    ).reset_index()

    top10_channels = df['YouTube Channel'].value_counts().head(10).index
    ch = df[df['YouTube Channel'].isin(top10_channels)].groupby('YouTube Channel').agg(
        video_count=('Article Date','count'), total_views=('views','sum'), total_likes=('likes','sum'), total_comments=('comments_count','sum')
    ).reset_index().sort_values('total_views', ascending=False)

    top10_videos = df.sort_values('views', ascending=False).head(10)[['Article Title','YouTube Channel','views','likes','comments_count']]

    df['like_view_ratio'] = df.apply(lambda x: x['likes']/x['views'] if x['views']>0 else 0, axis=1)
    df['comment_view_ratio'] = df.apply(lambda x: x['comments_count']/x['views'] if x['views']>0 else 0, axis=1)

    figs = []
    figs.append(("월별 추세", px.line(monthly, x='Article Date', y=['views','likes','comments'], title='월별 조회/좋아요/댓글 추세')))
    figs.append(("일별 추세", px.line(daily, x='Article Date', y=['views','likes','comments'], title='일별 조회/좋아요/댓글 추세')))
    figs.append(("주별 추세", px.line(weekly, x='Article Date', y=['views','likes','comments'], title='주별 조회/좋아요/댓글 추세')))

    dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    dow['DayOfWeek'] = pd.Categorical(dow['DayOfWeek'], categories=dow_order, ordered=True)
    dow = dow.sort_values('DayOfWeek')
    figs.append(("요일별 조회수", px.bar(dow, x='DayOfWeek', y='views', title='요일별 총 조회수')))

    figs.append(("채널별 총 조회수(Top10)", long_bar_fig(ch, 'YouTube Channel', 'total_views', '상위 10 채널별 총 조회수')))
    figs.append(("영상 Top10(조회수)", long_bar_fig(top10_videos, 'Article Title', 'views', '상위 10 영상(조회수)')))

    corr_fig = corr_heatmap_fig(df[['views','likes','comments_count','like_view_ratio','comment_view_ratio']], '상관관계')
    figs.append(("상관관계", corr_fig))

    tables = [
        ("월별", monthly), ("일별", daily), ("주별", weekly), ("요일별", dow), ("채널별(Top10)", ch), ("영상 Top10", top10_videos)
    ]

    return AnalysisResult("YouTube: 영상(게시물) 분석",
                          "월/일/주/요일별 추세와 상위 채널·영상 및 상관관계를 제공합니다.", figs, tables)


# 8) YouTube Reply

def analyze_youtube_reply(df: pd.DataFrame) -> AnalysisResult:
    df = ensure_id(df)
    df = df.copy()
    df['Reply Date'] = to_datetime_safe(df['Reply Date'])
    df['Article Day'] = to_datetime_safe(df['Article Day'])
    df['Reply Like'] = pd.to_numeric(df['Reply Like'], errors='coerce').fillna(0)

    valid = df.dropna(subset=['Reply Date','Article Day']).copy()
    valid['ReplyTimeDelta'] = (valid['Reply Date'] - valid['Article Day']).dt.days

    daily = valid.groupby(valid['Reply Date'].dt.to_period('D')).agg(
        reply_count=('Reply Text','count'), total_like=('Reply Like','sum'), avg_time_diff=('ReplyTimeDelta','mean')
    ).reset_index()
    daily['Reply Date'] = daily['Reply Date'].dt.to_timestamp()

    monthly = valid.groupby(valid['Reply Date'].dt.to_period('M')).agg(
        reply_count=('Reply Text','count'), total_like=('Reply Like','sum'), avg_time_diff=('ReplyTimeDelta','mean')
    ).reset_index()
    monthly['Reply Date'] = monthly['Reply Date'].dt.to_timestamp()

    dow = valid.groupby(valid['Reply Date'].dt.day_name()).agg(
        reply_count=('Reply Text','count'), total_like=('Reply Like','sum'), avg_time_diff=('ReplyTimeDelta','mean')
    ).reset_index().rename(columns={'Reply Date':'ReplyDayOfWeek'})

    article = df.groupby('Article URL').agg(
        reply_count=('Reply Text','count'), total_like=('Reply Like','sum')
    ).reset_index()

    writer = df.groupby('Reply Writer').agg(
        reply_count=('Reply Text','count'), total_like=('Reply Like','sum')
    ).reset_index()

    top_writers = writer.sort_values('reply_count', ascending=False).head(10)
    top_articles = article.sort_values('reply_count', ascending=False).head(10)

    figs = []
    figs.append(("일별 댓글/좋아요", px.line(daily, x='Reply Date', y=['reply_count','total_like'], title='일별 댓글/좋아요 추세')))
    figs.append(("월별 댓글/좋아요", px.line(monthly, x='Reply Date', y=['reply_count','total_like'], title='월별 댓글/좋아요 추세')))
    figs.append(("요일별 댓글 수", px.bar(dow.rename(columns={'index':'ReplyDayOfWeek'}), x='ReplyDayOfWeek', y='reply_count', title='요일별 댓글 수')))
    figs.append(("업로드일 기준", px.line(valid.groupby(valid['Article Day'].dt.to_period('D')).agg(
        article_reply_count=('Reply Text','count'), article_reply_like=('Reply Like','sum')
    ).reset_index().assign(**{'Article Day':lambda x: x['Article Day'].dt.to_timestamp()}),
        x='Article Day', y=['article_reply_count','article_reply_like'], title='영상 업로드 날짜별 댓글/좋아요')))
    figs.append(("Top10 작성자", long_bar_fig(top_writers, 'Reply Writer', 'reply_count', '상위 10 작성자')))
    figs.append(("Top10 영상", long_bar_fig(top_articles, 'Article URL', 'reply_count', '상위 10 영상별 댓글 수')))

    corr_fig = corr_heatmap_fig(valid[['Reply Like','ReplyTimeDelta']], '상관관계(좋아요/시차)')
    figs.append(("상관관계", corr_fig))

    tables = [
        ("일별", daily), ("월별", monthly), ("요일별", dow), ("Top10 작성자", top_writers), ("Top10 영상", top_articles)
    ]

    return AnalysisResult("YouTube: 댓글 분석",
                          "일/월/요일·업로드일 기준 추세와 상위 작성자/영상 및 상관관계를 제공합니다.", figs, tables)


# 9) YouTube Rereply

def analyze_youtube_rereply(df: pd.DataFrame) -> AnalysisResult:
    df = ensure_id(df)
    df = df.copy()
    df['Rereply Date'] = to_datetime_safe(df['Rereply Date'])
    df['Article Day'] = to_datetime_safe(df['Article Day'])
    df['Rereply Like'] = pd.to_numeric(df['Rereply Like'], errors='coerce').fillna(0)

    valid = df.dropna(subset=['Rereply Date','Article Day']).copy()
    valid['RereplyTimeDelta'] = (valid['Rereply Date'] - valid['Article Day']).dt.days

    daily = valid.groupby(valid['Rereply Date'].dt.to_period('D')).agg(
        rereply_count=('Rereply Text','count'), total_like=('Rereply Like','sum'), avg_time_diff=('RereplyTimeDelta','mean')
    ).reset_index()
    daily['Rereply Date'] = daily['Rereply Date'].dt.to_timestamp()

    monthly = valid.groupby(valid['Rereply Date'].dt.to_period('M')).agg(
        rereply_count=('Rereply Text','count'), total_like=('Rereply Like','sum'), avg_time_diff=('RereplyTimeDelta','mean')
    ).reset_index()
    monthly['Rereply Date'] = monthly['Rereply Date'].dt.to_timestamp()

    writer = df.groupby('Rereply Writer').agg(
        rereply_count=('Rereply Text','count'), total_like=('Rereply Like','sum')
    ).reset_index()
    top_writers = writer.sort_values('rereply_count', ascending=False).head(10)

    article = df.groupby('Article URL').agg(
        rereply_count=('Rereply Text','count'), total_like=('Rereply Like','sum')
    ).reset_index()
    top_articles = article.sort_values('rereply_count', ascending=False).head(10)

    figs = []
    figs.append(("일별 대댓글/좋아요", px.line(daily, x='Rereply Date', y=['rereply_count','total_like'], title='일별 대댓글/좋아요 추세')))
    figs.append(("월별 대댓글/좋아요", px.line(monthly, x='Rereply Date', y=['rereply_count','total_like'], title='월별 대댓글/좋아요 추세')))
    figs.append(("Top10 작성자", long_bar_fig(top_writers, 'Rereply Writer', 'rereply_count', '상위 10 대댓글 작성자')))
    figs.append(("Top10 영상", long_bar_fig(top_articles, 'Article URL', 'rereply_count', '상위 10 영상별 대댓글 수')))

    corr_fig = corr_heatmap_fig(valid[['Rereply Like','RereplyTimeDelta']], '상관관계(좋아요/시차)')
    figs.append(("상관관계", corr_fig))

    tables = [("일별", daily), ("월별", monthly), ("Top10 작성자", top_writers), ("Top10 영상", top_articles)]

    return AnalysisResult("YouTube: 대댓글 분석",
                          "일/월별 추세와 상위 작성자/영상 및 상관관계를 제공합니다.", figs, tables)


# 10) Hate Analysis (세 가지 변형)

def analyze_hate(df: pd.DataFrame, mode: str) -> AnalysisResult:
    date_col = first_col_contains(df, HATE_DATE_KEY)
    df = df.copy()
    df[date_col] = to_datetime_safe(df[date_col])

    if mode == 'hate_hate':
        target_cols = ['Hate']
    elif mode == 'hate_labels':
        present = [c for c in HATE_LABELS if c in df.columns]
        target_cols = present
    else:  # hate_clean
        target_cols = ['clean']

    # 월/일 평균
    monthly = df.groupby(df[date_col].dt.to_period('M'))[target_cols].mean().reset_index()
    monthly[date_col] = monthly[date_col].dt.to_timestamp()

    daily = df.groupby(df[date_col].dt.to_period('D'))[target_cols].mean().reset_index()
    daily[date_col] = daily[date_col].dt.to_timestamp()

    # 7일 이동평균
    rolling7 = (
        df.set_index(df[date_col]).sort_index()[target_cols]
          .rolling('7D').mean().reset_index()
          .rename(columns={'index': date_col})
    )

    figs = []
    # 월별/7일 평균 라인(최대 6개까지 표시)
    for label, sub in [("월별 평균", monthly), ("7일 이동평균", rolling7)]:
        y_cols = target_cols[:6]
        fig = px.line(sub, x=date_col, y=y_cols, title=f"{label} 추세")
        figs.append((label, fig))

    # 분포
    for col in target_cols:
        fig = px.histogram(df, x=col, nbins=50, title=f"{col} 분포")
        figs.append((f"{col} 분포", fig))

    # 레이블 히트맵(멀티레이블인 경우)
    if len(target_cols) > 1:
        heat_df = monthly.set_index(date_col)[target_cols]
        fig = px.imshow(heat_df.T, color_continuous_scale='Reds', aspect='auto',
                        title='월별 레이블 평균 히트맵')
        figs.append(("레이블 히트맵", fig))

    # 상관관계
    if len(target_cols) > 1:
        figs.append(("상관관계", corr_heatmap_fig(df[target_cols], '상관관계 히트맵')))

    tables = [("월별 평균", monthly), ("일별 평균", daily), ("7일 이동 평균", rolling7)]

    return AnalysisResult("Hate/Clean 레이블 분석",
                          f"자동 모드 감지: {mode}. 월/일/7일 평균, 분포, (해당 시) 히트맵/상관관계를 제공합니다.",
                          figs, tables)


# ──────────────────────────────────────────────────────────────────────────────
# Dash 앱 레이아웃
# ──────────────────────────────────────────────────────────────────────────────

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "CSV Analyzer (News/Cafe/YouTube/Hate)"

UPLOAD = dcc.Upload(
    id='upload-data',
    children=html.Div([
        html.Strong('CSV/Excel 파일을 여기로 드래그하거나 클릭하여 업로드'),
        html.Br(),
        html.Small('지원: .csv, .xlsx, .xls')
    ]),
    style={
        'width': '100%', 'height': '120px', 'lineHeight': '120px',
        'borderWidth': '2px', 'borderStyle': 'dashed', 'borderRadius': '8px',
        'textAlign': 'center', 'margin': '10px'
    },
    multiple=False
)

app.layout = dbc.Container([
    html.H3("CSV 자동 분석 대시보드"),
    html.P("네이버 뉴스/카페, 유튜브, 혐오(Hate) 레이블 CSV를 자동 감지하여 시각화합니다."),
    UPLOAD,
    dcc.Store(id='store-df'),
    dcc.Store(id='store-schema'),

    html.Div(id='file-info', className='text-muted mb-2'),

    html.Div(id='analysis-area'),
], fluid=True)


# ──────────────────────────────────────────────────────────────────────────────
# 콜백: 파일 업로드 → DF 파싱/스키마 감지 저장
# ──────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output('store-df', 'data'),
    Output('store-schema', 'data'),
    Output('file-info', 'children'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename')
)
def on_upload(contents, filename):
    if contents is None:
        return None, None, ""
    try:
        df = parse_contents(contents, filename)
        schema = detect_schema(df)
        info = f"파일: {filename} · 행: {len(df)} · 열: {len(df.columns)} · 감지된 스키마: {schema}"
        # 대용량은 일부만 저장할 수도 있으나 여기서는 전체 저장
        return df.to_json(date_format='iso', orient='split'), schema, info
    except Exception as e:
        return None, None, f"업로드/파싱 오류: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# 콜백: DF/스키마 → 분석 실행 및 렌더
# ──────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output('analysis-area', 'children'),
    Input('store-df', 'data'),
    Input('store-schema', 'data')
)
def render_analysis(df_json, schema):
    if df_json is None or schema is None:
        return dbc.Alert("CSV를 업로드하면 자동으로 분석합니다.", color='secondary')

    df = pd.read_json(df_json, orient='split')

    if schema == 'unknown':
        return dbc.Alert("알 수 없는 스키마입니다. 컬럼 구성을 확인해주세요.", color='warning')

    # 스키마별 분석 실행
    if schema == 'naver_news_article':
        result = analyze_naver_news_article(df)
    elif schema == 'naver_news_statistics':
        result = analyze_naver_news_statistics(df)
    elif schema == 'naver_news_reply':
        result = analyze_naver_news_reply(df)
    elif schema == 'naver_news_rereply':
        result = analyze_naver_news_rereply(df)
    elif schema == 'naver_cafe_article':
        result = analyze_naver_cafe_article(df)
    elif schema == 'naver_cafe_reply':
        result = analyze_naver_cafe_reply(df)
    elif schema == 'youtube_article':
        result = analyze_youtube_article(df)
    elif schema == 'youtube_reply':
        result = analyze_youtube_reply(df)
    elif schema == 'youtube_rereply':
        result = analyze_youtube_rereply(df)
    elif schema in ('hate_hate','hate_labels','hate_clean'):
        result = analyze_hate(df, schema)
    else:
        return dbc.Alert("지원하지 않는 스키마로 감지되었습니다.", color='warning')

    # 결과 렌더링(카드+탭)
    graphs = [
        dbc.Card([
            dbc.CardHeader(subtitle),
            dbc.CardBody(dcc.Graph(figure=fig))
        ], className='mb-3')
        for subtitle, fig in result.figures
    ]

    tables = [
        dbc.Card([
            dbc.CardHeader(subtitle),
            dbc.CardBody(dash_table.DataTable(
                data=tbl.to_dict('records'),
                columns=[{"name": c, "id": c} for c in tbl.columns],
                page_size=15,
                filter_action='native',
                sort_action='native',
                export_format='csv',
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left'}
            ))
        ], className='mb-3')
        for subtitle, tbl in result.tables
    ]

    return html.Div([
        html.H4(result.title),
        html.P(result.description),
        html.Hr(),
        html.H5("그래프"),
        *graphs,
        html.Hr(),
        html.H5("표 (CSV 다운로드 가능)"),
        *tables
    ])


# ──────────────────────────────────────────────────────────────────────────────
# 엔트리포인트
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8050, debug=False)