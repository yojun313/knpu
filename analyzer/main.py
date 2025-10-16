import sys
import pandas as pd
from PyQt5.QtWidgets import QApplication, QFileDialog

# 로컬 모듈에서 pandasgui.show 가져오기
# analyzer 폴더 안의 gui.py에 show 함수가 정의되어 있다면 아래와 같이 import
from pandasgui.gui import show

def open_csv_file():
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

if __name__ == "__main__":
    df = open_csv_file()
    # 로컬 pandasgui의 show() 함수로 GUI 띄우기
    gui = show(df, settings={'block': True})
