# ariel_client/src/gui/overlay_window.py (이 코드로 전체 교체)
import logging
from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QApplication, QMenu,
                               QGraphicsOpacityEffect)
from PySide6.QtCore import (Qt, QTimer, QPoint, QRect, Slot, QPropertyAnimation, 
                              QEasingCurve, QCoreApplication)
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
    def __init__(self, original_text: str, translated_text: str, style_config: dict):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.original_text = original_text
        self.translated_text = translated_text
        self.style_config = style_config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        self.translated_label = QLabel(self.translated_text); self.translated_label.setWordWrap(True); self.translated_label.setTextFormat(Qt.TextFormat.RichText)
        self.original_label = QLabel(self.original_text); self.original_label.setWordWrap(True)
        
        layout.addWidget(self.translated_label)
        layout.addWidget(self.original_label)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        
        self.apply_styles()
        self.animation.start()

    def apply_styles(self):
        font_family = self.style_config.get("font_family", "Malgun Gothic")
        font_size = self.style_config.get("font_size", 18)
        
        self.setStyleSheet(f"""
            TranslationItem {{
                background-color: {self.style_config.get("background_color", "rgba(20, 20, 20, 0.85)")};
                border-radius: 8px;
            }}
        """)
        
        self.translated_label.setStyleSheet(f"""
            background-color: transparent;
            color: {self.style_config.get("font_color", "#FFFFFF")};
            font-family: "{font_family}";
            font-size: {font_size}pt;
            font-weight: bold;
        """)

        orig_offset = self.style_config.get("original_text_font_size_offset", -4)
        self.original_label.setStyleSheet(f"""
            background-color: transparent;
            color: {self.style_config.get("original_text_font_color", "#BBBBBB")};
            font-family: "{font_family}";
            font-size: {font_size + orig_offset}pt;
        """)
        
        show_original = self.style_config.get("show_original_text", True)
        self.original_label.setVisible(show_original and bool(self.original_text))
        self.adjustSize()

    def fade_out_and_die(self):
        self.animation.stop()
        self.animation.setDuration(300)
        self.animation.setStartValue(self.opacity_effect.opacity())
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.Type.InQuad)
        # [수정] 애니메이션이 끝나면 레이아웃에서 위젯을 제거하고 삭제합니다.
        self.animation.finished.connect(self._on_fade_out_finished)
        self.animation.start()

    def _on_fade_out_finished(self):
        """애니메이션 종료 후 위젯을 안전하게 제거하는 슬롯."""
        # 자신을 레이아웃에서 제거
        if self.parent() and self.parent().layout():
            self.parent().layout().removeWidget(self)
        # 자신을 삭제
        self.deleteLater()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self.original_text:
            menu.addAction("Copy Original").triggered.connect(lambda: QApplication.clipboard().setText(self.original_text))
        if self.translated_text:
            menu.addAction("Copy Translated").triggered.connect(lambda: QApplication.clipboard().setText(self.translated_text))
        if menu.actions():
            menu.exec(event.globalPos())

class OverlayWindow(QWidget):
    RESIZE_MARGIN = 10
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # [수정] 위젯을 직접 관리하는 self.items 리스트 제거
        self.dragging = False
        self.resizing = False
        self.drag_start_position = QPoint()
        self.resize_edge = Qt.Edges()
        self.setMouseTracking(True)
        
        self._setup_ui()
        self.on_settings_changed()
        self._load_geometry()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignBottom) # [핵심] 자막이 아래부터 쌓이도록 정렬

        self.status_label = QLabel(self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.status_label)

    @Slot()
    def on_settings_changed(self):
        logger.debug("OverlayWindow: 설정 변경 감지, 스타일을 다시 로드합니다.")
        self.style_config = self.config_manager.get("stt_overlay_style", {})
        
        font_family = self.style_config.get("font_family", "Malgun Gothic")
        self.status_label.setStyleSheet(f"background-color: transparent; color: #CCCCCC; font-size: 10pt; font-family: '{font_family}';")
        
        # [수정] 레이아웃의 모든 자식 위젯에 스타일을 다시 적용
        for i in range(self.main_layout.count()):
            widget = self.main_layout.itemAt(i).widget()
            if isinstance(widget, TranslationItem):
                widget.style_config = self.style_config
                widget.apply_styles()
            
        self._apply_message_limit()

    @Slot(str, str)
    def add_translation_item(self, original: str, translated: str):
        if self.status_label.text():
            self.status_label.clear()

        item = TranslationItem(original, translated, self.style_config)
        # [핵심 수정] 새 자막을 항상 레이아웃의 0번째 위치(가장 위)에 삽입
        self.main_layout.insertWidget(0, item)
        
        self._apply_message_limit()

    def _apply_message_limit(self):
        max_messages = self.style_config.get("max_messages", 3)
        
        # [핵심 수정] 레이아웃에 있는 TranslationItem 위젯 개수를 직접 계산
        current_message_count = 0
        widgets_to_remove = []
        for i in range(self.main_layout.count()):
            widget = self.main_layout.itemAt(i).widget()
            if isinstance(widget, TranslationItem):
                current_message_count += 1
                if current_message_count > max_messages:
                    # 가장 아래에 있는(가장 오래된) 위젯부터 제거 목록에 추가
                    widgets_to_remove.append(widget)

        # 목록에 있는 위젯들을 페이드아웃 시킴
        for old_item in widgets_to_remove:
            old_item.fade_out_and_die()

    @Slot(str)
    def update_status_text(self, text: str):
        self.clear_messages()
        self.status_label.setText(text)
    
    def clear_messages(self):
        # [수정] 레이아웃의 모든 자막을 안전하게 제거
        widgets_to_remove = []
        for i in range(self.main_layout.count()):
            widget = self.main_layout.itemAt(i).widget()
            if isinstance(widget, TranslationItem):
                widgets_to_remove.append(widget)
        
        for item in widgets_to_remove:
            item.fade_out_and_die()
            
    def _load_geometry(self):
        pos_x = self.config_manager.get("overlay_pos_x")
        pos_y = self.config_manager.get("overlay_pos_y")
        width = self.config_manager.get("overlay_width", 800)
        height = self.config_manager.get("overlay_height", 250)
        
        if pos_x is None or pos_y is None:
            rect = QGuiApplication.primaryScreen().availableGeometry()
            pos_x = rect.center().x() - width / 2
            pos_y = rect.bottom() - height - 50
            
        self.setGeometry(int(pos_x), int(pos_y), width, height)
        
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
            self.dragging = self.resizing = False; self.unsetCursor()
            self._save_geometry()

    def update_cursor(self, pos: QPoint):
        edge = self.get_edge(pos)
        if (edge & Qt.Edge.TopEdge and edge & Qt.Edge.LeftEdge) or \
           (edge & Qt.Edge.BottomEdge and edge & Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif (edge & Qt.Edge.TopEdge and edge & Qt.Edge.RightEdge) or \
             (edge & Qt.Edge.BottomEdge and edge & Qt.Edge.LeftEdge):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def get_edge(self, pos: QPoint) -> Qt.Edges:
        edge = Qt.Edges(); m = self.RESIZE_MARGIN
        if pos.x() < m: edge |= Qt.Edge.LeftEdge
        if pos.x() > self.width() - m: edge |= Qt.Edge.RightEdge
        if pos.y() < m: edge |= Qt.Edge.TopEdge
        if pos.y() > self.height() - m: edge |= Qt.Edge.BottomEdge
        return edge
    
    def _save_geometry(self):
        geom = self.geometry()
        self.config_manager.set("overlay_pos_x", geom.x())
        self.config_manager.set("overlay_pos_y", geom.y())
        self.config_manager.set("overlay_width", geom.width())
        self.config_manager.set("overlay_height", geom.height())
        self.config_manager.save() # [추가] 변경 즉시 저장

    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)