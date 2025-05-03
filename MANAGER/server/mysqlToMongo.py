from pymongo import MongoClient
import ast
import pandas as pd
import os
import json

csv_path = os.path.join(os.path.dirname(__file__), "crawl_db.csv")
df = pd.read_csv(
    csv_path,
    encoding='utf-8',
    header=None,
    on_bad_lines='warn'
)


# 4. 각 행을 JSON 문서(dict)로 변환
json_documents = df.to_dict(orient="records")

dbs = []


for document in json_documents:
    del document['id']
    dbs.append(document)

ip = "121.152.225.232"
# 1. MongoDB 연결 설정
client = MongoClient(f"mongodb://{ip}:27017")
db = client["manager"]
collection = db["versions"]

collection.insert_many(json_documents)
