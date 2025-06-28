import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QComboBox,
                             QFormLayout, QMessageBox, QFileDialog, QSpinBox,
                             QColorDialog, QKeySequenceEdit, QCheckBox, QFrame,
                             QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette, QColor, QKeySequence, QFont

from config_manager import ConfigManager
from gui.overlay_window import TranslationItem

# 지원 언어 목록 (DeepL API 기준)
SUPPORTED_LANGUAGES = {
    "Bulgarian": "BG", "Czech": "CS", "Danish": "DA", "German": "DE",
    "Greek": "EL", "English (British)": "EN-GB", "English (American)": "EN-US",
    "Spanish": "ES", "Estonian": "ET", "Finnish": "FI", "French": "FR",
    "Hungarian": "HU", "Indonesian": "ID", "Italian": "IT", "Japanese": "JA",
    "Korean": "KO", "Lithuanian": "LT", "Latvian": "LV", "Norwegian": "NB",
    "Dutch": "NL", "Polish": "PL", "Portuguese (Brazilian)": "PT-BR",
    "Portuguese (European)": "PT-PT", "Romanian": "RO", "Russian": "RU",
    "Slovak": "SK", "Slovenian": "SL", "Swedish": "SV", "Turkish": "TR",
    "Ukrainian": "UK", "Chinese (Simplified)": "ZH"
}
CODE_TO_NAME = {v: k for k, v in SUPPORTED_LANGUAGES.items()}

# 설정 창 내부에 표시될 오버레이 미리보기 위젯
class OverlayPreview(QFrame):
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.example_items = []
        self.setStyleSheet("background-color: #333333; border-radius: 5px;")
        self.setMinimumHeight(200)

    def update_preview(self, temp_config=None):
        """임시 설정(temp_config)을 받아 미리보기를 업데이트합니다."""
        config_source = temp_config if temp_config is not None else self.config_manager.config

        for item in self.example_items:
            self.main_layout.removeWidget(item)
            item.deleteLater()
        self.example_items.clear()
        
        example_data = [
            ("This is the most recent translation.", self._get_example_translation(config_source)),
            ("This is a previous translation.", self._get_example_translation(config_source, is_prev=True)),
            ("And this is the oldest one.", self._get_example_translation(config_source, is_old=True))
        ]
        
        for original, translated in example_data:
            # 미리보기 아이템 생성 시 임시 config 전달
            item = TranslationItem(original, translated, self.config_manager, temp_config=temp_config)
            self.example_items.append(item)
            self.main_layout.addWidget(item)
        self._update_item_opacities()
        
    def _get_example_translation(self, config_source, is_prev=False, is_old=False):
        """제공된 설정을 기반으로 예시 번역 문장을 생성합니다."""
        target_langs = config_source.get("target_languages", ["KO"])
        if not target_langs: target_langs = ["KO"]
        
        if is_prev: return "\n".join(f"[{lang}] 이전 번역 예시" for lang in target_langs)
        if is_old: return "\n".join(f"[{lang}] 가장 오래된 번역 예시" for lang in target_langs)
        return "\n".join(f"[{lang}] 최신 번역 예시" for lang in target_langs)

    def _update_item_opacities(self):
        for i, item in enumerate(self.example_items):
            item.update_styles()
            opacity = 1.0 - (i * 0.15)
            if hasattr(item, 'opacity_effect'):
                item.opacity_effect.setOpacity(opacity)

# 메인 설정 창
class SetupWindow(QWidget):
    closed = Signal(bool, str)

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.setWindowTitle("Ariel 설정 - by Seeth")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.resize(600, 800)
        self.is_saved = False

        self._create_widgets()
        self._setup_layout()
        self._connect_signals()
        
        self.load_settings()

    def _create_widgets(self):
        self.overlay_preview = OverlayPreview(self.config_manager)
        
        self.google_path_edit = QLineEdit()
        self.google_browse_button = QPushButton("찾아보기...")
        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.source_lang_selectors = []
        self.target_lang_selectors = []
        self.add_source_lang_button = QPushButton("+ 원본 언어 추가")
        self.add_target_lang_button = QPushButton("+ 번역 언어 추가")

        self.sentence_delay_spinbox = QSpinBox()
        self.sentence_delay_spinbox.setRange(50, 3000)
        self.sentence_delay_spinbox.setSuffix(" ms")
        self.sentence_delay_spinbox.setToolTip("음성 인식이 끝난 후, 문장을 조합하기 위해 기다리는 시간입니다.\n짧을수록 반응이 빠르지만, 문장이 끊길 수 있습니다.")
        
        self.delay_minus_button = QPushButton("-50")
        self.delay_plus_button = QPushButton("+50")
        
        self.show_original_checkbox = QCheckBox("번역 결과 아래에 원본 텍스트 함께 표시")
        
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(8, 72)
        
        self.original_text_font_size_spinbox = QSpinBox()
        self.original_text_font_size_spinbox.setRange(-10, 10)
        self.original_text_font_size_spinbox.setToolTip("번역 폰트 크기와의 상대적인 차이값입니다.")

        # --- 색상 미리보기 위젯 생성 ---
        self.font_color_preview = QWidget()
        self.font_color_preview.setFixedSize(24, 24)
        self.bg_color_preview = QWidget()
        self.bg_color_preview.setFixedSize(24, 24)
        self.original_text_font_color_preview = QWidget()
        self.original_text_font_color_preview.setFixedSize(24, 24)

        self.font_color_button = QPushButton("번역 글자색")
        self.bg_color_button = QPushButton("번역 배경색")
        self.original_text_font_color_button = QPushButton("원본 글자색")
        
        self.start_hotkey_edit = QKeySequenceEdit()
        self.stop_hotkey_edit = QKeySequenceEdit()
        self.setup_hotkey_edit = QKeySequenceEdit()
        self.quit_hotkey_edit = QKeySequenceEdit()
        
        self.reset_button = QPushButton("설정 초기화")
        self.save_button = QPushButton("저장")
        self.cancel_button = QPushButton("취소")

    def _setup_layout(self):
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("<b>오버레이 미리보기</b>"))
        main_layout.addWidget(self.overlay_preview)
        
        form_layout = QFormLayout()
        
        form_layout.addRow(QLabel("<b>API 설정</b>"))
        google_path_layout = QHBoxLayout(); google_path_layout.addWidget(self.google_path_edit); google_path_layout.addWidget(self.google_browse_button)
        form_layout.addRow("Google Cloud Key:", google_path_layout)
        form_layout.addRow("DeepL API Key:", self.deepl_key_edit)
        
        form_layout.addRow(QLabel("<b>언어 설정</b>"))
        self.source_lang_layout = QVBoxLayout(); self.source_lang_layout.setSpacing(5)
        form_layout.addRow("원본 언어(음성):", self.source_lang_layout)
        form_layout.addRow(self.add_source_lang_button)
        
        self.target_lang_layout = QVBoxLayout(); self.target_lang_layout.setSpacing(5)
        form_layout.addRow("번역 언어(자막):", self.target_lang_layout)
        form_layout.addRow(self.add_target_lang_button)
        
        form_layout.addRow(QLabel("<b>번역 딜레이 설정</b>"))
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(self.delay_minus_button)
        delay_layout.addWidget(self.sentence_delay_spinbox)
        delay_layout.addWidget(self.delay_plus_button)
        delay_layout.addStretch()
        form_layout.addRow(delay_layout)

        form_layout.addRow(QLabel("<b>오버레이 스타일 설정</b>"))
        form_layout.addRow(self.show_original_checkbox)
        
        font_layout = QHBoxLayout(); font_layout.addWidget(QLabel("번역 폰트 크기:")); font_layout.addWidget(self.font_size_spinbox); font_layout.addStretch()
        form_layout.addRow(font_layout)
        
        original_font_layout = QHBoxLayout(); original_font_layout.addWidget(QLabel("원본 폰트 크기(상대값):")); original_font_layout.addWidget(self.original_text_font_size_spinbox); original_font_layout.addStretch()
        form_layout.addRow(original_font_layout)
        
        # --- 색상 설정 UI 변경 ---
        color_layout = QHBoxLayout()
        color_layout.addWidget(self.font_color_preview)
        color_layout.addWidget(self.font_color_button)
        color_layout.addWidget(self.bg_color_preview)
        color_layout.addWidget(self.bg_color_button)
        color_layout.addWidget(self.original_text_font_color_preview)
        color_layout.addWidget(self.original_text_font_color_button)
        color_layout.addStretch()
        form_layout.addRow("색상 설정:", color_layout)

        form_layout.addRow(QLabel("<b>단축키 설정</b>"))
        form_layout.addRow("번역 시작:", self.start_hotkey_edit)
        form_layout.addRow("번역 중지:", self.stop_hotkey_edit)
        form_layout.addRow("설정 창 열기/닫기:", self.setup_hotkey_edit)
        form_layout.addRow("프로그램 종료:", self.quit_hotkey_edit)
        
        main_layout.addLayout(form_layout)
        
        button_layout_h = QHBoxLayout()
        button_layout_h.addWidget(self.reset_button, 0, Qt.AlignmentFlag.AlignLeft)
        button_layout_h.addStretch(1)
        button_layout_h.addWidget(self.save_button)
        button_layout_h.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout_h)

    def _connect_signals(self):
        self.google_browse_button.clicked.connect(self.browse_google_key_file)
        self.cancel_button.clicked.connect(self.close)
        self.save_button.clicked.connect(self.save_settings)
        
        self.add_source_lang_button.clicked.connect(lambda: self.add_language_selector("source"))
        self.add_target_lang_button.clicked.connect(lambda: self.add_language_selector("target"))
        
        # 미리보기 업데이트를 위한 시그널 연결
        self.show_original_checkbox.stateChanged.connect(self.update_preview_style)
        self.font_size_spinbox.valueChanged.connect(self.update_preview_style)
        self.original_text_font_size_spinbox.valueChanged.connect(self.update_preview_style)
        
        # 색상 버튼 시그널 연결 수정
        self.font_color_button.clicked.connect(lambda: self.choose_color(self.font_color_preview))
        self.bg_color_button.clicked.connect(lambda: self.choose_color(self.bg_color_preview, has_alpha=True))
        self.original_text_font_color_button.clicked.connect(lambda: self.choose_color(self.original_text_font_color_preview))
        
        self.delay_minus_button.clicked.connect(lambda: self.adjust_delay(-50))
        self.delay_plus_button.clicked.connect(lambda: self.adjust_delay(50))
        self.reset_button.clicked.connect(self.reset_settings_confirmed)

    def adjust_delay(self, amount):
        current_value = self.sentence_delay_spinbox.value()
        self.sentence_delay_spinbox.setValue(current_value + amount)

    def reset_settings_confirmed(self):
        reply = QMessageBox.question(self, '설정 초기화',
                                     "정말로 모든 설정을 기본값으로 되돌리시겠습니까?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.reset_to_defaults()
            QMessageBox.information(self, "초기화 완료", "설정이 초기화되었습니다. 창을 다시 열어주세요.")
            self.is_saved = True # 재시작을 유도하기 위해 저장된 것으로 처리
            self.close()

    def add_language_selector(self, type, lang_code=None):
        layout, selector_list, max_count = (self.source_lang_layout, self.source_lang_selectors, 3) if type == "source" else (self.target_lang_layout, self.target_lang_selectors, 2)
        if len(selector_list) >= max_count: return

        selector = QComboBox()
        for name, code in SUPPORTED_LANGUAGES.items(): selector.addItem(name, code)
        if lang_code and lang_code in SUPPORTED_LANGUAGES.values(): selector.setCurrentIndex(selector.findData(lang_code))
        
        remove_button = QPushButton("x"); remove_button.setFixedSize(24, 24)
        row = QHBoxLayout(); row.addWidget(selector); row.addWidget(remove_button)
        layout.addLayout(row)

        item = {"row": row, "selector": selector, "button": remove_button}
        selector_list.append(item)
        
        remove_button.clicked.connect(lambda: self.remove_language_selector(item, selector_list, layout))
        selector.currentIndexChanged.connect(self.update_preview_style)
        self.update_add_button_state()

    def remove_language_selector(self, item_to_remove, selector_list, parent_layout):
        for i, item in enumerate(selector_list):
            if item == item_to_remove:
                while item["row"].count():
                    child = item["row"].takeAt(0)
                    if child.widget(): child.widget().deleteLater()
                parent_layout.removeItem(item["row"])
                item["row"].deleteLater()
                selector_list.pop(i)
                self.update_add_button_state()
                self.update_preview_style()
                break

    def update_add_button_state(self):
        self.add_source_lang_button.setEnabled(len(self.source_lang_selectors) < 3)
        self.add_target_lang_button.setEnabled(len(self.target_lang_selectors) < 2)

    def load_settings(self):
        self.google_path_edit.setText(self.config_manager.get("google_credentials_path", ""))
        self.deepl_key_edit.setText(self.config_manager.get("deepl_api_key", ""))
        
        # 기존 언어 선택자 모두 제거 후 다시 생성
        for i in range(len(self.source_lang_selectors) - 1, -1, -1): self.remove_language_selector(self.source_lang_selectors[i], self.source_lang_selectors, self.source_lang_layout)
        for i in range(len(self.target_lang_selectors) - 1, -1, -1): self.remove_language_selector(self.target_lang_selectors[i], self.target_lang_selectors, self.target_lang_layout)

        for lang_code in self.config_manager.get("source_languages", ["en-US"]): self.add_language_selector("source", lang_code)
        for lang_code in self.config_manager.get("target_languages", ["KO"]): self.add_language_selector("target", lang_code)
        
        self.sentence_delay_spinbox.setValue(self.config_manager.get("sentence_commit_delay_ms", 700))
        self.show_original_checkbox.setChecked(self.config_manager.get("show_original_text", True))
        self.font_size_spinbox.setValue(self.config_manager.get("overlay_font_size", 18))
        self.original_text_font_size_spinbox.setValue(self.config_manager.get("original_text_font_size_offset", -4))
        
        self.start_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_start_translate", "")))
        self.stop_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_stop_translate", "")))
        self.setup_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_toggle_setup_window", "")))
        self.quit_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_quit_app", "")))
        
        # --- 색상 미리보기 초기화 ---
        self._update_color_previews()
        
        self.update_preview_style()

    def _update_color_previews(self):
        """설정값으로 모든 색상 미리보기 위젯의 색상을 업데이트합니다."""
        font_color = self.config_manager.get("overlay_font_color")
        bg_color = self.config_manager.get("overlay_bg_color")
        original_color = self.config_manager.get("original_text_font_color")
        
        for preview_widget, color_str in [
            (self.font_color_preview, font_color),
            (self.bg_color_preview, bg_color),
            (self.original_text_font_color_preview, original_color)
        ]:
            palette = preview_widget.palette()
            palette.setColor(QPalette.ColorRole.Window, QColor(color_str))
            preview_widget.setAutoFillBackground(True)
            preview_widget.setPalette(palette)
            preview_widget.update()

    def choose_color(self, preview_widget, has_alpha=False):
        """색상 대화상자를 열고 선택된 색상을 미리보기 위젯에 적용합니다."""
        initial_color = preview_widget.palette().color(QPalette.ColorRole.Window)
        
        options = QColorDialog.ColorDialogOption()
        if has_alpha:
            options |= QColorDialog.ColorDialogOption.ShowAlphaChannel
            
        color = QColorDialog.getColor(initial_color, self, "색상 선택", options)
            
        if color.isValid():
            palette = preview_widget.palette()
            palette.setColor(QPalette.ColorRole.Window, color)
            preview_widget.setPalette(palette)
            self.update_preview_style()
    
    def save_settings(self):
        """모든 UI 위젯의 현재 값을 읽어 설정을 저장합니다."""
        self.config_manager.set("google_credentials_path", self.google_path_edit.text())
        self.config_manager.set("deepl_api_key", self.deepl_key_edit.text())
        self.config_manager.set("source_languages", [item["selector"].currentData() for item in self.source_lang_selectors])
        self.config_manager.set("target_languages", [item["selector"].currentData() for item in self.target_lang_selectors])
        self.config_manager.set("sentence_commit_delay_ms", self.sentence_delay_spinbox.value())
        self.config_manager.set("overlay_font_size", self.font_size_spinbox.value())
        self.config_manager.set("original_text_font_size_offset", self.original_text_font_size_spinbox.value())
        self.config_manager.set("show_original_text", self.show_original_checkbox.isChecked())
        
        # --- 색상 저장 로직 수정 ---
        self.config_manager.set("overlay_font_color", self.font_color_preview.palette().color(QPalette.ColorRole.Window).name())
        self.config_manager.set("overlay_bg_color", self.bg_color_preview.palette().color(QPalette.ColorRole.Window).name(QColor.NameFormat.HexArgb))
        self.config_manager.set("original_text_font_color", self.original_text_font_color_preview.palette().color(QPalette.ColorRole.Window).name())

        # 단축키 저장
        self.config_manager.set("hotkey_start_translate", self.start_hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).lower())
        self.config_manager.set("hotkey_stop_translate", self.stop_hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).lower())
        self.config_manager.set("hotkey_toggle_setup_window", self.setup_hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).lower())
        self.config_manager.set("hotkey_quit_app", self.quit_hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).lower())
        
        self.is_saved = True
        QMessageBox.information(self, "저장 완료", "설정이 저장되었습니다.")
        self.close()

    def update_preview_style(self, _=None):
        """미리보기를 위해 UI 위젯의 현재 값으로 임시 config를 생성하고 업데이트합니다."""
        temp_config = self.config_manager.config.copy()
        temp_config.update({
            "show_original_text": self.show_original_checkbox.isChecked(),
            "overlay_font_size": self.font_size_spinbox.value(),
            "original_text_font_size_offset": self.original_text_font_size_spinbox.value(),
            "target_languages": [item["selector"].currentData() for item in self.target_lang_selectors],
            "overlay_font_color": self.font_color_preview.palette().color(QPalette.ColorRole.Window).name(),
            "overlay_bg_color": self.bg_color_preview.palette().color(QPalette.ColorRole.Window).name(QColor.NameFormat.HexArgb),
            "original_text_font_color": self.original_text_font_color_preview.palette().color(QPalette.ColorRole.Window).name(),
        })
        self.overlay_preview.update_preview(temp_config)
    
    def browse_google_key_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Google Cloud 인증 키 파일 선택", "", "JSON 파일 (*.json)")
        if filepath:
            self.google_path_edit.setText(filepath)

    def closeEvent(self, event):
        # 저장하지 않고 창을 닫으면 기존 설정을 다시 로드하여 변경사항을 버림
        if not self.is_saved:
            self.config_manager.load_config()
        self.closed.emit(self.is_saved, "all")
        super().closeEvent(event)