# ariel_client/src/gui/fluent_widgets.py (이 코드로 전체 교체)
import os
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea)
from PySide6.QtCore import Qt, QSize, QCoreApplication
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon

from ..utils import resource_path

logger = logging.getLogger(__name__)

class NavigationItemWidget(QWidget):
    """왼쪽 탐색 메뉴에 들어갈 아이콘과 텍스트 라벨 위젯"""
    def __init__(self, icon_path, text):
        super().__init__()
        self.icon_path = icon_path

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(15, 0, 15, 0)
        content_layout.setSpacing(15)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(22, 22)

        self.text_label = QLabel(self.tr("SetupWindow_PageTitles", text)) # 컨텍스트 수정
        self.text_label.setObjectName("navigationItemLabel")

        content_layout.addWidget(self.icon_label)
        content_layout.addWidget(self.text_label, 1)

        main_layout.addStretch(1)
        main_layout.addLayout(content_layout)
        main_layout.addStretch(1)

        self.set_active(False, "#b9bbbe", "#b9bbbe") # 비활성 상태로 초기화

    def set_active(self, is_active: bool, text_color: str, icon_color: str):
        """[수정] 활성 상태에 따라 아이콘과 텍스트 색상을 명확하게 설정합니다."""
        self.text_label.setStyleSheet(f"color: {text_color};")

        if not os.path.exists(self.icon_path):
            logging.warning(f"아이콘 파일을 찾을 수 없습니다: {self.icon_path}")
            return

        pixmap = QPixmap(self.icon_path)
        if pixmap.isNull(): return

        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(icon_color))
        painter.end()
        self.icon_label.setPixmap(pixmap.scaled(
            self.icon_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

    def tr(self, context, text):
        return QCoreApplication.translate(context, text)

# --- 이하 코드는 제공해주신 원본과 동일하게 유지 ---

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("settingsPage")
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setObjectName("settingsScrollArea")
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(25, 20, 25, 20)
        self.content_layout.setSpacing(15)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.content_widget)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.scroll_area)
    def add_widget(self, widget): self.content_layout.addWidget(widget)
    def add_layout(self, layout): self.content_layout.addLayout(layout)

class TitleLabel(QLabel):
    def __init__(self, text=""):
        super().__init__(self.tr("TitleLabel", text))
        self.setObjectName("titleLabel")
    def tr(self, context, text): return QCoreApplication.translate(context, text)

class DescriptionLabel(QLabel):
    def __init__(self, text=""):
        super().__init__(self.tr("DescriptionLabel", text))
        self.setObjectName("descriptionLabel")
        self.setWordWrap(True)
    def tr(self, context, text): return QCoreApplication.translate(context, text)

class SettingsCard(QFrame):
    def __init__(self, title="", description=None):
        super().__init__()
        self.setObjectName("settingsCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 15, 20, 15)
        self.layout.setSpacing(10)
        self.title_label = QLabel(self.tr("SettingsCard", title))
        self.title_label.setObjectName("cardTitleLabel")
        self.layout.addWidget(self.title_label)
        if description:
            self.desc_label = DescriptionLabel(self.tr("SettingsCard", description))
            self.desc_label.setObjectName("cardDescriptionLabel")
            self.layout.addWidget(self.desc_label)
        else: self.desc_label = None
    def add_widget(self, widget): self.layout.addWidget(widget)
    def add_layout(self, layout): self.layout.addLayout(layout)
    def tr(self, context, text): return QCoreApplication.translate(context, text)