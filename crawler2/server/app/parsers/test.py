import requests
import json
import re
from user_agent import generate_navigator

def random_heador():
    navigator = generate_navigator()
    navigator = navigator['user_agent']
    return {"User-Agent": navigator}

def Request(url: str, headers=None, sleep: float = 0, **kwargs):
    if headers is None:
        headers = random_heador()
    params = kwargs.pop('params', None)

    return requests.get(
        url,
        headers=headers,
        params=params,
        verify=False,
        **kwargs
        )

def extract_newsurls(text):
    # 정규식 패턴 정의 (조금 더 일반화된 형태로)
    pattern = r'https://blog\.naver\.com/[a-zA-Z0-9_-]+/\d+'

    # 정규식으로 모든 매칭되는 패턴 찾기
    urls = re.findall(pattern, text)
    urls = list(dict.fromkeys(urls))

    return urls
            
def extract_nexturl(text):
    try:
        json_data = json.loads(text)
        if 'url' in json_data and json_data['url']:
            return json_data['url']
        else:
            return None
    except Exception as e:
        return None

url = "https://s.search.naver.com/p/review/50/search.naver"

# 핵심 헤더 설정
"""headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://search.naver.com/search.naver?where=view&query=%EA%B2%BD%EC%B0%B0%EB%8C%80",
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}
"""
# 요청 파라미터 (제공해주신 URL에서 핵심적인 것 위주로 구성)
params = {
    "query": "경찰대",
    "start": "1",
    "page": "1",
    "ssc": "tab.blog.all",
    "api_type": "8",
    "nso" : "so:r,p:from20260101to20260102",
    # 아래 값들은 실제 브라우저 네트워크 탭에서 실시간 값을 복사해야 합니다.
    #"enlu_query": "IggCANmDULivAAAAtdoURqXUdp9ygLuVMM8qJjRQR2lcS0I2uWjdRWojAIEqlvwfYIkM/JSbMePlrOj0WOU1x1lDSmSMxhAUh4YfpZ8PADfmUfCM1gbHmDtefEzBnXmIoteuR9ATwx1TxD+a/8B6eGOOjD35qN6NLOBGSqlpx1jSARv6f74eqBzQ4Mb8uNE4CBAQ1+vLKn9VXjdMz6Nx6JGASbhVQ843uvmgHrSvMbiRbC7OquNB50SCLS+dQW47hkDDPS5hQZHofvh4kcgIjMcWyshBAWzTSuSR5+VPxIUYo6RHCrc+Fc19YiqZzRi64ppm00xs6e1Rsq4i9TfM/3NlU9tIdYygdsUmBiQEJq1BX2PWzLMLy4IPeNPMlH5SHF57kYhBgpLfajgc8vjbP3PMiV7xcvBcTa79ZK1FP0nZFzLRPd7psCSOu4LH6P0BBGyQVjqRlZrwVrJ6Ztv8uaRR2cOvFd8CO3gukC+fW1SRpc3QDdXJCB6Mlu6k6WkKf91ihYelFiO/BFOcSlxjOe7wpPuFIotNr3MYStAMYCetQt2ezLL0Y5GU9DzFqLQkilpjeRegy+BW4l3saZfOdszuEisGt6qCyfGG3R3bwyx746Lws+/+h261hmyfsGQRn3tzAiBDF5HN9Zx2ZkWWlUp2oa8Qtnc06llY5PgK4Em12MN23HOxmCvWbQo=",
    #"enqx_theme": "IggCABqCULjvAAAAh/DtntZaiMLGh3DOFtIyqyhawT/RmEJoqBIeDZwybxC8ayW35x3PEVp091n0PqhO3IbC7WD8I+IgUVGV7Q2dNQ==",
    #"equery": "IggCACSCULgRAAAAMBLVzqVFN+0kPL9E1njzrA==",
    #"lgl_lat": "36.803708",
    #"lgl_long": "126.936100",
}

response = Request(url, params=params)

if response.status_code == 200:
    print("성공적으로 데이터를 가져왔습니다.")
    # 보통 JSON 형태나 JSONP(콜백 함수로 감싸진 텍스트) 형태로 응답이 옵니다.
    print(response.text[:500]) 
else:
    print(f"오류 발생: {response.status_code}")
    
json_text = response.text
urlList = []
            
while True:
    pre_urlList = extract_newsurls(json_text)
    for url in pre_urlList:
        if url not in urlList and 'book' not in url:
            urlList.append(url)

    nextUrl = extract_nexturl(json_text)
    if nextUrl is None:
        break
    else:
        api_url = nextUrl
        response = Request(api_url)
        response.raise_for_status()
        json_text = response.text