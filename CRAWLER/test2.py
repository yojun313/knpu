import requests
import json
import re
from bs4 import BeautifulSoup

# API URL 및 파라미터 설정
api_url = "https://s.search.naver.com/p/newssearch/search.naver"

params = {
    "de": "2023.01.01",
    "ds": "2024.01.04",
    "eid": "",
    "field": "0",
    "force_original": "",
    "is_dts": "0",
    "is_sug_officeid": "0",
    "mynews": "0",
    "news_office_checked": "",
    "nlu_query": "",
    "nqx_theme": "",
    "nso": "so:r,p:from20240801to20240802,a:all",
    "nx_and_query": "",
    "nx_search_hlquery": "",
    "nx_search_query": "",
    "nx_sub_query": "",
    "office_category": "0",
    "office_section_code": "0",
    "office_type": "0",
    "pd": "3",
    "photo": "0",
    "query": "아이패드",
    "query_original": "",
    "service_area": "0",
    "sort": "2",
    "spq": "0",
    "start": "1",
    "where": "news_tab_api",
    "_callback": "jQuery112406351013586512539_1722744441764",
    "_": "1722744441765"
}

headers = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "ko-KR,ko;q=0.9",
    "referer": "https://search.naver.com/search.naver?where=news&query=%EA%B2%BD%EC%B0%B0%20%EC%9D%B8%EC%82%AC&sm=tab_opt&sort=2&photo=0&field=0&pd=3&ds=2024.08.01&de=2024.08.02&docid=&related=0&mynews=0&office_type=0&office_section_code=0&news_office_checked=&nso=so%3Ar%2Cp%3Afrom20240801to20240802&is_sug_officeid=0&office_category=0&service_area=0",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
}

# API 요청 보내기
try:
    response = requests.get(api_url, headers=headers, params=params, verify=False)
    print(f"응답 상태 코드: {response.status_code}")

    if response.status_code == 200:
        # 응답 텍스트 출력
        print("응답 텍스트:")
        print(response.text[:500])  # 응답 텍스트의 앞부분만 출력 (디버깅 목적)

        # JSONP에서 JSON 추출
        try:
            jsonp_text = response.text
            json_text = re.sub(r'^.*?\(', '', jsonp_text)[:-2]
            data = json.loads(json_text)

            # 추출된 JSON 출력
            print("추출된 JSON 데이터:")
            print(json.dumps(data, ensure_ascii=False, indent=4))

            # 뉴스 데이터 추출
            news_items = []
            for item in data["contents"]:
                soup = BeautifulSoup(item, 'html.parser')

                title_tag = soup.find('a', class_='news_tit')
                title = title_tag['title'] if title_tag else ''

                url = title_tag['href'] if title_tag else ''

                source_tag = soup.find('a', class_='info press')
                source = source_tag.text.strip() if source_tag else ''

                date_tag = soup.find('span', class_='info')
                date = date_tag.text.strip() if date_tag else ''

                description_tag = soup.find('a', class_='api_txt_lines dsc_txt_wrap')
                description = description_tag.text.strip() if description_tag else ''

                news_data = {
                    'title': title,
                    'url': url,
                    'date': date,
                    'source': source,
                    'description': description
                }
                news_items.append(news_data)

            # JSON 파일로 저장
            output_file = 'news.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(news_items, f, ensure_ascii=False, indent=4)

            print(f"뉴스 데이터를 {output_file} 파일로 저장했습니다.")

            # JSON 파일을 다시 읽어들여 출력
            with open(output_file, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                print("저장된 JSON 파일 내용:")
                print(json.dumps(loaded_data, ensure_ascii=False, indent=4))

            # 뉴스 개수 확인
            news_count = len(news_items)
            print(f"수집된 뉴스 개수: {news_count}")

        except Exception as e:
            print("JSON 데이터 처리 중 오류 발생:", e)

    else:
        print("API 요청에 실패했습니다.")
        print(f"응답 내용: {response.text}")

except requests.exceptions.SSLError as ssl_error:
    print(f"SSL 오류 발생: {ssl_error}")
except Exception as e:
    print(f"요청 중 오류 발생: {e}")
