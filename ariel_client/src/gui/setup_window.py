# ariel_client/src/gui/setup_window.py (이 코드로 전체 교체)
import sys
import logging
import random
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QListWidget, QStackedWidget, QVBoxLayout,
                             QListWidgetItem, QPushButton, QSpacerItem, QSizePolicy, QLineEdit,
                             QKeySequenceEdit, QLabel, QSlider, QMessageBox, QComboBox, 
                             QSpinBox, QColorDialog, QFrame, QFontComboBox, QFormLayout, QDialog,
                             QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, Signal, QSize, QCoreApplication, QTranslator, QLocale, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QKeySequence, QColor, QFont, QScreen, QPainter, QFontMetrics

from ..utils import resource_path
from ..config_manager import ConfigManager
from .fluent_widgets import (NavigationItemWidget, SettingsPage, TitleLabel,
                             DescriptionLabel, SettingsCard)

logger = logging.getLogger(__name__)

# 확장된 UI 언어 목록
UI_LANGUAGES = {
    "Auto Detect": "auto",
    "English": "en",
    "Korean": "ko",
    "Japanese": "ja",
    "Chinese (Simplified)": "zh",
    "German": "de",
    "French": "fr",
    "Spanish": "es",
}

# DeepL API가 지원하는 언어 목록
DEEPL_LANGUAGES = {
    "Auto Detect": "auto", "Korean": "KO", "English": "EN", "Japanese": "JA",
    "Chinese": "ZH", "German": "DE", "French": "FR", "Spanish": "ES",
    # 필요에 따라 더 많은 언어 추가
}

# 번역 '대상' 언어에 시스템 언어 옵션 추가
TARGET_LANGUAGES = {"System Language": "auto", **{k: v for k, v in DEEPL_LANGUAGES.items() if v != 'auto'}}

def get_system_language():
    """시스템 언어 코드를 앱에서 사용하는 2자리 코드로 변환 (e.g., 'ko_KR' -> 'ko')"""
    lang = QLocale.system().name().split('_')[0]
    return lang if lang in UI_LANGUAGES.values() else "en" # 지원 목록에 없으면 영어로

class ColorPickerButton(QPushButton):
    """색상 선택 다이얼로그를 여는 커스텀 버튼 위젯"""
    colorChanged = Signal(QColor)
    def __init__(self, color=Qt.GlobalColor.white, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(32, 28))
        self._color = QColor()
        self.set_color(QColor(color))
        self.clicked.connect(self.on_click)

    def set_color(self, color):
        if self._color != color:
            self._color = color
            self.update_style()

    def color(self): return self._color
    
    def update_style(self):
        border_color = "#8f9296" if self._color.lightness() > 127 else "#4f545c"
        self.setStyleSheet(f"background-color: {self._color.name()}; border-radius: 6px; border: 1px solid {border_color};")

    def on_click(self):
        title = QCoreApplication.translate("ColorPickerButton", "Select Color")
        color = QColorDialog.getColor(self._color, self, title)
        if color.isValid() and color != self._color:
            self.set_color(color)
            self.colorChanged.emit(color)

class BaseSettingsPage(SettingsPage):
    """모든 설정 페이지의 기반 클래스"""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
    def load_settings(self): pass
    def save_settings(self): pass
    def retranslate_ui(self): pass
    def tr(self, context, text): return QCoreApplication.translate(context, text)

class ProgramSettingsPage(BaseSettingsPage):
    """프로그램 기본 설정 페이지 (API 키, 테마, 볼륨, 단축키)"""
    language_changed = Signal(str)
    theme_changed = Signal()

    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        
        self.title_label = TitleLabel()
        self.desc_label = DescriptionLabel()
        self.add_widget(self.title_label)
        self.add_widget(self.desc_label)

        # UI 언어
        self.lang_card = SettingsCard()
        self.lang_combo = QComboBox()
        for name, code in UI_LANGUAGES.items(): self.lang_combo.addItem(name, code)
        self.lang_card.add_widget(self.lang_combo)
        self.add_widget(self.lang_card)

        # API 키
        self.api_card = SettingsCard()
        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_card.add_widget(self.deepl_key_edit)
        self.add_widget(self.api_card)

        # UI 테마
        self.theme_card = SettingsCard()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "Custom"])
        self.theme_card.add_widget(self.theme_combo)
        self.add_widget(self.theme_card)
        
        # 알림음 볼륨
        self.volume_card = SettingsCard()
        volume_layout = QHBoxLayout()
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_label = QLabel("80%")
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_label)
        self.volume_card.add_layout(volume_layout)
        self.add_widget(self.volume_card)

        # 커스텀 테마 색상
        self.custom_colors_card = SettingsCard()
        self.color_pickers = {}
        colors_map = { "Primary Background": "BACKGROUND_PRIMARY", "Secondary Background": "BACKGROUND_SECONDARY", "Tertiary Background": "BACKGROUND_TERTIARY", "Primary Text": "TEXT_PRIMARY", "Header Text": "TEXT_HEADER", "Muted Text": "TEXT_MUTED", "Interactive Normal": "INTERACTIVE_NORMAL", "Interactive Hover": "INTERACTIVE_HOVER", "Interactive Accent": "INTERACTIVE_ACCENT", "Interactive Accent Hover": "INTERACTIVE_ACCENT_HOVER", "Border Color": "BORDER_COLOR" }
        for name_key, color_conf_key in colors_map.items():
            layout, label = QHBoxLayout(), QLabel()
            layout.addWidget(label); layout.addStretch(1)
            picker = ColorPickerButton()
            picker.colorChanged.connect(self.theme_changed.emit)
            self.color_pickers[color_conf_key] = (label, name_key, picker)
            layout.addWidget(picker); self.custom_colors_card.add_layout(layout)
        self.add_widget(self.custom_colors_card)

        # 단축키
        self.hotkey_card = SettingsCard()
        self.hotkey_widgets = {}
        self.hotkey_labels = {}
        hotkey_map = { "hotkey_toggle_stt": "Start/Stop Voice Translation", "hotkey_toggle_ocr": "Start/Stop Screen Translation", "hotkey_toggle_setup": "Open/Close Settings Window", "hotkey_quit_app": "Quit Program" }
        for action, desc_key in hotkey_map.items():
            layout, label = QHBoxLayout(), QLabel()
            self.hotkey_labels[action] = (label, desc_key)
            layout.addWidget(label)
            key_edit = QKeySequenceEdit()
            self.hotkey_widgets[action] = key_edit
            layout.addWidget(key_edit)
            self.hotkey_card.add_layout(layout)
        self.add_widget(self.hotkey_card)

        self.lang_combo.currentIndexChanged.connect(lambda: self.language_changed.emit(self.lang_combo.currentData()))
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        self.volume_slider.valueChanged.connect(lambda v: self.volume_label.setText(f"{v}%"))

    def on_theme_changed(self, text: str):
        self.custom_colors_card.setVisible(text.lower() == "custom")
        if not self.theme_combo.signalsBlocked(): self.theme_changed.emit()

    def retranslate_ui(self):
        self.title_label.setText(self.tr("ProgramSettingsPage", "Program Settings"))
        self.desc_label.setText(self.tr("ProgramSettingsPage", "Configure API key, theme, and global hotkeys."))
        self.lang_card.title_label.setText(self.tr("ProgramSettingsPage", "UI Language"))
        if self.lang_card.desc_label: self.lang_card.desc_label.setText(self.tr("ProgramSettingsPage", "Restart the program to apply language changes."))
        self.api_card.title_label.setText(self.tr("ProgramSettingsPage", "DeepL API Key"))
        if self.api_card.desc_label: self.api_card.desc_label.setText(self.tr("ProgramSettingsPage", "API key is required for translation functions."))
        self.deepl_key_edit.setPlaceholderText(self.tr("ProgramSettingsPage", "Enter your DeepL API Key"))
        self.theme_card.title_label.setText(self.tr("ProgramSettingsPage", "UI Theme"))
        self.volume_card.title_label.setText(self.tr("ProgramSettingsPage", "Notification Sound Volume"))
        self.custom_colors_card.title_label.setText(self.tr("ProgramSettingsPage", "Custom Theme Colors"))
        self.hotkey_card.title_label.setText(self.tr("ProgramSettingsPage", "Global Hotkeys"))
        
        for label, name_key, _ in self.color_pickers.values():
            label.setText(f"{self.tr('ProgramSettingsPage', name_key)}:")
        for action, (label, desc_key) in self.hotkey_labels.items():
            label.setText(f"{self.tr('ProgramSettingsPage', desc_key)}:")
            
    def load_settings(self):
        self.lang_combo.blockSignals(True)
        lang_code = self.config_manager.get("app_language", "auto")
        if (index := self.lang_combo.findData(lang_code)) != -1: self.lang_combo.setCurrentIndex(index)
        self.lang_combo.blockSignals(False)
        self.deepl_key_edit.setText(self.config_manager.get("deepl_api_key", ""))
        self.theme_combo.blockSignals(True)
        theme = self.config_manager.get("app_theme", "dark")
        self.theme_combo.setCurrentText(theme.capitalize())
        self.custom_colors_card.setVisible(theme == "custom")
        self.theme_combo.blockSignals(False)
        volume = self.config_manager.get("notification_volume", 80)
        self.volume_slider.setValue(volume)
        self.volume_label.setText(f"{volume}%")
        custom_colors = self.config_manager.get("custom_theme_colors", {})
        default_colors = self.config_manager.get_default_config()["custom_theme_colors"]
        for key, (_, _, picker) in self.color_pickers.items():
            picker.set_color(QColor(custom_colors.get(key, default_colors.get(key))))
        for action, widget in self.hotkey_widgets.items():
            widget.setKeySequence(QKeySequence.fromString(self.config_manager.get(action, ""), QKeySequence.PortableText))

    def save_settings(self):
        self.config_manager.set("app_language", self.lang_combo.currentData())
        self.config_manager.set("deepl_api_key", self.deepl_key_edit.text())
        self.config_manager.set("app_theme", self.theme_combo.currentText().lower())
        self.config_manager.set("notification_volume", self.volume_slider.value())
        custom_colors = {key: picker.color().name() for key, (_, _, picker) in self.color_pickers.items()}
        self.config_manager.set("custom_theme_colors", custom_colors)
        for action, widget in self.hotkey_widgets.items():
            self.config_manager.set(action, widget.keySequence().toString(QKeySequence.PortableText))

class TranslationSettingsPage(BaseSettingsPage):
    """번역 설정 페이지 (언어, 모드, VAD 등)"""
    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.title_label = TitleLabel()
        self.desc_label = DescriptionLabel()
        self.add_widget(self.title_label)
        self.add_widget(self.desc_label)

        # --- STT 설정 ---
        self.stt_card = SettingsCard()
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
        
        # VAD 민감도
        vad_layout = QHBoxLayout()
        self.vad_label = QLabel()
        vad_layout.addWidget(self.vad_label)
        self.vad_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_slider.setRange(1, 3)
        self.vad_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        vad_layout.addWidget(self.vad_slider)
        self.stt_card.add_layout(vad_layout)

        # 문장 구분 시간
        silence_layout = QHBoxLayout()
        self.silence_label = QLabel()
        silence_layout.addWidget(self.silence_label)
        self.silence_spinbox = QSpinBox()
        self.silence_spinbox.setRange(1, 5)
        silence_layout.addWidget(self.silence_spinbox)
        self.stt_card.add_layout(silence_layout)
        self.add_widget(self.stt_card)

        # --- OCR 설정 ---
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
        self.ocr_mode_combo.addItems(["Patch Mode", "Standard Overlay"])
        ocr_mode_layout.addWidget(self.ocr_mode_combo)
        ocr_mode_layout.addStretch()
        self.ocr_card.add_layout(ocr_mode_layout)
        self.add_widget(self.ocr_card)
        
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
        self.vad_label.setText(self.tr("TranslationSettingsPage", "VAD Sensitivity (1=Low, 3=High):"))
        self.silence_label.setText(self.tr("TranslationSettingsPage", "Sentence-break Silence:"))
        self.silence_spinbox.setSuffix(self.tr("TranslationSettingsPage", " sec"))
        
        self.ocr_card.title_label.setText(self.tr("TranslationSettingsPage", "Screen Translation (OCR)"))
        self.ocr_source_label.setText(self.tr("TranslationSettingsPage", "Source:"))
        self.ocr_target_label.setText(self.tr("TranslationSettingsPage", "Target:"))
        self.ocr_mode_label.setText(self.tr("TranslationSettingsPage", "Mode:"))

    def load_settings(self):
        self.stt_source_combo.setCurrentText(next((n for n, c in DEEPL_LANGUAGES.items() if c == self.config_manager.get("stt_source_language", "auto")), "Auto Detect"))
        self.stt_target_combo.setCurrentText(next((n for n, c in TARGET_LANGUAGES.items() if c == self.config_manager.get("stt_target_language", "auto")), "System Language"))
        self.vad_slider.setValue(self.config_manager.get("vad_sensitivity", 3))
        self.silence_spinbox.setValue(int(self.config_manager.get("silence_threshold_s", 1)))
        
        self.ocr_source_combo.setCurrentText(next((n for n, c in DEEPL_LANGUAGES.items() if c == self.config_manager.get("ocr_source_language", "auto")), "Auto Detect"))
        self.ocr_target_combo.setCurrentText(next((n for n, c in TARGET_LANGUAGES.items() if c == self.config_manager.get("ocr_target_language", "auto")), "System Language"))
        self.ocr_mode_combo.setCurrentText(self.config_manager.get("ocr_mode", "Patch Mode"))

    def save_settings(self):
        self.config_manager.set("stt_source_language", self.stt_source_combo.currentData())
        self.config_manager.set("stt_target_language", self.stt_target_combo.currentData())
        self.config_manager.set("vad_sensitivity", self.vad_slider.value())
        self.config_manager.set("silence_threshold_s", float(self.silence_spinbox.value()))
        
        self.config_manager.set("ocr_source_language", self.ocr_source_combo.currentData())
        self.config_manager.set("ocr_target_language", self.ocr_target_combo.currentData())
        self.config_manager.set("ocr_mode", self.ocr_mode_combo.currentText())

class StyleSettingsPage(BaseSettingsPage):
    """오버레이 스타일 설정 페이지 (STT, OCR 개별 설정 및 미리보기)"""
    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.preview_dialog = None
        self.title_label = TitleLabel()
        self.desc_label = DescriptionLabel()
        self.add_widget(self.title_label)
        self.add_widget(self.desc_label)

        self.style_widgets = {}

        # STT 오버레이 스타일
        self.stt_card = SettingsCard()
        stt_widgets = self.create_style_controls()
        self.style_widgets['stt'] = stt_widgets
        self.stt_card.add_layout(self.create_style_layout(stt_widgets))
        stt_preview_btn = QPushButton()
        stt_preview_btn.clicked.connect(lambda: self.show_preview('stt'))
        stt_widgets['preview_button'] = stt_preview_btn
        self.stt_card.add_widget(stt_preview_btn)
        self.add_widget(self.stt_card)
        
        # OCR 오버레이 스타일
        self.ocr_card = SettingsCard()
        ocr_widgets = self.create_style_controls()
        self.style_widgets['ocr'] = ocr_widgets
        self.ocr_card.add_layout(self.create_style_layout(ocr_widgets))
        ocr_preview_btn = QPushButton()
        ocr_preview_btn.clicked.connect(lambda: self.show_preview('ocr'))
        ocr_widgets['preview_button'] = ocr_preview_btn
        self.ocr_card.add_widget(ocr_preview_btn)
        self.add_widget(self.ocr_card)
        
    def get_current_style(self, overlay_type: str):
        """UI 컨트롤에서 현재 스타일 값을 읽어 딕셔너리로 반환"""
        widgets = self.style_widgets[overlay_type]
        return {
            "font_family": widgets['font_combo'].currentFont().family(),
            "font_size": widgets['size_spin'].value(),
            "font_color": widgets['color_picker'].color(),
            "background_color": widgets['bg_picker'].color()
        }

    def show_preview(self, overlay_type: str):
        """미리보기 창을 표시"""
        style_dict = self.get_current_style(overlay_type)
        if self.preview_dialog:
            self.preview_dialog.close()
        
        if overlay_type == 'stt':
            self.preview_dialog = STTPreviewDialog(style_dict, self)
        else: # ocr
            self.preview_dialog = OCRPreviewDialog(style_dict, self)
            
        self.preview_dialog.show()
        # 설정창이 있는 화면의 중앙에 위치시키기
        if screen := self.window().screen():
            screen_center = screen.geometry().center()
            self.preview_dialog.move(screen_center - self.preview_dialog.rect().center())

    def create_style_controls(self):
        widgets = {
            'font_label': QLabel(), 'font_combo': QFontComboBox(),
            'size_label': QLabel(), 'size_spin': QSpinBox(),
            'color_label': QLabel(), 'color_picker': ColorPickerButton(),
            'bg_label': QLabel(), 'bg_picker': ColorPickerButton()
        }
        widgets['size_spin'].setRange(8, 72)
        return widgets

    def create_style_layout(self, widgets):
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form_layout.addRow(widgets['font_label'], widgets['font_combo'])
        form_layout.addRow(widgets['size_label'], widgets['size_spin'])
        form_layout.addRow(widgets['color_label'], widgets['color_picker'])
        form_layout.addRow(widgets['bg_label'], widgets['bg_picker'])
        return form_layout

    def retranslate_ui(self):
        self.title_label.setText(self.tr("StyleSettingsPage", "Overlay Style Settings"))
        self.desc_label.setText(self.tr("StyleSettingsPage", "Customize the appearance of translation overlays."))
        self.stt_card.title_label.setText(self.tr("StyleSettingsPage", "Voice (STT) Overlay"))
        self.ocr_card.title_label.setText(self.tr("StyleSettingsPage", "Screen (OCR) Overlay"))
        if self.ocr_card.desc_label: self.ocr_card.desc_label.setText(self.tr("StyleSettingsPage", "Patch Mode does not have a separate style. This setting applies to Standard Overlay mode."))
        
        for overlay_type in ['stt', 'ocr']:
            widgets = self.style_widgets[overlay_type]
            widgets['font_label'].setText(self.tr("StyleSettingsPage", "Font Family:"))
            widgets['size_label'].setText(self.tr("StyleSettingsPage", "Font Size:"))
            widgets['color_label'].setText(self.tr("StyleSettingsPage", "Font Color:"))
            widgets['bg_label'].setText(self.tr("StyleSettingsPage", "Background Color:"))
            widgets['preview_button'].setText(self.tr("StyleSettingsPage", "Preview"))

    def load_settings(self):
        stt_style = self.config_manager.get("stt_overlay_style", {})
        stt_widgets = self.style_widgets['stt']
        stt_widgets['font_combo'].setCurrentFont(QFont(stt_style.get("font_family", "Malgun Gothic")))
        stt_widgets['size_spin'].setValue(stt_style.get("font_size", 18))
        stt_widgets['color_picker'].set_color(QColor(stt_style.get("font_color", "#FFFFFF")))
        stt_widgets['bg_picker'].set_color(QColor(stt_style.get("background_color", "rgba(0,0,0,0.8)")))
        
        ocr_style = self.config_manager.get("ocr_overlay_style", {})
        ocr_widgets = self.style_widgets['ocr']
        ocr_widgets['font_combo'].setCurrentFont(QFont(ocr_style.get("font_family", "Malgun Gothic")))
        ocr_widgets['size_spin'].setValue(ocr_style.get("font_size", 14))
        ocr_widgets['color_picker'].set_color(QColor(ocr_style.get("font_color", "#FFFFFF")))
        ocr_widgets['bg_picker'].set_color(QColor(ocr_style.get("background_color", "rgba(20,20,20,0.9)")))

    def save_settings(self):
        stt_style = self.config_manager.get("stt_overlay_style", {})
        stt_widgets = self.style_widgets['stt']
        stt_style["font_family"] = stt_widgets['font_combo'].currentFont().family()
        stt_style["font_size"] = stt_widgets['size_spin'].value()
        stt_style["font_color"] = stt_widgets['color_picker'].color().name(QColor.NameFormat.HexRgb)
        stt_style["background_color"] = stt_widgets['bg_picker'].color().name(QColor.NameFormat.HexArgb)
        self.config_manager.set("stt_overlay_style", stt_style)
        
        ocr_style = self.config_manager.get("ocr_overlay_style", {})
        ocr_widgets = self.style_widgets['ocr']
        ocr_style["font_family"] = ocr_widgets['font_combo'].currentFont().family()
        ocr_style["font_size"] = ocr_widgets['size_spin'].value()
        ocr_style["font_color"] = ocr_widgets['color_picker'].color().name(QColor.NameFormat.HexRgb)
        ocr_style["background_color"] = ocr_widgets['bg_picker'].color().name(QColor.NameFormat.HexArgb)
        self.config_manager.set("ocr_overlay_style", ocr_style)

class SetupWindow(QWidget):
    """전체 설정 창 메인 위젯"""
    closed = Signal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.translator = QTranslator(self)
        self.setObjectName("setupWindow")
        self.setMinimumSize(960, 720)
        
        self._init_ui()
        self._add_pages()
        
        self.navigation_bar.currentRowChanged.connect(self.pages_stack.setCurrentIndex)
        self.navigation_bar.currentRowChanged.connect(self.update_navigation_style)
        self.program_page.language_changed.connect(self.change_language)
        self.program_page.theme_changed.connect(self.apply_stylesheet)
        
        self.save_button.clicked.connect(self.save_and_close)
        self.cancel_button.clicked.connect(self.close)
        self.reset_button.clicked.connect(self.reset_settings)
        
        self.load_settings()
        self.retranslate_ui(self.config_manager.get("app_language", "auto"))
        self.apply_stylesheet()
        self.navigation_bar.setCurrentRow(0)
        self.resize(1024, 768)

    def _init_ui(self):
        main_layout=QHBoxLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)
        self.navigation_bar=QListWidget(); self.navigation_bar.setObjectName("navigationBar"); self.navigation_bar.setFixedWidth(240); self.navigation_bar.setSpacing(5)
        self.pages_stack=QStackedWidget(); self.pages=[]
        content_widget=QWidget(); content_widget.setObjectName("contentWidget"); content_layout=QVBoxLayout(content_widget); content_layout.setContentsMargins(0,0,0,0); content_layout.setSpacing(0)
        content_layout.addWidget(self.pages_stack, 1)
        button_bar=QFrame(); button_bar.setObjectName("buttonBar"); button_bar_layout=QHBoxLayout(button_bar); button_bar_layout.setContentsMargins(20,10,20,10)
        self.reset_button=QPushButton(); self.reset_button.setObjectName("secondaryButton"); button_bar_layout.addWidget(self.reset_button)
        button_bar_layout.addSpacerItem(QSpacerItem(40,20,QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum))
        self.save_button=QPushButton(); self.save_button.setObjectName("primaryButton"); button_bar_layout.addWidget(self.save_button)
        self.cancel_button=QPushButton(); self.cancel_button.setObjectName("secondaryButton"); button_bar_layout.addWidget(self.cancel_button)
        content_layout.addWidget(button_bar); main_layout.addWidget(self.navigation_bar); main_layout.addWidget(content_widget,1)
        
    def _add_pages(self):
        self.program_page = ProgramSettingsPage(self.config_manager)
        self.translation_page = TranslationSettingsPage(self.config_manager)
        self.style_page = StyleSettingsPage(self.config_manager)
        
        self.add_page(self.program_page, "Program", "assets/icons/settings.svg")
        self.add_page(self.translation_page, "Translation", "assets/icons/language.svg")
        self.add_page(self.style_page, "Overlay Style", "assets/icons/style.svg")

    def add_page(self, page_widget, title_key, icon_path):
        self.pages.append(page_widget); self.pages_stack.addWidget(page_widget)
        item=QListWidgetItem()
        item_widget=NavigationItemWidget(resource_path(icon_path), title_key)
        # 패딩 문제 해결을 위해 위젯의 높이를 늘림
        item.setSizeHint(QSize(item_widget.sizeHint().width(), 48))
        item.setData(Qt.ItemDataRole.UserRole, title_key)
        self.navigation_bar.addItem(item)
        self.navigation_bar.setItemWidget(item,item_widget)

    def update_navigation_style(self):
        theme = self.config_manager.get("app_theme", "dark")
        is_light_theme = theme == 'light'
        active_text_color = "#ffffff"
        inactive_text_color = "#4f5660" if is_light_theme else "#b9bbbe"
        active_icon_color = "#ffffff"
        inactive_icon_color = "#4f5660" if is_light_theme else "#b9bbbe"

        for row in range(self.navigation_bar.count()):
            item = self.navigation_bar.item(row); widget = self.navigation_bar.itemWidget(item)
            is_selected = row == self.navigation_bar.currentRow()
            item.setSelected(is_selected)
            if isinstance(widget, NavigationItemWidget):
                text_color = active_text_color if is_selected else inactive_text_color
                icon_color = active_icon_color if is_selected else inactive_icon_color
                widget.set_active(is_selected, text_color, icon_color)

    def save_and_close(self):
        current_lang = self.config_manager.get("app_language")
        for page in self.pages:
            page.save_settings()
        self.config_manager.save()
        new_lang = self.config_manager.get("app_language")
        
        if current_lang != new_lang and current_lang != 'auto':
            QMessageBox.information(self, self.tr("SetupWindow", "Restart required"), self.tr("SetupWindow", "UI language change requires a program restart to take full effect."))
        if self.config_manager.get("is_first_run"):
            self.config_manager.set("is_first_run", False)
            self.config_manager.save()
        self.close()

    def reset_settings(self):
        reply = QMessageBox.question(self, self.tr("SetupWindow", "Reset Settings"), self.tr("SetupWindow", "Are you sure you want to reset all settings to their default values?"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.reset_to_defaults()
            self.load_settings()
            self.apply_stylesheet()
            QMessageBox.information(self, self.tr("SetupWindow", "Complete"), self.tr("SetupWindow", "All settings have been reset."))

    def load_settings(self):
        for page in self.pages: page.load_settings()

    def apply_stylesheet(self):
        if self.program_page: self.program_page.save_settings()
        theme = self.config_manager.get("app_theme", "dark")
        try:
            qss = self.generate_qss(theme)
            if (app := QApplication.instance()): app.setStyleSheet(qss)
            self.update_navigation_style() 
        except Exception as e:
            logging.error(f"Error applying stylesheet: {e}", exc_info=True)

    def generate_qss(self, theme):
        if theme == "custom":
            qss_template_path = resource_path('assets/style_template.qss')
            with open(qss_template_path, 'r', encoding='utf-8') as f: qss = f.read()
            custom_colors = self.config_manager.get("custom_theme_colors", {})
            for key, color_val in custom_colors.items(): qss = qss.replace(f"%{key}%", str(color_val))
        else:
            qss_path = resource_path(f'assets/style_{"dark" if theme == "dark" else "light"}.qss')
            with open(qss_path, 'r', encoding='utf-8') as f: qss = f.read()
        return qss.replace("%ASSET_PATH%", resource_path("assets").replace("\\", "/"))

    def change_language(self, lang_code):
        if self.program_page: self.program_page.save_settings()
        app = QApplication.instance()
        if app is None: return
        
        effective_lang = get_system_language() if lang_code == "auto" else lang_code
        
        app.removeTranslator(self.translator)
        if self.translator.load(resource_path(f'translations/ariel_{effective_lang}.qm')):
            app.installTranslator(self.translator)
        else:
            logging.warning(f"Failed to change language dynamically: '{effective_lang}.qm' not found. Falling back to English if possible.")
            if effective_lang != "en" and self.translator.load(resource_path('translations/ariel_en.qm')):
                app.installTranslator(self.translator)

        self.retranslate_ui(effective_lang)
        
    def retranslate_ui(self, lang_code):
        self.setWindowTitle(self.tr("SetupWindow", "Ariel Settings"))
        self.save_button.setText(self.tr("SetupWindow", "Save and Close"))
        self.cancel_button.setText(self.tr("SetupWindow", "Cancel"))
        self.reset_button.setText(self.tr("SetupWindow", "Reset Settings"))
        
        for row in range(self.navigation_bar.count()):
            item = self.navigation_bar.item(row); widget = self.navigation_bar.itemWidget(item)
            title_key = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(widget, NavigationItemWidget):
                widget.text_label.setText(self.tr("SetupWindow_PageTitles", title_key))

        for page in self.pages:
            page.retranslate_ui()
    
    def tr(self, context, text):
        return QCoreApplication.translate(context, text)

    def closeEvent(self, event):
        # 열려있는 미리보기 창이 있다면 닫기
        for child in self.findChildren(QDialog):
            if isinstance(child, (STTPreviewDialog, OCRPreviewDialog)):
                child.close()
        self.closed.emit()
        super().closeEvent(event)

# --- 미리보기 기능 구현을 위한 새로운 클래스들 ---

class BasePreviewDialog(QDialog):
    """미리보기 대화 상자의 기반 클래스"""
    def __init__(self, style, parent=None):
        super().__init__(parent)
        self.style = style
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.bg_color = QColor(self.style.get("background_color", QColor(0, 0, 0, 200)))
        self.font_color = QColor(self.style.get("font_color", QColor(255, 255, 255)))
        self.font = QFont(self.style.get("font_family", "Arial"), self.style.get("font_size", 18))
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)
        super().paintEvent(event)

class STTPreviewDialog(BasePreviewDialog):
    """STT 오버레이 미리보기 대화 상자"""
    def __init__(self, style, parent=None):
        super().__init__(style, parent)
        self.test_sentences = [
            "This is a preview of the voice translation overlay.",
            "스타일이 어떻게 보이는지 테스트하는 문장입니다.",
            "The text will fade in and out.",
        ]
        self.current_sentence_index = 0

        self.label = QLabel(self)
        self.label.setFont(self.font)
        self.label.setStyleSheet(f"color: {self.font_color.name()}; background: transparent;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        self.opacity_effect = QGraphicsOpacityEffect(self.label)
        self.label.setGraphicsEffect(self.opacity_effect)
        
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_text)
        
        self.update_text()
        
    def showEvent(self, event):
        self.timer.start(4000) # 4초마다 텍스트 변경
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def update_text(self):
        # Fade out
        self.animation.stop()
        self.animation.setDuration(500)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.Type.InQuad)
        self.animation.finished.connect(self._change_text_and_fade_in)
        self.animation.start()

    def _change_text_and_fade_in(self):
        self.animation.finished.disconnect(self._change_text_and_fade_in)
        
        text = self.test_sentences[self.current_sentence_index]
        self.label.setText(text)
        
        # Resize based on new text
        fm = QFontMetrics(self.font)
        text_width = fm.horizontalAdvance(text)
        self.setFixedSize(text_width + 40, fm.height() + 20)

        self.current_sentence_index = (self.current_sentence_index + 1) % len(self.test_sentences)

        # Fade in
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()

class OCRPreviewDialog(BasePreviewDialog):
    """OCR (Standard Overlay) 미리보기 대화 상자"""
    def __init__(self, style, parent=None):
        super().__init__(style, parent)
        self.setFixedSize(450, 200)

        # 가짜 배경 텍스트
        self.background_text = "Dies ist ein Beispieltext in einer Fremdsprache. (German)\n" \
                               "これは外国語のサンプルテキストです。 (Japanese)\n" \
                               "Ceci est un exemple de texte dans une langue étrangère. (French)"

        # 오버레이 텍스트
        self.overlay_text = "This is an example text in a foreign language.\n" \
                            "This is a sample text in a foreign language.\n" \
                            "This is an example of text in a foreign language."
    
    def paintEvent(self, event):
        # 1. 반투명 배경 그리기 (부모 클래스에서 처리)
        super().paintEvent(event)
        
        # 2. 배경에 가짜 외국어 텍스트 그리기 (어둡고 흐릿하게)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bg_font = QFont("Segoe UI", 12)
        bg_font_color = QColor("#555")
        painter.setFont(bg_font)
        painter.setPen(bg_font_color)
        painter.drawText(self.rect().adjusted(10, 10, -10, -10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.background_text)

        # 3. 그 위에 설정된 스타일로 오버레이 텍스트 그리기
        painter.setFont(self.font)
        painter.setPen(self.font_color)
        painter.drawText(self.rect().adjusted(10, 10, -10, -10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.overlay_text)


if __name__ == '__main__':
    from ..config_manager import ConfigManager
    
    app = QApplication(sys.argv)
    
    # 더미 ConfigManager 생성
    config_manager = ConfigManager()
    
    # 시스템 언어 감지 및 적용
    app_lang = config_manager.get("app_language", "auto")
    if app_lang == "auto":
        app_lang = get_system_language()

    translator = QTranslator()
    if translator.load(resource_path(f'translations/ariel_{app_lang}.qm')):
        app.installTranslator(translator)
    else:
        logging.warning(f"Main: Could not load translation for '{app_lang}'.")
        if app_lang != 'en' and translator.load(resource_path('translations/ariel_en.qm')):
             app.installTranslator(translator)
             
    window = SetupWindow(config_manager)
    
    def apply_initial_stylesheet():
        theme = config_manager.get("app_theme", "dark")
        qss_path = resource_path(f'assets/style_{"dark" if theme == "dark" else "light"}.qss')
        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                qss = f.read().replace("%ASSET_PATH%", resource_path("assets").replace("\\", "/"))
            app.setStyleSheet(qss)
            window.update_navigation_style()
        except FileNotFoundError:
            logging.error(f"Stylesheet not found at {qss_path}")
        except Exception as e:
            logging.error(f"Error applying initial stylesheet: {e}")

    apply_initial_stylesheet()
    window.show()
    sys.exit(app.exec())