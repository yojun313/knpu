from transformers import pipeline

# GPU를 사용하려면 device=0 설정
summarizer = pipeline(
    "summarization",
    model="sshleifer/distilbart-cnn-12-6",
    revision="a4f8f3e",
    device=0  # GPU를 사용
)

# 요약 작업
article = "이탈리아 베네치아(베니스)시는 문화유적·생태계 보호, 과잉관광 등을 이유로 크루즈선 입항 금지라는 특단의 조처를 내렸고(2021년), 네덜란드 암스테르담시는 크루즈를 ‘환경을 오염하는 관광 방식’으로 규정해 입항을 단계적으로 줄여 2035년까지 전면 폐지하기로 선언했다(2023년).1 스페인 바르셀로나시도 크루즈선 규제에 동참했다(2023년). 한국에선 제주도 시민단체들이 성명을 내어 크루즈의 환경오염 문제에 대한 대응을 제주도정에 요구했다(2023년). 2024년 8월에는 기후단체 ‘멸종저항’의 네덜란드지부가 화석연료 남용을 이유로 크루즈선 입항을 몸으로 막는 시위를 하는 등 시민사회의 반대 여론과 압박도 커지고 있다."
summary = summarizer(article, max_length=100, min_length=30, do_sample=False)
print(summary[0]['summary_text'])
