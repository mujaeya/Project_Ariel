# ariel_client/src/gui/setup_window.py (이 코드로 전체 교체)

import sys
import logging
# [해결] QPainter, QFontMetrics, QFont 등 누락된 모든 클래스를 import 합니다.
from PySide6.QtGui import (QKeySequence, QColor, QFont, QPainter, QFontMetrics)
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QListWidget, QStackedWidget, QVBoxLayout,
                             QListWidgetItem, QPushButton, QSpacerItem, QSizePolicy, QLineEdit,
                             QKeySequenceEdit, QLabel, QSlider, QMessageBox, QComboBox,
                             QSpinBox, QColorDialog, QFrame, QFontComboBox, QFormLayout, QDialog,
                             QGraphicsOpacityEffect, QCheckBox, QLayout)
from PySide6.QtCore import Qt, Signal, QSize, QCoreApplication, QTranslator, QLocale, QTimer, QPropertyAnimation, QEasingCurve, Slot

from ..utils import resource_path
from ..config_manager import ConfigManager
from .fluent_widgets import (NavigationItemWidget, SettingsPage, TitleLabel,
                             DescriptionLabel, SettingsCard)

logger = logging.getLogger(__name__)

# --- 설정값 정의 ---
# (이 부분은 기존 코드와 동일하여 생략... 하려 했으나, 생략 없이 제공)
UI_LANGUAGES = {
    "Auto Detect": "auto", "English": "en", "Korean": "ko", "Japanese": "ja",
    "Chinese (Simplified)": "zh", "German": "de", "French": "fr", "Spanish": "es",
}
DEEPL_LANGUAGES = {
    "Auto Detect": "auto", "Korean": "KO", "English": "EN", "Japanese": "JA",
    "Chinese": "ZH", "German": "DE", "French": "FR", "Spanish": "ES",
}
TARGET_LANGUAGES = {"System Language": "auto", **{k: v for k, v in DEEPL_LANGUAGES.items() if v != 'auto'}}

WHISPER_MODELS = {
    "Base (Fastest)": "base",
    "Small": "small",
    "Medium (Recommended)": "medium",
    "Large-v3 (Most Accurate)": "large-v3"
}
# --- ---

def get_system_language():
    lang = QLocale.system().name().split('_')[0]
    return lang if lang in UI_LANGUAGES.values() else "en"

class ColorPickerButton(QPushButton):
    colorChanged = Signal(QColor)
    def __init__(self, color=Qt.GlobalColor.white, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(32, 28))
        self._color = QColor()
        self.set_color(QColor(color))
        self.clicked.connect(self.on_click)

    def set_color(self, color):
        if self._color != color: self._color = color; self.update_style()
    def color(self): return self._color
    def update_style(self):
        border_color = "#8f9296" if self._color.lightness() > 127 else "#4f545c"
        self.setStyleSheet(f"background-color: {self._color.name()}; border-radius: 6px; border: 1px solid {border_color};")
    def on_click(self):
        title = QCoreApplication.translate("ColorPickerButton", "Select Color")
        color = QColorDialog.getColor(self._color, self, title)
        if color.isValid() and color != self._color: self.set_color(color); self.colorChanged.emit(color)

class BaseSettingsPage(SettingsPage):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
    def load_settings(self): pass
    def save_settings(self): pass
    def retranslate_ui(self): pass
    def tr(self, context, text): return QCoreApplication.translate(context, text)

class ProgramSettingsPage(BaseSettingsPage):
    # (이 클래스는 기존 코드와 동일)
    language_changed = Signal(str)
    theme_changed = Signal()

    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.title_label = TitleLabel()
        self.desc_label = DescriptionLabel()
        self.add_widget(self.title_label); self.add_widget(self.desc_label)

        # Language Card
        self.lang_card = SettingsCard()
        self.lang_card_desc = DescriptionLabel()
        self.lang_card_desc.setObjectName("cardDescriptionLabel")
        self.lang_card.add_widget(self.lang_card_desc)
        self.lang_combo = QComboBox()
        for name, code in UI_LANGUAGES.items(): self.lang_combo.addItem(name, code)
        self.lang_card.add_widget(self.lang_combo)
        self.add_widget(self.lang_card)

        # API Card
        self.api_card = SettingsCard()
        self.api_card_desc = DescriptionLabel()
        self.api_card_desc.setObjectName("cardDescriptionLabel")
        self.api_card.add_widget(self.api_card_desc)
        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_card.add_widget(self.deepl_key_edit)
        self.add_widget(self.api_card)
        
        # Theme Card
        self.theme_card = SettingsCard()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "Custom"])
        self.theme_card.add_widget(self.theme_combo)
        self.add_widget(self.theme_card)
        
        # Volume Card
        self.volume_card = SettingsCard()
        volume_layout = QHBoxLayout()
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_label = QLabel("80%")
        volume_layout.addWidget(self.volume_slider); volume_layout.addWidget(self.volume_label)
        self.volume_card.add_layout(volume_layout); self.add_widget(self.volume_card)
        
        # Custom Colors Card
        self.custom_colors_card = SettingsCard()
        self.color_pickers = {}
        colors_map = { "Primary Background": "BACKGROUND_PRIMARY", "Secondary Background": "BACKGROUND_SECONDARY", "Tertiary Background": "BACKGROUND_TERTIARY", "Primary Text": "TEXT_PRIMARY", "Header Text": "TEXT_HEADER", "Muted Text": "TEXT_MUTED", "Interactive Normal": "INTERACTIVE_NORMAL", "Interactive Hover": "INTERACTIVE_HOVER", "Interactive Accent": "INTERACTIVE_ACCENT", "Interactive Accent Hover": "INTERACTIVE_ACCENT_HOVER", "Border Color": "BORDER_COLOR" }
        for name_key, color_conf_key in colors_map.items():
            layout, label = QHBoxLayout(), QLabel(); layout.addWidget(label); layout.addStretch(1); picker = ColorPickerButton(); picker.colorChanged.connect(self.theme_changed.emit)
            self.color_pickers[color_conf_key] = (label, name_key, picker); layout.addWidget(picker); self.custom_colors_card.add_layout(layout)
        self.add_widget(self.custom_colors_card)
        
        # Hotkey Card
        self.hotkey_card = SettingsCard()
        self.hotkey_widgets = {}
        self.hotkey_labels = {}
        hotkey_map = { "hotkey_toggle_stt": "Start/Stop Voice Translation", "hotkey_toggle_ocr": "Start/Stop Screen Translation", "hotkey_toggle_setup": "Open/Close Settings Window", "hotkey_quit_app": "Quit Program" }
        for action, desc_key in hotkey_map.items():
            layout, label = QHBoxLayout(), QLabel(); self.hotkey_labels[action] = (label, desc_key); layout.addWidget(label); key_edit = QKeySequenceEdit()
            self.hotkey_widgets[action] = key_edit; layout.addWidget(key_edit); self.hotkey_card.add_layout(layout)
        self.add_widget(self.hotkey_card)
        
        self.lang_combo.currentIndexChanged.connect(lambda: self.language_changed.emit(self.lang_combo.currentData()))
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        self.volume_slider.valueChanged.connect(lambda v: self.volume_label.setText(f"{v}%"))

    def on_theme_changed(self, text: str):
        self.custom_colors_card.setVisible(text.lower() == "custom")
        if not self.theme_combo.signalsBlocked(): self.theme_changed.emit()

    def retranslate_ui(self):
        self.title_label.setText(self.tr("ProgramSettingsPage", "Program Settings")); self.desc_label.setText(self.tr("ProgramSettingsPage", "Configure API key, theme, and global hotkeys."))
        self.lang_card.title_label.setText(self.tr("ProgramSettingsPage", "UI Language")); self.lang_card_desc.setText(self.tr("ProgramSettingsPage", "Restart the program to apply language changes."))
        self.api_card.title_label.setText(self.tr("ProgramSettingsPage", "DeepL API Key")); self.api_card_desc.setText(self.tr("ProgramSettingsPage", "API key is required for translation functions."))
        self.deepl_key_edit.setPlaceholderText(self.tr("ProgramSettingsPage", "Enter your DeepL API Key")); self.theme_card.title_label.setText(self.tr("ProgramSettingsPage", "UI Theme"))
        self.volume_card.title_label.setText(self.tr("ProgramSettingsPage", "Notification Sound Volume")); self.custom_colors_card.title_label.setText(self.tr("ProgramSettingsPage", "Custom Theme Colors"))
        self.hotkey_card.title_label.setText(self.tr("ProgramSettingsPage", "Global Hotkeys"))
        for label, name_key, _ in self.color_pickers.values(): label.setText(f"{self.tr('ProgramSettingsPage', name_key)}:")
        for action, (label, desc_key) in self.hotkey_labels.items(): label.setText(f"{self.tr('ProgramSettingsPage', desc_key)}:")

    def load_settings(self):
        self.lang_combo.blockSignals(True); lang_code = self.config_manager.get("app_language", "auto"); index = self.lang_combo.findData(lang_code); self.lang_combo.setCurrentIndex(index if index != -1 else 0); self.lang_combo.blockSignals(False)
        self.deepl_key_edit.setText(self.config_manager.get("deepl_api_key", "")); self.theme_combo.blockSignals(True)
        theme = self.config_manager.get("app_theme", "dark"); self.theme_combo.setCurrentText(theme.capitalize()); self.custom_colors_card.setVisible(theme == "custom"); self.theme_combo.blockSignals(False)
        volume = self.config_manager.get("notification_volume", 80); self.volume_slider.setValue(volume); self.volume_label.setText(f"{volume}%")
        custom_colors = self.config_manager.get("custom_theme_colors", {}); default_colors = self.config_manager.get_default_config()["custom_theme_colors"]
        for key, (_, _, picker) in self.color_pickers.items(): picker.set_color(QColor(custom_colors.get(key, default_colors.get(key))))
        for action, widget in self.hotkey_widgets.items(): widget.setKeySequence(QKeySequence.fromString(self.config_manager.get(action, ""), QKeySequence.PortableText))

    def save_settings(self):
        self.config_manager.set("app_language", self.lang_combo.currentData()); self.config_manager.set("deepl_api_key", self.deepl_key_edit.text())
        self.config_manager.set("app_theme", self.theme_combo.currentText().lower()); self.config_manager.set("notification_volume", self.volume_slider.value())
        custom_colors = {key: picker.color().name() for key, (_, _, picker) in self.color_pickers.items()}; self.config_manager.set("custom_theme_colors", custom_colors)
        for action, widget in self.hotkey_widgets.items(): self.config_manager.set(action, widget.keySequence().toString(QKeySequence.PortableText))

class TranslationSettingsPage(BaseSettingsPage):
    # (이 클래스는 이전 버전과 동일)
    ocr_mode_changed = Signal(str)

    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.title_label = TitleLabel()
        self.desc_label = DescriptionLabel()
        self.add_widget(self.title_label)
        self.add_widget(self.desc_label)

        # === STT 설정 카드 ===
        self.stt_card = SettingsCard()
        
        # STT 언어 설정
        stt_lang_layout = QHBoxLayout()
        self.stt_source_label = QLabel()
        stt_lang_layout.addWidget(self.stt_source_label)
        self.stt_source_combo = self.create_lang_combo(is_source=True)
        stt_lang_layout.addWidget(self.stt_source_combo)
        stt_lang_layout.addStretch()
        self.stt_target_label = QLabel()
        stt_lang_layout.addWidget(self.stt_target_label)
        self.stt_target_combo = self.create_lang_combo(is_source=False)
        stt_lang_layout.addWidget(self.stt_target_combo)
        self.stt_card.add_layout(stt_lang_layout)

        # STT 모델 선택 설정
        stt_model_layout = QHBoxLayout()
        self.stt_model_label = QLabel()
        stt_model_layout.addWidget(self.stt_model_label)
        self.stt_model_combo = QComboBox()
        for name, code in WHISPER_MODELS.items():
            self.stt_model_combo.addItem(name, code)
        stt_model_layout.addWidget(self.stt_model_combo)
        stt_model_layout.addStretch()
        self.stt_card.add_layout(stt_model_layout)
        
        self.add_widget(self.stt_card)

        # === OCR 설정 카드 ===
        self.ocr_card = SettingsCard()
        ocr_lang_layout = QHBoxLayout()
        self.ocr_source_label = QLabel()
        ocr_lang_layout.addWidget(self.ocr_source_label)
        self.ocr_source_combo = self.create_lang_combo(is_source=True)
        ocr_lang_layout.addWidget(self.ocr_source_combo)
        ocr_lang_layout.addStretch()
        self.ocr_target_label = QLabel()
        ocr_lang_layout.addWidget(self.ocr_target_label)
        self.ocr_target_combo = self.create_lang_combo(is_source=False)
        ocr_lang_layout.addWidget(self.ocr_target_combo)
        self.ocr_card.add_layout(ocr_lang_layout)
        
        ocr_mode_layout = QHBoxLayout()
        self.ocr_mode_label = QLabel()
        ocr_mode_layout.addWidget(self.ocr_mode_label)
        self.ocr_mode_combo = QComboBox()
        self.ocr_mode_combo.addItems(["Standard Overlay", "Patch Mode"])
        ocr_mode_layout.addWidget(self.ocr_mode_combo)
        ocr_mode_layout.addStretch()
        self.ocr_card.add_layout(ocr_mode_layout)
        self.add_widget(self.ocr_card)
        
        # === 시그널 연결 ===
        self.ocr_mode_combo.currentTextChanged.connect(self.ocr_mode_changed.emit)
        
        self.stt_model_combo.currentIndexChanged.connect(
            lambda: self.config_manager.set("stt_model_size", self.stt_model_combo.currentData())
        )

    def create_lang_combo(self, is_source: bool):
        combo = QComboBox()
        lang_dict = DEEPL_LANGUAGES if is_source else TARGET_LANGUAGES
        for name, code in lang_dict.items():
            combo.addItem(name, code)
        return combo

    def retranslate_ui(self):
        self.title_label.setText(self.tr("TranslationSettingsPage", "Translation Settings"))
        self.desc_label.setText(self.tr("TranslationSettingsPage", "Configure language and mode for each translation feature."))
        
        self.stt_card.title_label.setText(self.tr("TranslationSettingsPage", "Voice Translation (STT)"))
        self.stt_source_label.setText(self.tr("TranslationSettingsPage", "Source:"))
        self.stt_target_label.setText(self.tr("TranslationSettingsPage", "Target:"))
        self.stt_model_label.setText(self.tr("TranslationSettingsPage", "STT Model:"))
        
        self.ocr_card.title_label.setText(self.tr("TranslationSettingsPage", "Screen Translation (OCR)"))
        self.ocr_source_label.setText(self.tr("TranslationSettingsPage", "Source:"))
        self.ocr_target_label.setText(self.tr("TranslationSettingsPage", "Target:"))
        self.ocr_mode_label.setText(self.tr("TranslationSettingsPage", "Mode:"))

    def load_settings(self):
        self.stt_source_combo.setCurrentText(next((n for n, c in DEEPL_LANGUAGES.items() if c == self.config_manager.get("stt_source_language", "auto")), "Auto Detect"))
        self.stt_target_combo.setCurrentText(next((n for n, c in TARGET_LANGUAGES.items() if c == self.config_manager.get("stt_target_language", "auto")), "System Language"))
        
        model_size = self.config_manager.get("stt_model_size", "medium")
        self.stt_model_combo.blockSignals(True)
        self.stt_model_combo.setCurrentText(next((name for name, code in WHISPER_MODELS.items() if code == model_size), "Medium (Recommended)"))
        self.stt_model_combo.blockSignals(False)

        self.ocr_source_combo.setCurrentText(next((n for n, c in DEEPL_LANGUAGES.items() if c == self.config_manager.get("ocr_source_language", "auto")), "Auto Detect"))
        self.ocr_target_combo.setCurrentText(next((n for n, c in TARGET_LANGUAGES.items() if c == self.config_manager.get("ocr_target_language", "auto")), "System Language"))
        self.ocr_mode_combo.setCurrentText(self.config_manager.get("ocr_mode", "Standard Overlay"))

    def save_settings(self):
        self.config_manager.set("stt_source_language", self.stt_source_combo.currentData())
        self.config_manager.set("stt_target_language", self.stt_target_combo.currentData())
        self.config_manager.set("stt_model_size", self.stt_model_combo.currentData())
        
        self.config_manager.set("ocr_source_language", self.ocr_source_combo.currentData())
        self.config_manager.set("ocr_target_language", self.ocr_target_combo.currentData())
        self.config_manager.set("ocr_mode", self.ocr_mode_combo.currentText())

class StyleSettingsPage(BaseSettingsPage):
    # (이 클래스는 기존 코드와 대부분 동일하지만, 프리뷰 관련 로직이 강화됨)
    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.preview_dialogs = {}
        self.title_label = TitleLabel()
        self.desc_label = DescriptionLabel()
        self.add_widget(self.title_label)
        self.add_widget(self.desc_label)
        self.style_widgets = {}

        # STT 오버레이 설정 카드
        self.stt_card = SettingsCard()
        stt_widgets = self.create_style_controls()
        self.style_widgets['stt'] = stt_widgets
        self.stt_card.add_layout(self.create_style_layout(stt_widgets))
        
        stt_preview_btn = QPushButton()
        stt_preview_btn.clicked.connect(lambda: self.toggle_preview('stt'))
        stt_widgets['preview_button'] = stt_preview_btn
        self.stt_card.add_widget(stt_preview_btn)
        self.add_widget(self.stt_card)
        
        # OCR 오버레이 설정 카드
        self.ocr_card = SettingsCard()
        ocr_widgets = self.create_style_controls(is_ocr=True)
        self.style_widgets['ocr'] = ocr_widgets
        self.ocr_card.add_layout(self.create_style_layout(ocr_widgets, is_ocr=True))
        
        self.ocr_preview_btn = QPushButton()
        self.ocr_preview_btn.clicked.connect(lambda: self.toggle_preview('ocr'))
        ocr_widgets['preview_button'] = self.ocr_preview_btn # 참조 저장
        self.ocr_card.add_widget(self.ocr_preview_btn)
        
        self.add_widget(self.ocr_card)

    def get_current_style(self, overlay_type: str):
        widgets = self.style_widgets[overlay_type]
        style = {
            "font_family": widgets['font_combo'].currentFont().family(),
            "font_size": widgets['size_spin'].value(),
            "font_color": widgets['color_picker'].color(),
            "background_color": widgets['bg_picker'].color(),
        }
        if overlay_type == 'stt':
            style.update({
                "show_original_text": widgets['show_original_check'].isChecked(),
                "original_text_font_size_offset": widgets['original_size_spin'].value(),
                "original_text_font_color": widgets['original_color_picker'].color()
            })
        return style

    # [수정] 프리뷰 토글 로직 강화
    def toggle_preview(self, overlay_type: str):
        dialog = self.preview_dialogs.get(overlay_type)
        if dialog and dialog.isVisible():
            dialog.close()
            return
            
        style_dict = self.get_current_style(overlay_type)
        
        # [핵심] '원본 표시' 설정을 딕셔너리에 포함시켜 전달
        if overlay_type == 'stt':
            style_dict['show_original_text'] = self.style_widgets['stt']['show_original_check'].isChecked()

        dialog = StandardOverlayPreviewDialog(style_dict, self)
        dialog.finished.connect(lambda: self.preview_dialogs.pop(overlay_type, None))
        self.preview_dialogs[overlay_type] = dialog
        dialog.show()
        if screen := self.window().screen():
            screen_center = screen.geometry().center()
            dialog.move(screen_center - dialog.rect().center())

    def create_style_controls(self, is_ocr: bool = False):
        widgets = {
            'font_label': QLabel(), 'font_combo': QFontComboBox(),
            'size_label': QLabel(), 'size_spin': QSpinBox(),
            'color_label': QLabel(), 'color_picker': ColorPickerButton(),
            'bg_label': QLabel(), 'bg_picker': ColorPickerButton()
        }
        widgets['size_spin'].setRange(8, 72)
        
        if not is_ocr:
            widgets.update({
                'max_messages_label': QLabel(),
                'max_messages_spin': QSpinBox(),
                'show_original_label': QLabel(),
                'show_original_check': QCheckBox(),
                'original_size_label': QLabel(),
                'original_size_spin': QSpinBox(),
                'original_color_label': QLabel(),
                'original_color_picker': ColorPickerButton(),
            })
            widgets['max_messages_spin'].setRange(1, 3) 
            widgets['original_size_spin'].setRange(-10, 0)
        return widgets
    
    def create_style_layout(self, widgets, is_ocr: bool = False):
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        form_layout.addRow(widgets['font_label'], widgets['font_combo'])
        form_layout.addRow(widgets['size_label'], widgets['size_spin'])
        form_layout.addRow(widgets['color_label'], widgets['color_picker'])
        form_layout.addRow(widgets['bg_label'], widgets['bg_picker'])
        
        if not is_ocr:
            form_layout.addRow(widgets['max_messages_label'], widgets['max_messages_spin'])
            form_layout.addRow(widgets['show_original_label'], widgets['show_original_check'])
            form_layout.addRow(widgets['original_size_label'], widgets['original_size_spin'])
            form_layout.addRow(widgets['original_color_label'], widgets['original_color_picker'])
        return form_layout

    def retranslate_ui(self):
        self.title_label.setText(self.tr("StyleSettingsPage", "Overlay Style Settings"))
        self.desc_label.setText(self.tr("StyleSettingsPage", "Customize the appearance of translation overlays."))
        self.stt_card.title_label.setText(self.tr("StyleSettingsPage", "Voice (STT) Overlay"))
        self.ocr_card.title_label.setText(self.tr("StyleSettingsPage", "Screen (OCR) Overlay"))
        
        for overlay_type in ['stt', 'ocr']:
            widgets = self.style_widgets[overlay_type]
            widgets['font_label'].setText(self.tr("StyleSettingsPage", "Font Family:"))
            widgets['size_label'].setText(self.tr("StyleSettingsPage", "Translated Font Size:"))
            widgets['color_label'].setText(self.tr("StyleSettingsPage", "Translated Font Color:"))
            widgets['bg_label'].setText(self.tr("StyleSettingsPage", "Background Color:"))
            
            # [수정] 버튼 텍스트 설정 분리
            preview_btn = widgets.get('preview_button')
            if preview_btn and preview_btn.isEnabled():
                preview_btn.setText(self.tr("StyleSettingsPage", "Preview"))
            elif preview_btn:
                preview_btn.setText(self.tr("StyleSettingsPage", "Preview is not available for Patch Mode"))

        stt_widgets = self.style_widgets['stt']
        stt_widgets['max_messages_label'].setText(self.tr("StyleSettingsPage", "Max Messages:"))
        stt_widgets['show_original_label'].setText(self.tr("StyleSettingsPage", "Show Original Text:"))
        stt_widgets['original_size_label'].setText(self.tr("StyleSettingsPage", "Original Text Size (Offset):"))
        stt_widgets['original_color_label'].setText(self.tr("StyleSettingsPage", "Original Text Color:"))

    def load_settings(self):
        stt_style = self.config_manager.get("stt_overlay_style", {})
        stt_widgets = self.style_widgets['stt']
        stt_widgets['font_combo'].setCurrentFont(QFont(stt_style.get("font_family", "Malgun Gothic")))
        stt_widgets['size_spin'].setValue(stt_style.get("font_size", 18))
        stt_widgets['color_picker'].set_color(QColor(stt_style.get("font_color", "#FFFFFF")))
        stt_widgets['bg_picker'].set_color(QColor(stt_style.get("background_color", "rgba(0,0,0,0.8)")))
        stt_widgets['max_messages_spin'].setValue(stt_style.get("max_messages", 3))
        stt_widgets['show_original_check'].setChecked(stt_style.get("show_original_text", True))
        stt_widgets['original_size_spin'].setValue(stt_style.get("original_text_font_size_offset", -4))
        stt_widgets['original_color_picker'].set_color(QColor(stt_style.get("original_text_font_color", "#BBBBBB")))
        
        ocr_style = self.config_manager.get("ocr_overlay_style", {})
        ocr_widgets = self.style_widgets['ocr']
        ocr_widgets['font_combo'].setCurrentFont(QFont(ocr_style.get("font_family", "Malgun Gothic")))
        ocr_widgets['size_spin'].setValue(ocr_style.get("font_size", 14))
        ocr_widgets['color_picker'].set_color(QColor(ocr_style.get("font_color", "#FFFFFF")))
        ocr_widgets['bg_picker'].set_color(QColor(ocr_style.get("background_color", "rgba(20,20,20,0.9)")))

    def save_settings(self):
        stt_widgets = self.style_widgets['stt']
        stt_style = {
            "font_family": stt_widgets['font_combo'].currentFont().family(),
            "font_size": stt_widgets['size_spin'].value(),
            "font_color": stt_widgets['color_picker'].color().name(QColor.NameFormat.HexRgb),
            "background_color": stt_widgets['bg_picker'].color().name(QColor.NameFormat.HexArgb),
            "max_messages": stt_widgets['max_messages_spin'].value(),
            "show_original_text": stt_widgets['show_original_check'].isChecked(),
            "original_text_font_size_offset": stt_widgets['original_size_spin'].value(),
            "original_text_font_color": stt_widgets['original_color_picker'].color().name(QColor.NameFormat.HexRgb),
        }
        self.config_manager.set("stt_overlay_style", stt_style)
        
        ocr_widgets = self.style_widgets['ocr']
        ocr_style = {
            "font_family": ocr_widgets['font_combo'].currentFont().family(),
            "font_size": ocr_widgets['size_spin'].value(),
            "font_color": ocr_widgets['color_picker'].color().name(QColor.NameFormat.HexRgb),
            "background_color": ocr_widgets['bg_picker'].color().name(QColor.NameFormat.HexArgb),
        }
        self.config_manager.set("ocr_overlay_style", ocr_style)

    # [수정] OCR 모드에 따라 프리뷰 UI를 동적으로 변경하는 슬롯
    @Slot(str)
    def set_ocr_style_enabled(self, ocr_mode: str):
        enabled = ocr_mode == "Standard Overlay"
        
        # OCR 설정 위젯 활성화/비활성화
        for widget in self.style_widgets['ocr'].values():
            if isinstance(widget, (QWidget, QLayout)):
                widget.setEnabled(enabled)

        # 프리뷰 버튼 상태 및 텍스트 변경
        preview_btn = self.style_widgets['ocr'].get('preview_button')
        if preview_btn:
            preview_btn.setEnabled(enabled)
            if not enabled:
                preview_btn.setText(self.tr("StyleSettingsPage", "Preview is not available for Patch Mode"))
            else:
                preview_btn.setText(self.tr("StyleSettingsPage", "Preview"))

class SetupWindow(QWidget):
    # (이 클래스는 기존 코드와 동일)
    closed = Signal()
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent); self.config_manager = config_manager; self.translator = QTranslator(self); self.setObjectName("setupWindow"); self.setMinimumSize(960, 720)
        self._init_ui(); self._add_pages()
        self.navigation_bar.currentRowChanged.connect(self.pages_stack.setCurrentIndex); self.navigation_bar.currentRowChanged.connect(self.update_navigation_style)
        self.program_page.language_changed.connect(self.change_language); self.program_page.theme_changed.connect(self.apply_stylesheet)
        self.save_button.clicked.connect(self.save_and_close); self.cancel_button.clicked.connect(self.close); self.reset_button.clicked.connect(self.reset_settings)
        self.translation_page.ocr_mode_changed.connect(self.style_page.set_ocr_style_enabled)
        self.load_settings(); self.retranslate_ui(self.config_manager.get("app_language", "auto")); self.apply_stylesheet(); self.navigation_bar.setCurrentRow(0); self.resize(1024, 768)

    def _init_ui(self):
        main_layout=QHBoxLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0); self.navigation_bar=QListWidget(); self.navigation_bar.setObjectName("navigationBar"); self.navigation_bar.setFixedWidth(240); self.navigation_bar.setSpacing(5); self.pages_stack=QStackedWidget(); self.pages=[]
        content_widget=QWidget(); content_widget.setObjectName("contentWidget"); content_layout=QVBoxLayout(content_widget); content_layout.setContentsMargins(0,0,0,0); content_layout.setSpacing(0); content_layout.addWidget(self.pages_stack, 1); button_bar=QFrame(); button_bar.setObjectName("buttonBar"); button_bar_layout=QHBoxLayout(button_bar); button_bar_layout.setContentsMargins(20,10,20,10); self.reset_button=QPushButton(); self.reset_button.setObjectName("secondaryButton"); button_bar_layout.addWidget(self.reset_button); button_bar_layout.addSpacerItem(QSpacerItem(40,20,QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum)); self.save_button=QPushButton(); self.save_button.setObjectName("primaryButton"); button_bar_layout.addWidget(self.save_button); self.cancel_button=QPushButton(); self.cancel_button.setObjectName("secondaryButton"); button_bar_layout.addWidget(self.cancel_button); content_layout.addWidget(button_bar); main_layout.addWidget(self.navigation_bar); main_layout.addWidget(content_widget,1)

    def _add_pages(self):
        self.program_page = ProgramSettingsPage(self.config_manager); self.translation_page = TranslationSettingsPage(self.config_manager); self.style_page = StyleSettingsPage(self.config_manager)
        self.add_page(self.program_page, "Program", "assets/icons/settings.svg"); self.add_page(self.translation_page, "Translation", "assets/icons/language.svg"); self.add_page(self.style_page, "Overlay Style", "assets/icons/style.svg")

    def add_page(self, page_widget, title_key, icon_path):
        self.pages.append(page_widget); self.pages_stack.addWidget(page_widget); item=QListWidgetItem(); item_widget=NavigationItemWidget(resource_path(icon_path), title_key)
        item.setSizeHint(QSize(item_widget.sizeHint().width(), 48)); item.setData(Qt.ItemDataRole.UserRole, title_key); self.navigation_bar.addItem(item); self.navigation_bar.setItemWidget(item,item_widget)

    def update_navigation_style(self):
        theme = self.config_manager.get("app_theme", "dark"); is_light_theme = theme == 'light'
        active_text_color = "#ffffff"; inactive_text_color = "#4f5660" if is_light_theme else "#b9bbbe"; active_icon_color = "#ffffff"; inactive_icon_color = "#4f5660" if is_light_theme else "#b9bbbe"
        for row in range(self.navigation_bar.count()):
            item = self.navigation_bar.item(row); widget = self.navigation_bar.itemWidget(item); is_selected = row == self.navigation_bar.currentRow(); item.setSelected(is_selected)
            if isinstance(widget, NavigationItemWidget): widget.set_active(is_selected, active_text_color if is_selected else inactive_text_color, active_icon_color if is_selected else inactive_icon_color)

    def save_and_close(self):
        current_lang = self.config_manager.get("app_language", "auto"); [p.save_settings() for p in self.pages]; self.config_manager.save(); new_lang = self.config_manager.get("app_language")
        if current_lang != new_lang and current_lang != 'auto': QMessageBox.information(self, self.tr("SetupWindow", "Restart required"), self.tr("SetupWindow", "UI language change requires a program restart to take full effect."))
        if self.config_manager.get("is_first_run"): self.config_manager.set("is_first_run", False); self.config_manager.save()
        self.close()

    def reset_settings(self):
        reply = QMessageBox.question(self, self.tr("SetupWindow", "Reset Settings"), self.tr("SetupWindow", "Are you sure you want to reset all settings to their default values?"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: self.config_manager.reset_to_defaults(); self.load_settings(); self.apply_stylesheet(); QMessageBox.information(self, self.tr("SetupWindow", "Complete"), self.tr("SetupWindow", "All settings have been reset."))

    def load_settings(self):
        for page in self.pages: page.load_settings()
        initial_ocr_mode = self.config_manager.get("ocr_mode", "Standard Overlay")
        self.style_page.set_ocr_style_enabled(initial_ocr_mode)

    def apply_stylesheet(self):
        if self.program_page: self.program_page.save_settings(); theme = self.config_manager.get("app_theme", "dark")
        try:
            base_qss_name = "style_dark.qss" if theme != "light" else "style_light.qss"
            if theme == "custom": base_qss_name = "style_template.qss"
            qss_path = resource_path(f'assets/styles/{base_qss_name}')
            with open(qss_path, 'r', encoding='utf-8') as f: qss = f.read()
            if theme == "custom":
                custom_colors = self.config_manager.get("custom_theme_colors", {}); 
                for key, color_val in custom_colors.items(): qss = qss.replace(f"%{key}%", str(color_val))
            if (app := QApplication.instance()): app.setStyleSheet(qss.replace("%ASSET_PATH%", resource_path("assets").replace("\\", "/")))
            self.update_navigation_style() 
        except Exception as e: logging.error(f"Error applying stylesheet: {e}", exc_info=True)

    def change_language(self, lang_code):
        if self.program_page: self.program_page.save_settings(); app = QApplication.instance(); effective_lang = get_system_language() if lang_code == "auto" else lang_code; app.removeTranslator(self.translator)
        if self.translator.load(resource_path(f'translations/ariel_{effective_lang}.qm')): app.installTranslator(self.translator)
        else: logging.warning(f"Failed to load translation: '{effective_lang}.qm'"); app.installTranslator(QTranslator())
        self.retranslate_ui(effective_lang)

    def retranslate_ui(self, lang_code):
        self.setWindowTitle(self.tr("SetupWindow", "Ariel Settings")); self.save_button.setText(self.tr("SetupWindow", "Save and Close")); self.cancel_button.setText(self.tr("SetupWindow", "Cancel")); self.reset_button.setText(self.tr("SetupWindow", "Reset Settings"))
        for row in range(self.navigation_bar.count()):
            item = self.navigation_bar.item(row); widget = self.navigation_bar.itemWidget(item); title_key = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(widget, NavigationItemWidget): widget.text_label.setText(self.tr("SetupWindow_PageTitles", title_key))
        for page in self.pages: page.retranslate_ui()

    def tr(self, context, text): return QCoreApplication.translate(context, text)

    def closeEvent(self, event):
        for dialog in self.style_page.preview_dialogs.values():
            if dialog: dialog.close()
        self.style_page.preview_dialogs.clear()
        self.closed.emit(); super().closeEvent(event)

# [수정] StandardOverlayPreviewDialog 클래스 수정
class StandardOverlayPreviewDialog(QDialog):
    def __init__(self, style, parent=None):
        super().__init__(parent)
        self.style = style
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        # 스타일 값 추출
        self.bg_color = QColor(self.style.get("background_color", QColor(0, 0, 0, 200)))
        self.font_color = QColor(self.style.get("font_color", QColor(255, 255, 255)))
        self.font = QFont(self.style.get("font_family", "Arial"), self.style.get("font_size", 18))
        self.show_original = self.style.get("show_original_text", False) # 원본 표시 여부

        # 테스트 문장 설정
        self.test_sentences = [
            ("This is a preview.", "이것은 미리보기입니다."),
            ("The style will be applied.", "스타일이 적용됩니다."),
            ("A wonderful experience!", "놀라운 경험!"),
        ]
        self.current_sentence_index = 0
        
        # 라벨 설정
        self.label = QLabel(self)
        self.label.setFont(self.font)
        self.label.setStyleSheet(f"color: {self.font_color.name()}; background: transparent;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        # 애니메이션 및 타이머 설정
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.animation = QPropertyAnimation(self, b"opacity")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_text)
        
        self.update_text() # 첫 실행

    def paintEvent(self, event):
        # [수정] 여기서 QPainter를 사용
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)
        # super().paintEvent(event) # QLabel이 직접 그리므로 super 호출은 불필요

    def showEvent(self, event):
        self.timer.start(4000)
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def update_text(self):
        self.animation.stop()
        self.animation.setDuration(500)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.Type.InQuad)
        self.animation.finished.connect(self._change_text_and_fade_in)
        self.animation.start()

    def _change_text_and_fade_in(self):
        try:
            self.animation.finished.disconnect(self._change_text_and_fade_in)
        except RuntimeError:
            pass # 이미 연결이 끊긴 경우
        
        original, translated = self.test_sentences[self.current_sentence_index]
        
        # [핵심] 원본 표시 여부에 따라 텍스트 구성
        if self.show_original:
            offset = self.style.get("original_text_font_size_offset", -4)
            orig_color = self.style.get("original_text_font_color", QColor("#BBBBBB")).name()
            display_text = (
                f'<span style="font-size:{self.font.pointSize() + offset}pt; color:{orig_color};">{original}</span><br/>'
                f'{translated}'
            )
        else:
            display_text = translated
        
        self.label.setText(display_text)
        
        # [수정] 텍스트 크기에 맞춰 창 크기 조절 (QFontMetrics 사용)
        fm = QFontMetrics(self.font)
        # RichText의 실제 크기를 계산하기 위해 document 사용
        doc = self.label.document()
        doc.setHtml(display_text)
        doc.setTextWidth(400) # 최대 너비 제한
        self.setFixedSize(int(doc.idealWidth()) + 40, int(doc.size().height()) + 20)
        
        self.current_sentence_index = (self.current_sentence_index + 1) % len(self.test_sentences)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()


# --- main 함수 (테스트용) ---
if __name__ == '__main__':
    from ..config_manager import ConfigManager
    app = QApplication(sys.argv)
    config_manager = ConfigManager()
    
    app_lang = config_manager.get("app_language", "auto")
    if app_lang == "auto":
        app_lang = get_system_language()

    translator = QTranslator()
    translation_path = resource_path(f'translations/ariel_{app_lang}.qm')
    if translator.load(translation_path):
        app.installTranslator(translator)
    else:
        logging.warning(f"Could not load translation for '{app_lang}' from {translation_path}")

    window = SetupWindow(config_manager)
    window.show()
    sys.exit(app.exec())