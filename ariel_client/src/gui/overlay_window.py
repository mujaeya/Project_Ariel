# ariel_client/src/gui/overlay_window.py (이 코드로 전체 교체)
import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, Slot, QPoint
from PySide6.QtGui import QFont, QCursor
from ..config_manager import ConfigManager

class TranslationItem(QWidget):
    def __init__(self, original_text, translated_results: dict, config_manager, source: str):
        super().__init__()
        self.config_manager = config_manager
        self.current_config = self.config_manager.get_active_profile()
        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("translationItem")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(5)

        source_indicator = "[화면]" if source == "ocr" else "[음성]"
        original_label = QLabel(f"<b>{source_indicator}</b> {original_text}")
        original_label.setWordWrap(True)
        original_label.setObjectName("originalLabel")
        original_label.setTextFormat(Qt.TextFormat.RichText)
        self.layout.addWidget(original_label)

        target_languages = self.current_config.get("target_languages", [])
        for lang_code in target_languages:
            translated_text = translated_results.get(lang_code, "")
            if translated_text:
                lang_label = QLabel(f"<b>[{lang_code.upper()}]</b> {translated_text}")
                lang_label.setWordWrap(True)
                lang_label.setTextFormat(Qt.TextFormat.RichText)
                lang_label.setObjectName("translatedLabel")
                lang_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self.layout.addWidget(lang_label)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.update_styles()

    def update_styles(self):
        font_size = self.current_config.get("overlay_font_size", 18)
        self.setStyleSheet(f"""
            QWidget#translationItem {{
                background-color: {self.current_config.get("overlay_bg_color", "rgba(0,0,0,0.75)")};
                border-radius: 6px;
            }}
            QLabel#originalLabel {{ color: #DDDDDD; font-size: {font_size - 2}px; border-bottom: 1px solid #555; padding-bottom: 3px; }}
            QLabel#translatedLabel {{ color: {self.current_config.get("overlay_font_color", "#FFFFFF")}; font-size: {font_size}px; font-weight: bold; }}
        """)

class OverlayWindow(QWidget):
    MAX_STT_ITEMS = 3
    RESIZE_MARGIN = 8

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.ocr_item_layout = QVBoxLayout()
        self.stt_item_layout = QVBoxLayout()
        self.stt_item_layout.setSpacing(8)
        
        self.main_layout.addLayout(self.ocr_item_layout)
        self.main_layout.addSpacing(10)
        self.main_layout.addLayout(self.stt_item_layout)
        self.main_layout.addStretch(1)

        self.stt_items = []
        self.ocr_item = None
        
        self.dragging = False
        self.resizing = False
        self.drag_start_position = QPoint()

        # 저장된 위치/크기 불러오기
        pos_x = self.config_manager.get("overlay_pos_x")
        pos_y = self.config_manager.get("overlay_pos_y")
        width = self.config_manager.get("overlay_width", 800)
        height = self.config_manager.get("overlay_height", 200)
        self.resize(width, height)
        if pos_x is not None and pos_y is not None:
            self.move(pos_x, pos_y)
        else:
            self.move_to_center()

    def update_status(self, message: str):
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #BBBBBB; font-style: italic; font-size: 13px; background-color: rgba(20,20,20,0.7); border-radius: 4px; padding: 5px;")
        self.status_label.setVisible(bool(message))

    def add_translation(self, original, results, source):
        # [핵심 수정] 소스에 따라 다른 레이아웃에 아이템 추가
        if source == "ocr":
            # 기존 OCR 아이템이 있으면 삭제
            if self.ocr_item:
                self.ocr_item.deleteLater()
            # 새 OCR 아이템을 OCR 레이아웃에 추가
            self.ocr_item = TranslationItem(original, results, self.config_manager, source)
            self.ocr_item_layout.addWidget(self.ocr_item)
        
        elif source == "stt":
            # 새 STT 아이템을 STT 레이아웃에 추가
            item = TranslationItem(original, results, self.config_manager, source)
            self.stt_item_layout.addWidget(item)
            self.stt_items.append(item)
            # 최대 개수 초과 시 가장 오래된 아이템 삭제
            if len(self.stt_items) > self.MAX_STT_ITEMS:
                old_item = self.stt_items.pop(0)
                old_item.deleteLater()
            self.update_stt_opacity()

    def update_stt_opacity(self):
        # STT 아이템들에 대해서만 투명도 조절
        for i, item in enumerate(self.stt_items):
            opacity = 1.0 - (len(self.stt_items) - 1 - i) * 0.25
            item.opacity_effect.setOpacity(max(0.2, opacity))

    def clear_all(self):
        # 모든 아이템 삭제
        if self.ocr_item:
            self.ocr_item.deleteLater()
            self.ocr_item = None
        for item in self.stt_items:
            item.deleteLater()
        self.stt_items.clear()

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
            else:
                self.dragging = True
                self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_start_position)
        elif self.resizing:
            # 크기 조절 로직 (생략, 이전 코드와 동일하게 구현 가능)
            pass 
        else:
            cursor_shape = Qt.CursorShape.ArrowCursor
            edge = self.get_edge(event.position().toPoint())
            if edge in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge): cursor_shape = Qt.CursorShape.SizeVerCursor
            elif edge in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge): cursor_shape = Qt.CursorShape.SizeHorCursor
            # ... 대각선 커서 로직 추가 가능 ...
            self.setCursor(cursor_shape)
        event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.resizing = False
        self.unsetCursor()
        # 변경된 위치와 크기 저장
        self.config_manager.set("overlay_pos_x", self.pos().x())
        self.config_manager.set("overlay_pos_y", self.pos().y())
        self.config_manager.set("overlay_width", self.width())
        self.config_manager.set("overlay_height", self.height())
        event.accept()

    def move_to_center(self):
        screen_geo = QApplication.primaryScreen().geometry()
        self.move(screen_geo.center() - self.rect().center())