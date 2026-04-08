from enum import Enum   

# TODO - mongoDB 크롤러 데이터 문서 status 필드 아래의 정수값으로 저장
# 사용 예) CrawlStatus.COMPLETED.value -> 0
class CrawlStatus(Enum):
    COMPLETED = 0
    RUNNING = 1
    STOPPED = 2
    ERROR = 3