import os
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea)
from PySide6.QtCore import Qt, QSize, QCoreApplication
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon

from ..utils import resource_path

# --- 탐색 메뉴 아이템 위젯 ---
class NavigationItemWidget(QWidget):
    """왼쪽 탐색 메뉴에 들어갈 아이콘과 텍스트 라벨 위젯"""
    def __init__(self, icon_path, text):
        super().__init__()
        self.icon_path = icon_path
        
        # 1. 메인 레이아웃을 QVBoxLayout (수직)으로 설정합니다.
        # 이 레이아웃이 위젯 전체의 정렬을 담당합니다.
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # 바깥 여백은 0
        main_layout.setSpacing(0)

        # 2. 실제 콘텐츠(아이콘, 텍스트)를 담을 QHBoxLayout (수평)을 생성합니다.
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(15, 0, 15, 0) # 좌우 여백만 설정
        content_layout.setSpacing(15)

        # --- 위젯 생성 (기존과 동일) ---
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(22, 22)
        
        self.text_label = QLabel(self.tr(text))
        self.text_label.setObjectName("navigationItemLabel")
        
        # --- 콘텐츠 레이아웃에 위젯 추가 (기존과 동일) ---
        content_layout.addWidget(self.icon_label)
        content_layout.addWidget(self.text_label, 1)

        # 3. [핵심 수정] 메인 수직 레이아웃에 '위쪽 여백' -> '콘텐츠' -> '아래쪽 여백' 순으로 추가합니다.
        # addStretch(1)은 가능한 모든 공간을 차지하는 빈 공간을 만듭니다.
        main_layout.addStretch(1)
        main_layout.addLayout(content_layout) # 중앙에 콘텐츠를 배치
        main_layout.addStretch(1)

        # 초기 아이콘 로드 로직은 그대로 유지합니다.
        self.update_icon(self.icon_path)

    # set_active, update_icon, tr 메서드는 제공해주신 현황과 동일하게 유지됩니다.
    def set_active(self, is_active, active_color="#ffffff", inactive_color="#b9bbbe", active_text_color=None, inactive_text_color=None):
        """아이템의 활성 상태에 따라 아이콘과 텍스트 색상을 모두 변경합니다."""
        icon_color_to_set = active_color if is_active else inactive_color
        
        if active_text_color and inactive_text_color:
            text_color_to_set = active_text_color if is_active else inactive_text_color
            self.text_label.setStyleSheet(f"color: {text_color_to_set};")
        else:
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

    def update_icon(self, icon_path):
        """아이콘 경로를 기반으로 아이콘을 업데이트합니다."""
        if not os.path.exists(icon_path):
            logging.warning(f"아이콘 파일을 찾을 수 없습니다: {icon_path}")
            self.icon_label.setPixmap(QPixmap())
            return
        
        icon = QIcon(icon_path)
        pixmap = icon.pixmap(self.icon_label.size())
        self.icon_label.setPixmap(pixmap)

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
    """페이지 내의 섹션 제목 (예: 'API 설정')"""
    def __init__(self, text):
        super().__init__(self.tr(text))
        self.setObjectName("titleLabel")

    def tr(self, text):
        return QCoreApplication.translate("TitleLabel", text)


# --- 설명 텍스트 라벨 ---
class DescriptionLabel(QLabel):
    """설정 항목에 대한 설명"""
    def __init__(self, text):
        super().__init__(self.tr(text))
        self.setObjectName("descriptionLabel")
        self.setWordWrap(True)

    def tr(self, text):
        return QCoreApplication.translate("DescriptionLabel", text)


# --- 설정 카드 위젯 ---
class SettingsCard(QFrame):
    """하나의 설정 그룹을 묶는 카드 위젯"""
    def __init__(self, title, description=None):
        super().__init__()
        self.setObjectName("settingsCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 15, 20, 15)
        self.layout.setSpacing(10)

        self.title_label = QLabel(self.tr(title))
        self.title_label.setObjectName("cardTitleLabel")
        self.layout.addWidget(self.title_label)

        if description:
            self.desc_label = DescriptionLabel(self.tr(description))
            self.desc_label.setObjectName("cardDescriptionLabel")
            self.layout.addWidget(self.desc_label)

    def add_widget(self, widget):
        self.layout.addWidget(widget)

    def add_layout(self, layout):
        self.layout.addLayout(layout)

    def tr(self, text):
        return QCoreApplication.translate("SettingsCard", text)