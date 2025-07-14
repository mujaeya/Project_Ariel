import os
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea)
from PySide6.QtCore import Qt, QSize, QCoreApplication
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon

from ..utils import resource_path

logger = logging.getLogger(__name__)

# --- 탐색 메뉴 아이템 위젯 ---
class NavigationItemWidget(QWidget):
    """왼쪽 탐색 메뉴에 들어갈 아이콘과 텍스트 라벨 위젯"""
    def __init__(self, icon_path, text):
        super().__init__()
        self.icon_path = icon_path

        # [업데이트] 콘텐츠의 수직 중앙 정렬을 위해 QVBoxLayout과 addStretch 사용
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(15, 0, 15, 0)
        content_layout.setSpacing(15)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(22, 22)

        # [업데이트] 국제화를 위해 tr 함수 적용
        self.text_label = QLabel(self.tr(text))
        self.text_label.setObjectName("navigationItemLabel")

        content_layout.addWidget(self.icon_label)
        content_layout.addWidget(self.text_label, 1)

        main_layout.addStretch(1)
        main_layout.addLayout(content_layout)
        main_layout.addStretch(1)

        # [원본 기능 유지] 위젯 생성 시 비활성 상태로 초기화
        self.set_active(False)

    def set_active(self, is_active, active_color="#ffffff", inactive_color="#b9bbbe", active_text_color=None, inactive_text_color=None):
        """[업데이트] 아이템 활성 상태에 따라 아이콘과 텍스트 색상을 모두 변경합니다."""
        icon_color_to_set = active_color if is_active else inactive_color
        
        # [업데이트] 텍스트 색상 변경 로직 추가
        if active_text_color and inactive_text_color:
            text_color_to_set = active_text_color if is_active else inactive_text_color
            self.text_label.setStyleSheet(f"color: {text_color_to_set};")
        else:
            # QSS에서 제어할 수 있도록 스타일시트 초기화
            self.text_label.setStyleSheet("")

        if not os.path.exists(self.icon_path):
            logging.warning(f"아이콘 파일을 찾을 수 없습니다: {self.icon_path}")
            return

        pixmap = QPixmap(self.icon_path)
        if pixmap.isNull(): return

        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(icon_color_to_set))
        painter.end()
        self.icon_label.setPixmap(pixmap.scaled(
            self.icon_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

    # [업데이트] 국제화 지원을 위한 tr 메소드 추가
    def tr(self, text):
        return QCoreApplication.translate("NavigationItemWidget", text)


# --- 설정 페이지의 기본 프레임 ---
class SettingsPage(QWidget):
    """각 설정 카테고리의 기반이 되는 스크롤 가능한 페이지 위젯"""
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

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)


# --- 섹션 제목 라벨 ---
class TitleLabel(QLabel):
    """[업데이트] 페이지 내의 섹션 제목 (예: 'API 설정')"""
    def __init__(self, text=""):
        # [업데이트] 국제화를 위해 tr 함수 적용
        super().__init__(self.tr(text))
        self.setObjectName("titleLabel")

    # [업데이트] 국제화 지원을 위한 tr 메소드 추가
    def tr(self, text):
        return QCoreApplication.translate("TitleLabel", text)


# --- 설명 텍스트 라벨 ---
class DescriptionLabel(QLabel):
    """[업데이트] 설정 항목에 대한 설명"""
    def __init__(self, text=""):
        # [업데이트] 국제화를 위해 tr 함수 적용
        super().__init__(self.tr(text))
        self.setObjectName("descriptionLabel")
        self.setWordWrap(True)

    # [업데이트] 국제화 지원을 위한 tr 메소드 추가
    def tr(self, text):
        return QCoreApplication.translate("DescriptionLabel", text)


# --- 설정 카드 위젯 ---
class SettingsCard(QFrame):
    """[업데이트] 하나의 설정 그룹을 묶는 카드 위젯"""
    def __init__(self, title="", description=None):
        super().__init__()
        self.setObjectName("settingsCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 15, 20, 15)
        self.layout.setSpacing(10)

        # [업데이트] 국제화를 위해 tr 함수 적용
        self.title_label = QLabel(self.tr(title))
        self.title_label.setObjectName("cardTitleLabel")
        self.layout.addWidget(self.title_label)

        if description:
            # [업데이트] 국제화를 위해 tr 함수 적용
            self.desc_label = DescriptionLabel(self.tr(description))
            self.desc_label.setObjectName("cardDescriptionLabel")
            self.layout.addWidget(self.desc_label)
        else:
            self.desc_label = None

    def add_widget(self, widget): self.layout.addWidget(widget)
    def add_layout(self, layout): self.layout.addLayout(layout)

    # [업데이트] 국제화 지원을 위한 tr 메소드 추가
    def tr(self, text):
        return QCoreApplication.translate("SettingsCard", text)