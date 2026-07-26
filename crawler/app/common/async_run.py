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
