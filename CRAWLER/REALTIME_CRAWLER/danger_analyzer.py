import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from transformers import pipeline, BertTokenizer, BertForSequenceClassification
import torch
import joblib
import os
import tkinter as tk
from tkinter import filedialog
import datetime
import sentencepiece

# DangerAnalyzer 모듈 생성
# 모듈 이름: danger_analyzer.py
# 함수 이름: train_model(), analyze_risk()

# 전역으로 로드하여 여러 함수에서 재사용할 수 있도록 변경
sentiment_analyzer = pipeline("sentiment-analysis", model="monologg/kobert", trust_remote_code=True)  # 한국어 텍스트 분석에 최적화된 KoBERT 모델 사용
tokenizer = BertTokenizer.from_pretrained('monologg/kobert', trust_remote_code=True)  # 한국어 특화 BERT 모델인 KoBERT 사용
model = BertForSequenceClassification.from_pretrained('monologg/kobert', num_labels=2, trust_remote_code=True)  # 한국어 특화 BERT 모델인 KoBERT 사용

# 1. 학습을 위한 함수 정의
# 이 함수는 데이터를 받아 TF-IDF와 LDA를 학습시킨 모델을 저장한다.
def train_model():
    # 사용자에게 여러 파일 선택 창 제공
    root = tk.Tk()
    root.withdraw()  # GUI 창 숨기기
    file_paths = filedialog.askopenfilenames(title="학습에 사용할 CSV 파일을 선택하세요", filetypes=[("CSV Files", "*.csv")])
    
    if not file_paths:
        print("파일을 선택하지 않았습니다. 학습을 종료합니다.")
        return
    
    # 여러 CSV 파일을 읽어 하나의 데이터프레임으로 결합 (대용량 파일을 처리하기 위해 청크 단위로 처리)
    data_frames = []
    for file_path in file_paths:
        for chunk in pd.read_csv(file_path, chunksize=1000):
            data_frames.append(chunk)
    data = pd.concat(data_frames, ignore_index=True)
    
    # 데이터의 본문 컬럼 이름 통일 ('Article Text')
    content_column = 'Article Text'
    if content_column not in data.columns:
        raise ValueError("CSV 파일에 본문 데이터를 포함하는 'Article Text' 컬럼이 없습니다.")
    
    # NaN 값을 빈 문자열로 대체하고, 빈 문자열 또는 공백만 있는 행 제거
    data = data.assign(**{content_column: data[content_column].fillna('')})
    data = data[data[content_column].str.strip() != '']
    
    # TF-IDF 학습
    vectorizer = TfidfVectorizer(max_features=1000, stop_words=None)
    X = vectorizer.fit_transform(data[content_column])
    
    # LDA 학습
    lda = LatentDirichletAllocation(n_components=5, random_state=42)
    lda.fit(X)
    
    # 현재 시간 기반 폴더 생성 및 모델 저장
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    folder_name = f"trained_model_{timestamp}"
    os.makedirs(folder_name, exist_ok=True)
    joblib.dump(vectorizer, os.path.join(folder_name, 'tfidf_vectorizer.pkl'))
    joblib.dump(lda, os.path.join(folder_name, 'lda_model.pkl'))
    
    print(f"TF-IDF 및 LDA 모델 학습 완료 및 '{folder_name}' 폴더에 저장됨.")

# 2. 실시간 분석을 위한 함수 정의
# 이 함수는 실시간으로 데이터를 받아 위험도를 0에서 10 사이의 실수로 반환한다.
def analyze_risk(content):
    # 사용자에게 폴더 선택 창 제공
    root = tk.Tk()
    root.withdraw()  # GUI 창 숨기기
    folder_path = filedialog.askdirectory(title="모델이 저장된 폴더를 선택하세요")
    
    if not folder_path:
        print("폴더를 선택하지 않았습니다. 분석을 종료합니다.")
        return
    
    # 저장된 모델 불러오기
    vectorizer_path = os.path.join(folder_path, 'tfidf_vectorizer.pkl')
    lda_path = os.path.join(folder_path, 'lda_model.pkl')
    
    if not (os.path.exists(vectorizer_path) and os.path.exists(lda_path)):
        raise ValueError("선택한 폴더에 필요한 모델 파일(tfidf_vectorizer.pkl, lda_model.pkl)이 없습니다.")
    
    vectorizer = joblib.load(vectorizer_path)
    lda = joblib.load(lda_path)
    
    # TF-IDF 벡터화
    X = vectorizer.transform([content])
    
    # LDA 주제 확률 추정
    topic_distribution = lda.transform(X)[0]
    topic_risk_score = max(topic_distribution) * 10  # 주제의 위험도를 0-10 사이로 스케일링
    
    # 감정 분석을 통해 위험도 평가
    sentiment = sentiment_analyzer(content)[0]['label']
    if 'negative' in sentiment.lower():
        sentiment_risk_score = 7  # 부정적 감정일 경우 위험도를 높게 설정
    elif 'positive' in sentiment.lower():
        sentiment_risk_score = 1  # 긍정적 감정일 경우 위험도를 낮게 설정
    else:
        sentiment_risk_score = 4  # 중립적인 감정일 경우 중간 정도의 위험도 설정
    
    # BERT 기반 의도 분석을 통해 위험도 평가
    inputs = tokenizer(content, return_tensors='pt')
    outputs = model(**inputs)
    logits = outputs.logits
    intent_score = torch.softmax(logits, dim=1)[0][1].item() * 10  # 의도에 대한 위험도를 0-10 사이로 스케일링
    
    # 최종 위험도 계산 (주제 위험도, 감정 위험도, 의도 위험도를 결합)
    final_risk_score = (topic_risk_score + sentiment_risk_score + intent_score) / 3
    
    return round(final_risk_score, 2)

# 학습 데이터로 모델 학습
if __name__ == '__main__':
    train_model()

    # 실시간 분석 예시
    sample_content = ["이 글은 매우 위험한 행동을 예고하고 있습니다.", "내일 저녁 6시에 성수역에서 다 죽인다", "오늘 밤에 그냥 죽어버리려고", "내일 날씨 좋을 것 같다", "이 게임 재미있나요?"]
    print(sample_content[0])
    print(f"실시간 위험도 분석 결과: {analyze_risk(sample_content[0])}")
    print(sample_content[1])
    print(f"실시간 위험도 분석 결과: {analyze_risk(sample_content[1])}")
    print(sample_content[2])
    print(f"실시간 위험도 분석 결과: {analyze_risk(sample_content[2])}")
    print(sample_content[3])
    print(f"실시간 위험도 분석 결과: {analyze_risk(sample_content[3])}")
    print(sample_content[4])
    print(f"실시간 위험도 분석 결과: {analyze_risk(sample_content[4])}")

    # 주의 사항
    # 위 코드는 수집된 데이터와 함께 분석하는 코드로, 데이터의 크기에 따라 분석 시간이 길어질 수 있다.
    # 대규모 데이터의 경우, 분석 성능 향상을 위해 적절한 샘플링 또는 병렬 처리를 고려할 수 있다.
