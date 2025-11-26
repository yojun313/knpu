from PyQt6 import QtWebEngineWidgets
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase, QPalette, QColor
import os
import sys
import platform
from config import VERSION
from windows.splash_window import SplashDialog
from PyQt6.QtCore import QCoreApplication, Qt
from core.setting import get_setting, set_setting
from ui.style import theme_option
from PyQt6.QtGui import QIcon, QGuiApplication
from config import ASSETS_PATH
from packaging import version

def build_app():
    if version.parse(VERSION) < version.parse(get_setting("LastVersion")):
        set_setting("LastVersion", VERSION)
    
    os.environ.update({
        "QT_DEVICE_PIXEL_RATIO": "0",
        "QT_AUTO_SCREEN_SCALE_FACTOR": "1",
        "QT_SCREEN_SCALE_FACTORS": "1",
        "QT_SCALE_FACTOR": "1"
    })

    # High DPI 스케일링 활성화
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu" 
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

    app = QApplication(sys.argv)
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
    font_id = QFontDatabase.addApplicationFont(font_path)

    if font_id != -1:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            font = QFont(families[0])
            font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)  # ✅ 변경됨
            app.setFont(font)
        else:
            print("⚠️ 폰트 패밀리를 찾을 수 없음:", font_path)
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
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(225, 225, 225))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(76, 163, 224))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    else:
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(142, 45, 197).lighter())
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)

    return app, theme


def main():
    app, theme = build_app()
    splash = SplashDialog(version=VERSION, theme=theme)
    splash.show()
    splash.updateStatus("Loading System Libraries")

    from windows.main_window import MainWindow
    window = MainWindow(splash)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
