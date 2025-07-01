# src/gui/setup_window.py (이 코드로 전체를 교체해주세요)
# (이 파일의 다른 부분은 이전과 동일하며, SetupWindow 클래스의 __init__ 부분만 수정되었습니다.)
import sys
import os
import logging
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QListWidget, QStackedWidget, QVBoxLayout, 
                             QListWidgetItem, QPushButton, QSpacerItem, QSizePolicy, QLineEdit,
                             QKeySequenceEdit, QLabel, QFileDialog, QComboBox, QSpinBox, 
                             QCheckBox, QColorDialog, QInputDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QKeySequence, QPalette, QColor
from gui.overlay_window import TranslationItem
from utils import resource_path
from config_manager import ConfigManager
from gui.fluent_widgets import (NavigationItemWidget, SettingsPage, TitleLabel, 
                               DescriptionLabel, SettingsCard)

# ... ApiSettingsPage, LanguageSettingsPage 등 다른 클래스들은 이전과 동일 ...
# SUPPORTED_LANGUAGES, CODE_TO_NAME 코드는 그대로 유지
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


class ApiSettingsPage(SettingsPage):
    """API 및 Tesseract 경로 설정 페이지"""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        
        self.add_widget(TitleLabel("연동 서비스 설정"))
        self.add_widget(DescriptionLabel("Ariel의 핵심 기능에 필요한 외부 서비스 및 프로그램을 연동합니다."))
        
        tesseract_card = SettingsCard("Tesseract OCR", "화면 번역(OCR) 기능을 사용하기 위해 tesseract.exe 파일의 위치를 지정해야 합니다.")
        self.tesseract_path_edit = QLineEdit()
        self.tesseract_browse_button = QPushButton("파일 찾아보기...")
        self.tesseract_browse_button.clicked.connect(self.browse_tesseract)
        tesseract_layout = QHBoxLayout()
        tesseract_layout.addWidget(self.tesseract_path_edit)
        tesseract_layout.addWidget(self.tesseract_browse_button)
        tesseract_card.add_layout(tesseract_layout)
        self.add_widget(tesseract_card)

        google_card = SettingsCard("Google Cloud (음성 인식)", "음성을 텍스트로 변환(STT)하기 위해 Google Cloud의 인증 키 파일(.json)이 필요합니다.")
        self.google_path_edit = QLineEdit()
        self.google_browse_button = QPushButton("파일 찾아보기...")
        self.google_browse_button.clicked.connect(self.browse_google_key)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.google_path_edit)
        path_layout.addWidget(self.google_browse_button)
        google_card.add_layout(path_layout)
        self.add_widget(google_card)

        deepl_card = SettingsCard("DeepL (기계 번역)", "텍스트를 다른 언어로 번역하기 위해 DeepL API 인증 키가 필요합니다.")
        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        deepl_card.add_widget(self.deepl_key_edit)
        self.add_widget(deepl_card)

    def browse_tesseract(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Tesseract 실행 파일 선택", "", "Tesseract (tesseract.exe)")
        if filepath:
            self.tesseract_path_edit.setText(filepath.replace("\\", "/"))

    def browse_google_key(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Google Cloud 인증 키 파일 선택", "", "JSON 파일 (*.json)")
        if filepath:
            self.google_path_edit.setText(filepath)

    def load_settings(self):
        self.tesseract_path_edit.setText(self.config_manager.get("tesseract_path", ""))
        self.google_path_edit.setText(self.config_manager.get("google_credentials_path", ""))
        self.deepl_key_edit.setText(self.config_manager.get("deepl_api_key", ""))

    def save_settings(self):
        tesseract_path = self.tesseract_path_edit.text().replace("\\", "/")
        google_path = self.google_path_edit.text().replace("\\", "/")
        self.config_manager.set("tesseract_path", tesseract_path)
        self.config_manager.set("google_credentials_path", google_path)
        self.config_manager.set("deepl_api_key", self.deepl_key_edit.text())


class LanguageSettingsPage(SettingsPage):
    """언어 설정 페이지"""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.source_lang_selectors = []
        self.target_lang_selectors = []

        self.add_widget(TitleLabel("언어 설정"))
        self.add_widget(DescriptionLabel("번역할 원본 언어와 번역될 대상 언어를 선택합니다."))

        source_card = SettingsCard("원본 언어 (음성 인식)", "인식할 음성의 언어를 선택하세요. 최대 3개까지 추가할 수 있습니다.")
        self.source_lang_layout = QVBoxLayout()
        source_card.add_layout(self.source_lang_layout)
        self.add_source_lang_button = QPushButton("+ 원본 언어 추가")
        self.add_source_lang_button.clicked.connect(lambda: self.add_language_selector("source"))
        source_card.add_widget(self.add_source_lang_button)
        self.add_widget(source_card)

        target_card = SettingsCard("번역 언어 (자막)", "음성을 번역하여 표시할 언어를 선택하세요. 최대 2개까지 추가할 수 있습니다.")
        self.target_lang_layout = QVBoxLayout()
        target_card.add_layout(self.target_lang_layout)
        self.add_target_lang_button = QPushButton("+ 번역 언어 추가")
        self.add_target_lang_button.clicked.connect(lambda: self.add_language_selector("target"))
        target_card.add_widget(self.add_target_lang_button)
        self.add_widget(target_card)
        
        delay_card = SettingsCard("번역 딜레이 설정", "음성 인식이 끝난 후, 문장을 조합하기 위해 기다리는 시간입니다.\n짧을수록 반응이 빠르지만, 문장이 끊겨 번역될 수 있습니다.")

        self.sentence_delay_spinbox = QSpinBox()
        self.sentence_delay_spinbox.setRange(50, 3000)
        self.sentence_delay_spinbox.setSuffix(" ms")

        presets_layout = QHBoxLayout()
        presets_layout.addWidget(QLabel("추천 설정:"))
        fast_button = QPushButton("빠른 반응 (250ms)")
        default_button = QPushButton("기본값 (700ms)")
        stable_button = QPushButton("안정적 문장 (1200ms)")

        fast_button.clicked.connect(lambda: self.sentence_delay_spinbox.setValue(250))
        default_button.clicked.connect(lambda: self.sentence_delay_spinbox.setValue(700))
        stable_button.clicked.connect(lambda: self.sentence_delay_spinbox.setValue(1200))

        presets_layout.addWidget(fast_button)
        presets_layout.addWidget(default_button)
        presets_layout.addWidget(stable_button)
        presets_layout.addStretch()

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("수동 설정:"))
        delay_layout.addWidget(self.sentence_delay_spinbox)
        delay_layout.addStretch()

        delay_card.add_layout(delay_layout)
        delay_card.add_layout(presets_layout)
        self.add_widget(delay_card)

    def add_language_selector(self, type, lang_code=None):
        layout, selector_list, max_count = (self.source_lang_layout, self.source_lang_selectors, 3) if type == "source" else (self.target_lang_layout, self.target_lang_selectors, 2)
        if len(selector_list) >= max_count: return

        selector = QComboBox()
        for name, code in SUPPORTED_LANGUAGES.items(): selector.addItem(name, code)
        if lang_code and lang_code in SUPPORTED_LANGUAGES.values(): selector.setCurrentIndex(selector.findData(lang_code))
        
        remove_button = QPushButton("삭제")
        
        row = QHBoxLayout()
        row.addWidget(selector, 1)
        row.addWidget(remove_button)
        layout.addLayout(row)

        item = {"row": row, "selector": selector, "button": remove_button}
        selector_list.append(item)
        
        remove_button.clicked.connect(lambda: self.remove_language_selector(item, selector_list, layout))
        self.update_add_button_state()

    def remove_language_selector(self, item_to_remove, selector_list, parent_layout):
        if selector_list is self.source_lang_selectors and len(selector_list) <= 1:
            QMessageBox.warning(self, "삭제 불가", "원본 언어는 최소 1개 이상 필요합니다.")
            return

        for i, item in enumerate(selector_list):
            if item == item_to_remove:
                while item["row"].count():
                    child = item["row"].takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                parent_layout.removeItem(item["row"])
                item["row"].deleteLater()
                
                selector_list.pop(i)
                self.update_add_button_state()
                break

    def update_add_button_state(self):
        self.add_source_lang_button.setEnabled(len(self.source_lang_selectors) < 3)
        self.add_target_lang_button.setEnabled(len(self.target_lang_selectors) < 2)

    def load_settings(self):
        while len(self.source_lang_selectors) > 0: self.remove_language_selector(self.source_lang_selectors[0], self.source_lang_selectors, self.source_lang_layout)
        while len(self.target_lang_selectors) > 0: self.remove_language_selector(self.target_lang_selectors[0], self.target_lang_selectors, self.target_lang_layout)

        source_langs = self.config_manager.get("source_languages", ["en-US"])
        if not source_langs: source_langs = ["en-US"]
        for lang_code in source_langs: self.add_language_selector("source", lang_code)
        
        target_langs = self.config_manager.get("target_languages", ["KO"])
        if not target_langs: target_langs = []
        for lang_code in target_langs: self.add_language_selector("target", lang_code)
        
        self.sentence_delay_spinbox.setValue(self.config_manager.get("sentence_commit_delay_ms", 700))
        self.update_add_button_state()

    def save_settings(self):
        self.config_manager.set("source_languages", [item["selector"].currentData() for item in self.source_lang_selectors])
        self.config_manager.set("target_languages", [item["selector"].currentData() for item in self.target_lang_selectors])
        self.config_manager.set("sentence_commit_delay_ms", self.sentence_delay_spinbox.value())


class StyleSettingsPage(SettingsPage):
    """오버레이 스타일 설정 페이지"""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        
        self.add_widget(TitleLabel("오버레이 스타일"))
        self.add_widget(DescriptionLabel("번역 자막이 표시되는 오버레이 창의 디자인을 설정합니다."))
        
        font_card = SettingsCard("폰트 및 표시 형식")
        self.show_original_checkbox = QCheckBox("번역 결과 아래에 원본 텍스트 함께 표시")
        font_card.add_widget(self.show_original_checkbox)
        
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("번역 폰트 크기:"))
        self.font_size_spinbox = QSpinBox(); self.font_size_spinbox.setRange(8, 72)
        font_size_layout.addWidget(self.font_size_spinbox)
        font_size_layout.addStretch()
        font_card.add_layout(font_size_layout)

        original_font_layout = QHBoxLayout()
        original_font_layout.addWidget(QLabel("원본 폰트 크기(상대값):"))
        self.original_font_size_spinbox = QSpinBox(); self.original_font_size_spinbox.setRange(-10, 10)
        original_font_layout.addWidget(self.original_font_size_spinbox)
        original_font_layout.addStretch()
        font_card.add_layout(original_font_layout)
        self.add_widget(font_card)

        color_card = SettingsCard("색상")
        self.font_color_widget = self.create_color_widget("번역 글자색")
        self.bg_color_widget = self.create_color_widget("번역 배경색 (투명도 포함)", has_alpha=True)
        self.original_text_font_color_widget = self.create_color_widget("원본 글자색")

        color_card.add_widget(self.font_color_widget)
        color_card.add_widget(self.bg_color_widget)
        color_card.add_widget(self.original_text_font_color_widget)
        self.add_widget(color_card)

        preview_card = SettingsCard("실시간 미리보기")
        self.temp_preview_config = {}

        self.preview_item = TranslationItem(
            "This is the original text.", 
            {"KO": "이것은 번역된 텍스트입니다.", "JA": "これは翻訳されたテキストです。"},
            self.config_manager,
            temp_config=self.temp_preview_config
        )
        preview_card.add_widget(self.preview_item)
        self.add_widget(preview_card)
        
        self.show_original_checkbox.stateChanged.connect(self.update_preview)
        self.font_size_spinbox.valueChanged.connect(self.update_preview)
        self.original_font_size_spinbox.valueChanged.connect(self.update_preview)
        
    def update_preview(self):
        self.temp_preview_config['overlay_font_size'] = self.font_size_spinbox.value()
        self.temp_preview_config['original_text_font_size_offset'] = self.original_font_size_spinbox.value()
        self.temp_preview_config['show_original_text'] = self.show_original_checkbox.isChecked()
        self.temp_preview_config['overlay_font_color'] = self.font_color_widget.preview.palette().color(QPalette.ColorRole.Window).name()
        self.temp_preview_config['overlay_bg_color'] = self.bg_color_widget.preview.palette().color(QPalette.ColorRole.Window).name(QColor.NameFormat.HexArgb)
        self.temp_preview_config['original_text_font_color'] = self.original_text_font_color_widget.preview.palette().color(QPalette.ColorRole.Window).name()
        
        self.preview_item.update_styles()

    def create_color_widget(self, text, has_alpha=False):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton(text)
        preview = QWidget(); preview.setFixedSize(24, 24); preview.setAutoFillBackground(True)
        button.clicked.connect(lambda: self.choose_color(preview, has_alpha))
        layout.addWidget(button, 1); layout.addWidget(preview)
        container.preview = preview 
        return container

    def choose_color(self, preview_widget, has_alpha=False):
        initial_color = preview_widget.palette().color(QPalette.ColorRole.Window)
        options = QColorDialog.ColorDialogOption()
        if has_alpha: options |= QColorDialog.ColorDialogOption.ShowAlphaChannel
        color = QColorDialog.getColor(initial_color, self, "색상 선택", options)
        if color.isValid():
            palette = preview_widget.palette()
            palette.setColor(QPalette.ColorRole.Window, color)
            preview_widget.setPalette(palette)
            self.update_preview()

    def load_settings(self):
        self.show_original_checkbox.setChecked(self.config_manager.get("show_original_text", True))
        self.font_size_spinbox.setValue(self.config_manager.get("overlay_font_size", 18))
        self.original_font_size_spinbox.setValue(self.config_manager.get("original_text_font_size_offset", -4))
        self._update_color_preview(self.font_color_widget, self.config_manager.get("overlay_font_color", "#FFFFFF"))
        self._update_color_preview(self.bg_color_widget, self.config_manager.get("overlay_bg_color", "#80000000"))
        self._update_color_preview(self.original_text_font_color_widget, self.config_manager.get("original_text_font_color", "#CCCCCC"))
        self.update_preview()

    def _update_color_preview(self, container_widget, color_str):
        preview = container_widget.preview
        palette = preview.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(color_str))
        preview.setPalette(palette)
    
    def save_settings(self):
        self.config_manager.set("show_original_text", self.show_original_checkbox.isChecked())
        self.config_manager.set("overlay_font_size", self.font_size_spinbox.value())
        self.config_manager.set("original_text_font_size_offset", self.original_font_size_spinbox.value())
        self.config_manager.set("overlay_font_color", self.font_color_widget.preview.palette().color(QPalette.ColorRole.Window).name())
        self.config_manager.set("overlay_bg_color", self.bg_color_widget.preview.palette().color(QPalette.ColorRole.Window).name(QColor.NameFormat.HexArgb))
        self.config_manager.set("original_text_font_color", self.original_text_font_color_widget.preview.palette().color(QPalette.ColorRole.Window).name())


class HotkeySettingsPage(SettingsPage):
    """단축키 설정 페이지"""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.add_widget(TitleLabel("단축키 설정"))
        self.add_widget(DescriptionLabel("자주 사용하는 기능을 키보드 단축키로 빠르게 실행하세요."))
        
        hotkey_card = SettingsCard("전역 단축키")
        self.start_hotkey_edit = self.create_hotkey_edit(hotkey_card, "음성 번역 시작/중지:")
        self.ocr_hotkey_edit = self.create_hotkey_edit(hotkey_card, "화면 번역 (OCR):")
        self.setup_hotkey_edit = self.create_hotkey_edit(hotkey_card, "설정 창 열기/닫기:")
        self.quit_hotkey_edit = self.create_hotkey_edit(hotkey_card, "프로그램 종료:")
        self.add_widget(hotkey_card)

    def create_hotkey_edit(self, parent_card, label_text):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label_text))
        key_edit = QKeySequenceEdit()
        layout.addWidget(key_edit)
        parent_card.add_layout(layout)
        return key_edit
        
    def load_settings(self):
        self.start_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_start_translate", "shift+1")))
        self.ocr_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_ocr", "shift+3")))
        self.setup_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_toggle_setup_window", "shift+`")))
        self.quit_hotkey_edit.setKeySequence(QKeySequence.fromString(self.config_manager.get("hotkey_quit_app", "shift+0")))

    def save_settings(self):
        portable_format = QKeySequence.SequenceFormat.PortableText
        self.config_manager.set("hotkey_start_translate", self.start_hotkey_edit.keySequence().toString(portable_format).lower())
        self.config_manager.set("hotkey_ocr", self.ocr_hotkey_edit.keySequence().toString(portable_format).lower())
        self.config_manager.set("hotkey_toggle_setup_window", self.setup_hotkey_edit.keySequence().toString(portable_format).lower())
        self.config_manager.set("hotkey_quit_app", self.quit_hotkey_edit.keySequence().toString(portable_format).lower())


class ProfileSettingsPage(SettingsPage):
    """프로필 관리 페이지"""
    profile_changed = Signal()

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.add_widget(TitleLabel("프로필 관리"))
        self.add_widget(DescriptionLabel("다양한 작업 환경에 맞는 설정 프리셋을 저장하고 관리합니다."))
        
        profile_card = SettingsCard("프로필 목록")
        self.profile_list_widget = QListWidget()
        self.profile_list_widget.itemSelectionChanged.connect(self.update_button_states)
        profile_card.add_widget(self.profile_list_widget)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("새로 만들기...")
        self.rename_button = QPushButton("이름 변경...")
        self.remove_button = QPushButton("삭제")
        self.activate_button = QPushButton("활성화"); self.activate_button.setObjectName("primaryButton")
        button_layout.addWidget(self.add_button); button_layout.addWidget(self.rename_button)
        button_layout.addWidget(self.remove_button); button_layout.addStretch()
        button_layout.addWidget(self.activate_button)
        profile_card.add_layout(button_layout)
        self.add_widget(profile_card)

        notification_card = SettingsCard("알림 설정")
        self.show_tray_notifications_checkbox = QCheckBox("프로필 전환, 번역 시작/중지 시 트레이 알림 표시")
        notification_card.add_widget(self.show_tray_notifications_checkbox)
        self.add_widget(notification_card)
        
        self.add_button.clicked.connect(self.add_profile); self.rename_button.clicked.connect(self.rename_profile)
        self.remove_button.clicked.connect(self.remove_profile); self.activate_button.clicked.connect(self.activate_profile)

    def load_settings(self):
        self.profile_list_widget.clear()
        profile_names = self.config_manager.get_profile_names()
        active_profile = self.config_manager.get_active_profile_name()
        for name in profile_names:
            item = QListWidgetItem(name)
            self.profile_list_widget.addItem(item)
            if name == active_profile:
                font = item.font(); font.setBold(True); item.setFont(font)
                item.setText(f"{name} (활성)")
                self.profile_list_widget.setCurrentItem(item)
        self.update_button_states()
        self.show_tray_notifications_checkbox.setChecked(self.config_manager.get("show_tray_notifications", True))

    def update_button_states(self):
        selected_item = self.profile_list_widget.currentItem()
        is_selected = selected_item is not None
        self.rename_button.setEnabled(is_selected); self.remove_button.setEnabled(is_selected)
        is_active = is_selected and selected_item.text().endswith(" (활성)")
        self.activate_button.setEnabled(is_selected and not is_active)

    def add_profile(self):
        text, ok = QInputDialog.getText(self, "새 프로필 만들기", "새 프로필의 이름을 입력하세요:")
        if ok and text:
            success, message = self.config_manager.add_profile(text)
            if success: self.load_settings()
            else: QMessageBox.warning(self, "오류", message)

    def rename_profile(self):
        selected_item = self.profile_list_widget.currentItem()
        if not selected_item: return
        old_name = selected_item.text().replace(" (활성)", "")
        text, ok = QInputDialog.getText(self, "프로필 이름 변경", "새 이름을 입력하세요:", text=old_name)
        if ok and text and text != old_name:
            success, message = self.config_manager.rename_profile(old_name, text)
            if success: self.load_settings(); self.profile_changed.emit()
            else: QMessageBox.warning(self, "오류", message)
    
    def remove_profile(self):
        selected_item = self.profile_list_widget.currentItem()
        if not selected_item: return
        profile_name = selected_item.text().replace(" (활성)", "")
        reply = QMessageBox.question(self, "프로필 삭제", f"정말로 '{profile_name}' 프로필을 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
    if reply == QMessageBox.StandardButton.Yes:
        success, message = self.config_manager.remove_profile(profile_name)
        if success:
            self.load_settings()
            self.profile_changed.emit() 
        else:
            QMessageBox.warning(self, "오류", message)

    def activate_profile(self):
        selected_item = self.profile_list_widget.currentItem()
        if not selected_item: return
        profile_name = selected_item.text().replace(" (활성)", "")
        if self.config_manager.switch_profile(profile_name):
            self.load_settings(); self.profile_changed.emit()
    
    def save_settings(self):
        self.config_manager.set("show_tray_notifications", self.show_tray_notifications_checkbox.isChecked())


# --- 메인 설정 창 ---
class SetupWindow(QWidget):
    closed = Signal(bool, str)
    # [핵심 수정] 생성자에 initial_page_index 인자 추가
    def __init__(self, config_manager: ConfigManager, initial_page_index=0):
        super().__init__()
        self.config_manager = config_manager
        self.is_saved = False
        self.setObjectName("setupWindow")
        self.setWindowTitle("Ariel 설정")
        self.resize(800, 600)
        self.load_stylesheet()
        self._init_ui()
        self._add_pages()
        self.navigation_bar.currentRowChanged.connect(self.pages_stack.setCurrentIndex)
        self.navigation_bar.currentRowChanged.connect(self.update_navigation_icons)
        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button.clicked.connect(self.close)
        self.profile_page.profile_changed.connect(self.load_settings)
        self.load_settings()
        
        # [핵심 수정] 생성자 마지막에서 전달받은 인덱스로 페이지를 설정
        self.navigation_bar.setCurrentRow(initial_page_index)

    def _init_ui(self):
        main_layout = QHBoxLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)
        self.navigation_bar = QListWidget(); self.navigation_bar.setObjectName("navigationBar"); self.navigation_bar.setFixedWidth(220)
        self.pages_stack = QStackedWidget(); self.pages = []
        content_layout = QVBoxLayout(); content_layout.setContentsMargins(0,0,0,0); content_layout.setSpacing(0)
        content_layout.addWidget(self.pages_stack, 1)
        button_bar = QWidget(); button_bar.setObjectName("buttonBar")
        button_bar_layout = QHBoxLayout(button_bar); button_bar_layout.setContentsMargins(10,10,10,10)
        button_bar_layout.addSpacerItem(QSpacerItem(40,20,QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum))
        self.save_button = QPushButton("현재 프로필에 저장"); self.save_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton("취소")
        button_bar_layout.addWidget(self.save_button); button_bar_layout.addWidget(self.cancel_button)
        content_layout.addWidget(button_bar)
        main_layout.addWidget(self.navigation_bar); main_layout.addLayout(content_layout, 1)

    def _add_pages(self):
        self.profile_page = ProfileSettingsPage(self.config_manager)
        self.api_page = ApiSettingsPage(self.config_manager)
        self.lang_page = LanguageSettingsPage(self.config_manager)
        self.style_page = StyleSettingsPage(self.config_manager)
        self.hotkey_page = HotkeySettingsPage(self.config_manager)
        
        # 페이지 인덱스: 0=프로필, 1=연동 서비스, 2=언어, 3=스타일, 4=단축키
        self.add_page(self.profile_page, "프로필", 'assets/icons/profile.svg')
        self.add_page(self.api_page, "연동 서비스", 'assets/icons/key.svg')
        self.add_page(self.lang_page, "언어 및 번역", 'assets/icons/language.svg')
        self.add_page(self.style_page, "오버레이 스타일", 'assets/icons/brush.svg')
        self.add_page(self.hotkey_page, "단축키", 'assets/icons/keyboard.svg')

    def add_page(self, page_widget, title, icon_relative_path):
        self.pages.append(page_widget)
        self.pages_stack.addWidget(page_widget)
        item = QListWidgetItem()
        item_widget = NavigationItemWidget(icon_relative_path, title)
        item.setSizeHint(item_widget.sizeHint())
        self.navigation_bar.addItem(item)
        self.navigation_bar.setItemWidget(item, item_widget)
        
    def update_navigation_icons(self, current_row):
        for row in range(self.navigation_bar.count()):
            item = self.navigation_bar.item(row)
            widget = self.navigation_bar.itemWidget(item)
            if isinstance(widget, NavigationItemWidget):
                color = "#0053C6" if row == current_row else "#333333"
                widget.set_icon_color(color)

    def load_stylesheet(self):
        style_path = resource_path('style.qss')
        try:
            with open(style_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            logging.warning(f"경고: 스타일시트 파일을 찾을 수 없습니다: {style_path}")

    def load_settings(self):
        logging.info(f"'{self.config_manager.get_active_profile_name()}' 프로필의 설정을 불러옵니다.")
        for page in self.pages:
            if hasattr(page, 'load_settings'):
                page.load_settings()

    def save_settings(self):
        logging.info(f"'{self.config_manager.get_active_profile_name()}' 프로필에 현재 설정을 저장합니다.")
        for page in self.pages:
            if hasattr(page, 'save_settings'):
                page.save_settings()
        self.is_saved = True
        self.close()

    def closeEvent(self, event):
        self.closed.emit(self.is_saved, "all")
        super().closeEvent(event)