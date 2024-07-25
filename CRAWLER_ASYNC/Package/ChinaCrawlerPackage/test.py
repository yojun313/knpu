from datetime import datetime, timedelta
import calendar

def DateSplitter(start_date, end_date):
    # 날짜 문자열을 datetime 객체로 변환
    start = datetime.strptime(str(start_date), '%Y%m%d')
    end = datetime.strptime(str(end_date), '%Y%m%d')

    result = []
    current = start

    while current <= end:
        # 현재 날짜의 월의 마지막 날 계산
        _, last_day = calendar.monthrange(current.year, current.month)
        month_end = datetime(current.year, current.month, last_day)

        # 월의 마지막 날이 종료 날짜보다 크면 종료 날짜로 설정
        if month_end > end:
            month_end = end

        # 월의 시작일과 종료일 추가
        result.append([str(current.strftime('%Y%m%d')), str(month_end.strftime('%Y%m%d'))])

        # 다음 달의 첫 번째 날로 이동
        next_month = current.replace(day=28) + timedelta(days=4)  # 이 방법으로 다음 달로 이동
        current = next_month.replace(day=1)  # 다음 달의 첫 번째 날로 설정

    return result

# 테스트
print(DateSplitter(20230101, 20230110))
