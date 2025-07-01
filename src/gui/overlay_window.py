# src/gui/overlay_window.py (동적 레이아웃 적용 버전)
import sys
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QGraphicsOpacityEffect, QSizePolicy, QPushButton)
from PySide6.QtCore import Qt, Slot, QPoint
from PySide6.QtGui import QFont, QCursor, QColor

from config_manager import ConfigManager

class TranslationItem(QWidget):
    """
    다중 번역(최대 2개)을 지원하는 동적 레이아웃의 번역 결과 위젯.
    """
    def __init__(self, original_text, translated_results: dict, config_manager, temp_config=None):
        super().__init__()
        self.config_manager = config_manager
        self.current_config = temp_config if temp_config is not None else self.config_manager.get_active_profile()

        self.original_text = original_text
        self.translated_results = translated_results
        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("translationItem")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # --- 레이아웃 생성 ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(4)
        
        # <<<<<<< 핵심 수정: 번역 결과에 따라 동적으로 라벨 생성 >>>>>>>>>
        target_languages = self.current_config.get("target_languages", [])
        
        # 1. 첫 번째 번역 라벨 (항상 존재)
        lang1_code = target_languages[0] if target_languages else ""
        lang1_text = self.translated_results.get(lang1_code, "")
        self.translation_label_1 = self.create_translation_label(lang1_code, lang1_text)
        self.main_layout.addWidget(self.translation_label_1)

        # 2. 두 번째 번역 라벨 (조건부 생성)
        self.translation_label_2 = None
        if len(target_languages) > 1:
            lang2_code = target_languages[1]
            lang2_text = self.translated_results.get(lang2_code, "")
            self.translation_label_2 = self.create_translation_label(lang2_code, lang2_text)
            self.main_layout.addWidget(self.translation_label_2)

        # 3. 원본 텍스트 라벨 (조건부 생성)
        show_original = self.current_config.get("show_original_text", True)
        if len(target_languages) < 2 and show_original:
            self.original_label = QLabel(self.original_text)
            self.original_label.setWordWrap(True)
            self.original_label.setObjectName("original_label")
            self.main_layout.addWidget(self.original_label)
        else:
            self.original_label = None

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.update_styles()

    def create_translation_label(self, lang_code, text):
        """번역 언어 라벨과 복사 버튼이 포함된 위젯을 생성합니다."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label_text = f"<b>[{lang_code.upper()}]</b> {text}"
        label = QLabel(label_text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setObjectName("translated_label")

        copy_button = QPushButton("📋")
        copy_button.setFixedSize(20, 20)
        copy_button.setToolTip(f"{text} 복사")
        copy_button.clicked.connect(lambda: self.copy_to_clipboard(text))

        layout.addWidget(label, 1)
        layout.addWidget(copy_button)
        return container

    def copy_to_clipboard(self, text_to_copy):
        try:
            import pyperclip
            pyperclip.copy(text_to_copy)
            print(f"클립보드에 복사됨: {text_to_copy}")
        except Exception as e:
            print(f"클립보드 복사 중 오류 발생: {e}")

    def update_styles(self):
        font_size = self.current_config.get("overlay_font_size", 18)
        original_font_size_offset = self.current_config.get("original_text_font_size_offset", -4)
        
        # 스타일시트는 CSS 선택자를 통해 일괄 적용
        self.setStyleSheet(f"""
            QWidget#translationItem {{
                background-color: {self.current_config.get("overlay_bg_color", "rgba(0,0,0,160)")};
                border-radius: 5px;
            }}
            QLabel#translated_label {{
                color: {self.current_config.get("overlay_font_color", "#FFFFFF")};
                font-family: "{self.current_config.get("overlay_font_family", "Malgun Gothic")}";
                font-size: {font_size}px;
            }}
            QLabel#original_label {{
                color: {self.current_config.get("original_text_font_color", "#BBBBBB")};
                font-family: "{self.current_config.get("overlay_font_family", "Malgun Gothic")}";
                font-size: {font_size + original_font_size_offset}px;
                padding-top: 2px;
            }}
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 3px;
            }}
        """)
        self.updateGeometry()


class OverlayWindow(QWidget):
    # ... (OverlayWindow의 나머지 코드는 이전 버전과 동일) ...
    MAX_ITEMS = 3
    RESIZE_MARGIN = 8

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(self.RESIZE_MARGIN, self.RESIZE_MARGIN, self.RESIZE_MARGIN, self.RESIZE_MARGIN)
        self.main_layout.setSpacing(4)
        
        self.status_layout = QHBoxLayout()
        self.status_layout.setContentsMargins(0, 0, 0, 0)
        self.status_layout.addStretch(1)
        self.status_label = QLabel()
        self.status_layout.addWidget(self.status_label)
        
        self.translation_items = []
        self.main_layout.addStretch(1)
        self.update_styles()
        
        self.dragging = False
        self.resizing = False
        self.drag_start_position = QPoint()
        self.resize_edge = 0

    def get_edge(self, pos: QPoint):
        edge = 0
        if pos.x() < self.RESIZE_MARGIN: edge |= Qt.Edge.LeftEdge
        if pos.x() > self.width() - self.RESIZE_MARGIN: edge |= Qt.Edge.RightEdge
        if pos.y() < self.RESIZE_MARGIN: edge |= Qt.Edge.TopEdge
        if pos.y() > self.height() - self.RESIZE_MARGIN: edge |= Qt.Edge.BottomEdge
        return edge

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.resize_edge = self.get_edge(event.position().toPoint())
            if self.resize_edge != 0:
                self.resizing = True
                self.resize_start_geometry = self.geometry()
                self.resize_start_pos = event.globalPosition().toPoint()
            else:
                self.dragging = True
                self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self.resizing:
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            geom = self.geometry()
            if self.resize_edge & Qt.Edge.LeftEdge: geom.setLeft(self.resize_start_geometry.left() + delta.x())
            if self.resize_edge & Qt.Edge.RightEdge: geom.setRight(self.resize_start_geometry.right() + delta.x())
            if self.resize_edge & Qt.Edge.TopEdge: geom.setTop(self.resize_start_geometry.top() + delta.y())
            if self.resize_edge & Qt.Edge.BottomEdge: geom.setBottom(self.resize_start_geometry.bottom() + delta.y())
            if geom.width() < self.minimumWidth() or geom.height() < self.minimumHeight(): return
            self.setGeometry(geom)
        elif self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_start_position)
        else:
            edge = self.get_edge(pos)
            if (edge == (Qt.Edge.LeftEdge | Qt.Edge.TopEdge)) or (edge == (Qt.Edge.RightEdge | Qt.Edge.BottomEdge)): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (edge == (Qt.Edge.RightEdge | Qt.Edge.TopEdge)) or (edge == (Qt.Edge.LeftEdge | Qt.Edge.BottomEdge)): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif (edge == Qt.Edge.LeftEdge) or (edge == Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif (edge == Qt.Edge.TopEdge) or (edge == Qt.Edge.BottomEdge): self.setCursor(Qt.CursorShape.SizeVerCursor)
            else: self.unsetCursor()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.resizing or self.dragging:
            self.config_manager.set("overlay_pos_x", self.pos().x())
            self.config_manager.set("overlay_pos_y", self.pos().y())
            self.config_manager.set("overlay_width", self.width())
            self.config_manager.set("overlay_height", self.height())
            
        self.dragging = False
        self.resizing = False
        self.unsetCursor()
        event.accept()

    def update_styles(self):
        font = QFont(self.config_manager.get("overlay_font_family", "Malgun Gothic"), 10)
        font.setItalic(True)
        color = self.config_manager.get("status_font_color", "#CCCCCC")
        self.status_label.setFont(font)
        self.status_label.setStyleSheet(f"color: {color}; background-color: rgba(0,0,0,120); padding: 3px; border-radius: 3px;")
        for item in self.translation_items: item.update_styles()

    def move_to_center_of_primary_screen(self):
        primary_screen = QApplication.primaryScreen()
        if not primary_screen:
            print("주 모니터를 찾을 수 없습니다.")
            return
        screen_geometry = primary_screen.geometry()
        target_x = screen_geometry.x() + (screen_geometry.width() - self.width()) // 2
        target_y = screen_geometry.y() + 50
        self.move(target_x, target_y)

    # <<<<<<< 핵심 수정: 받는 데이터 형식에 맞춰 add_translation 수정 >>>>>>>>>
    @Slot(str, dict)
    def add_translation(self, original, translated_results):
        if not translated_results: return
        
        item = TranslationItem(original, translated_results, self.config_manager)
        self.main_layout.insertWidget(0, item)
        self.translation_items.insert(0, item)
        
        if len(self.translation_items) > self.MAX_ITEMS:
            old_item = self.translation_items.pop()
            self.main_layout.removeWidget(old_item); old_item.deleteLater()
            
        self._update_item_opacities()
        self.update_status("번역 대기 중...")

    def _update_item_opacities(self):
        for i, item in enumerate(self.translation_items):
            opacity = 1.0 - (i * 0.15)
            if hasattr(item, 'opacity_effect'): item.opacity_effect.setOpacity(opacity)

    @Slot(str)
    def update_status(self, message: str):
        if self.status_layout.parent():
            self.main_layout.removeItem(self.status_layout)
        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))
        if message:
            self.main_layout.insertLayout(self.main_layout.count() - 1, self.status_layout)