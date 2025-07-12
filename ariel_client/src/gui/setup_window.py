# F:/projects/Project_Ariel/ariel_client/src/gui/setup_window.py (최종 복원 및 개선 버전)

import sys
import logging
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QListWidget, QStackedWidget, QVBoxLayout,
                             QListWidgetItem, QPushButton, QSpacerItem, QSizePolicy, QLineEdit,
                             QKeySequenceEdit, QLabel, QFileDialog, QSlider, QMessageBox,
                             QComboBox, QSpinBox, QColorDialog, QScrollArea, QFrame)
from PySide6.QtCore import Qt, Signal, QSize, QCoreApplication
from PySide6.QtGui import QKeySequence, QColor, QPalette, QIcon

# 프로젝트 구조에 맞는 상대 경로 임포트
from ..utils import resource_path
from ..config_manager import ConfigManager
from .fluent_widgets import (NavigationItemWidget, SettingsPage, TitleLabel,
                               DescriptionLabel, SettingsCard)

logger = logging.getLogger(__name__)

# --- [신규] 지원 언어 목록 ---
SUPPORTED_LANGUAGES = {
    "Auto Detect": "auto",
    "Korean": "KO",
    "English": "EN",
    "Japanese": "JA",
    "Chinese": "ZH",
    "German": "DE",
    "French": "FR",
    "Spanish": "ES",
}

class ColorPickerButton(QPushButton):
    """사용자가 클릭하여 색상을 선택할 수 있는 작은 버튼 위젯."""
    colorChanged = Signal(QColor)
    def __init__(self, color=Qt.GlobalColor.white, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(32, 28))
        self.set_color(QColor(color))
        self.clicked.connect(self.on_click)

    def set_color(self, color):
        self._color = color
        self.setStyleSheet(f"background-color: {self._color.name()}; border-radius: 6px; border: 1px solid #7f8c8d;")

    def color(self):
        return self._color

    def on_click(self):
        color = QColorDialog.getColor(self._color, self, self.tr("Select Color"))
        if color.isValid():
            self.set_color(color)
            self.colorChanged.emit(color)

    def tr(self, text):
        return QCoreApplication.translate("ColorPickerButton", text)

class ProgramSettingsPage(SettingsPage):
    """프로그램의 전반적인 설정을 담당하는 페이지."""
    theme_applied = Signal()
    language_changed = Signal()

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.add_widget(TitleLabel(self.tr("Program Settings")))
        self.add_widget(DescriptionLabel(self.tr("Configure the basic behavior of the program.")))

        lang_card = SettingsCard(self.tr("UI Language"), self.tr("Restart the program to apply language changes."))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("한국어", "ko")
        lang_card.add_widget(self.lang_combo)
        self.add_widget(lang_card)

        api_card = SettingsCard(self.tr("DeepL API Key"), self.tr("DeepL API key is required for translation."))
        self.deepl_key_edit = QLineEdit(); self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepl_key_edit.setPlaceholderText(self.tr("Enter your API key"))
        api_card.add_widget(self.deepl_key_edit); self.add_widget(api_card)

        theme_card = SettingsCard(self.tr("UI Theme"))
        self.theme_combo = QComboBox(); self.theme_combo.addItems(["Dark", "Light", "Custom"])
        theme_card.add_widget(self.theme_combo); self.add_widget(theme_card)

        self.custom_colors_card = SettingsCard(self.tr("Custom Theme Colors"), self.tr("Click the color buttons to change to your desired colors. Changes are applied immediately."))
        self.color_pickers = {}
        colors_to_pick = {
            "Primary Background": "BACKGROUND_PRIMARY", "Secondary Background": "BACKGROUND_SECONDARY",
            "Tertiary Background": "BACKGROUND_TERTIARY", "Primary Text": "TEXT_PRIMARY",
            "Header Text": "TEXT_HEADER", "Muted Text": "TEXT_MUTED", "Interactive Normal": "INTERACTIVE_NORMAL",
            "Interactive Hover": "INTERACTIVE_HOVER",
            "Interactive Accent": "INTERACTIVE_ACCENT",
            "Interactive Accent Hover": "INTERACTIVE_ACCENT_HOVER"
        }
        for name, key in colors_to_pick.items():
            layout = QHBoxLayout()
            layout.addWidget(QLabel(f"{self.tr(name)}:"))
            layout.addStretch(1)
            initial_color_hex = self.config_manager.get("custom_theme_colors", {}).get(key, "#000000")
            color_picker = ColorPickerButton(initial_color_hex)
            color_picker.colorChanged.connect(
                lambda color, k=key: self.on_color_changed(k, color)
            )
            self.color_pickers[key] = color_picker
            layout.addWidget(color_picker)
            self.custom_colors_card.add_layout(layout)
        self.add_widget(self.custom_colors_card)

        hotkey_card = SettingsCard(self.tr("Global Hotkeys"), self.tr("Set hotkeys to quickly execute the program's main functions."))
        self.hotkey_widgets = {}
        hotkey_actions = {
            "hotkey_toggle_stt": "Start/Stop Voice Translation",
            "hotkey_toggle_ocr": "Start/Stop Screen Translation",
            "hotkey_toggle_setup": "Open/Close Settings Window",
            "hotkey_quit_app": "Quit Program"
        }
        for action, desc in hotkey_actions.items():
            layout = QHBoxLayout()
            layout.addWidget(QLabel(f"{self.tr(desc)}:"))
            key_edit = QKeySequenceEdit()
            self.hotkey_widgets[action] = key_edit
            layout.addWidget(key_edit)
            hotkey_card.add_layout(layout)
        self.add_widget(hotkey_card)

        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)

    def on_theme_changed(self, text: str):
        is_custom = text.lower() == "custom"
        self.custom_colors_card.setVisible(is_custom)
        if not self.theme_combo.signalsBlocked():
            self.config_manager.set("app_theme", text.lower())
            self.theme_applied.emit()

    def on_color_changed(self, color_key: str, new_color: QColor):
        custom_colors = self.config_manager.get("custom_theme_colors", {})
        custom_colors[color_key] = new_color.name()
        self.config_manager.set("custom_theme_colors", custom_colors)
        if self.theme_combo.currentText().lower() == "custom":
            self.theme_applied.emit()

    def load_settings(self):
        current_lang = self.config_manager.get("app_language", "en")
        index = self.lang_combo.findData(current_lang)
        if index != -1: self.lang_combo.setCurrentIndex(index)
        
        self.deepl_key_edit.setText(self.config_manager.get("deepl_api_key", ""))
        
        theme = self.config_manager.get("app_theme", "dark")
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentText(theme.capitalize())
        self.theme_combo.blockSignals(False)
        self.custom_colors_card.setVisible(theme == "custom")
        
        custom_colors = self.config_manager.get("custom_theme_colors", {})
        for key, picker in self.color_pickers.items():
            color_hex = custom_colors.get(key, "#ffffff")
            picker.set_color(QColor(color_hex))
            
        for action, widget in self.hotkey_widgets.items():
            hotkey_str = self.config_manager.get(action, "")
            widget.setKeySequence(QKeySequence.fromString(hotkey_str, QKeySequence.PortableText))

    def save_settings(self):
        self.config_manager.set("app_language", self.lang_combo.currentData())
        self.config_manager.set("deepl_api_key", self.deepl_key_edit.text())
        app_theme = self.theme_combo.currentText().lower()
        self.config_manager.set("app_theme", app_theme)
        if app_theme == "custom":
            custom_colors = {key: picker.color().name() for key, picker in self.color_pickers.items()}
            self.config_manager.set("custom_theme_colors", custom_colors)
        for action, widget in self.hotkey_widgets.items():
            sequence = widget.keySequence()
            hotkey_str = sequence.toString(QKeySequence.PortableText).lower().replace("meta", "cmd")
            self.config_manager.set(action, hotkey_str)

    def tr(self, text):
        return QCoreApplication.translate("ProgramSettingsPage", text)


class OcrSettingsPage(SettingsPage):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.add_widget(TitleLabel(self.tr("Screen Translation (OCR) Settings")))
        self.add_widget(DescriptionLabel(self.tr("Configure the detailed behavior for screen text recognition and translation.")))

        lang_card = SettingsCard(self.tr("Language Settings"))
        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        for name, code in SUPPORTED_LANGUAGES.items():
            self.source_lang_combo.addItem(self.tr(name), code)
            if code != 'auto': 
                self.target_lang_combo.addItem(self.tr(name), code)
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel(self.tr("Source Language:")))
        lang_layout.addWidget(self.source_lang_combo)
        lang_layout.addStretch(1)
        lang_layout.addWidget(QLabel(self.tr("Target Language:")))
        lang_layout.addWidget(self.target_lang_combo)
        lang_card.add_layout(lang_layout)
        self.add_widget(lang_card)
        
        mode_card = SettingsCard(self.tr("Translation Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.tr("Standard Overlay"), self.tr("Style-Cloning Patch (WIP)")])
        mode_card.add_widget(self.mode_combo)
        self.add_widget(mode_card)

    def load_settings(self):
        source_code = self.config_manager.get("ocr_source_language", "auto")
        target_code = self.config_manager.get("ocr_target_language", "KO")
        self.source_lang_combo.setCurrentIndex(self.source_lang_combo.findData(source_code))
        self.target_lang_combo.setCurrentIndex(self.target_lang_combo.findData(target_code))
        
        mode = self.config_manager.get("ocr_mode", "overlay")
        self.mode_combo.setCurrentIndex(0 if mode == "overlay" else 1)

    def save_settings(self):
        self.config_manager.set("ocr_source_language", self.source_lang_combo.currentData())
        self.config_manager.set("ocr_target_language", self.target_lang_combo.currentData())
        self.config_manager.set("ocr_mode", "overlay" if self.mode_combo.currentIndex() == 0 else "patch")

    def tr(self, text):
        return QCoreApplication.translate("OcrSettingsPage", text)

class SttSettingsPage(SettingsPage):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.add_widget(TitleLabel(self.tr("Voice Translation (STT) Settings")))
        self.add_widget(DescriptionLabel(self.tr("Configure the detailed behavior for system sound recognition and translation.")))

        lang_card = SettingsCard(self.tr("Language Settings"))
        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        for name, code in SUPPORTED_LANGUAGES.items():
            self.source_lang_combo.addItem(self.tr(name), code)
            if code != 'auto':
                self.target_lang_combo.addItem(self.tr(name), code)
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel(self.tr("Source Language:")))
        lang_layout.addWidget(self.source_lang_combo)
        lang_layout.addStretch(1)
        lang_layout.addWidget(QLabel(self.tr("Target Language:")))
        lang_layout.addWidget(self.target_lang_combo)
        lang_card.add_layout(lang_layout)
        self.add_widget(lang_card)
        
        vad_card = SettingsCard(self.tr("Voice Activity Detection (VAD) Sensitivity"), self.tr("Adjust how sensitively voice is detected. (1: Low, 3: High)"))
        self.vad_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_slider.setRange(1, 3)
        self.vad_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.vad_slider.setSingleStep(1)
        vad_card.add_widget(self.vad_slider)
        self.add_widget(vad_card)
        
        silence_card = SettingsCard(self.tr("Sentence-break Silence (seconds)"), self.tr("Set how long a silence must be to be considered the end of a sentence."))
        self.silence_spinbox = QSpinBox()
        self.silence_spinbox.setRange(1, 5)
        self.silence_spinbox.setSuffix(self.tr(" s"))
        silence_card.add_widget(self.silence_spinbox)
        self.add_widget(silence_card)

    def load_settings(self):
        source_code = self.config_manager.get("stt_source_language", "auto")
        target_code = self.config_manager.get("stt_target_language", "KO")
        self.source_lang_combo.setCurrentIndex(self.source_lang_combo.findData(source_code))
        self.target_lang_combo.setCurrentIndex(self.target_lang_combo.findData(target_code))

        self.vad_slider.setValue(self.config_manager.get("vad_sensitivity", 3))
        self.silence_spinbox.setValue(int(self.config_manager.get("silence_threshold_s", 1.0)))

    def save_settings(self):
        self.config_manager.set("stt_source_language", self.source_lang_combo.currentData())
        self.config_manager.set("stt_target_language", self.target_lang_combo.currentData())
        self.config_manager.set("vad_sensitivity", self.vad_slider.value())
        self.config_manager.set("silence_threshold_s", float(self.silence_spinbox.value()))

    def tr(self, text):
        return QCoreApplication.translate("SttSettingsPage", text)

class StyleSettingsPage(SettingsPage):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.add_widget(TitleLabel(self.tr("Overlay Style Settings")))
        self.add_widget(DescriptionLabel(self.tr("Configure the design of the overlay window where translation results are displayed, including font and colors.")))
        
        stt_card = SettingsCard(self.tr("Voice (STT) Overlay"))
        self.add_widget(stt_card)

        ocr_card = SettingsCard(self.tr("Screen (OCR) Overlay"))
        self.add_widget(ocr_card)

    def load_settings(self):
        pass

    def save_settings(self):
        pass

    def tr(self, text):
        return QCoreApplication.translate("StyleSettingsPage", text)

class SetupWindow(QWidget):
    closed = Signal()
    theme_changed = Signal()

    def __init__(self, config_manager: ConfigManager, initial_page_index=0):
        super().__init__()
        self.config_manager = config_manager
        self.setObjectName("setupWindow")
        self.setWindowTitle(self.tr("Ariel Settings"))
        self.setMinimumSize(960, 600)
        self.resize(1024, 720)
        self._init_ui()
        self._add_pages()
        self.apply_stylesheet()
        self.navigation_bar.currentRowChanged.connect(self.pages_stack.setCurrentIndex)
        self.navigation_bar.currentRowChanged.connect(self.update_navigation_icons)
        self.theme_changed.connect(self.update_navigation_icons)
        self.save_button.clicked.connect(self.save_and_close)
        self.cancel_button.clicked.connect(self.close)
        self.reset_button.clicked.connect(self.reset_settings)
        self.load_settings()
        self.navigation_bar.setCurrentRow(initial_page_index)

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.navigation_bar = QListWidget()
        self.navigation_bar.setObjectName("navigationBar")
        self.navigation_bar.setFixedWidth(240)
        self.navigation_bar.setSpacing(5)
        
        self.pages_stack = QStackedWidget()
        self.pages = []
        
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        content_layout.addWidget(self.pages_stack, 1)

        button_bar = QFrame()
        button_bar.setObjectName("buttonBar")
        button_bar.setFrameShape(QFrame.Shape.StyledPanel)
        button_bar_layout = QHBoxLayout(button_bar)
        button_bar_layout.setContentsMargins(20, 10, 20, 10)
        
        self.reset_button = QPushButton(self.tr("Reset Settings"))
        # [수정 사항 적용] reset_button에 objectName 설정
        self.reset_button.setObjectName("secondaryButton") 
        button_bar_layout.addWidget(self.reset_button)
        
        button_bar_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        self.save_button = QPushButton(self.tr("Save and Close"))
        self.save_button.setObjectName("primaryButton")
        
        self.cancel_button = QPushButton(self.tr("Cancel"))
        # [수정 사항 적용] cancel_button에 objectName 설정
        self.cancel_button.setObjectName("secondaryButton") 
        
        button_bar_layout.addWidget(self.save_button)
        button_bar_layout.addWidget(self.cancel_button)
        
        content_layout.addWidget(button_bar)
        main_layout.addWidget(self.navigation_bar)
        main_layout.addWidget(content_widget, 1)

    def _add_pages(self):
        self.program_page = ProgramSettingsPage(self.config_manager)
        self.ocr_page = OcrSettingsPage(self.config_manager)
        self.stt_page = SttSettingsPage(self.config_manager)
        self.style_page = StyleSettingsPage(self.config_manager)
        
        self.add_page(self.program_page, "Program", resource_path("assets/icons/settings.svg"))
        self.add_page(self.ocr_page, "Screen Translation (OCR)", resource_path("assets/icons/ocr.svg"))
        self.add_page(self.stt_page, "Voice Translation (STT)", resource_path("assets/icons/audio.svg"))
        self.add_page(self.style_page, "Overlay Style", resource_path("assets/icons/style.svg"))
        
        self.program_page.theme_applied.connect(self.apply_stylesheet)

    def add_page(self, page_widget, title, icon_path):
        self.pages.append(page_widget)
        self.pages_stack.addWidget(page_widget)
        
        item = QListWidgetItem()
        item_widget = NavigationItemWidget(icon_path, title)
        
        item.setSizeHint(QSize(self.navigation_bar.width(), 40)) 
        
        self.navigation_bar.addItem(item)
        self.navigation_bar.setItemWidget(item, item_widget)
        
    def update_navigation_icons(self):
        """네비게이션 아이템의 선택 상태에 따라 아이콘과 텍스트 색상을 모두 업데이트합니다."""
        theme = self.config_manager.get("app_theme", "dark")
        
        if theme == 'custom':
            colors = self.config_manager.get("custom_theme_colors")
            active_icon_color = colors.get("TEXT_HEADER", "#ffffff")
            inactive_icon_color = colors.get("TEXT_MUTED", "#85929e")
            active_text_color = colors.get("TEXT_HEADER", "#ffffff")
            inactive_text_color = colors.get("TEXT_PRIMARY", "#eaf2f8")
            
        elif theme == 'light':
            active_icon_color = "#ffffff"
            inactive_icon_color = "#4f5660" 
            active_text_color = "#ffffff" 
            inactive_text_color = "#2e3338" 
            
        else: 
            active_icon_color = "#ffffff"
            inactive_icon_color = "#b9bbbe"
            active_text_color = "#ffffff"  
            inactive_text_color = "#b9bbbe"

        current_row = self.navigation_bar.currentRow()
        for row in range(self.navigation_bar.count()):
            item = self.navigation_bar.item(row)
            widget = self.navigation_bar.itemWidget(item)
            if isinstance(widget, NavigationItemWidget):
                widget.set_active(
                    is_active=(row == current_row),
                    active_color=active_icon_color,
                    inactive_color=inactive_icon_color,
                    active_text_color=active_text_color,
                    inactive_text_color=inactive_text_color
                )

    def apply_stylesheet(self):
        theme = self.config_manager.get("app_theme", "dark")
        try:
            if theme == "custom":
                qss_template_path = resource_path('assets/style_template.qss')
                with open(qss_template_path, 'r', encoding='utf-8') as f:
                    stylesheet = f.read()
                custom_colors = self.config_manager.get("custom_theme_colors", {})
                for key, color_val in custom_colors.items():
                    stylesheet = stylesheet.replace(f"%{key}%", str(color_val))
                logging.info("커스텀 테마를 생성하여 적용했습니다.")
            else:
                qss_file = 'style_dark.qss' if theme == "dark" else 'style_light.qss'
                qss_path = resource_path(f'assets/{qss_file}')
                with open(qss_path, 'r', encoding='utf-8') as f:
                    stylesheet = f.read()
            
            asset_path = resource_path("assets").replace("\\", "/")
            stylesheet = stylesheet.replace("%ASSET_PATH%", asset_path)
            
            app = QApplication.instance()
            if app:
                app.setStyleSheet(stylesheet)
            
            logging.info(f"'{theme}' 테마가 적용되었습니다.")
            self.theme_changed.emit()
        except Exception as e:
            logging.error(f"스타일시트 적용 중 오류 발생: {e}", exc_info=True)

    def save_and_close(self):
        current_lang = self.config_manager.get("app_language")
        new_lang = self.program_page.lang_combo.currentData()

        self.save_settings()

        if current_lang != new_lang:
            QMessageBox.information(self, self.tr("Restart required"), self.tr("UI language change requires a program restart to take full effect."))
        
        if self.config_manager.get("is_first_run"):
            self.config_manager.set("is_first_run", False, is_global=True)
        self.close()

    def reset_settings(self):
        reply = QMessageBox.question(self, self.tr("Reset Settings"), self.tr("Are you sure you want to reset all settings to their default values?"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            # 프로필 기반이므로 활성 프로필을 리셋하는 것이 더 적절할 수 있습니다.
            # 여기서는 전체 설정을 리셋합니다.
            self.config_manager.reset_config()
            self.load_settings()
            self.apply_stylesheet()
            QMessageBox.information(self, self.tr("Complete"), self.tr("All settings have been reset."))

    def load_settings(self):
        for page in self.pages:
            if hasattr(page, 'load_settings'):
                page.load_settings()
        self.update_navigation_icons()
        
    def save_settings(self):
        for page in self.pages:
            if hasattr(page, 'save_settings'):
                page.save_settings()
        self.config_manager.save_config()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def tr(self, text):
        return QCoreApplication.translate("SetupWindow", text)