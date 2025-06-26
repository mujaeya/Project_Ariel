# src/gui/setup_window.py
import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QComboBox, 
                             QFormLayout, QMessageBox, QFileDialog, QSpinBox, QColorDialog)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette, QColor

from config_manager import ConfigManager
from utils.audio_device_manager import get_audio_input_devices

SUPPORTED_LANGUAGES = {
    "한국어": "KO", "영어 (미국)": "en-US", "영어 (영국)": "en-GB", "일본어": "ja-JP",
    "중국어 (간체)": "zh-CN", "스페인어": "es-ES", "프랑스어": "fr-FR", "독일어": "de-DE",
}

class SetupWindow(QWidget):
    closed = Signal(bool)

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.setWindowTitle("Ariel 설정 - by Seeth")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.resize(500, 350)
        self.is_saved = False

        self._create_widgets()
        self._setup_layout()
        self._connect_signals()
        
        self.populate_audio_devices()
        self.populate_languages()
        self.load_settings()

    def _create_widgets(self):
        self.google_path_edit = QLineEdit()
        self.google_browse_button = QPushButton("찾아보기...")
        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        self.audio_device_combo = QComboBox()
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(10, 72)
        self.font_color_button = QPushButton("색상 선택")
        self.font_color_preview = QLabel()
        self.font_color_preview.setFixedSize(24, 24)
        self.font_color_preview.setAutoFillBackground(True)
        self.save_button = QPushButton("저장")
        self.cancel_button = QPushButton("취소")

    def _setup_layout(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        form_layout.addRow(QLabel("<b>API 및 언어 설정</b>"))
        google_path_layout = QHBoxLayout()
        google_path_layout.addWidget(self.google_path_edit)
        google_path_layout.addWidget(self.google_browse_button)
        form_layout.addRow("Google Cloud Key:", google_path_layout)
        form_layout.addRow("DeepL API Key:", self.deepl_key_edit)
        form_layout.addRow("원본 언어:", self.source_lang_combo)
        form_layout.addRow("번역 언어:", self.target_lang_combo)
        
        form_layout.addRow(QLabel("<b>오디오 설정</b>"))
        form_layout.addRow("입력 장치:", self.audio_device_combo)
        
        form_layout.addRow(QLabel("<b>오버레이 스타일 설정</b>"))
        form_layout.addRow("폰트 크기 (px):", self.font_size_spinbox)
        font_color_layout = QHBoxLayout()
        font_color_layout.addWidget(self.font_color_button)
        font_color_layout.addWidget(self.font_color_preview)
        font_color_layout.addStretch()
        form_layout.addRow("폰트 색상:", font_color_layout)
        
        main_layout.addLayout(form_layout)
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

    def _connect_signals(self):
        self.google_browse_button.clicked.connect(self.browse_google_key_file)
        self.font_color_button.clicked.connect(self.choose_font_color)
        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button.clicked.connect(self.close)

    def populate_audio_devices(self):
        self.audio_devices = get_audio_input_devices()
        for device in self.audio_devices:
            self.audio_device_combo.addItem(device['name'])

    def populate_languages(self):
        for name in SUPPORTED_LANGUAGES.keys():
            self.source_lang_combo.addItem(name)
            self.target_lang_combo.addItem(name)

    def load_settings(self):
        self.google_path_edit.setText(self.config_manager.get("google_credentials_path"))
        self.deepl_key_edit.setText(self.config_manager.get("deepl_api_key"))
        self._select_combo_item_by_value(self.source_lang_combo, self.config_manager.get("source_language"))
        self._select_combo_item_by_value(self.target_lang_combo, self.config_manager.get("target_language"))
        self.audio_device_combo.setCurrentText(self.config_manager.get("audio_input_device_name"))
        self.font_size_spinbox.setValue(self.config_manager.get("overlay_font_size"))
        font_color_hex = self.config_manager.get("overlay_font_color")
        palette = self.font_color_preview.palette()
        palette.setColor(QPalette.Window, QColor(font_color_hex))
        self.font_color_preview.setPalette(palette)
        self.font_color_preview.setProperty("color_hex", font_color_hex)

    def save_settings(self):
        source_lang_name = self.source_lang_combo.currentText()
        target_lang_name = self.target_lang_combo.currentText()
        self.config_manager.set("google_credentials_path", self.google_path_edit.text())
        self.config_manager.set("deepl_api_key", self.deepl_key_edit.text())
        self.config_manager.set("source_language", SUPPORTED_LANGUAGES.get(source_lang_name, ""))
        self.config_manager.set("target_language", SUPPORTED_LANGUAGES.get(target_lang_name, ""))
        self.config_manager.set("audio_input_device_name", self.audio_device_combo.currentText())
        self.config_manager.set("overlay_font_size", self.font_size_spinbox.value())
        self.config_manager.set("overlay_font_color", self.font_color_preview.property("color_hex"))
        
        self.is_saved = True
        QMessageBox.information(self, "저장 완료", "설정이 저장되었습니다.")
        self.close()

    def browse_google_key_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Google Cloud 인증 키 파일 선택", "", "JSON 파일 (*.json)")
        if filepath:
            self.google_path_edit.setText(filepath)

    def choose_font_color(self):
        initial_color = QColor(self.font_color_preview.property("color_hex"))
        color = QColorDialog.getColor(initial_color, self)
        if color.isValid():
            hex_color = color.name().upper()
            palette = self.font_color_preview.palette()
            palette.setColor(QPalette.Window, color)
            self.font_color_preview.setPalette(palette)
            self.font_color_preview.setProperty("color_hex", hex_color)

    def _select_combo_item_by_value(self, combo: QComboBox, value_to_find: str):
        for name, code in SUPPORTED_LANGUAGES.items():
            if code == value_to_find:
                combo.setCurrentText(name)
                return

    def closeEvent(self, event):
        self.closed.emit(self.is_saved)
        super().closeEvent(event)