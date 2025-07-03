import sys
import logging
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QListWidget, QStackedWidget, QVBoxLayout,
                             QListWidgetItem, QPushButton, QSpacerItem, QSizePolicy, QLineEdit,
                             QKeySequenceEdit, QLabel, QFileDialog, QSlider, QMessageBox,
                             QComboBox, QSpinBox, QColorDialog)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QKeySequence, QColor, QPalette, QIcon

from ..utils import resource_path
from ..config_manager import ConfigManager
from .fluent_widgets import (NavigationItemWidget, SettingsPage, TitleLabel,
                               DescriptionLabel, SettingsCard)

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
        color = QColorDialog.getColor(self._color, self, "색상 선택")
        if color.isValid():
            self.set_color(color)
            self.colorChanged.emit(color)

class FilePathSelector(QWidget):
    """'찾아보기' 버튼으로 파일 경로를 선택하게 하는 위젯."""
    def __init__(self, placeholder=""):
        super().__init__()
        layout = QHBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        self.path_edit = QLineEdit(); self.path_edit.setPlaceholderText(placeholder)
        self.browse_button = QPushButton("찾아보기..."); self.browse_button.clicked.connect(self.browse_file)
        layout.addWidget(self.path_edit); layout.addWidget(self.browse_button)
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "오디오 파일 선택", "", "오디오 파일 (*.wav *.mp3)")
        if file_path: self.path_edit.setText(file_path)
    def text(self): return self.path_edit.text()
    def setText(self, text): self.path_edit.setText(text)

class ProgramSettingsPage(SettingsPage):
    """프로그램의 전반적인 설정을 담당하는 페이지."""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.add_widget(TitleLabel("프로그램 설정"))
        self.add_widget(DescriptionLabel("UI 테마, 언어, API 키 등 프로그램의 기본 동작을 설정합니다."))

        api_card = SettingsCard("DeepL API 키", "텍스트 번역을 위해 DeepL API 인증 키가 필요합니다.")
        self.deepl_key_edit = QLineEdit(); self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepl_key_edit.setPlaceholderText("API 인증 키를 입력하세요")
        api_card.add_widget(self.deepl_key_edit); self.add_widget(api_card)

        theme_card = SettingsCard("UI 테마")
        self.theme_combo = QComboBox(); self.theme_combo.addItems(["Dark", "Light", "Custom"])
        theme_card.add_widget(self.theme_combo); self.add_widget(theme_card)
        
        self.custom_colors_card = SettingsCard("커스텀 테마 색상")
        self.color_pickers = {}
        # style_template.qss의 플레이스홀더와 일치해야 함
        colors_to_pick = {
            "주 배경": "BACKGROUND_PRIMARY", "부 배경": "BACKGROUND_SECONDARY",
            "페이지 배경": "BACKGROUND_TERTIARY", "기본 텍스트": "TEXT_PRIMARY",
            "헤더 텍스트": "TEXT_HEADER", "설명 텍스트": "TEXT_MUTED", "일반 버튼": "INTERACTIVE_NORMAL",
            "포인트 버튼": "INTERACTIVE_ACCENT"
        }
        for name, key in colors_to_pick.items():
            layout = QHBoxLayout()
            layout.addWidget(QLabel(f"{name}:"))
            layout.addStretch(1)
            color_picker = ColorPickerButton()
            self.color_pickers[key] = color_picker
            layout.addWidget(color_picker)
            self.custom_colors_card.add_layout(layout)
        self.add_widget(self.custom_colors_card)

        hotkey_card = SettingsCard("전역 단축키")
        self.hotkey_widgets = {}
        hotkey_actions = { "toggle_stt": "음성 번역", "toggle_ocr": "화면 번역", "toggle_setup": "설정 창", "quit_app": "프로그램 종료" }
        for action, desc in hotkey_actions.items():
            hotkey_card.add_widget(QLabel(f"{desc} 시작/중지"))
            key_edit = QKeySequenceEdit()
            hotkey_card.add_widget(key_edit)
            self.hotkey_widgets[action] = key_edit
        self.add_widget(hotkey_card)

        self.theme_combo.currentTextChanged.connect(lambda text: self.custom_colors_card.setVisible(text.lower() == "custom"))

    def load_settings(self):
        self.deepl_key_edit.setText(self.config_manager.get("deepl_api_key", ""))
        theme = self.config_manager.get("app_theme", "dark")
        self.theme_combo.setCurrentText(theme.capitalize())
        self.custom_colors_card.setVisible(theme == "custom")
        # TODO: 커스텀 색상 로드 로직 추가
        
        for action, widget in self.hotkey_widgets.items():
            hotkey_str = self.config_manager.get(f"hotkey_{action}", "")
            widget.setKeySequence(QKeySequence.fromString(hotkey_str, QKeySequence.PortableText))

    def save_settings(self):
        self.config_manager.set("deepl_api_key", self.deepl_key_edit.text())
        self.config_manager.set("app_theme", self.theme_combo.currentText().lower())
        # TODO: 커스텀 색상 저장 로직 추가
        
        for action, widget in self.hotkey_widgets.items():
            sequence = widget.keySequence()
            if sequence.count() >= 1 and not (sequence.toString() in ["Ctrl", "Shift", "Alt"]):
                hotkey_str = sequence.toString(QKeySequence.PortableText).lower().replace("meta", "cmd")
                self.config_manager.set(f"hotkey_{action}", hotkey_str)
            else:
                self.config_manager.set(f"hotkey_{action}", "")

class OcrSettingsPage(SettingsPage):
    """화면 번역(OCR) 관련 설정을 담당하는 페이지."""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.add_widget(TitleLabel("화면 번역 (OCR) 설정"))
        self.add_widget(DescriptionLabel("화면의 텍스트를 인식하고 번역하는 기능의 세부 동작을 설정합니다."))
        mode_card = SettingsCard("번역 모드")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["표준 오버레이 (Standard Overlay)", "스타일 복제 패치 (Style Patch) - 개발 중"])
        mode_card.add_widget(self.mode_combo)
        self.add_widget(mode_card)
    def load_settings(self):
        mode = self.config_manager.get("ocr_mode", "overlay")
        self.mode_combo.setCurrentIndex(0 if mode == "overlay" else 1)
    def save_settings(self):
        self.config_manager.set("ocr_mode", "overlay" if self.mode_combo.currentIndex() == 0 else "patch")

class SttSettingsPage(SettingsPage):
    """음성 번역(STT) 관련 설정을 담당하는 페이지."""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.add_widget(TitleLabel("음성 번역 (STT) 설정"))
        self.add_widget(DescriptionLabel("시스템 사운드를 인식하고 번역하는 기능의 세부 동작을 설정합니다."))
        vad_card = SettingsCard("음성 감지 감도 (VAD Sensitivity)")
        self.vad_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_slider.setRange(1, 3)
        vad_card.add_widget(self.vad_slider)
        self.add_widget(vad_card)
        silence_card = SettingsCard("문장 구분 침묵 시간 (초)")
        self.silence_spinbox = QSpinBox()
        self.silence_spinbox.setRange(1, 5)
        self.silence_spinbox.setSuffix(" 초")
        silence_card.add_widget(self.silence_spinbox)
        self.add_widget(silence_card)
    def load_settings(self):
        self.vad_slider.setValue(self.config_manager.get("vad_sensitivity", 3))
        self.silence_spinbox.setValue(int(self.config_manager.get("silence_threshold_s", 1.0)))
    def save_settings(self):
        self.config_manager.set("vad_sensitivity", self.vad_slider.value())
        self.config_manager.set("silence_threshold_s", float(self.silence_spinbox.value()))

class StyleSettingsPage(SettingsPage):
    """번역 오버레이의 스타일 설정을 담당하는 페이지."""
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.add_widget(TitleLabel("오버레이 스타일 설정"))
        self.add_widget(DescriptionLabel("번역 결과가 표시되는 오버레이 창의 글꼴, 색상 등 디자인을 설정합니다."))
        font_card = SettingsCard("글꼴 설정")
        font_card.add_widget(QLabel("글자 크기"))
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(8, 72)
        font_card.add_widget(self.font_size_spinbox)
        self.add_widget(font_card)
        color_card = SettingsCard("색상 설정")
        self.add_widget(color_card)
    def load_settings(self):
        self.font_size_spinbox.setValue(self.config_manager.get("overlay_font_size", 18))
    def save_settings(self):
        self.config_manager.set("overlay_font_size", self.font_size_spinbox.value())

class SetupWindow(QWidget):
    """메인 설정 창 클래스. 테마 관리와 페이지 전환을 담당."""
    closed = Signal()
    theme_changed = Signal()

    def __init__(self, config_manager: ConfigManager, initial_page_index=0):
        super().__init__()
        self.config_manager = config_manager
        self.setObjectName("setupWindow")
        self.setWindowTitle("Ariel 설정")
        self.setMinimumSize(960, 600)
        self.resize(1024, 720)
        
        self._init_ui()
        self._add_pages()
        self.apply_stylesheet()

        self.navigation_bar.currentRowChanged.connect(self.update_navigation_icons)
        self.theme_changed.connect(self.update_navigation_icons)
        self.save_button.clicked.connect(self.save_and_close)
        self.cancel_button.clicked.connect(self.close)
        self.reset_button.clicked.connect(self.reset_settings)

        self.load_settings()
        self.navigation_bar.setCurrentRow(initial_page_index)

    def _init_ui(self):
        main_layout = QHBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        self.navigation_bar = QListWidget(); self.navigation_bar.setObjectName("navigationBar"); self.navigation_bar.setFixedWidth(240); self.navigation_bar.setSpacing(5)
        self.pages_stack = QStackedWidget(); self.pages = []
        content_widget = QWidget(); content_widget.setObjectName("contentWidget")
        content_layout = QVBoxLayout(content_widget); content_layout.setContentsMargins(0, 0, 0, 0); content_layout.setSpacing(0)
        content_layout.addWidget(self.pages_stack, 1)
        button_bar = QWidget(); button_bar.setObjectName("buttonBar")
        button_bar_layout = QHBoxLayout(button_bar); button_bar_layout.setContentsMargins(20, 10, 20, 10)
        self.reset_button = QPushButton("설정 초기화"); button_bar_layout.addWidget(self.reset_button)
        button_bar_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.save_button = QPushButton("저장 후 닫기"); self.save_button.setObjectName("primaryButton"); self.cancel_button = QPushButton("취소")
        button_bar_layout.addWidget(self.save_button); button_bar_layout.addWidget(self.cancel_button); content_layout.addWidget(button_bar)
        main_layout.addWidget(self.navigation_bar); main_layout.addWidget(content_widget, 1)

    def _add_pages(self):
        self.program_page = ProgramSettingsPage(self.config_manager)
        self.ocr_page = OcrSettingsPage(self.config_manager)
        self.stt_page = SttSettingsPage(self.config_manager)
        self.style_page = StyleSettingsPage(self.config_manager)
        
        self.add_page(self.program_page, "프로그램 설정", resource_path("assets/icons/settings.svg"))
        self.add_page(self.ocr_page, "화면 번역 설정", resource_path("assets/icons/ocr.svg"))
        self.add_page(self.stt_page, "음성 자막 설정", resource_path("assets/icons/audio.svg"))
        self.add_page(self.style_page, "오버레이 설정", resource_path("assets/icons/style.svg"))

    def add_page(self, page_widget, title, icon_path):
        self.pages.append(page_widget); self.pages_stack.addWidget(page_widget); item = QListWidgetItem(); item_widget = NavigationItemWidget(icon_path, title)
        item.setSizeHint(item_widget.sizeHint()); self.navigation_bar.addItem(item); self.navigation_bar.setItemWidget(item, item_widget)
        
    def update_navigation_icons(self):
        """현재 테마에 맞춰 네비게이션 아이콘/텍스트 색상을 갱신합니다."""
        theme = self.config_manager.get("app_theme", "dark")
        current_row = self.navigation_bar.currentRow()

        # 테마별 색상 정의
        if theme == 'dark':
            active_icon_color, inactive_icon_color = "#FFFFFF", "#8e9297"
            active_text_color, inactive_text_color = "#FFFFFF", "#d1d5db"
        else: # light or custom
            active_icon_color, inactive_icon_color = "#0056b3", "#4f5660"
            active_text_color, inactive_text_color = "#212529", "#495057"
        
        for row in range(self.navigation_bar.count()):
            item = self.navigation_bar.item(row)
            widget = self.navigation_bar.itemWidget(item)
            if isinstance(widget, NavigationItemWidget):
                is_active = (row == current_row)
                
                widget.set_icon_color(active_icon_color if is_active else inactive_icon_color)
                
                font = widget.text_label.font()
                font.setBold(is_active)
                widget.text_label.setFont(font)
                
                # QSS 대신 직접 색상을 설정하여 실시간 변경 보장
                palette = widget.text_label.palette()
                palette.setColor(QPalette.ColorRole.WindowText, QColor(active_text_color if is_active else inactive_text_color))
                widget.text_label.setPalette(palette)

    def apply_stylesheet(self):
        """설정에 맞는 테마를 동적으로 불러와 앱 전체에 적용합니다."""
        theme = self.config_manager.get("app_theme", "dark")
        stylesheet = ""
        try:
            if theme == "custom":
                # 커스텀 테마: 템플릿 파일에서 색상 값 교체 (미구현)
                qss_file = 'style_dark.qss' # fallback
                logging.warning("커스텀 테마는 아직 지원되지 않아 다크 테마로 대체합니다.")
            else:
                qss_file = 'style_dark.qss' if theme == "dark" else 'style_light.qss'
            
            qss_path = resource_path(f'assets/{qss_file}')
            with open(qss_path, 'r', encoding='utf-8') as f:
                stylesheet = f.read()

            asset_path = resource_path("assets").replace("\\", "/")
            stylesheet = stylesheet.replace("%ASSET_PATH%", asset_path)
            
            QApplication.instance().setStyleSheet(stylesheet)
            logging.info(f"'{theme}' 테마가 적용되었습니다.")
            self.theme_changed.emit()

        except Exception as e:
            logging.error(f"스타일시트 적용 중 오류 발생: {e}", exc_info=True)

    def save_and_close(self):
        self.save_settings()
        self.config_manager.set("is_first_run", False, is_global=True)
        self.apply_stylesheet()
        self.close()

    def reset_settings(self):
        reply = QMessageBox.question(self, "설정 초기화", "정말로 모든 설정을 초기값으로 되돌리시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.reset_config()
            self.load_settings()
            self.apply_stylesheet()
            QMessageBox.information(self, "완료", "모든 설정이 초기화되었습니다.")

    def load_settings(self):
        for page in self.pages:
            if hasattr(page, 'load_settings'):
                page.load_settings()
        
    def save_settings(self):
        for page in self.pages:
            if hasattr(page, 'save_settings'):
                page.save_settings()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)