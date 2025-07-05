# ariel_client/src/gui/overlay_window.py (이 코드로 전체 교체)
import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, Slot, QPoint, QRect
from PySide6.QtGui import QFont, QCursor, QGuiApplication, QPainter, QColor

from ..config_manager import ConfigManager

class TranslationItem(QWidget):
    """
    개별 번역 결과를 표시하는 위젯 (원본 + 번역본).
    이 위젯의 디자인과 기능은 그대로 유지됩니다.
    """
    def __init__(self, original_text, translated_results: dict, config_manager, source: str):
        super().__init__()
        self.config_manager = config_manager
        self.current_config = self.config_manager.get_active_profile()
        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("translationItem")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 10, 12, 10)
        self.layout.setSpacing(5)

        source_indicator = "[화면 텍스트]" if source == "ocr" else "[음성 인식]"
        original_label = QLabel(f"<b>{source_indicator}</b> {original_text}")
        original_label.setWordWrap(True)
        original_label.setObjectName("originalLabel")
        original_label.setTextFormat(Qt.TextFormat.RichText)
        original_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
                background-color: {self.current_config.get("overlay_bg_color", "rgba(0, 0, 0, 0.75)")};
                border-radius: 8px;
            }}
            QLabel#originalLabel {{ 
                color: #DDDDDD; 
                font-size: {font_size - 2}pt; 
                border-bottom: 1px solid #555; 
                padding-bottom: 4px; 
                margin-bottom: 4px;
            }}
            QLabel#translatedLabel {{ 
                color: {self.current_config.get("overlay_font_color", "#FFFFFF")}; 
                font-size: {font_size}pt; 
                font-weight: bold; 
            }}
        """)

class OverlayWindow(QWidget):
    MAX_STT_ITEMS = 3
    RESIZE_MARGIN = 10

    def __init__(self, config_manager: ConfigManager, overlay_type: str = 'stt'):
        super().__init__()
        self.config_manager = config_manager
        self.overlay_type = overlay_type
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)

        self.item_layout = QVBoxLayout()
        self.main_layout.addLayout(self.item_layout)
        self.main_layout.addStretch(1)

        if self.overlay_type == 'stt':
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.setMouseTracking(True)
            self.background_color = QColor(20, 20, 20, 180)
            self.stt_items = []
            self.dragging = False
            self.resizing = False
            # ❗ [오류 수정] 타입을 int(0)에서 Qt.Edges()로 변경
            self.resize_edge = Qt.Edges() 
            self.drag_start_position = QPoint()
            self.load_geometry()
        else: # 'ocr'
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.background_color = QColor(0, 0, 0, 0)
            self.ocr_item = None

    def paintEvent(self, event):
        if self.overlay_type == 'stt':
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), self.background_color)

    def load_geometry(self):
        if self.overlay_type == 'stt':
            pos_x = self.config_manager.get("stt_overlay_pos_x")
            pos_y = self.config_manager.get("stt_overlay_pos_y")
            width = self.config_manager.get("stt_overlay_width", 600)
            height = self.config_manager.get("stt_overlay_height", 200)
            
            self.resize(width, height)
            
            if pos_x is not None and pos_y is not None:
                self.move(pos_x, pos_y)
            else:
                if QGuiApplication.primaryScreen():
                    screen_geo = QGuiApplication.primaryScreen().geometry()
                    self.move(screen_geo.center() - self.rect().center())

    @Slot(str, dict, str)
    def add_translation(self, original, results, source):
        if self.overlay_type != source:
            return

        if source == "ocr":
            if self.ocr_item: self.ocr_item.deleteLater()
            self.ocr_item = TranslationItem(original, results, self.config_manager, source)
            self.item_layout.addWidget(self.ocr_item)
            self.adjustSize()
        
        elif source == "stt":
            item = TranslationItem(original, results, self.config_manager, source)
            self.item_layout.insertWidget(0, item)
            self.stt_items.insert(0, item)

            if len(self.stt_items) > self.MAX_STT_ITEMS:
                old_item = self.stt_items.pop()
                old_item.deleteLater()
            self.update_stt_opacity()

    def update_stt_opacity(self):
        for i, item in enumerate(self.stt_items):
            opacity = 1.0 - (i * 0.3)
            item.opacity_effect.setOpacity(max(0.2, opacity))

    def clear_all(self):
        if self.overlay_type == 'ocr' and self.ocr_item:
            self.ocr_item.deleteLater()
            self.ocr_item = None
        elif self.overlay_type == 'stt':
            for item in self.stt_items:
                item.deleteLater()
            self.stt_items.clear()
        if self.layout() is not None:
             self.adjustSize()

    # --- 마우스 이벤트 핸들러 (STT 창 전용) ---
    def get_edge(self, pos: QPoint) -> Qt.Edges:
        # ❗ [오류 수정] 반환 타입을 명시하고, 초기값을 Qt.Edges()로 설정
        edge = Qt.Edges()
        if pos.x() < self.RESIZE_MARGIN: edge |= Qt.Edge.LeftEdge
        if pos.x() > self.width() - self.RESIZE_MARGIN: edge |= Qt.Edge.RightEdge
        if pos.y() < self.RESIZE_MARGIN: edge |= Qt.Edge.TopEdge
        if pos.y() > self.height() - self.RESIZE_MARGIN: edge |= Qt.Edge.BottomEdge
        return edge

    def mousePressEvent(self, event):
        if self.overlay_type == 'stt' and event.button() == Qt.MouseButton.LeftButton:
            self.resize_edge = self.get_edge(event.position().toPoint())
            # ❗ [오류 수정] 비교 대상을 int(0)에서 Qt.Edges()로 변경
            if self.resize_edge != Qt.Edges():
                self.resizing = True
                self.resize_start_geometry = self.geometry()
                self.resize_start_global_pos = event.globalPosition().toPoint()
            else:
                self.dragging = True
                self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.overlay_type != 'stt': return

        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_start_position)
        elif self.resizing:
            new_rect = QRect(self.resize_start_geometry)
            delta = event.globalPosition().toPoint() - self.resize_start_global_pos

            if self.resize_edge & Qt.Edge.LeftEdge: new_rect.setLeft(self.resize_start_geometry.left() + delta.x())
            if self.resize_edge & Qt.Edge.RightEdge: new_rect.setRight(self.resize_start_geometry.right() + delta.x())
            if self.resize_edge & Qt.Edge.TopEdge: new_rect.setTop(self.resize_start_geometry.top() + delta.y())
            if self.resize_edge & Qt.Edge.BottomEdge: new_rect.setBottom(self.resize_start_geometry.bottom() + delta.y())
            
            if new_rect.width() < 200: new_rect.setWidth(200)
            if new_rect.height() < 50: new_rect.setHeight(50)

            self.setGeometry(new_rect)
        else:
            edge = self.get_edge(event.position().toPoint())
            if (edge == (Qt.Edge.TopEdge | Qt.Edge.LeftEdge)) or (edge == (Qt.Edge.BottomEdge | Qt.Edge.RightEdge)): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (edge == (Qt.Edge.TopEdge | Qt.Edge.RightEdge)) or (edge == (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge)): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge): self.setCursor(Qt.CursorShape.SizeVerCursor)
            else: self.unsetCursor()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.overlay_type == 'stt' and event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.resizing = False
            self.unsetCursor()
            # ❗ [추가] 상태 변수 초기화
            self.resize_edge = Qt.Edges()
            # 변경된 위치와 크기를 설정 파일에 저장
            self.config_manager.set("stt_overlay_pos_x", self.pos().x())
            self.config_manager.set("stt_overlay_pos_y", self.pos().y())
            self.config_manager.set("stt_overlay_width", self.width())
            self.config_manager.set("stt_overlay_height", self.height())
            event.accept()