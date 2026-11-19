import re

# 따옴표 구문("..."), 앞에 +/-가 붙은 따옴표 구문, 그 외 공백으로 나뉜 단어
_TOKEN = re.compile(r'[+-]?"[^"]+"|\S+')


def parse_naver_query(query):
    """상세검색 연산자가 든 검색어를 네이버 검색이 쓰는 nx_* 파라미터로 나눈다.

    네이버 검색 페이지가 같은 검색어로 직접 만드는 값과 같아지도록 맞췄다.
      - "구문": 정확히 일치 → nx_and_query에 따옴표째로 들어간다
      - +단어 / +"구문": 반드시 포함 → nx_and_query
      - -단어 / -"구문": 제외 → nx_sub_query
      - 단어 | 단어: 하나 이상 포함 → nx_search_query에 그대로 남는다
      - 나머지 일반 단어 → nx_search_query (없으면 첫 포함 조건의 내용)
    연산자가 하나도 없으면(잘못 쓴 |, 짝이 안 맞는 따옴표 포함) 상세검색 없이
    query만으로 검색하도록 전부 빈 값을 돌려준다.
    """
    plain, and_terms, sub_terms = [], [], []
    for tok in _TOKEN.findall(query):
        if len(tok) > 2 and tok[0] == '"' and tok[-1] == '"':
            and_terms.append(tok)
        elif len(tok) > 1 and tok[0] == "+":
            and_terms.append(tok[1:])
        elif len(tok) > 1 and tok[0] == "-":
            sub_terms.append(tok[1:])
        else:
            plain.append(tok)

    # 단독 | 가 아니면(앞뒤에 붙여 쓴 경우) 네이버도 OR 연산자로 보지 않는다
    has_or = "|" in plain
    if not (and_terms or sub_terms or has_or):
        return {
            "nx_and_query": "",
            "nx_search_hlquery": "",
            "nx_search_query": "",
            "nx_sub_query": "",
        }

    # 앞뒤에 남거나 연달아 나온 | 는 버린다 ('"A" | B' → 'B')
    search_terms = []
    for tok in plain:
        if tok == "|" and (not search_terms or search_terms[-1] == "|"):
            continue
        search_terms.append(tok)
    while search_terms and search_terms[-1] == "|":
        search_terms.pop()

    nx_search_query = " ".join(search_terms)
    if not nx_search_query and and_terms:
        nx_search_query = and_terms[0].strip('"')

    return {
        "nx_and_query": " ".join(and_terms),
        # 네이버 검색 페이지는 이 값을 비워서 보낸다(결과에 영향 없음, 강조 표시용)
        "nx_search_hlquery": "",
        "nx_search_query": nx_search_query,
        "nx_sub_query": " ".join(sub_terms),
    }


def naver_query_text(query):
    """검색창에 보낼 검색어. 제외어(-단어)로 시작하면 뒤로 옮긴다.

    블로그·카페 검색은 검색어가 제외어로 시작하면 결과를 하나도 돌려주지 않는다
    ('-입학 경찰대학' → 0건, '경찰대학 -입학' → 정상). 순서만 바꾸므로 의미는 같다.
    """
    tokens = _TOKEN.findall(query)
    lead = 0
    while lead < len(tokens) and len(tokens[lead]) > 1 and tokens[lead][0] == "-":
        lead += 1
    if lead == 0 or lead == len(tokens):
        return query
    return " ".join(tokens[lead:] + tokens[:lead])
