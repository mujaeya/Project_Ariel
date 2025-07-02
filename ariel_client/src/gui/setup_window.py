# ariel_client/src/gui/setup_window.py (이 코드로 전체 교체)
import sys
import os
import logging
import sounddevice as sd
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QListWidget, QStackedWidget, QVBoxLayout, 
                             QListWidgetItem, QPushButton, QSpacerItem, QSizePolicy, QLineEdit,
                             QKeySequenceEdit, QLabel, QFileDialog, QComboBox, QSpinBox, 
                             QCheckBox, QColorDialog, QInputDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QPalette, QColor
from .overlay_window import TranslationItem
from ..utils import resource_path
from ..config_manager import ConfigManager
from .fluent_widgets import (NavigationItemWidget, SettingsPage, TitleLabel, 
                               DescriptionLabel, SettingsCard)

# ... (SUPPORTED_LANGUAGES, CODE_TO_NAME 등은 그대로 유지) ...
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
    """API 키 및 서버 주소 설정 페이지"""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        
        self.add_widget(TitleLabel("연동 서비스 설정"))
        self.add_widget(DescriptionLabel("Ariel의 핵심 기능에 필요한 외부 서비스 및 설정을 연동합니다."))
        
        # [수정] 서버 URL 설정 UI 추가
        server_card = SettingsCard("Ariel 백엔드 서버", "OCR, STT 등 무거운 작업을 처리하는 백엔드 서버의 주소를 입력합니다.")
        self.server_url_edit = QLineEdit()
        self.server_url_edit.setPlaceholderText("예: http://127.0.0.1:8000")
        server_card.add_widget(self.server_url_edit)
        self.add_widget(server_card)

        # [수정] DeepL 설정은 클라이언트에 계속 필요하므로 유지
        deepl_card = SettingsCard("DeepL (기계 번역)", "텍스트를 다른 언어로 번역하기 위해 DeepL API 인증 키가 필요합니다. 이 정보는 서버로 전송되지 않습니다.")
        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        deepl_card.add_widget(self.deepl_key_edit)
        self.add_widget(deepl_card)
        
        # [수정] Tesseract 및 Google Cloud 관련 UI는 제거

    def load_settings(self):
        # [수정] 서버 URL 로드
        self.server_url_edit.setText(self.config_manager.get("server_url", "http://127.0.0.1:8000"))
        self.deepl_key_edit.setText(self.config_manager.get("deepl_api_key", ""))

    def save_settings(self):
        # [수정] 서버 URL 저장
        self.config_manager.set("server_url", self.server_url_edit.text())
        self.config_manager.set("deepl_api_key", self.deepl_key_edit.text())

class AudioSettingsPage(SettingsPage):
    """'Ariel Audio Sense'가 적용된 지능형 오디오 설정 페이지"""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        
        self.add_widget(TitleLabel("오디오 설정"))
        self.add_widget(DescriptionLabel("번역할 소리가 나는 오디오 장치를 선택합니다.\n'✅ (권장)' 태그가 붙은 자동 선택 장치를 권장합니다."))
        
        audio_card = SettingsCard("입력 장치 (Source)")
        self.device_list = QListWidget()
        self.device_list.setStyleSheet("QListWidget { border-radius: 6px; }")
        audio_card.add_widget(self.device_list)
        
        refresh_button = QPushButton("장치 목록 새로고침")
        refresh_button.clicked.connect(self.populate_audio_devices)
        audio_card.add_widget(refresh_button)
        
        self.add_widget(audio_card)
        self.populate_audio_devices()

    def populate_audio_devices(self):
        self.device_list.clear()
        try:
            devices = sd.query_devices()
            default_output_device = sd.query_devices(kind='output')
            
            # --- 지능형 자동 선택 로직 ---
            recommended_device = None
            if default_output_device:
                # 1순위: 윈도우 기본 출력 장치의 WASAPI 루프백 장치
                for i, dev in enumerate(devices):
                    is_input = dev['max_input_channels'] > 0
                    is_wasapi = 'WASAPI' in dev['hostapi']
                    is_loopback = 'loopback' in dev['name'].lower()
                    if is_input and is_wasapi and is_loopback and default_output_device['name'] in dev['name']:
                        recommended_device = (i, dev)
                        break
            
            # 2순위: 가상 오디오 케이블
            if not recommended_device:
                for i, dev in enumerate(devices):
                     if dev['max_input_channels'] > 0 and 'cable' in dev['name'].lower():
                         recommended_device = (i, dev)
                         break

            # --- 사용자 친화적 목록 생성 ---
            if recommended_device:
                index, dev = recommended_device
                item = QListWidgetItem(f"✅ {dev['name']} (권장)")
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.device_list.addItem(item)
            
            for i, dev in enumerate(devices):
                if (recommended_device and i == recommended_device[0]) or dev['max_input_channels'] == 0:
                    continue
                if 'mapper' not in dev['name'].lower():
                    icon = "🔊" if 'loopback' in dev['name'].lower() or 'mix' in dev['name'].lower() else "🎤"
                    item = QListWidgetItem(f"{icon} {dev['name']}")
                    item.setData(Qt.ItemDataRole.UserRole, i)
                    self.device_list.addItem(item)
        except Exception as e:
            logging.error(f"오디오 장치 목록을 불러오는 데 실패했습니다: {e}", exc_info=True)
            self.device_list.addItem("장치를 찾을 수 없음")
        
        self.load_settings()

    def load_settings(self):
        saved_device_index = self.config_manager.get("audio_input_device_index")
        if saved_device_index is not None:
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == saved_device_index:
                    item.setSelected(True)
                    return
        if self.device_list.count() > 0:
            self.device_list.item(0).setSelected(True)

    def save_settings(self):
        selected_items = self.device_list.selectedItems()
        if selected_items:
            selected_index = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.config_manager.set("audio_input_device_index", selected_index)

# 내부 클래스들의 import 경로가 정확한지 확인해야 함)
class SetupWindow(QWidget):
    closed = Signal() # [수정] 시그널 파라미터 단순화
    
    def __init__(self, config_manager: ConfigManager, initial_page_index=0):
        super().__init__()
        self.config_manager = config_manager
        self.is_saved = False # 저장 여부 플래그
        self.setObjectName("setupWindow")
        self.setWindowTitle("Ariel 설정")
        self.resize(1024, 768)
        self.load_stylesheet()
        self._init_ui()
        self._add_pages()

        # 시그널 연결
        self.navigation_bar.currentRowChanged.connect(self.pages_stack.setCurrentIndex)
        self.navigation_bar.currentRowChanged.connect(self.update_navigation_icons)
        self.save_button.clicked.connect(self.save_and_close)
        self.cancel_button.clicked.connect(self.close)
        
        # self.profile_page.profile_changed.connect(self.load_settings) # 프로필 페이지 구현 시 활성화
        
        self.load_settings()
        self.navigation_bar.setCurrentRow(initial_page_index)

    def _init_ui(self):
        # (UI 초기화 코드는 이전과 동일)
        main_layout = QHBoxLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)
        self.navigation_bar = QListWidget(); self.navigation_bar.setObjectName("navigationBar"); self.navigation_bar.setFixedWidth(220)
        self.pages_stack = QStackedWidget(); self.pages = []
        content_layout = QVBoxLayout(); content_layout.setContentsMargins(0,0,0,0); content_layout.setSpacing(0)
        content_layout.addWidget(self.pages_stack, 1)
        button_bar = QWidget(); button_bar.setObjectName("buttonBar")
        button_bar_layout = QHBoxLayout(button_bar); button_bar_layout.setContentsMargins(10,10,10,10)
        button_bar_layout.addSpacerItem(QSpacerItem(40,20,QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum))
        self.save_button = QPushButton("저장"); self.save_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton("취소")
        button_bar_layout.addWidget(self.save_button); button_bar_layout.addWidget(self.cancel_button)
        content_layout.addWidget(button_bar)
        main_layout.addWidget(self.navigation_bar); main_layout.addLayout(content_layout, 1)


    def _add_pages(self):
        # [수정] 페이지 인스턴스 생성 및 추가
        # self.profile_page = ProfileSettingsPage(self.config_manager) # 프로필 페이지 구현 시 활성화
        self.api_page = ApiSettingsPage(self.config_manager)
        self.audio_page = AudioSettingsPage(self.config_manager) # 오디오 페이지 인스턴스 생성
        # self.lang_page = LanguageSettingsPage(self.config_manager) # 언어 페이지 구현 시 활성화
        # self.style_page = StyleSettingsPage(self.config_manager) # 스타일 페이지 구현 시 활성화
        # self.hotkey_page = HotkeySettingsPage(self.config_manager) # 단축키 페이지 구현 시 활성화
        self.add_page(self.api_page, "연동 서비스", 'assets/icons/key.svg')
        self.add_page(self.audio_page, "오디오 설정", 'assets/icons/audio.svg') # 아이콘은 임의 지정
        # ...
        # (다른 페이지들 add_page 호출은 필요 시 활성화)

    def add_page(self, page_widget, title, icon_relative_path):
        self.pages.append(page_widget)
        self.pages_stack.addWidget(page_widget)
        item = QListWidgetItem()
        item_widget = NavigationItemWidget(icon_relative_path, title)
        item.setSizeHint(item_widget.sizeHint())
        self.navigation_bar.addItem(item)
        self.navigation_bar.setItemWidget(item, item_widget)
        
    def update_navigation_icons(self, current_row):
        # (이전과 동일)
        for row in range(self.navigation_bar.count()):
            item = self.navigation_bar.item(row)
            widget = self.navigation_bar.itemWidget(item)
            if isinstance(widget, NavigationItemWidget):
                color = "#0053C6" if row == current_row else "#333333"
                widget.set_icon_color(color)


    def load_stylesheet(self):
        # [수정] 'assets/' 경로를 추가해줍니다.
        style_path = resource_path('assets/style.qss')
        try:
            with open(style_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            # 이제 assets 폴더에 파일이 없다면 경고가 뜨는 것이 정상입니다.
            logging.warning(f"경고: 스타일시트 파일을 찾을 수 없습니다: {style_path}")

    def load_settings(self):
        for page in self.pages:
            if hasattr(page, 'load_settings'):
                page.load_settings()

    def save_settings(self):
        for page in self.pages:
            if hasattr(page, 'save_settings'):
                page.save_settings()
        self.is_saved = True
        
    def save_and_close(self):
        self.save_settings()
        self.close()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)