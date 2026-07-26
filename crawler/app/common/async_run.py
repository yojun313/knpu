"""URL 목록을 수집한 뒤, 그 각각의 URL에 요청을 보내 기사/댓글을 가져오는 단계를
세마포어로 동시성을 제한한 비동기로 돌리기 위한 공용 유틸. 네이버 뉴스/블로그/카페 파서가
모두 같은 패턴(URL 수집은 동기, 본문/댓글 수집은 비동기)을 쓰므로 여기 한 곳에 모아둔다."""

import asyncio

import aiohttp


def speed_to_concurrency(speed) -> int:
    """크롤링 옵션의 '속도(1~10)' 값을 동시 요청 수로 변환한다."""
    try:
        n = int(float(speed))
    except (TypeError, ValueError):
        n = 1
    return max(1, min(20, n))


async def run_with_concurrency(items, worker, concurrency: int):
    """worker(session, semaphore, item) 코루틴을 concurrency만큼 동시에 실행한다."""
    if not items:
        return
    semaphore = asyncio.Semaphore(concurrency)
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [worker(session, semaphore, item) for item in items]
        await asyncio.gather(*tasks, return_exceptions=True)
