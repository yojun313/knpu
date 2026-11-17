import pandas as pd
import os
import threading

# 테이블(CSV)별로 지금까지 기록한 행 수. 하루 치 수집을 마칠 때마다 이 값을 DB에 체크포인트로
# 남기고, 이어받기 때 그 행 수 이후(=완료되지 못한 날짜)의 행을 잘라낸다.
# 키는 CSV 파일의 절대 경로다.
_row_counts = {}
_row_counts_lock = threading.Lock()


def _csv_path(tablePath, tableName):
    return os.path.abspath(os.path.join(tablePath, f"{tableName}.csv"))


def setRowCount(tablePath, tableName, count):
    with _row_counts_lock:
        _row_counts[_csv_path(tablePath, tableName)] = count


def getRowCounts(tablePath):
    """tablePath 폴더 안 테이블들의 기록된 행 수 {테이블명: 행 수}."""
    folder = os.path.abspath(tablePath)
    with _row_counts_lock:
        return {
            os.path.basename(path)[: -len(".csv")]: count
            for path, count in _row_counts.items()
            if os.path.dirname(path) == folder
        }


def makeCSV(tablePath, tableName, columns):
    df = pd.DataFrame(columns=columns)
    file_path = os.path.join(tablePath, tableName + ".csv")
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    setRowCount(tablePath, tableName, 0)


def addToCSV(tablePath, tableName, data_list, columns):
    df_new = pd.DataFrame(data_list, columns=columns)
    file_path = os.path.join(tablePath, f"{tableName}.csv")

    write_header = not os.path.exists(file_path)
    df_new.to_csv(file_path, mode="a", header=write_header, index=False)

    key = _csv_path(tablePath, tableName)
    with _row_counts_lock:
        _row_counts[key] = _row_counts.get(key, 0) + len(df_new)
