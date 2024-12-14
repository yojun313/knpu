from PyQt5.QtWidgets import QWidget, QShortcut, QVBoxLayout, \
    QHBoxLayout, QLabel, QDialog, QLineEdit, QMessageBox, \
    QPushButton, QStackedWidget, QListWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence, QFont
from datetime import datetime
import platform
import os

class Manager_Setting(QDialog):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setWindowTitle("Settings")
        self.resize(800, 400)

        # 메인 레이아웃 생성
        main_layout = QVBoxLayout()  # QVBoxLayout으로 변경하여 아래쪽에 버튼 섹션 추가 가능

        # 상단 레이아웃 (카테고리 목록과 설정 페이지)
        content_layout = QHBoxLayout()

        # 왼쪽: 카테고리 목록
        self.category_list = QListWidget()
        self.category_list.addItem("앱 설정")
        self.category_list.addItem("DB 설정")
        self.category_list.addItem("정보")
        self.category_list.addItem("도움말")  # Help 섹션 추가

        self.category_list.currentRowChanged.connect(self.display_category)
        self.category_list.setCurrentRow(0)  # 첫 번째 항목을 기본 선택

        # 오른쪽: 설정 내용 (Stacked Widget)
        self.stacked_widget = QStackedWidget()

        # 앱 설정 페이지 추가
        self.app_settings_page = self.create_app_settings_page(self.main.SETTING)
        self.stacked_widget.addWidget(self.app_settings_page)

        # DB 설정 페이지 추가
        self.db_settings_page = self.create_db_settings_page(self.main.SETTING)
        self.stacked_widget.addWidget(self.db_settings_page)

        # info 설정 페이지 추가
        self.info_settings_page = self.create_info_settings_page(self.main.SETTING)
        self.stacked_widget.addWidget(self.info_settings_page)

        self.help_page = self.create_help_page()
        self.stacked_widget.addWidget(self.help_page)

        # 콘텐츠 레이아웃 구성
        content_layout.addWidget(self.category_list, 2)
        content_layout.addWidget(self.stacked_widget, 6)

        # 저장 및 취소 버튼 섹션
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)  # 저장 버튼 클릭 이벤트 연결

        # 취소 버튼
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)  # 취소 버튼 클릭 이벤트 연결

        close_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        close_shortcut.activated.connect(self.reject)
        close_shortcut_mac = QShortcut(QKeySequence("Ctrl+ㅈ"), self)
        close_shortcut_mac.activated.connect(self.reject)
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_settings)
        save_shortcut_mac = QShortcut(QKeySequence("Ctrl+ㄴ"), self)
        save_shortcut_mac.activated.connect(self.save_settings)

        button_layout.addStretch()  # 버튼을 오른쪽으로 정렬
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)

        # 메인 레이아웃 구성
        main_layout.addLayout(content_layout)
        main_layout.addLayout(button_layout)

        self.setStyleSheet('''
            QPushButton {
                border: none;
                border-radius: 5px;
                padding: 9px;
                font-size: 15px;
            }
            QLabel {
                font-size: 14px;
                font-family: 'Malgun Gothic';
                font-weight: bold;
            }
        '''
        )
        default_font = QFont(os.path.join(os.path.dirname(__file__), 'source', 'malgun.ttf'))  # 폰트 이름과 크기 지정
        self.setFont(default_font)

        self.setLayout(main_layout)

    def create_app_settings_page(self, setting):
        """
        앱 설정 페이지 생성
        """
        app_layout = QVBoxLayout()
        app_layout.setSpacing(10)  # 섹션 간 간격
        app_layout.setContentsMargins(10, 10, 10, 10)  # 여백 설정

        ################################################################################
        # 앱 테마 설정 섹션
        theme_layout = QHBoxLayout()
        theme_label = QLabel("앱 테마 설정:")
        theme_label.setAlignment(Qt.AlignLeft)
        theme_label.setToolTip("MANAGER의 색 테마를 설정합니다")

        self.light_mode_toggle = QPushButton("라이트 모드")
        self.dark_mode_toggle = QPushButton("다크 모드")

        self.init_toggle_style(self.light_mode_toggle, setting['Theme'] == 'default')
        self.init_toggle_style(self.dark_mode_toggle, setting['Theme'] != 'default')

        self.light_mode_toggle.clicked.connect(
            lambda: self.update_toggle(self.light_mode_toggle, self.dark_mode_toggle)
        )
        self.dark_mode_toggle.clicked.connect(
            lambda: self.update_toggle(self.dark_mode_toggle, self.light_mode_toggle)
        )

        theme_buttons_layout = QHBoxLayout()
        theme_buttons_layout.setSpacing(10)
        theme_buttons_layout.addWidget(self.light_mode_toggle)
        theme_buttons_layout.addWidget(self.dark_mode_toggle)

        theme_layout.addWidget(theme_label, 1)
        theme_layout.addLayout(theme_buttons_layout, 2)

        app_layout.addLayout(theme_layout)
        ################################################################################

        ################################################################################
        # 부팅 스크린 사이즈 설정 섹션
        screen_size_layout = QHBoxLayout()
        screen_size_label = QLabel("부팅 시 창 크기:")
        screen_size_label.setAlignment(Qt.AlignLeft)
        screen_size_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        screen_size_label.setToolTip("MANAGER 부팅 시 기본 창 크기를 설정합니다")

        self.default_size_toggle = QPushButton("기본값")
        self.maximized_toggle = QPushButton("최대화")

        self.init_toggle_style(self.default_size_toggle, setting['ScreenSize'] == 'default')
        self.init_toggle_style(self.maximized_toggle, setting['ScreenSize'] != 'default')

        self.default_size_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_size_toggle, self.maximized_toggle)
        )
        self.maximized_toggle.clicked.connect(
            lambda: self.update_toggle(self.maximized_toggle, self.default_size_toggle)
        )

        screen_size_buttons_layout = QHBoxLayout()
        screen_size_buttons_layout.setSpacing(10)
        screen_size_buttons_layout.addWidget(self.default_size_toggle)
        screen_size_buttons_layout.addWidget(self.maximized_toggle)

        screen_size_layout.addWidget(screen_size_label, 1)
        screen_size_layout.addLayout(screen_size_buttons_layout, 2)

        app_layout.addLayout(screen_size_layout)
        ################################################################################

        ################################################################################
        # 부팅 스크린 사이즈 설정 섹션
        boot_terminal_layout = QHBoxLayout()
        boot_terminal_label = QLabel("부팅 시 터미널:")
        boot_terminal_label.setAlignment(Qt.AlignLeft)
        boot_terminal_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        boot_terminal_label.setToolTip("MANAGER 부팅 시 터미널 창 여부를 설정합니다")

        self.default_bootterminal_toggle = QPushButton("끄기")
        self.on_bootterminal_toggle = QPushButton("켜기")

        self.init_toggle_style(self.default_bootterminal_toggle, setting['BootTerminal'] == 'default')
        self.init_toggle_style(self.on_bootterminal_toggle, setting['BootTerminal'] != 'default')

        self.default_bootterminal_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_bootterminal_toggle, self.on_bootterminal_toggle)
        )
        self.on_bootterminal_toggle.clicked.connect(
            lambda: self.update_toggle(self.on_bootterminal_toggle, self.default_bootterminal_toggle)
        )

        boot_terminal_buttons_layout = QHBoxLayout()
        boot_terminal_buttons_layout.setSpacing(10)
        boot_terminal_buttons_layout.addWidget(self.default_bootterminal_toggle)
        boot_terminal_buttons_layout.addWidget(self.on_bootterminal_toggle)

        boot_terminal_layout.addWidget(boot_terminal_label, 1)
        boot_terminal_layout.addLayout(boot_terminal_buttons_layout, 2)

        app_layout.addLayout(boot_terminal_layout)
        ################################################################################

        ################################################################################
        # 프로세스 콘솔 설정 섹션
        process_console_layout = QHBoxLayout()
        process_console_label = QLabel("프로세스 콘솔:")
        process_console_label.setAlignment(Qt.AlignLeft)
        process_console_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        process_console_label.setToolTip("KEMKIM, CSV로 저장 등 복잡한 작업 수행 시 진행 상황을 나타내는 콘솔 창 여부를 설정합니다")

        self.default_processconsole_toggle = QPushButton("켜기")
        self.off_processconsole_toggle = QPushButton("끄기")

        self.init_toggle_style(self.default_processconsole_toggle, setting['ProcessConsole'] == 'default')
        self.init_toggle_style(self.off_processconsole_toggle, setting['ProcessConsole'] != 'default')

        self.default_processconsole_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_processconsole_toggle, self.off_processconsole_toggle)
        )
        self.off_processconsole_toggle.clicked.connect(
            lambda: self.update_toggle(self.off_processconsole_toggle, self.default_processconsole_toggle)
        )

        process_console_buttons_layout = QHBoxLayout()
        process_console_buttons_layout.setSpacing(10)
        process_console_buttons_layout.addWidget(self.default_processconsole_toggle)
        process_console_buttons_layout.addWidget(self.off_processconsole_toggle)

        process_console_layout.addWidget(process_console_label, 1)
        process_console_layout.addLayout(process_console_buttons_layout, 2)

        app_layout.addLayout(process_console_layout)
        ################################################################################

        ################################################################################
        # 자동 업데이트 설정 섹션
        auto_update_layout = QHBoxLayout()
        auto_update_label = QLabel("자동 업데이트:")
        auto_update_label.setAlignment(Qt.AlignLeft)
        auto_update_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        auto_update_label.setToolTip("MANAGER 부팅 시 자동 업데이트 여부를 설정합니다")

        self.default_update_toggle = QPushButton("끄기")
        self.auto_update_toggle = QPushButton("켜기")

        self.init_toggle_style(self.default_update_toggle, setting['AutoUpdate'] == 'default')
        self.init_toggle_style(self.auto_update_toggle, setting['AutoUpdate'] != 'default')

        self.default_update_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_update_toggle, self.auto_update_toggle)
        )
        self.auto_update_toggle.clicked.connect(
            lambda: self.update_toggle(self.auto_update_toggle, self.default_update_toggle)
        )

        auto_update_buttons_layout = QHBoxLayout()
        auto_update_buttons_layout.setSpacing(10)
        auto_update_buttons_layout.addWidget(self.default_update_toggle)
        auto_update_buttons_layout.addWidget(self.auto_update_toggle)

        auto_update_layout.addWidget(auto_update_label, 1)
        auto_update_layout.addLayout(auto_update_buttons_layout, 2)

        app_layout.addLayout(auto_update_layout)
        ################################################################################

        ################################################################################
        # ChatGPT API Key 입력 섹션
        def open_details_url():
            """자세히 버튼 클릭 시 URL 열기"""
            import webbrowser
            url = "https://hyunicecream.tistory.com/78"  # 원하는 URL 입력
            webbrowser.open(url)

        def disable_api_key_input():
            """API Key 입력창 비활성화"""
            api_key = self.api_key_input.text()
            if api_key:
                self.api_key_input.setDisabled(True)  # 입력창 비활성화
                self.save_api_key_button.setEnabled(False)  # 저장 버튼 비활성화
                self.edit_api_key_button.setEnabled(True)  # 수정 버튼 활성화
                setting['APIKey'] = api_key  # 설정에 저장
                QMessageBox.information(self, "성공", "API Key가 저장되었습니다.")
            else:
                QMessageBox.warning(self, "경고", "API Key를 입력하세요.")

        def enable_api_key_input():
            """API Key 입력창 활성화"""
            self.api_key_input.setDisabled(False)  # 입력창 활성화
            self.save_api_key_button.setEnabled(True)  # 저장 버튼 활성화
            self.edit_api_key_button.setEnabled(False)  # 수정 버튼 비활성화

        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("ChatGPT API:")
        api_key_label.setAlignment(Qt.AlignLeft)
        api_key_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        api_key_label.setToolTip("ChatGPT 기능을 사용하기 위한 API Key를 설정합니다")

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your Key")
        self.api_key_input.setStyleSheet("font-size: 14px; padding: 5px;")
        if setting['GPT_Key'] != 'default' and len(setting['GPT_Key']) >= 20:
            self.api_key_input.setText(setting['GPT_Key'])  # 기존 값이 있으면 표시
            self.api_key_input.setDisabled(True)
        else:
            self.api_key_input.setEnabled(True)
        #################################################################################

        ################################################################################
        # GPT TTS 설정 섹션
        gpt_tts_layout = QHBoxLayout()
        gpt_tts_label = QLabel("ChatGPT TTS:")
        gpt_tts_label.setAlignment(Qt.AlignLeft)
        gpt_tts_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        gpt_tts_label.setToolTip("ChatGPT 프롬프트 음성인식 사용 시 TTS(TextToSpeech) 답변 여부를 설정합니다")

        self.default_gpttts_toggle = QPushButton("켜기")
        self.off_gpttts_toggle = QPushButton("끄기")

        self.init_toggle_style(self.default_gpttts_toggle, setting['GPT_TTS'] == 'default')
        self.init_toggle_style(self.off_gpttts_toggle, setting['GPT_TTS'] != 'default')

        self.default_gpttts_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_gpttts_toggle, self.off_gpttts_toggle)
        )
        self.off_gpttts_toggle.clicked.connect(
            lambda: self.update_toggle(self.off_gpttts_toggle, self.default_gpttts_toggle)
        )

        gpt_tts_buttons_layout = QHBoxLayout()
        gpt_tts_buttons_layout.setSpacing(10)  # 버튼 간 간격 설정
        gpt_tts_buttons_layout.addWidget(self.default_gpttts_toggle)
        gpt_tts_buttons_layout.addWidget(self.off_gpttts_toggle)

        gpt_tts_layout.addWidget(gpt_tts_label, 1)
        gpt_tts_layout.addLayout(gpt_tts_buttons_layout, 2)

        app_layout.addLayout(gpt_tts_layout)
        ################################################################################

        # 저장 버튼
        self.save_api_key_button = QPushButton("저장")
        self.save_api_key_button.clicked.connect(disable_api_key_input)

        # 수정 버튼
        self.edit_api_key_button = QPushButton("수정")
        self.edit_api_key_button.clicked.connect(enable_api_key_input)

        # 자세히 버튼
        self.details_button = QPushButton("자세히")
        self.details_button.clicked.connect(open_details_url)

        # 버튼 레이아웃
        api_key_buttons_layout = QHBoxLayout()
        api_key_buttons_layout.setSpacing(10)
        api_key_buttons_layout.addWidget(self.save_api_key_button, 1)
        api_key_buttons_layout.addWidget(self.edit_api_key_button, 1)
        api_key_buttons_layout.addWidget(self.details_button, 1)

        # 전체 레이아웃
        api_key_input_layout = QHBoxLayout()
        api_key_input_layout.setSpacing(10)
        api_key_input_layout.addWidget(self.api_key_input, 3)
        api_key_input_layout.addLayout(api_key_buttons_layout, 1)

        api_key_layout.addWidget(api_key_label, 1)
        api_key_layout.addLayout(api_key_input_layout, 2)

        app_layout.addLayout(api_key_layout)

        ################################################################################

        # 아래쪽 여유 공간 추가
        app_layout.addStretch()

        app_settings_widget = QWidget()
        app_settings_widget.setLayout(app_layout)
        return app_settings_widget

    def create_db_settings_page(self, setting):

        # DB 설정 페이지 생성
        db_layout = QVBoxLayout()
        db_layout.setSpacing(10)  # 섹션 간 간격 설정
        db_layout.setContentsMargins(10, 10, 10, 10)  # 여백 설정

        ################################################################################
        # 내 DB만 표시 설정 섹션
        db_display_layout = QHBoxLayout()
        mydb_label = QLabel("내 DB만 표시:")
        mydb_label.setAlignment(Qt.AlignLeft)
        mydb_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        mydb_label.setToolTip("DB 목록에서 자신이 크롤링한 DB만 표시할지 여부를 설정합니다")

        self.default_mydb_toggle = QPushButton("끄기")
        self.auto_mydb_toggle = QPushButton("켜기")

        self.init_toggle_style(self.default_mydb_toggle, setting['MyDB'] == 'default')
        self.init_toggle_style(self.auto_mydb_toggle, setting['MyDB'] != 'default')

        self.default_mydb_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_mydb_toggle, self.auto_mydb_toggle)
        )
        self.auto_mydb_toggle.clicked.connect(
            lambda: self.update_toggle(self.auto_mydb_toggle, self.default_mydb_toggle)
        )

        db_display_buttons_layout = QHBoxLayout()
        db_display_buttons_layout.setSpacing(10)  # 버튼 간 간격 설정
        db_display_buttons_layout.addWidget(self.default_mydb_toggle)
        db_display_buttons_layout.addWidget(self.auto_mydb_toggle)

        db_display_layout.addWidget(mydb_label, 1)
        db_display_layout.addLayout(db_display_buttons_layout, 2)

        db_layout.addLayout(db_display_layout)
        ################################################################################

        ################################################################################
        # DB 자동 새로고침 설정 섹션
        db_refresh_layout = QHBoxLayout()
        db_refresh_label = QLabel("DB 자동 새로고침:")
        db_refresh_label.setAlignment(Qt.AlignLeft)
        db_refresh_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        db_refresh_label.setToolTip("DATABASE 섹션으로 이동 시 자동으로 DB 목록을 새로고침할지 여부를 설정합니다\n'Ctrl+R'로 수동 새로고침 가능합니다")

        self.default_dbrefresh_toggle = QPushButton("켜기")
        self.off_dbrefresh_toggle = QPushButton("끄기")

        self.init_toggle_style(self.default_dbrefresh_toggle, setting['DB_Refresh'] == 'default')
        self.init_toggle_style(self.off_dbrefresh_toggle, setting['DB_Refresh'] != 'default')

        self.default_dbrefresh_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_dbrefresh_toggle, self.off_dbrefresh_toggle)
        )
        self.off_dbrefresh_toggle.clicked.connect(
            lambda: self.update_toggle(self.off_dbrefresh_toggle, self.default_dbrefresh_toggle)
        )

        db_refresh_buttons_layout = QHBoxLayout()
        db_refresh_buttons_layout.setSpacing(10)  # 버튼 간 간격 설정
        db_refresh_buttons_layout.addWidget(self.default_dbrefresh_toggle)
        db_refresh_buttons_layout.addWidget(self.off_dbrefresh_toggle)

        db_refresh_layout.addWidget(db_refresh_label, 1)
        db_refresh_layout.addLayout(db_refresh_buttons_layout, 2)

        db_layout.addLayout(db_refresh_layout)
        ################################################################################

        ################################################################################
        # DB 키워드 정렬 설정 섹션
        db_keywordsort_layout = QHBoxLayout()
        db_keywordsort_label = QLabel("DB 목록 정렬:")
        db_keywordsort_label.setAlignment(Qt.AlignLeft)
        db_keywordsort_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        db_keywordsort_label.setToolTip("DATABASE 섹션에서 DB 목록의 정렬 기준을 설정힙니다")

        self.default_dbkeywordsort_toggle = QPushButton("최신순")
        self.on_dbkeywordsort_toggle = QPushButton("키워드순")

        self.init_toggle_style(self.default_dbkeywordsort_toggle, setting['DBKeywordSort'] == 'default')
        self.init_toggle_style(self.on_dbkeywordsort_toggle, setting['DBKeywordSort'] != 'default')

        self.default_dbkeywordsort_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_dbkeywordsort_toggle, self.on_dbkeywordsort_toggle)
        )
        self.on_dbkeywordsort_toggle.clicked.connect(
            lambda: self.update_toggle(self.on_dbkeywordsort_toggle, self.default_dbkeywordsort_toggle)
        )

        db_keywordsort_buttons_layout = QHBoxLayout()
        db_keywordsort_buttons_layout.setSpacing(10)  # 버튼 간 간격 설정
        db_keywordsort_buttons_layout.addWidget(self.default_dbkeywordsort_toggle)
        db_keywordsort_buttons_layout.addWidget(self.on_dbkeywordsort_toggle)

        db_keywordsort_layout.addWidget(db_keywordsort_label, 1)
        db_keywordsort_layout.addLayout(db_keywordsort_buttons_layout, 2)

        db_layout.addLayout(db_keywordsort_layout)
        ################################################################################

        # 아래쪽 여유 공간 추가
        db_layout.addStretch()

        db_settings_widget = QWidget()
        db_settings_widget.setLayout(db_layout)
        return db_settings_widget

    def create_info_settings_page(self, setting):
        def wrap_text_by_words(text, max_line_length):
            split = '/'
            if platform.system() == 'Windows':
                split = '\\'
            """
            문자열을 '/' 단위로 나누고 줄바꿈(\n)을 추가하는 함수.
            '/'를 유지합니다.
            """
            words = text.split(split)  # '/'를 기준으로 나누기
            current_line = ""
            lines = []

            for word in words:
                word_with_slash = word + split  # '/'를 다시 추가
                if len(current_line) + len(word_with_slash) <= max_line_length:
                    current_line += word_with_slash
                else:
                    lines.append(current_line.strip())
                    current_line = word_with_slash
            if current_line:
                lines.append(current_line.strip())

            return "\n".join(lines)

        def update_runtime():
            """실시간으로 구동 시간을 정수 형식으로 업데이트하는 메서드"""
            elapsed_time = datetime.now() - self.main.startTime
            total_seconds = int(elapsed_time.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.manager_time_label.setText(f"구동 시간: {hours}시간 {minutes}분 {seconds}초")

        ################################################################################
        # 사용자 정보 페이지 레이아웃 생성
        info_layout = QVBoxLayout()
        info_layout.setSpacing(20)
        info_layout.setContentsMargins(20, 20, 20, 20)

        ################################################################################
        # 사용자 정보 표시 섹션
        user_info_section = QVBoxLayout()
        user_title_label = QLabel("사용자 정보")
        user_title_label.setAlignment(Qt.AlignLeft)
        user_title_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        # 사용자 정보 추가 (예: 이름, 이메일, 디바이스)
        user_name_label = QLabel(f"이름: {self.main.user}")

        user_email_label = QLabel(f"이메일: {self.main.usermail}")

        user_device_label = QLabel(f"디바이스: {self.main.user_device}")

        if self.main.gpt_api_key == 'default' or len(self.main.gpt_api_key) < 20:
            GPT_key_label = QLabel(f"ChatGPT API Key: 없음")
        else:
            GPT_key_label = QLabel(f"ChatGPT Key: {self.main.gpt_api_key[:40]}...")

        # 사용자 정보 섹션 레이아웃 구성
        user_info_section.addWidget(user_title_label)
        user_info_section.addWidget(user_name_label)
        user_info_section.addWidget(user_email_label)
        user_info_section.addWidget(user_device_label)
        user_info_section.addWidget(GPT_key_label)

        # 사용자 정보 섹션에 구분선 추가
        user_info_separator = QLabel()

        info_layout.addLayout(user_info_section)
        info_layout.addWidget(user_info_separator)
        ################################################################################

        ################################################################################
        # MANAGER 정보 표시 섹션
        manager_info_section = QVBoxLayout()
        manager_title_label = QLabel("MANAGER 정보")
        manager_title_label.setAlignment(Qt.AlignLeft)
        manager_title_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        # MANAGER 정보 추가
        manager_version_label = QLabel(f"버전: {self.main.versionNum}")

        manager_location_label = QLabel(f"앱 경로: {wrap_text_by_words(self.main.program_directory, 40)}")

        setting_location_label = QLabel(f"설정 경로: {wrap_text_by_words(self.main.settings.fileName(), 40)}")

        # 실시간 업데이트를 위한 구동 시간 라벨
        self.manager_time_label = QLabel("구동 시간: 계산 중...")

        # MANAGER 정보 섹션 레이아웃 구성
        manager_info_section.addWidget(manager_title_label)
        manager_info_section.addWidget(manager_version_label)
        manager_info_section.addWidget(manager_location_label)
        manager_info_section.addWidget(setting_location_label)
        manager_info_section.addWidget(self.manager_time_label)

        info_layout.addLayout(manager_info_section)
        ################################################################################

        # 아래쪽 여유 공간 추가
        info_layout.addStretch()

        # 위젯 설정
        info_settings_widget = QWidget()
        info_settings_widget.setLayout(info_layout)

        # 타이머 설정: 1초마다 구동 시간 업데이트
        self.timer = QTimer()
        self.timer.timeout.connect(update_runtime)
        self.timer.start(1000)

        return info_settings_widget

    def create_help_page(self):
        """
        Help 페이지 생성
        """
        help_layout = QVBoxLayout()
        help_layout.setSpacing(10)
        help_layout.setContentsMargins(20, 20, 20, 20)

        # 제목
        help_title_label = QLabel("Instructions\n")
        help_title_label.setAlignment(Qt.AlignLeft)
        help_title_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        # 설명 텍스트
        help_text_label = QLabel("아래 링크를 클릭하여 사용 설명서를 확인하세요.")
        help_text_label.setAlignment(Qt.AlignLeft)

        # 첫 번째 하이퍼링크
        link1_label = QLabel('<a href="https://knpu.re.kr/tool">BIGMACLAB MANAGER</a>')
        link1_label.setOpenExternalLinks(True)
        link1_label.setAlignment(Qt.AlignLeft)

        # 두 번째 하이퍼링크
        link2_label = QLabel('<a href="https://knpu.re.kr/kemkim">KEM KIM</a>')
        link2_label.setOpenExternalLinks(True)
        link2_label.setAlignment(Qt.AlignLeft)

        # 레이아웃 구성
        help_layout.addWidget(help_title_label)
        help_layout.addWidget(help_text_label)
        help_layout.addWidget(link1_label)
        help_layout.addWidget(link2_label)
        help_layout.addStretch()

        help_widget = QWidget()
        help_widget.setLayout(help_layout)
        return help_widget

    def open_help_url(self):
        """
        Help 페이지에서 URL 열기
        """
        import webbrowser
        url = "https://example.com/manual"  # 사용 설명서 URL
        webbrowser.open(url)

    def display_category(self, index):
        """
        카테고리에 따라 해당 설정 페이지 표시
        """
        self.stacked_widget.setCurrentIndex(index)

    def init_toggle_style(self, button, is_selected):
        """
        토글 버튼 스타일 초기화
        """
        if is_selected:
            button.setStyleSheet("background-color: #2c3e50; font-weight: bold; color: #eaeaea;")
        else:
            button.setStyleSheet("background-color: lightgray; color: black;")

    def update_toggle(self, selected_button, other_button):
        """
        선택된 버튼과 비선택 버튼 스타일 업데이트
        """
        self.init_toggle_style(selected_button, True)
        self.init_toggle_style(other_button, False)

    def save_settings(self):
        # 선택된 설정 가져오기
        theme = 'default' if self.light_mode_toggle.styleSheet().find("#2c3e50") != -1 else 'dark'
        screen_size = 'default' if self.default_size_toggle.styleSheet().find("#2c3e50") != -1 else 'max'
        auto_update = 'default' if self.default_update_toggle.styleSheet().find("#2c3e50") != -1 else 'auto'
        my_db = 'default' if self.default_mydb_toggle.styleSheet().find("#2c3e50") != -1 else 'mydb'
        db_refresh = 'default' if self.default_dbrefresh_toggle.styleSheet().find("#2c3e50") != -1 else 'off'
        gpt_tts = 'default' if self.default_gpttts_toggle.styleSheet().find("#2c3e50") != -1 else 'off'
        boot_terminal = 'default' if self.default_bootterminal_toggle.styleSheet().find("#2c3e50") != -1 else 'on'
        db_keywordsort =  'default' if self.default_dbkeywordsort_toggle.styleSheet().find("#2c3e50") != -1 else 'on'
        process_console = 'default' if self.default_processconsole_toggle.styleSheet().find("#2c3e50") != -1 else 'off'
        api_key = self.api_key_input.text()
        api_key.replace('\n', '').replace(' ', '')

        self.main.SETTING['Theme'] = theme
        self.main.SETTING['ScreenSize'] = screen_size
        self.main.SETTING['AutoUpdate'] = auto_update
        self.main.SETTING['MyDB'] = my_db
        self.main.SETTING['GPT_Key'] = api_key
        self.main.SETTING['DB_Refresh'] = db_refresh
        self.main.SETTING['GPT_TTS'] = gpt_tts
        self.main.SETTING['BootTerminal'] = boot_terminal
        self.main.SETTING['DBKeywordSort'] = db_keywordsort
        self.main.SETTING['ProcessConsole'] = process_console
        self.main.gpt_api_key = api_key

        options = {
            "theme": {"key": 'Theme', "value": theme},  # 테마 설정
            "screensize": {"key": 'ScreenSize', "value": screen_size},  # 스크린 사이즈 설정
            "autoupdate": {"key": 'AutoUpdate', "value": auto_update},  # 자동 업데이트 설정
            "mydb": {"key": 'MyDB', "value": my_db},  # 내 DB만 보기 설정
            "GPT_Key": {"key": 'GPT_Key', "value": api_key},
            "DB_Refresh": {"key": 'DB_Refresh', "value": db_refresh},
            "GPT_TTS": {"key": 'GPT_TTS', "value": gpt_tts},
            "BootTerminal": {"key": 'BootTerminal', "value": boot_terminal},
            'DBKeywordSort': {'key': 'DBKeywordSort', "value": db_keywordsort},
            'ProcessConsole': {'key': 'ProcessConsole', 'value': process_console}
        }
        for option in options.values():
            self.main.update_settings(option['key'], option['value'])

        self.accept()


