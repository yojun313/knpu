import requests
import re
import urllib

def extract_blogurls(text):
    # 정규식 패턴 정의
    pattern = r'https://blog\.naver\.com/[a-zA-Z0-9_-]+/\d+'

    # 정규식으로 모든 매칭되는 패턴 찾기
    urls = re.findall(pattern, text)
    urls = list(dict.fromkeys(urls))
    
    return urls

def extract_nexturl(text):
    # 정규식 패턴 정의
    pattern = r'https://s\.search\.naver\.com/p/review[^"]*'

    # 정규식으로 매칭되는 패턴 찾기
    match = re.search(pattern, text)

    if match:
        return match.group(0)
    else:
        return None

startDate = '20230102'
endDate = '20230202'
keyword = "테러 +예고"
keyword = urllib.parse.quote_plus(keyword)

api_url = f"https://s.search.naver.com/p/review/48/search.naver?ssc=tab.blog.all&api_type=8&query={keyword}&start=1&ac=0&aq=0&spq=0&sm=tab_opt&nso=so%3Add%2Cp%3Afrom{startDate}to{endDate}&prank=30&ngn_country=KR&lgl_rcode=15200104&fgn_region=&fgn_city=&lgl_lat=36.7512&lgl_long=126.9629&abt=&retry_count=0"
response = requests.get(api_url)
json_text = response.text
urlList = extract_blogurls(json_text)
nexturl = extract_nexturl(json_text)

for url in urlList:
    print(url)
    
print('\n\n')

print(nexturl)