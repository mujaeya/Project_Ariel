import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsOpacityEffect, QSizePolicy
from PySide6.QtCore import Qt, Slot, QPoint
from PySide6.QtGui import QFont, QCursor

from config_manager import ConfigManager

class TranslationItem(QWidget):
    """번역 결과 한 줄을 표시하는 커스텀 위젯"""
    def __init__(self, original_text, translated_text, config_manager):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.config_manager = config_manager
        
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 2, 0, 2)
        self.layout.setSpacing(0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.translated_label = QLabel(translated_text)
        self.original_label = QLabel(original_text)

        for label in [self.translated_label, self.original_label]:
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.translated_label.setTextFormat(Qt.TextFormat.RichText)
        
        self.layout.addWidget(self.translated_label)
        self.layout.addWidget(self.original_label)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.update_styles()

    def update_styles(self):
        font_family = self.config_manager.get("overlay_font_family", "Malgun Gothic")
        font_size = self.config_manager.get("overlay_font_size", 18)
        font_color = self.config_manager.get("overlay_font_color", "#FFFFFF")
        bg_color = self.config_manager.get("overlay_bg_color", "rgba(0, 0, 0, 160)")
        show_original = self.config_manager.get("show_original_text", True)
        original_font_size_offset = self.config_manager.get("original_text_font_size_offset", -4)
        original_font_color = self.config_manager.get("original_text_font_color", "#BBBBBB")
        
        source_langs = self.config_manager.get("source_languages", ["en-US"])
        source_lang_code = source_langs[0].split('-')[0] if source_langs else "en"
        rtl_languages = ['ar', 'he', 'fa']
        alignment = Qt.AlignmentFlag.AlignRight if source_lang_code in rtl_languages else Qt.AlignmentFlag.AlignLeft
        
        t_font = QFont(font_family, font_size); t_font.setBold(True)
        self.translated_label.setFont(t_font)
        self.translated_label.setStyleSheet(f"color: {font_color}; background-color: {bg_color}; border-radius: 5px; padding: 8px;")
        self.translated_label.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        
        o_font = QFont(font_family, font_size + original_font_size_offset)
        self.original_label.setFont(o_font)
        self.original_label.setStyleSheet(f"color: {original_font_color}; background-color: transparent; padding: 2px 8px 5px;")
        self.original_label.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        self.original_label.setVisible(show_original)
        self.updateGeometry()

class OverlayWindow(QWidget):
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
        self.status_layout.addStretch(1)
        self.status_label = QLabel()
        self.status_layout.addWidget(self.status_label)
        
        self.translation_items = []
        
        self.update_styles()
        self.resize(800, 100)
        self._center_on_screen()

        self.dragging = False
        self.resizing = False
        self.drag_start_position = QPoint()
        self.resize_edge = 0

    def get_edge(self, pos: QPoint):
        edge = 0
        if pos.x() < self.RESIZE_MARGIN: edge |= Qt.LeftEdge.value
        if pos.x() > self.width() - self.RESIZE_MARGIN: edge |= Qt.RightEdge.value
        if pos.y() < self.RESIZE_MARGIN: edge |= Qt.TopEdge.value
        if pos.y() > self.height() - self.RESIZE_MARGIN: edge |= Qt.BottomEdge.value
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
        if self.resizing:
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            geom = self.geometry()
            if self.resize_edge & Qt.LeftEdge.value: geom.setLeft(self.resize_start_geometry.left() + delta.x())
            if self.resize_edge & Qt.RightEdge.value: geom.setRight(self.resize_start_geometry.right() + delta.x())
            if self.resize_edge & Qt.TopEdge.value: geom.setTop(self.resize_start_geometry.top() + delta.y())
            if self.resize_edge & Qt.BottomEdge.value: geom.setBottom(self.resize_start_geometry.bottom() + delta.y())
            if geom.width() < self.minimumWidth() or geom.height() < self.minimumHeight(): return
            self.setGeometry(geom)
        elif self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_start_position)
        else:
            edge = self.get_edge(event.position().toPoint())
            if (edge == (Qt.LeftEdge.value | Qt.TopEdge.value)) or (edge == (Qt.RightEdge.value | Qt.BottomEdge.value)): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (edge == (Qt.RightEdge.value | Qt.TopEdge.value)) or (edge == (Qt.LeftEdge.value | Qt.BottomEdge.value)): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif (edge == Qt.LeftEdge.value) or (edge == Qt.RightEdge.value): self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif (edge == Qt.TopEdge.value) or (edge == Qt.BottomEdge.value): self.setCursor(Qt.CursorShape.SizeVerCursor)
            else: self.unsetCursor()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.dragging or self.resizing:
            geom = self.geometry()
            geometry_list = [geom.x(), geom.y(), geom.width(), geom.height()]
            self.config_manager.set("overlay_geometry", geometry_list)

        self.dragging = False
        self.resizing = False
        self.unsetCursor()
        event.accept()

    def update_styles(self):
        font = QFont(self.config_manager.get("overlay_font_family", "Malgun Gothic"), self.config_manager.get("status_font_size", 10)); font.setItalic(True)
        color = self.config_manager.get("status_font_color", "#CCCCCC")
        self.status_label.setFont(font)
        self.status_label.setStyleSheet(f"color: {color}; background-color: rgba(0,0,0,120); padding: 3px; border-radius: 3px;")
        for item in self.translation_items: item.update_styles()

    def _center_on_screen(self):
        screen = self.screen()
        if screen: self.move((screen.geometry().width() - self.width()) // 2, 50)

    @Slot(str, str)
    def add_translation(self, original, translated):
        if not translated: return
        
        item = TranslationItem(original, translated, self.config_manager)
        
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
            self.main_layout.addLayout(self.status_layout)