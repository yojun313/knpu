import asyncio
import aiohttp


def speed_to_concurrency(speed) -> int:
    try:
        n = int(float(speed))
    except (TypeError, ValueError):
        n = 1
    return max(1, min(20, n))


async def run_with_concurrency(items, worker, concurrency: int):
    if not items:
        return
    semaphore = asyncio.Semaphore(concurrency)
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [worker(session, semaphore, item) for item in items]
        await asyncio.gather(*tasks, return_exceptions=True)
