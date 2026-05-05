from fastapi import APIRouter
import csv
import os
from collections import defaultdict

router = APIRouter()

csv_path = os.path.join(os.path.dirname(__file__), '..', 'forms', '경찰청_전국 경찰서 명칭 및 주소.csv')

@router.get("/stations")
def get_police_stations():
    temp_result = defaultdict(list)

    with open(csv_path, newline="", encoding="cp949") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sido = row["시도경찰청"]
            name = row["경찰서명칭"]
            temp_result[sido].append({"name": name})

    sorted_result = {}
    for sido in sorted(temp_result.keys()):
        sorted_result[sido] = sorted(temp_result[sido], key=lambda x: x["name"])

    return sorted_result