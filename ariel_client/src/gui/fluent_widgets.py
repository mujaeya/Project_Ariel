import os
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QColor

# [수정] 누락되었던 resource_path 임포트 추가
from ..utils import resource_path

# --- 탐색 메뉴 아이템 위젯 ---
class NavigationItemWidget(QWidget):
    """왼쪽 탐색 메뉴에 들어갈 아이콘과 텍스트 라벨 위젯"""
    def __init__(self, icon_path, text):
        super().__init__()
        # icon_path는 setup_window에서 이미 resource_path로 처리되어 넘어오므로 중복 호출 방지
        self.icon_path = icon_path 
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 10, 15, 10)
        self.layout.setSpacing(15)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(22, 22)
        
        self.text_label = QLabel(text)
        self.text_label.setObjectName("navigationItemLabel") # CSS 적용을 위해 ObjectName 추가
        
        self.layout.addWidget(self.icon_label)
        self.layout.addWidget(self.text_label)
        # self.layout.addStretch() # 텍스트가 왼쪽 정렬되도록 Stretch 제거

        self.set_icon_color("#AAAAAA") # 기본 비활성 아이콘 색상

    def set_icon_color(self, color):
        """SVG 아이콘의 색상을 변경하여 적용합니다."""
        if not os.path.exists(self.icon_path):
            logging.warning(f"아이콘 파일을 찾을 수 없습니다: {self.icon_path}")
            self.icon_label.setPixmap(QPixmap()) # 아이콘 없음을 표시
            return

        # QPixmap으로 SVG 파일을 직접 로드할 수 있습니다.
        pixmap = QPixmap(self.icon_path)
        if pixmap.isNull():
            logging.error(f"아이콘 파일 로드에 실패했습니다: {self.icon_path}")
            return

        painter = QPainter(pixmap)
        # [수정] 잘못된 상수 QPainter.CompositionMode.SourceIn -> 올바른 상수 QPainter.CompositionMode_SourceIn
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
        painter.end()
        self.icon_label.setPixmap(pixmap.scaled(
            self.icon_label.size(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        ))


# --- 설정 페이지의 기본 프레임 ---
class SettingsPage(QWidget):
    """각 설정 카테고리의 기반이 되는 스크롤 가능한 페이지 위젯"""
    def __init__(self):
        super().__init__()
        self.setObjectName("settingsPage")
        
        # 스크롤 기능 추가
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setObjectName("settingsScrollArea") # CSS 적용을 위함

        # 스크롤될 실제 콘텐츠 위젯
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(25, 20, 25, 20)
        self.content_layout.setSpacing(15)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.content_widget)
        
        # 메인 레이아웃 설정
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
        super().__init__(text)
        self.setObjectName("titleLabel")


# --- 설명 텍스트 라벨 ---
class DescriptionLabel(QLabel):
    """설정 항목에 대한 설명"""
    def __init__(self, text):
        super().__init__(text)
        self.setObjectName("descriptionLabel")
        self.setWordWrap(True)


# --- 설정 카드 위젯 ---
class SettingsCard(QFrame):
    """하나의 설정 그룹을 묶는 카드 위젯"""
    def __init__(self, title, description=None):
        super().__init__()
        self.setObjectName("settingsCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 15, 20, 15)
        self.layout.setSpacing(10)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitleLabel") # CSS 적용을 위함
        self.layout.addWidget(self.title_label)

        if description:
            self.desc_label = DescriptionLabel(description)
            self.desc_label.setObjectName("cardDescriptionLabel") # CSS 적용을 위함
            self.layout.addWidget(self.desc_label)

    def add_widget(self, widget):
        self.layout.addWidget(widget)

    def add_layout(self, layout):
        self.layout.addLayout(layout)