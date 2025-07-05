# F:/projects/Project_Ariel/ariel_client/src/gui/overlay_window.py (최종 완성본)
import logging
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QCursor

logger = logging.getLogger(__name__)

class TranslationItem(QWidget):
    def __init__(self, original_text: str, translated_text: str, source: str, style_config: dict):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(4)
        if source == "system":
            label_text = f"<b>{translated_text}</b>"
        else:
            label_text = f"<b>[음성]</b> {original_text}<br>{translated_text}"
        label = QLabel(label_text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        self.layout.addWidget(label)
        self.setGraphicsEffect(QGraphicsOpacityEffect(self))
        self.setStyleSheet(f"""
            background-color: {style_config.get("background_color", "rgba(20, 20, 20, 0.8)")};
            color: {style_config.get("font_color", "#ffffff")};
            font-size: 14pt;
            border-radius: 6px;
        """)

class OcrPatch(QLabel):
    def __init__(self, text: str, geometry: QRect, parent: QWidget, style_config: dict):
        super().__init__(text, parent)
        self.setGeometry(geometry)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            background-color: {style_config.get("background_color", "#ffffff")};
            color: {style_config.get("font_color", "#000000")};
            font-size: {style_config.get("font_size", 16)}pt;
            font-weight: bold; border: 1px solid #333; padding: 2px;
        """)
        self.show()

class OverlayWindow(QWidget):
    RESIZE_MARGIN = 10
    def __init__(self, mode: str, style_config: dict, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.style_config = style_config
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        if self.mode == 'stt':
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(10, 10, 10, 10)
            self.main_layout.setSpacing(8)
            self.main_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
            self.setMouseTracking(True)
            self.items = []
            self.dragging, self.resizing = False, False
        else: # 'ocr'
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.patches = []
            self.fade_out_timer = QTimer(self)
            self.fade_out_timer.setSingleShot(True)
            self.fade_out_timer.timeout.connect(self.hide_patches)

    def add_stt_message(self, original: str, translated: str, is_system: bool = False):
        item = TranslationItem(original, translated, "system" if is_system else "stt", self.style_config)
        self.main_layout.addWidget(item)
        self.items.insert(0, item)
        if len(self.items) > self.style_config.get("max_messages", 3): self.items.pop().deleteLater()
        for i, item in enumerate(self.items):
            item.graphicsEffect().setOpacity(max(0.15, 1.0 - (i * 0.35)))
    
    def clear_stt_messages(self):
        while self.items: self.items.pop().deleteLater()

    def update_ocr_patches(self, patches_data: list):
        self.hide_patches()
        if patches_data:
            parent_rect = QRect()
            for _, rect in patches_data: parent_rect = parent_rect.united(rect)
            self.setGeometry(parent_rect)
            for text, rect in patches_data:
                relative_rect = rect.translated(-parent_rect.topLeft())
                self.patches.append(OcrPatch(text, relative_rect, self, self.style_config))
            self.show()
            self.fade_out_timer.start(self.style_config.get("display_duration_ms", 4000))

    def hide_patches(self):
        while self.patches: self.patches.pop().deleteLater()
        self.hide()

    def mousePressEvent(self, event):
        if self.mode != 'stt' or event.button() != Qt.MouseButton.LeftButton: return
        self.resize_edge = self.get_edge(event.position().toPoint())
        if self.resize_edge != Qt.Edges():
            self.resizing, self.resize_start_geometry, self.resize_start_global_pos = True, self.geometry(), event.globalPosition().toPoint()
        else:
            self.dragging, self.drag_start_position = True, event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.mode != 'stt': return
        if self.dragging: self.move(event.globalPosition().toPoint() - self.drag_start_position)
        elif self.resizing:
            new_rect = QRect(self.resize_start_geometry)
            delta = event.globalPosition().toPoint() - self.resize_start_global_pos
            if self.resize_edge & Qt.Edge.LeftEdge: new_rect.setLeft(self.resize_start_geometry.left() + delta.x())
            if self.resize_edge & Qt.Edge.RightEdge: new_rect.setRight(self.resize_start_geometry.right() + delta.x())
            if self.resize_edge & Qt.Edge.TopEdge: new_rect.setTop(self.resize_start_geometry.top() + delta.y())
            if self.resize_edge & Qt.Edge.BottomEdge: new_rect.setBottom(self.resize_start_geometry.bottom() + delta.y())
            self.setGeometry(new_rect)
        else:
            edge = self.get_edge(event.position().toPoint())
            if (edge & Qt.Edge.TopEdge and edge & Qt.Edge.LeftEdge) or (edge & Qt.Edge.BottomEdge and edge & Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (edge & Qt.Edge.TopEdge and edge & Qt.Edge.RightEdge) or (edge & Qt.Edge.BottomEdge and edge & Qt.Edge.LeftEdge): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge): self.setCursor(Qt.CursorShape.SizeVerCursor)
            else: self.unsetCursor()
    
    def mouseReleaseEvent(self, event):
        if self.mode == 'stt': self.dragging = self.resizing = False

    def get_edge(self, pos: QPoint):
        edge = Qt.Edges()
        if pos.x() < self.RESIZE_MARGIN: edge |= Qt.Edge.LeftEdge
        if pos.x() > self.width() - self.RESIZE_MARGIN: edge |= Qt.Edge.RightEdge
        if pos.y() < self.RESIZE_MARGIN: edge |= Qt.Edge.TopEdge
        if pos.y() > self.height() - self.RESIZE_MARGIN: edge |= Qt.Edge.BottomEdge
        return edge