import sys
import logging
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QListWidget, QStackedWidget, QVBoxLayout,
                             QListWidgetItem, QPushButton, QSpacerItem, QSizePolicy, QLineEdit,
                             QKeySequenceEdit, QLabel, QFileDialog, QSlider, QMessageBox,
                             QComboBox, QSpinBox, QColorDialog, QFrame, QFontComboBox)
from PySide6.QtCore import Qt, Signal, QSize, QCoreApplication, QTranslator
from PySide6.QtGui import QKeySequence, QColor, QPalette, QIcon

from ..utils import resource_path
from ..config_manager import ConfigManager
from .fluent_widgets import (NavigationItemWidget, SettingsPage, TitleLabel,
                               DescriptionLabel, SettingsCard)

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "English": "en", "Korean": "ko", "Japanese": "ja",
    "Chinese": "zh", "German": "de", "French": "fr", "Spanish": "es",
}
SUPPORTED_DEEPL_LANGUAGES = {
    "Auto Detect": "auto", "Korean": "KO", "English": "EN-US", "Japanese": "JA",
    "Chinese": "ZH", "German": "DE", "French": "FR", "Spanish": "ES",
}

class ColorPickerButton(QPushButton):
    colorChanged = Signal()
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
            self.colorChanged.emit()

class BaseSettingsPage(SettingsPage):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager

    def retranslate_ui(self):
        pass

    def tr(self, context, text):
        return QCoreApplication.translate(context, text)

class ProgramSettingsPage(BaseSettingsPage):
    language_changed = Signal()
    theme_changed = Signal()

    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        
        self.title_label = TitleLabel()
        self.desc_label = DescriptionLabel()
        self.add_widget(self.title_label)
        self.add_widget(self.desc_label)

        self.lang_card = SettingsCard()
        self.lang_combo = QComboBox()
        for name, code in SUPPORTED_LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        self.lang_card.add_widget(self.lang_combo)
        self.add_widget(self.lang_card)

        self.api_card = SettingsCard()
        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_card.add_widget(self.deepl_key_edit)
        self.add_widget(self.api_card)

        self.theme_card = SettingsCard()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "Custom"])
        self.theme_card.add_widget(self.theme_combo)
        self.add_widget(self.theme_card)

        self.custom_colors_card = SettingsCard()
        self.color_pickers = {}
        colors_to_pick = { "Primary Background": "BACKGROUND_PRIMARY", "Secondary Background": "BACKGROUND_SECONDARY", "Tertiary Background": "BACKGROUND_TERTIARY", "Primary Text": "TEXT_PRIMARY", "Header Text": "TEXT_HEADER", "Muted Text": "TEXT_MUTED", "Interactive Normal": "INTERACTIVE_NORMAL", "Interactive Hover": "INTERACTIVE_HOVER", "Interactive Accent": "INTERACTIVE_ACCENT", "Interactive Accent Hover": "INTERACTIVE_ACCENT_HOVER", "Border Color": "BORDER_COLOR" }
        for name_key, color_conf_key in colors_to_pick.items():
            layout = QHBoxLayout(); label = QLabel()
            layout.addWidget(label); layout.addStretch(1)
            color_picker = ColorPickerButton()
            color_picker.colorChanged.connect(self.on_color_changed)
            self.color_pickers[color_conf_key] = (label, name_key, color_picker)
            layout.addWidget(color_picker); self.custom_colors_card.add_layout(layout)
        self.add_widget(self.custom_colors_card)

        self.hotkey_card = SettingsCard()
        self.hotkey_widgets = {}; self.hotkey_labels = {}
        hotkey_actions = { "hotkey_toggle_stt": "Start/Stop Voice Translation", "hotkey_toggle_ocr": "Start/Stop Screen Translation", "hotkey_toggle_setup": "Open/Close Settings Window", "hotkey_quit_app": "Quit Program" }
        for action, desc_key in hotkey_actions.items():
            layout = QHBoxLayout(); label = QLabel()
            self.hotkey_labels[action] = (label, desc_key); layout.addWidget(label)
            key_edit = QKeySequenceEdit(); self.hotkey_widgets[action] = key_edit
            layout.addWidget(key_edit); self.hotkey_card.add_layout(layout)
        self.add_widget(self.hotkey_card)

        self.lang_combo.currentIndexChanged.connect(lambda: self.language_changed.emit())
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)

    def on_theme_changed(self, text: str):
        self.custom_colors_card.setVisible(text.lower() == "custom")
        if not self.theme_combo.signalsBlocked():
            self.theme_changed.emit()

    def on_color_changed(self):
        if self.config_manager.get("app_theme") == "custom":
            self.theme_changed.emit()

    def retranslate_ui(self):
        self.title_label.setText(self.tr("ProgramSettingsPage", "Program Settings"))
        self.desc_label.setText(self.tr("ProgramSettingsPage", "Configure the basic behavior of the program."))
        self.lang_card.title_label.setText(self.tr("ProgramSettingsPage", "UI Language"))
        if self.lang_card.desc_label: self.lang_card.desc_label.setText(self.tr("ProgramSettingsPage", "Restart the program to apply language changes."))
        self.api_card.title_label.setText(self.tr("ProgramSettingsPage", "DeepL API Key"))
        if self.api_card.desc_label: self.api_card.desc_label.setText(self.tr("ProgramSettingsPage", "DeepL API key is required for translation."))
        self.deepl_key_edit.setPlaceholderText(self.tr("ProgramSettingsPage", "Enter your API key"))
        self.theme_card.title_label.setText(self.tr("ProgramSettingsPage", "UI Theme"))
        self.custom_colors_card.title_label.setText(self.tr("ProgramSettingsPage", "Custom Theme Colors"))
        if self.custom_colors_card.desc_label: self.custom_colors_card.desc_label.setText(self.tr("ProgramSettingsPage", "Click the color buttons to change to your desired colors. Changes are applied immediately."))
        self.hotkey_card.title_label.setText(self.tr("ProgramSettingsPage", "Global Hotkeys"))
        if self.hotkey_card.desc_label: self.hotkey_card.desc_label.setText(self.tr("ProgramSettingsPage", "Set hotkeys to quickly execute the program's main functions."))
        
        for label, name_key, _ in self.color_pickers.values():
            label.setText(f"{self.tr('ProgramSettingsPage', name_key)}:")
        for label, desc_key in self.hotkey_labels.values():
            label.setText(f"{self.tr('ProgramSettingsPage', desc_key)}:")
            
    def load_settings(self):
        self.lang_combo.blockSignals(True)
        lang_code = self.config_manager.get("app_language", "en")
        if (index := self.lang_combo.findData(lang_code)) != -1: self.lang_combo.setCurrentIndex(index)
        self.lang_combo.blockSignals(False)
        
        self.deepl_key_edit.setText(self.config_manager.get("deepl_api_key", ""))
        
        self.theme_combo.blockSignals(True)
        theme = self.config_manager.get("app_theme", "dark")
        self.theme_combo.setCurrentText(theme.capitalize())
        self.custom_colors_card.setVisible(theme == "custom")
        self.theme_combo.blockSignals(False)
        
        custom_colors = self.config_manager.get("custom_theme_colors", {})
        default_colors = self.config_manager.get_default_profile_settings()["custom_theme_colors"]
        for key, (_, _, picker) in self.color_pickers.items():
            picker.set_color(QColor(custom_colors.get(key, default_colors.get(key, "#000000"))))
            
        for action, widget in self.hotkey_widgets.items():
            widget.setKeySequence(QKeySequence.fromString(self.config_manager.get(action, ""), QKeySequence.PortableText))

    def save_settings(self):
        self.config_manager.set("app_language", self.lang_combo.currentData())
        self.config_manager.set("deepl_api_key", self.deepl_key_edit.text())
        self.config_manager.set("app_theme", self.theme_combo.currentText().lower())
        custom_colors = {key: picker.color().name() for key, (_, _, picker) in self.color_pickers.items()}
        self.config_manager.set("custom_theme_colors", custom_colors)
        for action, widget in self.hotkey_widgets.items():
            self.config_manager.set(action, widget.keySequence().toString(QKeySequence.PortableText).lower().replace("meta", "cmd"))

class OcrSettingsPage(BaseSettingsPage):
    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.title_label = TitleLabel(); self.desc_label = DescriptionLabel()
        self.add_widget(self.title_label); self.add_widget(self.desc_label)
        self.lang_card = SettingsCard(); self.source_lang_combo = QComboBox(); self.target_lang_combo = QComboBox()
        lang_layout = QHBoxLayout(); self.source_lang_label = QLabel(); self.target_lang_label = QLabel()
        lang_layout.addWidget(self.source_lang_label); lang_layout.addWidget(self.source_lang_combo); lang_layout.addStretch(1)
        lang_layout.addWidget(self.target_lang_label); lang_layout.addWidget(self.target_lang_combo)
        self.lang_card.add_layout(lang_layout); self.add_widget(self.lang_card)
        self.mode_card = SettingsCard(); self.mode_combo = QComboBox()
        self.mode_card.add_widget(self.mode_combo); self.add_widget(self.mode_card)

    def retranslate_ui(self):
        self.title_label.setText(self.tr("OcrSettingsPage", "Screen Translation (OCR) Settings"))
        self.desc_label.setText(self.tr("OcrSettingsPage", "Configure the detailed behavior for screen text recognition and translation."))
        self.lang_card.title_label.setText(self.tr("OcrSettingsPage", "Language Settings"))
        self.source_lang_label.setText(self.tr("OcrSettingsPage", "Source Language:"))
        self.target_lang_label.setText(self.tr("OcrSettingsPage", "Target Language:"))
        
        for combo in [self.source_lang_combo, self.target_lang_combo]:
            combo.blockSignals(True); current_data = combo.currentData(); combo.clear()
        
        for name, code in SUPPORTED_DEEPL_LANGUAGES.items():
            tr_name = self.tr("SUPPORTED_LANGUAGES", name)
            self.source_lang_combo.addItem(tr_name, code)
            if code != 'auto': self.target_lang_combo.addItem(tr_name, code)
        
        for combo, data in [(self.source_lang_combo, self.source_lang_combo.currentData()), (self.target_lang_combo, self.target_lang_combo.currentData())]:
            if (idx := combo.findData(data)) != -1: combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        self.mode_card.title_label.setText(self.tr("OcrSettingsPage", "Translation Mode"))
        current_idx = self.mode_combo.currentIndex(); self.mode_combo.clear()
        self.mode_combo.addItems([self.tr("OcrSettingsPage", "Standard Overlay"), self.tr("OcrSettingsPage", "Style-Cloning Patch (WIP)")])
        self.mode_combo.setCurrentIndex(current_idx)

    def load_settings(self):
        self.retranslate_ui()
        source_code = self.config_manager.get("ocr_source_language", "auto")
        target_code = self.config_manager.get("ocr_target_language", "KO")
        if (idx := self.source_lang_combo.findData(source_code)) != -1: self.source_lang_combo.setCurrentIndex(idx)
        if (idx := self.target_lang_combo.findData(target_code)) != -1: self.target_lang_combo.setCurrentIndex(idx)
        self.mode_combo.setCurrentIndex(0 if self.config_manager.get("ocr_mode", "overlay") == "overlay" else 1)

    def save_settings(self):
        self.config_manager.set("ocr_source_language", self.source_lang_combo.currentData())
        self.config_manager.set("ocr_target_language", self.target_lang_combo.currentData())
        self.config_manager.set("ocr_mode", "overlay" if self.mode_combo.currentIndex() == 0 else "patch")

class SttSettingsPage(BaseSettingsPage):
    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.title_label = TitleLabel(); self.desc_label = DescriptionLabel()
        self.add_widget(self.title_label); self.add_widget(self.desc_label)
        self.lang_card = SettingsCard(); self.source_lang_combo = QComboBox(); self.target_lang_combo = QComboBox()
        lang_layout = QHBoxLayout(); self.source_lang_label = QLabel(); self.target_lang_label = QLabel()
        lang_layout.addWidget(self.source_lang_label); lang_layout.addWidget(self.source_lang_combo); lang_layout.addStretch(1)
        lang_layout.addWidget(self.target_lang_label); lang_layout.addWidget(self.target_lang_combo)
        self.lang_card.add_layout(lang_layout); self.add_widget(self.lang_card)
        
        self.vad_card = SettingsCard(); self.vad_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_slider.setRange(1, 3); self.vad_slider.setTickPosition(QSlider.TickPosition.TicksBelow); self.vad_slider.setSingleStep(1)
        self.vad_card.add_widget(self.vad_slider); self.add_widget(self.vad_card)
        
        self.silence_card = SettingsCard(); self.silence_spinbox = QSpinBox()
        self.silence_spinbox.setRange(1, 5)
        self.silence_card.add_widget(self.silence_spinbox); self.add_widget(self.silence_card)

    def retranslate_ui(self):
        self.title_label.setText(self.tr("SttSettingsPage", "Voice Translation (STT) Settings"))
        self.desc_label.setText(self.tr("SttSettingsPage", "Configure the detailed behavior for system sound recognition and translation."))
        self.lang_card.title_label.setText(self.tr("SttSettingsPage", "Language Settings"))
        self.source_lang_label.setText(self.tr("SttSettingsPage", "Source Language:"))
        self.target_lang_label.setText(self.tr("SttSettingsPage", "Target Language:"))

        for combo in [self.source_lang_combo, self.target_lang_combo]:
            combo.blockSignals(True); current_data = combo.currentData(); combo.clear()
        for name, code in SUPPORTED_DEEPL_LANGUAGES.items():
            tr_name = self.tr("SUPPORTED_LANGUAGES", name)
            self.source_lang_combo.addItem(tr_name, code)
            if code != 'auto': self.target_lang_combo.addItem(tr_name, code)
        for combo, data in [(self.source_lang_combo, self.source_lang_combo.currentData()), (self.target_lang_combo, self.target_lang_combo.currentData())]:
            if (idx := combo.findData(data)) != -1: combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        self.vad_card.title_label.setText(self.tr("SttSettingsPage", "Voice Activity Detection (VAD) Sensitivity"))
        if self.vad_card.desc_label: self.vad_card.desc_label.setText(self.tr("SttSettingsPage", "Adjust how sensitively voice is detected. (1: Low, 3: High)"))
        self.silence_card.title_label.setText(self.tr("SttSettingsPage", "Sentence-break Silence (seconds)"))
        if self.silence_card.desc_label: self.silence_card.desc_label.setText(self.tr("SttSettingsPage", "Set how long a silence must be to be considered the end of a sentence."))
        self.silence_spinbox.setSuffix(self.tr("SttSettingsPage", " s"))

    def load_settings(self):
        self.retranslate_ui()
        source_code = self.config_manager.get("stt_source_language", "auto")
        target_code = self.config_manager.get("stt_target_language", "KO")
        if (idx := self.source_lang_combo.findData(source_code)) != -1: self.source_lang_combo.setCurrentIndex(idx)
        if (idx := self.target_lang_combo.findData(target_code)) != -1: self.target_lang_combo.setCurrentIndex(idx)
        self.vad_slider.setValue(self.config_manager.get("vad_sensitivity", 3))
        self.silence_spinbox.setValue(int(self.config_manager.get("silence_threshold_s", 1.0)))

    def save_settings(self):
        self.config_manager.set("stt_source_language", self.source_lang_combo.currentData())
        self.config_manager.set("stt_target_language", self.target_lang_combo.currentData())
        self.config_manager.set("vad_sensitivity", self.vad_slider.value())
        self.config_manager.set("silence_threshold_s", float(self.silence_spinbox.value()))

class StyleSettingsPage(BaseSettingsPage):
    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.title_label = TitleLabel(); self.desc_label = DescriptionLabel()
        self.add_widget(self.title_label); self.add_widget(self.desc_label)
        self.stt_card = SettingsCard(); self.add_widget(self.stt_card)
        self.ocr_card = SettingsCard(); self.add_widget(self.ocr_card)

    def retranslate_ui(self):
        self.title_label.setText(self.tr("StyleSettingsPage", "Overlay Style Settings"))
        self.desc_label.setText(self.tr("StyleSettingsPage", "Configure the design of the overlay window where translation results are displayed, including font and colors."))
        self.stt_card.title_label.setText(self.tr("StyleSettingsPage", "Voice (STT) Overlay"))
        self.ocr_card.title_label.setText(self.tr("StyleSettingsPage", "Screen (OCR) Overlay"))

    def load_settings(self): self.retranslate_ui()
    def save_settings(self): pass

class SetupWindow(QWidget):
    closed = Signal()

    def __init__(self, config_manager: ConfigManager, initial_page_index=0):
        super().__init__()
        self.config_manager = config_manager
        self.translator = QTranslator(self)
        self.setObjectName("setupWindow")
        self.setMinimumSize(960, 600)
        self._init_ui(); self._add_pages()
        self.navigation_bar.currentRowChanged.connect(self.pages_stack.setCurrentIndex)
        self.navigation_bar.currentRowChanged.connect(self.update_navigation_style)
        self.program_page.language_changed.connect(self.change_language)
        self.program_page.theme_changed.connect(self.apply_stylesheet)
        self.save_button.clicked.connect(self.save_and_close)
        self.cancel_button.clicked.connect(self.close)
        self.reset_button.clicked.connect(self.reset_settings)
        self.load_settings()
        self.apply_stylesheet()
        self.retranslate_ui()
        self.navigation_bar.setCurrentRow(initial_page_index)
        self.resize(1024, 720)

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
        self.ocr_page = OcrSettingsPage(self.config_manager)
        self.stt_page = SttSettingsPage(self.config_manager)
        self.style_page = StyleSettingsPage(self.config_manager)
        
        self.add_page(self.program_page, "Program", resource_path("assets/icons/settings.svg"))
        self.add_page(self.ocr_page, "Screen Translation (OCR)", resource_path("assets/icons/ocr.svg"))
        self.add_page(self.stt_page, "Voice Translation (STT)", resource_path("assets/icons/audio.svg"))
        self.add_page(self.style_page, "Overlay Style", resource_path("assets/icons/style.svg"))

    def add_page(self, page_widget, title_key, icon_path):
        self.pages.append(page_widget); self.pages_stack.addWidget(page_widget)
        item=QListWidgetItem(); item_widget=NavigationItemWidget(icon_path, title_key)
        item.setData(Qt.ItemDataRole.UserRole, title_key); item.setSizeHint(QSize(self.navigation_bar.width(),45))
        self.navigation_bar.addItem(item); self.navigation_bar.setItemWidget(item,item_widget)
        
    def update_navigation_style(self):
        theme = self.config_manager.get("app_theme", "dark")
        active_color, inactive_color = ("#ffffff", "#b9bbbe") if theme != 'light' else ("#ffffff", "#4f5660")
        for row in range(self.navigation_bar.count()):
            item = self.navigation_bar.item(row); widget = self.navigation_bar.itemWidget(item)
            is_selected = row == self.navigation_bar.currentRow()
            item.setSelected(is_selected)
            if isinstance(widget, NavigationItemWidget): widget.set_active(is_selected, active_color, inactive_color)

    def apply_stylesheet(self):
        self.program_page.save_settings()
        theme = self.config_manager.get("app_theme", "dark")
        try:
            qss = self.generate_qss(theme)
            if (app := QApplication.instance()): app.setStyleSheet(qss)
            logging.info(f"'{theme}' 테마가 적용되었습니다.")
            self.update_navigation_style() 
        except Exception as e:
            logging.error(f"스타일시트 적용 중 오류 발생: {e}", exc_info=True)

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

    def save_and_close(self):
        current_lang = self.config_manager.get("app_language")
        self.save_settings()
        new_lang = self.program_page.lang_combo.currentData()
        if current_lang != new_lang:
            QMessageBox.information(self, self.tr("SetupWindow", "Restart required"), self.tr("SetupWindow", "UI language change requires a program restart to take full effect."))
        if self.config_manager.get("is_first_run"):
            self.config_manager.set("is_first_run", False, is_global=True)
        self.close()

    def reset_settings(self):
        reply = QMessageBox.question(self, self.tr("SetupWindow", "Reset Settings"), self.tr("SetupWindow", "Are you sure you want to reset all settings to their default values?"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.reset_config(); self.load_settings(); self.apply_stylesheet()
            QMessageBox.information(self, self.tr("SetupWindow", "Complete"), self.tr("SetupWindow", "All settings have been reset."))

    def load_settings(self):
        for page in self.pages:
            if hasattr(page, 'load_settings'): page.load_settings()
        
    def save_settings(self):
        for page in self.pages:
            if hasattr(page, 'save_settings'): page.save_settings()
        self.config_manager.save_config()

    def change_language(self):
        self.program_page.save_settings()
        lang_code = self.program_page.lang_combo.currentData()
        
        app = QApplication.instance()
        app.removeTranslator(self.translator)
        if self.translator.load(resource_path(f'translations/ariel_{lang_code}.qm')):
            app.installTranslator(self.translator)
        else:
            logging.warning(f"동적 언어 변경 실패: '{lang_code}.qm'을 찾을 수 없습니다.")
        self.retranslate_ui()

    def retranslate_ui(self):
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

    def closeEvent(self, event):
        self.closed.emit(); super().closeEvent(event)

    def tr(self, context, text):
        return QCoreApplication.translate(context, text)