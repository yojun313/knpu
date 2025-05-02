import requests
import urllib.parse

params = {
  "cluster_rank": "15",
  "de": "2023.01.10",
  "ds": "2023.01.01",
  "eid": "",
  "field": "0",
  "force_original": "",
  "is_dts": "0",
  "is_sug_officeid": "0",
  "mynews": "0",
  "news_office_checked": "",
  "nlu_query": "",
  "nqx_theme": {
    "theme": {
      "main": {
        "name": "shopping",
        "source": "NLU",
        "score": "0.912155"
      }
    }
  },
  "nso": "so:r,p:from20230101to20230110,a:all",
  "nx_and_query": "",
  "nx_search_hlquery": "",
  "nx_search_query": "",
  "nx_sub_query": "",
  "office_category": "",
  "office_section_code": "0",
  "office_type": "0",
  "pd": "3",
  "photo": "0",
  "query": "아이패드",
  "query_original": "",
  "rev": "0",
  "service_area": "",
  "sm": "tab_smr",
  "sort": "0",
  "spq": "0",
  "ssc": "tab.news.all",
  "start": "11"
}

# 파라미터를 쿼리 문자열로 변환
query_string = urllib.parse.urlencode(params)

url = f"https://s.search.naver.com/p/newssearch/3/api/tab/more?{query_string}"
res = requests.get(url)
print(res.text)