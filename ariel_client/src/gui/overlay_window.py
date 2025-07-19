# ariel_client/src/gui/overlay_window.py (이 코드로 전체 교체)
import logging
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QMenu
from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QCursor, QGuiApplication, QAction, QColor

from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)

class OcrPatchWindow(QWidget):
    def __init__(self, patch_info: dict, style_config: dict):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(patch_info["rect"])
        bg_color = QColor(style_config.get("background_color", "#141414")); bg_color.setAlpha(255)
        self.label = QLabel(patch_info["translated"], self); self.label.setWordWrap(True); self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self); layout.setContentsMargins(2, 2, 2, 2); layout.addWidget(self.label)
        self.setStyleSheet(f"""
            OcrPatchWindow {{ background-color: {bg_color.name()}; border: 1px solid #111; }}
            QLabel {{ background-color: transparent; color: {style_config.get("font_color", "#FFFFFF")}; font-size: {style_config.get("font_size", 16)}pt; font-weight: bold; border: none; }}
        """)
        QTimer.singleShot(4000, self.close)

class TranslationItem(QWidget):
    def __init__(self, original_text: str, translated_text, source: str, style_config: dict):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.original_text = str(original_text); self.translated_text = str(translated_text)
        layout = QVBoxLayout(self); layout.setContentsMargins(10, 8, 10, 8); layout.setSpacing(4)
        label_text = f"<b>{self.translated_text}</b>" if source == "system" else self.format_stt_text(style_config)
        label = QLabel(label_text); label.setWordWrap(True); label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(label)
        self.setStyleSheet(f"""
            background-color: {style_config.get("background_color", "rgba(20, 20, 20, 0.8)")};
            color: {style_config.get("font_color", "#FFFFFF")}; font-family: {style_config.get("font_family", "Malgun Gothic")};
            font-size: {style_config.get("font_size", 14)}pt; border-radius: 6px;
        """)

    def format_stt_text(self, style_config: dict) -> str:
        text = ""
        if style_config.get("show_original_text", True):
            offset = style_config.get("original_text_font_size_offset", -2)
            # [수정] 원문 텍스트 스타일에도 font-family를 추가하여 폰트 통일
            font_family = style_config.get('font_family', 'Malgun Gothic')
            orig_style = f'font-family: {font_family}; font-size: {style_config.get("font_size", 14) + offset}pt; color: {style_config.get("original_text_font_color", "#BBBBBB")};'
            text += f'<div style="{orig_style}">{self.original_text}</div>'
        text += self.translated_text
        return text

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self.original_text:
            menu.addAction("Copy Original").triggered.connect(lambda: QApplication.clipboard().setText(self.original_text))
            menu.addAction("Copy Translated").triggered.connect(lambda: QApplication.clipboard().setText(self.translated_text))
            menu.exec(event.globalPos())

class OverlayWindow(QWidget):
    RESIZE_MARGIN = 10
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent); self.config_manager = config_manager
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.style_config = self.config_manager.get("stt_overlay_style", {})
        pos_x, pos_y = self.config_manager.get("overlay_pos_x"), self.config_manager.get("overlay_pos_y")
        width, height = self.config_manager.get("overlay_width", 800), self.config_manager.get("overlay_height", 250)
        if pos_x is None or pos_y is None:
            rect = QGuiApplication.primaryScreen().availableGeometry()
            pos_x, pos_y = rect.center().x() - width / 2, rect.bottom() - height - 50
        self.setGeometry(int(pos_x), int(pos_y), width, height)
        self.main_layout = QVBoxLayout(self); self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8); self.main_layout.addStretch(1)
        self.setMouseTracking(True); self.items = []; self.dragging = False; self.resizing = False
        self.drag_start_position = QPoint(); self.resize_edge = Qt.Edges()

    def add_stt_message(self, original: str, translated: str, is_system: bool = False):
        item = TranslationItem(original, translated, "system" if is_system else "stt", self.style_config)
        self.main_layout.insertWidget(self.main_layout.count() - 1, item); self.items.append(item)
        max_messages = self.style_config.get("max_messages", 3)
        if len(self.items) > max_messages:
            old_item = self.items.pop(0); self.main_layout.removeWidget(old_item); old_item.deleteLater()
            
    def clear_stt_messages(self):
        while self.items: item = self.items.pop(0); self.main_layout.removeWidget(item); item.deleteLater()
    
    def mousePressEvent(self, event):
        if not self.style_config.get("is_draggable", True) or event.button() != Qt.MouseButton.LeftButton: return
        self.resize_edge = self.get_edge(event.position().toPoint())
        if self.resize_edge != Qt.Edges(): self.resizing = True; self.resize_start_geometry = self.geometry(); self.resize_start_global_pos = event.globalPosition().toPoint()
        else: self.dragging = True; self.drag_start_position = event.globalPosition()

    def mouseMoveEvent(self, event):
        if not self.style_config.get("is_draggable", True): return
        if self.dragging: self.move(self.pos() + (event.globalPosition() - self.drag_start_position).toPoint()); self.drag_start_position = event.globalPosition()
        elif self.resizing:
            new_rect = QRect(self.resize_start_geometry); delta = event.globalPosition().toPoint() - self.resize_start_global_pos
            if self.resize_edge & Qt.Edge.LeftEdge: new_rect.setLeft(self.resize_start_geometry.left() + delta.x())
            if self.resize_edge & Qt.Edge.RightEdge: new_rect.setRight(self.resize_start_geometry.right() + delta.x())
            if self.resize_edge & Qt.Edge.TopEdge: new_rect.setTop(self.resize_start_geometry.top() + delta.y())
            if self.resize_edge & Qt.Edge.BottomEdge: new_rect.setBottom(self.resize_start_geometry.bottom() + delta.y())
            if new_rect.width() > self.minimumWidth() and new_rect.height() > self.minimumHeight(): self.setGeometry(new_rect)
        else: self.update_cursor(event.position().toPoint())
    
    def mouseReleaseEvent(self, event):
        if self.dragging or self.resizing:
            self.dragging = self.resizing = False; self.unsetCursor(); geom = self.geometry()
            self.config_manager.set("overlay_pos_x", geom.x()); self.config_manager.set("overlay_pos_y", geom.y())
            self.config_manager.set("overlay_width", geom.width()); self.config_manager.set("overlay_height", geom.height())

    def update_cursor(self, pos: QPoint):
        edge = self.get_edge(pos)
        if (edge & Qt.Edge.TopEdge and edge & Qt.Edge.LeftEdge) or (edge & Qt.Edge.BottomEdge and edge & Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif (edge & Qt.Edge.TopEdge and edge & Qt.Edge.RightEdge) or (edge & Qt.Edge.BottomEdge and edge & Qt.Edge.LeftEdge): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge): self.setCursor(Qt.CursorShape.SizeVerCursor)
        else: self.unsetCursor()

    def get_edge(self, pos: QPoint) -> Qt.Edges:
        edge = Qt.Edges(); m = self.RESIZE_MARGIN
        if pos.x() < m: edge |= Qt.Edge.LeftEdge
        if pos.x() > self.width() - m: edge |= Qt.Edge.RightEdge
        if pos.y() < m: edge |= Qt.Edge.TopEdge
        if pos.y() > self.height() - m: edge |= Qt.Edge.BottomEdge
        return edge

    def closeEvent(self, event):
        geom = self.geometry()
        self.config_manager.set("overlay_pos_x", geom.x()); self.config_manager.set("overlay_pos_y", geom.y())
        self.config_manager.set("overlay_width", geom.width()); self.config_manager.set("overlay_height", geom.height())
        super().closeEvent(event)