from datetime import datetime, timedelta

def split_years(start_date, end_date):
    # 문자열로 된 날짜를 datetime 객체로 변환
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")

    current = start
    results = []

    while current <= end:
        # 현재 연도의 첫 날 설정
        if current == start:
            start_of_year = current
        else:
            start_of_year = datetime(current.year, 1, 1)
        
        # 현재 연도의 마지막 날
        end_of_year = datetime(current.year, 12, 31)
        
        if end_of_year > end:
            end_of_year = end
        
        # 연도별 시작과 종료 날짜 저장
        results.append((start_of_year.strftime("%Y%m%d"), end_of_year.strftime("%Y%m%d")))
        
        # 다음 연도의 첫 날 설정
        current = end_of_year + timedelta(days=1)

    return results

# 사용 예
start_date = '20010117'
end_date = '20231207'
yearly_splits = split_years(start_date, end_date)

print(yearly_splits)

# 결과 출력
for start, end in yearly_splits:
    print(start, end)
