def parse_query(query):
    # 문자열을 공백으로 분리
    terms = query.split()

    # 첫 번째 단어를 nx_search_query에 할당
    if '+' in query or '-' in query:
        search_query = terms[0] if terms else ""
    if "|" in query:
        search_query = query
    else:
        search_query = " "

    # + 기호가 붙은 단어 찾기
    and_terms = [term[1:] for term in terms if term.startswith('+')]

    # - 기호가 붙은 단어 찾기
    sub_terms = [term[1:] for term in terms if term.startswith('-')]

    # 딕셔너리 반환
    query_params = {
        "nx_search_query": search_query,
        "nx_and_query": " ".join(and_terms) if and_terms else "",
        "nx_sub_query": " ".join(sub_terms) if sub_terms else "",
    }
    return query_params


print(parse_query("데이트 폭행"))
