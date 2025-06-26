# src/gui/overlay_window.py
import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QFont

from config_manager import ConfigManager

class OverlayWindow(QWidget):
    SPEAKER_COLORS = ["#FFFFFF", "#81D4FA", "#A5D6A7", "#FFCC80", "#B39DDB"]

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(5)

        self.top_label = self._create_label()
        self.center_label = self._create_label(is_bold=True)
        self.bottom_label = self._create_label()

        self.layout.addWidget(self.top_label, alignment=Qt.AlignmentFlag.AlignBottom)
        self.layout.addWidget(self.center_label, alignment=Qt.AlignmentFlag.AlignBottom)
        self.layout.addWidget(self.bottom_label, alignment=Qt.AlignmentFlag.AlignBottom)
        
        self.setLayout(self.layout)
        self.resize(800, 250)
        self._center_on_screen()
        
        self.clear_timer = QTimer(self)
        self.clear_timer.setSingleShot(True)
        self.clear_timer.timeout.connect(self.clear_all_labels)
        self.update_styles()

    def _create_label(self, is_bold=False) -> QLabel:
        label = QLabel(" ")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setVisible(False)
        label.setProperty("is_bold", is_bold)
        return label
    
    def update_styles(self):
        """config에서 스타일을 읽어와 모든 라벨에 적용합니다."""
        font_family = self.config_manager.get("overlay_font_family")
        font_size = self.config_manager.get("overlay_font_size")
        font_color = self.config_manager.get("overlay_font_color")
        bg_color = self.config_manager.get("overlay_bg_color")

        for label in [self.top_label, self.center_label, self.bottom_label]:
            is_bold = label.property("is_bold")
            current_font_size = font_size + 2 if is_bold else font_size
            
            font = QFont(font_family, current_font_size)
            font.setBold(is_bold)
            label.setFont(font)
            label.setStyleSheet(f"""
                QLabel {{
                    color: {font_color};
                    background-color: {bg_color};
                    border-radius: 5px;
                    padding: 8px;
                }}
            """)

    def _center_on_screen(self):
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = screen_geometry.height() - self.height() - 50
        self.move(x, y)

    @Slot(list)
    def update_translation(self, results: list):
        self.clear_all_labels()
        if not results: return
        count = len(results)
        if count == 1:
            self._set_label_text(self.center_label, results[0])
        elif count == 2:
            self._set_label_text(self.top_label, results[0])
            self._set_label_text(self.center_label, results[1])
        elif count >= 3:
            self._set_label_text(self.top_label, results[0])
            self._set_label_text(self.center_label, results[1])
            self._set_label_text(self.bottom_label, results[2])
        self.clear_timer.start(10000)

    def _set_label_text(self, label: QLabel, result: dict):
        label.setText(result['translated'])
        label.setVisible(True)

    @Slot()
    def clear_all_labels(self):
        self.top_label.setVisible(False)
        self.center_label.setVisible(False)
        self.bottom_label.setVisible(False)