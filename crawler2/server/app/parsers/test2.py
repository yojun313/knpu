import requests
import re
from urllib.parse import urlparse, parse_qs

def get_naver_blog_tokens(query):
    # 1. 최초 검색 URL (질문자님이 주신 링크 구조 활용)
    base_url = "https://search.naver.com/search.naver"
    params = {
        "ssc": "tab.blog.all",
        "query": query,
        "sm": "tab_dgs",
        "qdt": "1"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    print(f"[{query}] 최초 HTML 페이지 가져오는 중...")
    response = requests.get(base_url, params=params, headers=headers)
    
    if response.status_code != 200:
        print("페이지 요청 실패")
        return None

    html = response.text

    # 2. 정규표현식으로 자바스크립트 내부에 숨겨진 다음 페이지 API URL 통째로 추출
    # url: "https://s.search.naver.com/p/review/50/search.naver?..." 형태를 캡처
    pattern = r'url:\s*"(https://s\.search\.naver\.com/p/review/50/search\.naver\?[^"]+)"'
    match = re.search(pattern, html)

    if not match:
        print("API URL 패턴을 찾을 수 없습니다.")
        return None

    next_page_url = match.group(1)
    print("✅ 자바스크립트에서 2페이지 API URL 추출 성공!")

    # 3. 추출한 URL을 파싱하여 암호화 키들만 쏙 빼내기
    parsed_url = urlparse(next_page_url)
    query_params = parse_qs(parsed_url.query)

    try:
        tokens = {
            "enlu_query": query_params['enlu_query'][0],
            "enqx_theme": query_params['enqx_theme'][0],
            "equery": query_params['equery'][0]
        }
        return tokens
    except KeyError as e:
        print(f"파라미터 추출 실패 (키 누락): {e}")
        return None

# --- 실행 및 페이징 테스트 ---
if __name__ == "__main__":
    search_keyword = '"경찰대" - 변호사'
    
    # 1단계: 최초 페이지에서 토큰 발급 (스크래핑)
    api_tokens = get_naver_blog_tokens(search_keyword)

    if api_tokens:
        print("\n[추출된 암호화 토큰]")
        print(f"enlu_query: {api_tokens['enlu_query'][:20]}...")
        print(f"enqx_theme: {api_tokens['enqx_theme'][:20]}...")
        
        print("\n🚀 본격적인 페이징 수집을 시작합니다...")
        
        # 2단계: 추출한 토큰을 재사용하여 API 반복 호출 (원하는 페이지 수만큼)
        api_base_url = "https://s.search.naver.com/p/review/50/search.naver"
        
        # 반복문으로 2페이지부터 5페이지까지 긁어보는 예시
        for page_num in range(2, 6):
            start_num = (page_num - 1) * 30 + 1 # 1, 31, 61, 91...
            
            # API 호출용 파라미터 조립 (질문자님이 발견하신 파라미터 구조 그대로 적용)
            api_params = {
                "ssc": "tab.blog.all",
                "query": search_keyword,
                "api_type": "8",
                "page": str(page_num),
                "start": str(start_num),
                # 여기서 추출해둔 키를 그대로 끼워 넣습니다.
                "enlu_query": api_tokens['enlu_query'],
                "enqx_theme": api_tokens['enqx_theme'],
                "equery": api_tokens['equery']
                # (그 외 lgl_lat 등 부가적인 위치 정보 파라미터는 생략해도 보통 잘 동작합니다. 
                # 만약 막히면 추출된 전체 URL의 파라미터를 그대로 복사해서 쓰시면 됩니다.)
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": f"https://search.naver.com/search.naver?where=view&query={search_keyword}"
            }

            api_response = requests.get(api_base_url, params=api_params, headers=headers)
            
            if api_response.status_code == 200:
                print(f"-> {page_num}페이지 (start={start_num}) 데이터 수집 성공! (응답 길이: {len(api_response.text)})")
                # 여기서 JSON 파싱 및 데이터 저장 로직 구현
            else:
                print(f"-> {page_num}페이지 수집 실패: HTTP {api_response.status_code}")