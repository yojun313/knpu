import json, re

def parse_naver_query(query):
    # 큰따옴표 감싼 문구 추출
    quoted_terms = re.findall(r'"[^"]+"', query)
    
    # 기본 분리 (큰따옴표는 제외하고 나머지 처리)
    terms = query.split()

    # +, - 단어 추출
    and_terms = [term[1:] for term in terms if term.startswith('+')]
    sub_terms = [term[1:] for term in terms if term.startswith('-')]

    for qt in quoted_terms:
        and_terms.append(qt)

    # OR(|) 처리
    if "|" in query:
        nx_search_query = query
    else:
        # 1️⃣ 큰따옴표만 있을 경우
        if re.fullmatch(r'"[^"]+"', query.strip()):
            nx_search_query = query.replace('"', '')
        else:
            # 2️⃣ 일반 단어만 추출
            normal_terms = [
                t for t in terms if not (t.startswith('+') or t.startswith('-') or '"' in t)
            ]
            nx_search_query = " ".join([t.replace('"', '') for t in normal_terms]) if normal_terms else ""
            # 3️⃣ 만약 큰따옴표만 있었는데 split에서 잘렸을 경우 보정
            if not nx_search_query and quoted_terms:
                nx_search_query = quoted_terms[0].replace('"', '')

    # nx_and_query: 큰따옴표 + +단어
    nx_and_query = " ".join(and_terms) if and_terms else ""

    # nx_sub_query: -단어
    nx_sub_query = " ".join(sub_terms) if sub_terms else ""

    # nx_search_hlquery: 오직 "..." 단독 입력일 때만 유지
    stripped_query = query.strip()
    if re.fullmatch(r'"[^"]+"', stripped_query):
        nx_search_hlquery = stripped_query
    else:
        nx_search_hlquery = ""

    query_params = {
        "nx_and_query": nx_and_query,
        "nx_search_hlquery": nx_search_hlquery,
        "nx_search_query": nx_search_query,
        "nx_sub_query": nx_sub_query,
    }

    print(json.dumps(query_params, ensure_ascii=False, indent=4))
    return query_params


if __name__ == "__main__":
    input_query = input("Enter your query: ")
    parse_naver_query(input_query)
