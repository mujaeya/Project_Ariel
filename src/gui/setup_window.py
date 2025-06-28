import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QComboBox,
                             QFormLayout, QMessageBox, QFileDialog, QSpinBox,
                             QKeySequenceEdit, QCheckBox, QFrame,
                             QSizePolicy, QScrollArea, QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence
from qfluentwidgets import FluentWindow
from config_manager import ConfigManager
try:
    import deepl
except ImportError:
    deepl = None

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

class TranslationItem(QWidget):
    def __init__(self, original_text, translated_text, preview_config):
        super().__init__()
        self.preview_config = preview_config
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.translated_label = QLabel(translated_text)
        self.original_label = QLabel(original_text)
        self.layout.addWidget(self.translated_label)
        self.layout.addWidget(self.original_label)
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.update_styles()

    def update_styles(self):
        show_original = self.preview_config.get("show_original_text", True)
        self.original_label.setVisible(show_original)
        font_family = self.preview_config.get("overlay_font_family", "Malgun Gothic")
        base_font_size = self.preview_config.get("overlay_font_size", 18)
        t_color = self.preview_config.get('overlay_font_color', '#000000')
        o_color = self.preview_config.get('original_text_font_color', '#555555')
        translated_font = QFont(font_family, base_font_size)
        self.translated_label.setFont(translated_font)
        self.translated_label.setStyleSheet(f"color: {t_color}; background-color: transparent;")
        if show_original:
            offset = self.preview_config.get("original_text_font_size_offset", -4)
            original_font = QFont(font_family, base_font_size + offset)
            self.original_label.setFont(original_font)
            self.original_label.setStyleSheet(f"color: {o_color}; background-color: transparent;")

class OverlayPreview(QFrame):
    def __init__(self):
        super().__init__()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.example_items = []
        self.setMinimumHeight(200)

    def update_preview(self, preview_config):
        for item in self.example_items:
            self.main_layout.removeWidget(item)
            item.deleteLater()
        self.example_items.clear()
        self.setStyleSheet(f"background-color: {preview_config.get('overlay_bg_color')}; border-radius: 5px;")
        example_data = [
            ("This is the most recent translation.", self._get_example_translation(preview_config)),
            ("This is a previous translation.", self._get_example_translation(preview_config, is_prev=True)),
            ("And this is the oldest one.", self._get_example_translation(preview_config, is_old=True))
        ]
        for original, translated in example_data:
            item = TranslationItem(original, translated, preview_config)
            self.example_items.append(item)
            self.main_layout.addWidget(item)
        self._update_item_opacities()
        
    def _get_example_translation(self, preview_config, is_prev=False, is_old=False):
        target_langs = preview_config.get("target_languages", ["KO"])
        if not target_langs: target_langs = ["KO"]
        if is_prev: return "\n".join(f"[{lang}] 이전 번역 예시" for lang in target_langs)
        if is_old: return "\n".join(f"[{lang}] 가장 오래된 번역 예시" for lang in target_langs)
        return "\n".join(f"[{lang}] 최신 번역 예시" for lang in target_langs)

    def _update_item_opacities(self):
        for i, item in enumerate(self.example_items):
            item.opacity_effect.setOpacity(max(0.2, 1.0 - (i * 0.2)))

class SetupWindow(FluentWindow):
    closed = Signal(bool, str)

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        
        self.setTitleBar(TitleBar(self))
        self.titleBar.setWindowTitle('Ariel 설정')
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | self.windowFlags())
        self.resize(600, 850)
        
        self.is_saved = False
        
        self._create_widgets()
        self._setup_layout()
        self._connect_signals()
        self.load_settings()

    def _create_widgets(self):
        self.overlay_preview = OverlayPreview()
        self.google_path_edit = QLineEdit()
        self.google_browse_button = QPushButton("찾아보기...")
        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.source_lang_selectors = []
        self.target_lang_selectors = []
        self.add_source_lang_button = QPushButton("+ 원본 언어 추가")
        self.add_target_lang_button = QPushButton("+ 번역 언어 추가")
        self.formality_combo = QComboBox()
        self.formality_combo.addItems(["기본 (자동 감지)", "존댓말 (공식적인 톤)", "반말 (비공식적인 톤)"])
        self.use_video_model_checkbox = QCheckBox("소음/영상 컨텐츠에 최적화된 STT 모델 사용")
        self.sentence_delay_spinbox = QSpinBox()
        self.sentence_delay_spinbox.setRange(300, 3000)
        self.sentence_delay_spinbox.setSuffix(" ms")
        self.sentence_delay_spinbox.setToolTip("음성 인식이 끝난 후, 문장을 조합하기 위해 기다리는 시간입니다.")
        self.show_original_checkbox = QCheckBox("번역 결과 아래에 원본 텍스트 함께 표시")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["다크 테마", "라이트 테마"])
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(8, 72)
        self.original_text_font_size_spinbox = QSpinBox()
        self.original_text_font_size_spinbox.setRange(-10, 10)
        self.original_text_font_size_spinbox.setToolTip("번역 폰트 크기와의 상대적인 차이값입니다.")
        self.start_hotkey_edit = QKeySequenceEdit()
        self.stop_hotkey_edit = QKeySequenceEdit()
        self.setup_hotkey_edit = QKeySequenceEdit()
        self.save_button = QPushButton("저장")
        self.cancel_button = QPushButton("취소")

    def _setup_layout(self):
        self.main_container = QWidget()
        main_layout = QVBoxLayout(self.main_container)
        
        content_widget = QWidget()
        form_layout = QFormLayout(content_widget)
        form_layout.setContentsMargins(15, 15, 15, 15)
        form_layout.setSpacing(12)

        form_layout.addRow(QLabel("<b>오버레이 미리보기</b>"))
        form_layout.addRow(self.overlay_preview)
        form_layout.addRow(QLabel("<b>API 설정</b>"))
        google_path_layout = QHBoxLayout()
        google_path_layout.addWidget(self.google_path_edit)
        google_path_layout.addWidget(self.google_browse_button)
        form_layout.addRow("Google Cloud Key:", google_path_layout)
        form_layout.addRow("DeepL API Key:", self.deepl_key_edit)
        form_layout.addRow(QLabel("<b>언어 설정</b>"))
        self.source_lang_layout = QVBoxLayout()
        self.source_lang_layout.setSpacing(5)
        form_layout.addRow("원본 언어(음성):", self.source_lang_layout)
        form_layout.addRow(self.add_source_lang_button)
        self.target_lang_layout = QVBoxLayout()
        self.target_lang_layout.setSpacing(5)
        form_layout.addRow("번역 언어(자막):", self.target_lang_layout)
        form_layout.addRow(self.add_target_lang_button)
        form_layout.addRow("번역 톤(뉘앙스):", self.formality_combo)
        form_layout.addRow(QLabel("<b>음성 인식(STT) 고급 설정</b>"))
        form_layout.addRow(self.use_video_model_checkbox)
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("문장 조합 딜레이:"))
        delay_layout.addWidget(self.sentence_delay_spinbox)
        delay_layout.addStretch()
        form_layout.addRow(delay_layout)
        form_layout.addRow(QLabel("<b>오버레이 스타일 설정</b>"))
        form_layout.addRow("프로그램 테마:", self.theme_combo)
        form_layout.addRow(self.show_original_checkbox)
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("기본 폰트 크기:"))
        font_layout.addWidget(self.font_size_spinbox)
        font_layout.addStretch()
        form_layout.addRow(font_layout)
        original_style_layout = QHBoxLayout()
        original_style_layout.addWidget(QLabel("원본 텍스트 크기(상대값):"))
        original_style_layout.addWidget(self.original_text_font_size_spinbox)
        original_style_layout.addStretch()
        form_layout.addRow("원본 텍스트 스타일:", original_style_layout)
        form_layout.addRow(QLabel("<b>단축키 설정</b>"))
        form_layout.addRow("번역 시작:", self.start_hotkey_edit)
        form_layout.addRow("번역 중지:", self.stop_hotkey_edit)
        form_layout.addRow("설정 창 열기/닫기:", self.setup_hotkey_edit)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content_widget)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        button_layout_h = QHBoxLayout()
        button_layout_h.addStretch(1)
        button_layout_h.addWidget(self.save_button)
        button_layout_h.addWidget(self.cancel_button)
        main_layout.addWidget(scroll_area)
        main_layout.addLayout(button_layout_h)
        self.setCentralWidget(self.main_container)

    def _connect_signals(self):
        self.google_browse_button.clicked.connect(self.browse_google_key_file)
        self.cancel_button.clicked.connect(self.close)
        self.save_button.clicked.connect(self.save_settings)
        self.add_source_lang_button.clicked.connect(lambda: self.add_language_selector("source"))
        self.add_target_lang_button.clicked.connect(lambda: self.add_language_selector("target"))
        self.show_original_checkbox.stateChanged.connect(self.update_preview_style)
        self.font_size_spinbox.valueChanged.connect(self.update_preview_style)
        self.original_text_font_size_spinbox.valueChanged.connect(self.update_preview_style)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self):
        self.update_preview_style()
        QMessageBox.information(self, "테마 변경", "테마 설정이 변경되었습니다.\n프로그램을 재시작하면 모든 창에 적용됩니다.")

    def load_settings(self):
        self.google_path_edit.setText(self.config_manager.get("google_credentials_path", ""))
        self.deepl_key_edit.setText(self.config_manager.get("deepl_api_key", ""))
        for item in self.source_lang_selectors[:]: self.remove_language_selector(item, self.source_lang_selectors, self.source_lang_layout)
        for item in self.target_lang_selectors[:]: self.remove_language_selector(item, self.target_lang_selectors, self.target_lang_layout)
        for lang_code in self.config_manager.get("source_languages", ["en-US"]): self.add_language_selector("source", lang_code)
        for lang_code in self.config_manager.get("target_languages", ["KO"]): self.add_language_selector("target", lang_code)
        
        formality_map = {"default": 0, "more": 1, "less": 2}
        self.formality_combo.setCurrentIndex(formality_map.get(self.config_manager.get("translation_formality", "default"), 0))
        
        self.use_video_model_checkbox.setChecked(self.config_manager.get("use_video_model", False))
        self.show_original_checkbox.setChecked(self.config_manager.get("show_original_text", True))
        self.font_size_spinbox.setValue(self.config_manager.get("overlay_font_size", 18))
        self.original_text_font_size_spinbox.setValue(self.config_manager.get("original_text_font_size_offset", -4))
        self.sentence_delay_spinbox.setValue(self.config_manager.get("sentence_commit_delay_ms", 700))
        self.start_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_start_translate", "")))
        self.stop_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_stop_translate", "")))
        self.setup_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_toggle_setup_window", "")))
        
        theme_map = {"dark": 0, "light": 1}
        
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(theme_map.get(self.config_manager.get("theme", "dark"), 0))
        self.theme_combo.blockSignals(False)
        self.update_preview_style()

    def save_settings(self):
        deepl_key_to_check = self.deepl_key_edit.text()
        if deepl_key_to_check and deepl:
            try:
                deepl.Translator(deepl_key_to_check).get_usage()
            except Exception as e:
                QMessageBox.warning(self, "API 키 오류", f"입력하신 DeepL API 키가 유효하지 않습니다.\n\n{e}")
                return
        self.config_manager.set("google_credentials_path", self.google_path_edit.text())
        self.config_manager.set("deepl_api_key", deepl_key_to_check)
        source_langs = [item["selector"].currentData() for item in self.source_lang_selectors]
        self.config_manager.set("source_languages", source_langs)
        target_langs = [item["selector"].currentData() for item in self.target_lang_selectors]
        self.config_manager.set("target_languages", target_langs)
        
        formality_map = {0: "default", 1: "more", 2: "less"}
        self.config_manager.set("translation_formality", formality_map.get(self.formality_combo.currentIndex(), "default"))
        
        self.config_manager.set("use_video_model", self.use_video_model_checkbox.isChecked())
        self.config_manager.set("sentence_commit_delay_ms", self.sentence_delay_spinbox.value())
        self.config_manager.set("show_original_text", self.show_original_checkbox.isChecked())
        self.config_manager.set("overlay_font_size", self.font_size_spinbox.value())
        self.config_manager.set("original_text_font_size_offset", self.original_text_font_size_spinbox.value())
        
        theme_map = {0: "dark", 1: "light"}
        self.config_manager.set("theme", theme_map.get(self.theme_combo.currentIndex(), "dark"))
        
        self.config_manager.set("hotkey_start_translate", self.start_hotkey_edit.keySequence().toString(QKeySequence.PortableText).lower())
        self.config_manager.set("hotkey_stop_translate", self.stop_hotkey_edit.keySequence().toString(QKeySequence.PortableText).lower())
        self.config_manager.set("hotkey_toggle_setup_window", self.setup_hotkey_edit.keySequence().toString(QKeySequence.PortableText).lower())
        self.is_saved = True
        QMessageBox.information(self, "저장 완료", "설정이 저장되었습니다.")
        self.close()

    def update_preview_style(self, _=None):
        preview_config = {}
        preview_config["show_original_text"] = self.show_original_checkbox.isChecked()
        preview_config["overlay_font_size"] = self.font_size_spinbox.value()
        preview_config["original_text_font_size_offset"] = self.original_text_font_size_spinbox.value()
        preview_config["target_languages"] = [item["selector"].currentData() for item in self.target_lang_selectors if item.get("selector")]
        
        theme_map = {0: "dark", 1: "light"}
        selected_theme = theme_map.get(self.theme_combo.currentIndex(), "dark")
        theme_colors = self.config_manager.get("themes", {}).get(selected_theme, {})
        preview_config.update(theme_colors)
        self.overlay_preview.update_preview(preview_config)

    def browse_google_key_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Google Cloud 인증 키 파일 선택", "", "JSON 파일 (*.json)")
        if filepath: self.google_path_edit.setText(filepath)

    def add_language_selector(self, type, lang_code=None):
        layout, selectors, max_count = (self.source_lang_layout, self.source_lang_selectors, 3) if type == "source" else (self.target_lang_layout, self.target_lang_selectors, 2)
        if len(selectors) >= max_count: return
        selector = QComboBox()
        for name, code in SUPPORTED_LANGUAGES.items():
            selector.addItem(name, code)
        if lang_code and lang_code in SUPPORTED_LANGUAGES.values():
            selector.setCurrentIndex(selector.findData(lang_code))
        remove_button = QPushButton("x")
        remove_button.setFixedSize(24, 24)
        row = QHBoxLayout()
        row.addWidget(selector)
        row.addWidget(remove_button)
        layout.addLayout(row)
        item = {"row": row, "selector": selector, "button": remove_button}
        selectors.append(item)
        remove_button.clicked.connect(lambda: self.remove_language_selector(item, selectors, layout))
        selector.currentIndexChanged.connect(self.update_preview_style)
        self.update_add_button_state()
        self.update_preview_style()

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

    def closeEvent(self, event):
        self.closed.emit(self.is_saved, "all")
        super().closeEvent(event)

if __name__ == '__main__':
    class MockConfigManager:
        def __init__(self):
            self.config = {
                "google_credentials_path": "",
                "deepl_api_key": "",
                "source_languages": ["en-US"],
                "target_languages": ["KO"],
                "translation_formality": "default",
                "use_video_model": False,
                "sentence_commit_delay_ms": 700,
                "show_original_text": True,
                "overlay_font_size": 18,
                "original_text_font_size_offset": -4,
                "hotkey_start_translate": "alt+1",
                "hotkey_stop_translate": "alt+2",
                "hotkey_toggle_setup_window": "alt+s",
                "theme": "dark",
                "themes": {
                    "dark": {
                        "overlay_font_color": "#f0f0f0",
                        "overlay_bg_color": "rgba(43, 43, 43, 180)",
                        "original_text_font_color": "#aaaaaa"
                    },
                    "light": {
                        "overlay_font_color": "#000000",
                        "overlay_bg_color": "rgba(240, 240, 240, 180)",
                        "original_text_font_color": "#555555"
                    }
                }
            }
        def get(self, key, default=None):
            return self.config.get(key, default)
        def set(self, key, value):
            self.config[key] = value
            print(f"Set '{key}' to '{value}'")

    app = QApplication(sys.argv)
    config_manager = MockConfigManager() 
    window = SetupWindow(config_manager)
   
    window.show()
    sys.exit(app.exec())