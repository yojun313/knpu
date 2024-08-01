from rich.console import Console
from rich.live import Live
from rich.table import Table
import time

console = Console()

def generate_table(elements):
    table = Table(title="Real-time List Count")

    table.add_column("Metric", style="bold magenta")
    table.add_column("Value", style="bold cyan")

    table.add_row("List Count", str(len(elements)))

    return table

elements = []

# refresh_per_second를 높여서 더 자주 업데이트하도록 설정
with Live(generate_table(elements), refresh_per_second=10, console=console) as live:
    for i in range(1, 21):
        elements.append(i)  # 외부에서 리스트에 요소 추가
        live.update(generate_table(elements))
        time.sleep(0.5)
