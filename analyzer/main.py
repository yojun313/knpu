import sys
import os
import pandas as pd
from PyQt5.QtWidgets import QApplication, QFileDialog

# 로컬 pandasgui에서 show 함수 가져오기
from pandasgui.gui import show


def open_csv_from_dialog():
    """파일 탐색기에서 CSV 파일을 선택하고 DataFrame으로 불러옴"""
    app = QApplication(sys.argv)
    file_path, _ = QFileDialog.getOpenFileName(
        None,
        "CSV 파일 열기",
        "",
        "CSV Files (*.csv);;All Files (*)"
    )
    if not file_path:
        print("파일이 선택되지 않았습니다.")
        sys.exit()
    df = pd.read_csv(file_path)
    print(f"CSV 파일 로드 완료: {file_path}")
    return df


def open_csv_from_arg(path):
    """명령줄 인자로 받은 경로에서 CSV 파일을 불러옴"""
    if not os.path.isfile(path):
        print(f"❌ 파일을 찾을 수 없습니다: {path}")
        sys.exit(1)

    try:
        df = pd.read_csv(path)
        print(f"CSV 파일 로드 완료: {path}")
        return df
    except Exception as e:
        print(f"❌ CSV 파일 로드 중 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # 명령줄 인자 있는 경우 -> 바로 열기
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        df = open_csv_from_arg(csv_path)
    else:
        # 인자 없는 경우 -> 파일 탐색기 열기
        df = open_csv_from_dialog()

    # pandasgui로 GUI 띄우기
    gui = show(df, settings={'block': True})
