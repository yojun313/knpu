import requests
import re
response = requests.get('https://s.search.naver.com/p/newssearch/search.naver?de=2024.07.14&ds=2024.07.14&eid=&field=0&force_original=&is_dts=0&is_sug_officeid=0&mynews=0&news_office_checked=&nlu_query=&nqx_theme=&nso=%26nso%3Dso%3Add%2Cp%3Afrom20240714to20240714%2Ca%3Aall&nx_and_query=&nx_search_hlquery=&nx_search_query=&nx_sub_query=&office_category=0&office_section_code=0&office_type=0&pd=3&photo=0&query=%EC%98%AC%EB%A6%BC%ED%94%BD&query_original=&service_area=0&sort=1&spq=0&start=121&where=news_tab_api&nso=so:dd,p:from20240714to20240714,a:all?de=2024.07.14&ds=2024.07.14&eid=&field=0&force_original=&is_dts=0&is_sug_officeid=0&mynews=0&news_office_checked=&nlu_query=&nqx_theme=&nso=so%3Ar%2Cp%3Afrom20240801to20240802%2Ca%3Aall&nx_and_query=&nx_search_hlquery=&nx_search_query=&nx_sub_query=&office_category=0&office_section_code=0&office_type=0&pd=3&photo=0&query=%EC%98%AC%EB%A6%BC%ED%94%BD&query_original=&service_area=0&sort=1&spq=0&start=1&where=news_tab_api&_callback=jQuery112406351013586512539_1722744441764&_=1722744441765')
text = response.text
def extract_naver_urls(text):
    # 정규식 패턴 정의 (조금 더 일반화된 형태로)
    pattern = r'https://n\.news\.naver\.com/mnews/article/\d+/\d+\?sid=\d+'

    # 정규식으로 모든 매칭되는 패턴 찾기
    urls = re.findall(pattern, text)

    return urls


def extract_nexturl(text):
    # 정규식 패턴 정의
    pattern = r'https://s\.search\.naver\.com/p/newssearch/search\.naver\?.*'

    # 정규식으로 매칭되는 패턴 찾기
    match = re.search(pattern, text)

    if match:
        return match.group(0)[:-1].replace('}', '').replace(')', '')  # 매칭된 패턴과 그 뒤의 모든 문자열을 반환
    else:
        return None

result = extract_url_and_following_text(text)
print(result)


