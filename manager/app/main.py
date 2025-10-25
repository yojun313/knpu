from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QFontDatabase, QPalette, QColor
import os
import sys
import platform
from config import VERSION
from windows.splash_window import SplashDialog
from PyQt5.QtCore import QCoreApplication, Qt
from core.setting import get_setting, set_setting
from ui.style import theme_option
from PyQt5.QtGui import QIcon
from config import ASSETS_PATH


def build_app():
    os.environ.update({
        "QT_DEVICE_PIXEL_RATIO": "0",
        "QT_AUTO_SCREEN_SCALE_FACTOR": "1",
        "QT_SCREEN_SCALE_FACTORS": "1",
        "QT_SCALE_FACTOR": "1"
    })

    # High DPI 스케일링 활성화
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu" 
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    QCoreApplication.setAttribute(Qt.AA_Use96Dpi, True)

    app = QApplication([])
    app.setApplicationName("MANAGER")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("PAILAB")
    app.setWindowIcon(QIcon(os.path.join(ASSETS_PATH, 'exe_icon.png')))
    
    if platform.system() == "Windows":
        app.setStyle("WindowsVista")
    elif platform.system() == "Darwin":
        app.setStyle("Fusion")   # macOS도 Fusion이 안정적
    else:
        app.setStyle("Fusion")

    # 글꼴
    font_path = os.path.join(ASSETS_PATH, "malgun.ttf")
    # 등록
    font_id = QFontDatabase.addApplicationFont(font_path)
    if font_id != -1:
        family = QFontDatabase.applicationFontFamilies(font_id)[0]
        font = QFont(family)
        font.setStyleStrategy(QFont.PreferAntialias)
        app.setFont(font)
    else:
        print("⚠️ 폰트 로딩 실패:", font_path)

    if platform.system() == 'Windows':
        theme = get_setting("Theme", "default")
    else:
        def is_mac_dark_mode():
            """
            macOS 시스템 설정에서 다크 모드 활성화 여부 확인
            """
            try:
                import subprocess
                # macOS 명령어를 사용하여 다크 모드 상태를 가져옴
                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                # "Dark"가 반환되면 다크 모드가 활성화됨
                #return "Dark" in result.stdout
                return False
            except Exception as e:
                # 오류가 발생하면 기본적으로 라이트 모드로 간주
                return False
        theme = 'dark' if is_mac_dark_mode() else 'default'
        set_setting("Theme", theme)

    app.setStyleSheet(theme_option[theme])
    
    palette = QPalette()
    if theme == 'default':
        palette.setColor(QPalette.Window, QColor(240, 240, 240))          # 전체 배경
        palette.setColor(QPalette.WindowText, Qt.black)                   # 윈도우 텍스트
        palette.setColor(QPalette.Base, Qt.white)                         # 입력창, 리스트 배경
        palette.setColor(QPalette.AlternateBase, QColor(225, 225, 225))   # 교차 줄 배경
        palette.setColor(QPalette.Text, Qt.black)                         # 일반 텍스트
        palette.setColor(QPalette.Button, QColor(240, 240, 240))          # 버튼 배경
        palette.setColor(QPalette.ButtonText, Qt.black)                   # 버튼 텍스트
        palette.setColor(QPalette.BrightText, Qt.red)                     # 경고 강조 텍스트
        palette.setColor(QPalette.Highlight, QColor(76, 163, 224))        # 하이라이트 색 (파란색)
        palette.setColor(QPalette.HighlightedText, Qt.white)              # 하이라이트된 글씨 색
    else:
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(142, 45, 197).lighter())
        palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    return app, theme


def main():
    app, theme = build_app()
    splash = SplashDialog(version=VERSION, theme=theme)
    splash.show()
    splash.updateStatus("Loading System Libraries")

    from windows.main_window import MainWindow
    window = MainWindow(splash)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
