from PySide6 import QtWebEngineWidgets
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase, QPalette, QColor
from PySide6.QtCore import Qt, QSharedMemory
import os
import sys
from config import VERSION
from windows.splash_window import SplashDialog
from core.setting import get_setting, set_setting
from ui.style import theme_option
from PySide6.QtGui import QIcon, QGuiApplication
from config import ASSETS_PATH
from packaging import version

os.environ["QT_LOGGING_RULES"] = "*.warning=false"


def build_app():
    if version.parse(VERSION) < version.parse(get_setting("LastVersion")):
        set_setting("LastVersion", VERSION)

    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"

    if sys.platform == "win32":
        os.environ["QT_USE_PHYSICAL_DPI"] = "1"
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            "--enable-gpu-rasterization "
            "--enable-zero-copy "
            "--disable-gpu-driver-bug-workarounds "
            "--force-device-scale-factor=1"
        )

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("MANAGER")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("PAILAB")
    app.setWindowIcon(QIcon(os.path.join(ASSETS_PATH, "exe_icon.png")))
    app.setStyle("Fusion")

    # 글꼴
    font_path = os.path.join(ASSETS_PATH, "malgun.ttf")
    font_id = QFontDatabase.addApplicationFont(font_path)
    if font_id != -1:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app_font = QFont(families[0], 10)
            app_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
            app_font.setStyleStrategy(
                QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
            )
            app.setFont(app_font)

    theme = get_setting("Theme", "default")
    app.setStyleSheet(theme_option[theme])

    palette = QPalette()
    if theme == "default":
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


def set_windows_dpi_awareness():
    """Windows에서 Per-Monitor DPI v2 설정"""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def main():
    set_windows_dpi_awareness()
    shared_memory = QSharedMemory("PAILAB_MANAGER_UNIQUE_KEY")
    if not shared_memory.create(1):
        if shared_memory.attach():
            print("프로그램이 이미 실행 중입니다.")
            sys.exit(0)
        else:
            shared_memory.detach()
            if not shared_memory.create(1):
                sys.exit(0)

    app, theme = build_app()

    splash = SplashDialog(version=VERSION, theme=theme)
    splash.show()
    QApplication.processEvents()
    splash.updateStatus("Loading System Libraries")

    from windows.main_window import MainWindow

    window = MainWindow(splash)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
