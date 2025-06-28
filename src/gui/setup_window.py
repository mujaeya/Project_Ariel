# src/gui/setup_window.py (최종 완성본)
import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QComboBox,
                             QFormLayout, QMessageBox, QFileDialog, QSpinBox,
                             QColorDialog, QKeySequenceEdit, QCheckBox, QFrame,
                             QListWidget, QListWidgetItem, QAbstractItemView,
                             QSizePolicy) # QSizePolicy를 import 라인에 추가
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette, QColor, QKeySequence, QFont

from config_manager import ConfigManager
# 오버레이 미리보기를 위해 TranslationItem 클래스를 가져옵니다.
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

    def update_preview(self):
        # 기존 예시 아이템들 삭제
        for item in self.example_items:
            self.main_layout.removeWidget(item)
            item.deleteLater()
        self.example_items.clear()
        
        example_data = [
            ("This is the most recent translation.", self._get_example_translation()),
            ("This is a previous translation.", self._get_example_translation(is_prev=True)),
            ("And this is the oldest one.", self._get_example_translation(is_old=True))
        ]
        
        for original, translated in example_data:
            item = TranslationItem(original, translated, self.config_manager)
            self.example_items.append(item)
            self.main_layout.addWidget(item)
        self._update_item_opacities()
        
    def _get_example_translation(self, is_prev=False, is_old=False):
        """미리보기에 표시될 예시 번역문을 생성합니다."""
        target_langs = self.config_manager.get("target_languages", ["KO"])
        if not target_langs: target_langs = ["KO"] # 선택된 언어가 없을 경우 대비
        
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
        self.resize(600, 850)
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

        self.formality_combo = QComboBox()
        self.formality_combo.addItem("기본 (자동 감지)", "default")
        self.formality_combo.addItem("존댓말 (공식적인 톤)", "more")
        self.formality_combo.addItem("반말 (비공식적인 톤)", "less")

        self.use_video_model_checkbox = QCheckBox("소음/영상 컨텐츠에 최적화된 STT 모델 사용")
        self.sentence_delay_spinbox = QSpinBox()
        self.sentence_delay_spinbox.setRange(300, 3000) # 0.3초 ~ 3초
        self.sentence_delay_spinbox.setSuffix(" ms")
        self.sentence_delay_spinbox.setToolTip("음성 인식이 끝난 후, 문장을 조합하기 위해 기다리는 시간입니다.\n짧을수록 반응이 빠르지만, 문장이 끊길 수 있습니다.")
        self.show_original_checkbox = QCheckBox("번역 결과 아래에 원본 텍스트 함께 표시")
        
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(8, 72)
        self.font_color_button = QPushButton("번역 글자색")
        self.bg_color_button = QPushButton("번역 배경색")
        
        self.original_text_font_size_spinbox = QSpinBox()
        self.original_text_font_size_spinbox.setRange(-10, 10)
        self.original_text_font_size_spinbox.setToolTip("번역 폰트 크기와의 상대적인 차이값입니다.")
        self.original_text_font_color_button = QPushButton("원본 글자색")
        
        self.start_hotkey_edit = QKeySequenceEdit()
        self.stop_hotkey_edit = QKeySequenceEdit()
        self.setup_hotkey_edit = QKeySequenceEdit()

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
        
        form_layout.addRow("번역 톤(뉘앙스):", self.formality_combo)

        form_layout.addRow(QLabel("<b>음성 인식(STT) 고급 설정</b>"))
        form_layout.addRow(self.use_video_model_checkbox)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("문장 조합 딜레이:"))
        delay_layout.addWidget(self.sentence_delay_spinbox)
        delay_layout.addStretch()
        form_layout.addRow(delay_layout)

        form_layout.addRow(QLabel("<b>오버레이 스타일 설정</b>"))
        form_layout.addRow(self.show_original_checkbox)
        
        font_layout = QHBoxLayout(); font_layout.addWidget(QLabel("기본 폰트 크기:")); font_layout.addWidget(self.font_size_spinbox); font_layout.addStretch()
        form_layout.addRow(font_layout)
        
        color_layout = QHBoxLayout(); color_layout.addWidget(self.font_color_button); color_layout.addWidget(self.bg_color_button); color_layout.addStretch()
        form_layout.addRow("번역 색상:", color_layout)
        
        original_style_layout = QHBoxLayout(); original_style_layout.addWidget(QLabel("원본 텍스트 크기(상대값):")); original_style_layout.addWidget(self.original_text_font_size_spinbox); original_style_layout.addWidget(self.original_text_font_color_button); original_style_layout.addStretch()
        form_layout.addRow("원본 색상:", original_style_layout)

        form_layout.addRow(QLabel("<b>단축키 설정</b>"))
        form_layout.addRow("번역 시작:", self.start_hotkey_edit)
        form_layout.addRow("번역 중지:", self.stop_hotkey_edit)
        form_layout.addRow("설정 창 열기/닫기:", self.setup_hotkey_edit)
        
        main_layout.addLayout(form_layout)
        
        button_layout_h = QHBoxLayout(); button_layout_h.addStretch(1); button_layout_h.addWidget(self.save_button); button_layout_h.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout_h)

    def _connect_signals(self):
        self.google_browse_button.clicked.connect(self.browse_google_key_file)
        self.cancel_button.clicked.connect(self.close)
        self.save_button.clicked.connect(self.save_settings)
        
        self.add_source_lang_button.clicked.connect(lambda: self.add_language_selector("source"))
        self.add_target_lang_button.clicked.connect(lambda: self.add_language_selector("target"))
        
        # 스타일 변경 시 즉시 미리보기에 반영
        self.show_original_checkbox.stateChanged.connect(self.update_preview_style)
        self.font_size_spinbox.valueChanged.connect(self.update_preview_style)
        self.original_text_font_size_spinbox.valueChanged.connect(self.update_preview_style)
        self.formality_combo.currentIndexChanged.connect(self.update_preview_style)
        self.font_color_button.clicked.connect(lambda: self.choose_color("overlay_font_color"))
        self.bg_color_button.clicked.connect(lambda: self.choose_color("overlay_bg_color"))
        self.original_text_font_color_button.clicked.connect(lambda: self.choose_color("original_text_font_color"))

    def add_language_selector(self, type, lang_code=None):
        if type == "source":
            layout, selector_list, max_count = self.source_lang_layout, self.source_lang_selectors, 3
        else:
            layout, selector_list, max_count = self.target_lang_layout, self.target_lang_selectors, 2
        
        if len(selector_list) >= max_count: return

        selector = QComboBox()
        for name, code in SUPPORTED_LANGUAGES.items():
            selector.addItem(name, code)
        
        if lang_code and lang_code in SUPPORTED_LANGUAGES.values():
            index = selector.findData(lang_code)
            if index >= 0: selector.setCurrentIndex(index)
        
        remove_button = QPushButton("x")
        remove_button.setFixedSize(24, 24)
        
        row = QHBoxLayout()
        row.addWidget(selector)
        row.addWidget(remove_button)
        
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
                    widget = child.widget()
                    if widget: widget.deleteLater()
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
        
        for lang_code in self.config_manager.get("source_languages", ["en-US"]): self.add_language_selector("source", lang_code)
        for lang_code in self.config_manager.get("target_languages", ["KO"]): self.add_language_selector("target", lang_code)

        index = self.formality_combo.findData(self.config_manager.get("translation_formality", "default"))
        if index >= 0: self.formality_combo.setCurrentIndex(index)

        self.use_video_model_checkbox.setChecked(self.config_manager.get("use_video_model", False))
        self.show_original_checkbox.setChecked(self.config_manager.get("show_original_text", True))
        self.font_size_spinbox.setValue(self.config_manager.get("overlay_font_size", 18))
        self.original_text_font_size_spinbox.setValue(self.config_manager.get("original_text_font_size_offset", -4))
        self.sentence_delay_spinbox.setValue(self.config_manager.get("sentence_commit_delay_ms", 700))
        
        self.start_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_start_translate", "")))
        self.stop_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_stop_translate", "")))
        self.setup_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_toggle_setup_window", "")))
        
        self.update_preview_style()

    def save_settings(self):
        # 현재 UI 값들을 config 객체에 최종적으로 반영
        self.update_preview_style(save_to_config=True)

        self.config_manager.set("google_credentials_path", self.google_path_edit.text())
        self.config_manager.set("deepl_api_key", self.deepl_key_edit.text())
        
        source_langs = [item["selector"].currentData() for item in self.source_lang_selectors]
        self.config_manager.set("source_languages", source_langs)
        
        target_langs = [item["selector"].currentData() for item in self.target_lang_selectors]
        self.config_manager.set("target_languages", target_langs)
        
        self.config_manager.set("translation_formality", self.formality_combo.currentData())
        self.config_manager.set("use_video_model", self.use_video_model_checkbox.isChecked())
        self.config_manager.set("sentence_commit_delay_ms", self.sentence_delay_spinbox.value())
        
        self.config_manager.set("hotkey_start_translate", self.start_hotkey_edit.keySequence().toString(QKeySequence.PortableText).lower())
        self.config_manager.set("hotkey_stop_translate", self.stop_hotkey_edit.keySequence().toString(QKeySequence.PortableText).lower())
        self.config_manager.set("hotkey_toggle_setup_window", self.setup_hotkey_edit.keySequence().toString(QKeySequence.PortableText).lower())
        
        # 색상은 choose_color에서 임시로만 변경되므로, 여기서 최종 set
        self.config_manager.set("overlay_font_color", self.config_manager.config.get("overlay_font_color"))
        self.config_manager.set("overlay_bg_color", self.config_manager.config.get("overlay_bg_color"))
        self.config_manager.set("original_text_font_color", self.config_manager.config.get("original_text_font_color"))

        self.is_saved = True
        QMessageBox.information(self, "저장 완료", "설정이 저장되었습니다.")
        self.close()

    def update_preview_style(self, _=None, save_to_config=False):
        # 이 함수는 값 변경 시 임시로 config 객체에만 반영하고, 저장 시에만 set을 호출하도록 수정
        # (이 부분은 이전 코드의 로직을 그대로 사용해도 무방합니다)
        config_data = {
            "show_original_text": self.show_original_checkbox.isChecked(),
            "overlay_font_size": self.font_size_spinbox.value(),
            "original_text_font_size_offset": self.original_text_font_size_spinbox.value(),
            "target_languages": [item["selector"].currentData() for item in self.target_lang_selectors]
        }
        self.config_manager.config.update(config_data)
        
        self.overlay_preview.update_preview()

    def choose_color(self, config_key):
        initial_color = QColor(self.config_manager.get(config_key))
        color = QColorDialog.getColor(initial_color, self, "색상 선택")
        if color.isValid():
            if config_key == "overlay_bg_color": color.setAlpha(160)
            self.config_manager.config[config_key] = color.name(QColor.NameFormat.HexArgb)
            self.update_preview_style()

    def browse_google_key_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Google Cloud 인증 키 파일 선택", "", "JSON 파일 (*.json)")
        if filepath:
            self.google_path_edit.setText(filepath)

    def closeEvent(self, event):
        if not self.is_saved:
            self.config_manager.load_config() # 저장하지 않고 닫으면 원래 설정으로 복구
        self.closed.emit(self.is_saved, "all")
        super().closeEvent(event)