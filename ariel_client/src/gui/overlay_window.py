# ariel_client/src/gui/overlay_window.py (이 코드로 전체 교체)
import logging
from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QApplication, QMenu,
                               QGraphicsOpacityEffect, QSizePolicy)
from PySide6.QtCore import (Qt, QTimer, QPoint, QRect, Slot, QPropertyAnimation, 
                              QEasingCurve, Property, QParallelAnimationGroup)
from PySide6.QtGui import QCursor, QGuiApplication, QAction, QColor

from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)

# OcrPatchWindow 클래스는 변경 없음 (기존 코드와 동일)
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
    # (이 클래스는 기존 코드와 대부분 동일하지만, 애니메이션을 위해 opacity property를 가짐)
    def _get_opacity(self):
        if not self.graphicsEffect(): return 1.0
        return self.graphicsEffect().opacity()

    def _set_opacity(self, opacity):
        if not self.graphicsEffect():
            self.opacity_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self.opacity_effect)
        self.graphicsEffect().setOpacity(opacity)

    opacity = Property(float, _get_opacity, _set_opacity)

    def __init__(self, original_text: str, translated_text: str, style_config: dict, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.original_text = original_text
        self.translated_text = translated_text
        self.style_config = style_config
        self.is_current_line = False # 기본값은 False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        
        self.translated_label = QLabel(self.translated_text)
        self.translated_label.setWordWrap(True)
        self.translated_label.setTextFormat(Qt.TextFormat.RichText)
        self.translated_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.original_label = QLabel(self.original_text)
        self.original_label.setWordWrap(True)
        self.original_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        layout.addWidget(self.translated_label)
        layout.addWidget(self.original_label)
        self.apply_styles()

    def update_text(self, original_text: str, translated_text: str):
        self.original_text = original_text
        self.translated_text = translated_text
        self.translated_label.setText(translated_text)
        self.original_label.setText(original_text)
        self.original_label.setVisible(self.style_config.get("show_original_text", True) and bool(self.original_text))
        self.adjustSize() # 텍스트 변경 후 크기 재조정

    def apply_styles(self):
        font_family = self.style_config.get("font_family", "Malgun Gothic")
        font_size = self.style_config.get("font_size", 18)
        
        bg_color_str = self.style_config.get("background_color", "rgba(0, 0, 0, 0.8)")
        self.setStyleSheet(f"background-color: {bg_color_str}; border-radius: 8px;")
        
        self.translated_label.setStyleSheet(f"""
            background-color: transparent;
            color: {self.style_config.get("font_color", "#FFFFFF")};
            font-family: "{font_family}"; font-size: {font_size}pt; font-weight: bold;
        """)

        orig_offset = self.style_config.get("original_text_font_size_offset", -4)
        self.original_label.setStyleSheet(f"""
            background-color: transparent;
            color: {self.style_config.get("original_text_font_color", "#BBBBBB")};
            font-family: "{font_family}"; font-size: {font_size + orig_offset}pt;
        """)
        
        show_original = self.style_config.get("show_original_text", True)
        self.original_label.setVisible(show_original and bool(self.original_text))

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self.original_text: menu.addAction("Copy Original").triggered.connect(lambda: QApplication.clipboard().setText(self.original_text))
        if self.translated_text: menu.addAction("Copy Translated").triggered.connect(lambda: QApplication.clipboard().setText(self.translated_text))
        if menu.actions(): menu.exec(event.globalPos())

# ==================== [핵심] OverlayWindow 전면 재설계 ====================
class OverlayWindow(QWidget):
    RESIZE_MARGIN = 10
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.style_config = {}
        self.dragging = False
        self.resizing = False
        self.drag_start_position = QPoint()
        self.resize_edge = Qt.Edges()

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # [수정] 자식 위젯의 위치를 직접 제어하므로, 마우스 이벤트를 자식에게 전달하지 않음
        self.setMouseTracking(True) 
        
        self.items = [] # QVBoxLayout 대신 리스트로 아이템 관리
        self.animation_group = QParallelAnimationGroup(self)
        
        self.status_label = QLabel(self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()

        self.on_settings_changed()
        self._load_geometry()

    @Slot()
    def on_settings_changed(self):
        logger.debug("OverlayWindow: Settings changed, reloading styles and behavior.")
        self.style_config = self.config_manager.get("stt_overlay_style", {})
        
        font_family = self.style_config.get("font_family", "Malgun Gothic")
        self.status_label.setStyleSheet(f"background-color: transparent; color: #CCCCCC; font-size: 10pt; font-family: '{font_family}';")
        
        # 모든 아이템에 새 스타일 적용
        for item in self.items:
            item.style_config = self.style_config
            item.apply_styles()
            item.adjustSize() # 스타일 변경 후 크기 재조정

        self._update_layout() # 레이아웃 즉시 갱신

    # [수정] update_current_line -> update_item으로 통합
    @Slot(str, str, bool)
    def update_item(self, original: str, translated: str, is_final: bool):
        self.status_label.hide()

        if not self.items or self.items[0].is_current_line is False:
            # 새 아이템 추가
            new_item = TranslationItem(original, translated, self.style_config, self)
            new_item.is_current_line = not is_final
            self.items.insert(0, new_item)
            new_item.show()
        else:
            # 기존 아이템 업데이트
            current_item = self.items[0]
            current_item.update_text(original, translated)
            current_item.is_current_line = not is_final

        self._apply_message_limit()
        self._update_layout()

    def _apply_message_limit(self):
        max_messages = self.style_config.get("max_messages", 3)
        if len(self.items) > max_messages:
            items_to_remove = self.items[max_messages:]
            self.items = self.items[:max_messages] # 리스트에서 즉시 제거
            for item in items_to_remove:
                self.fade_out_and_die(item)

    # [핵심] 수동 레이아웃 및 애니메이션 함수
    def _update_layout(self):
        self.animation_group.clear() # 이전 애니메이션 중지
        
        spacing = 8
        current_y = self.height() - self.RESIZE_MARGIN # 아래쪽부터 시작
        
        for i, item in enumerate(self.items):
            item.adjustSize() # 최신 크기 반영
            target_y = current_y - item.height()
            current_y = target_y - spacing
            
            # 위치 애니메이션
            pos_anim = QPropertyAnimation(item, b"pos", self)
            pos_anim.setDuration(300)
            pos_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            pos_anim.setEndValue(QPoint(self.RESIZE_MARGIN, target_y))
            self.animation_group.addAnimation(pos_anim)

            # 투명도 애니메이션 (인덱스에 따라)
            opacity_anim = QPropertyAnimation(item, b"opacity", self)
            opacity_anim.setDuration(300)
            opacity_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            
            # [핵심] 위치에 따른 투명도 계산
            if i == 0: # 최상단 (현재 입력중 또는 가장 최신)
                target_opacity = 1.0
            elif i == 1:
                target_opacity = 0.8
            elif i == 2:
                target_opacity = 0.6
            else: # 그 이상은 투명
                target_opacity = 0.0

            opacity_anim.setEndValue(target_opacity)
            self.animation_group.addAnimation(opacity_anim)
        
        self.animation_group.start()

    def fade_out_and_die(self, item: QWidget):
        anim = QPropertyAnimation(item, b"opacity", self)
        anim.setDuration(300)
        anim.setEndValue(0.0)
        anim.finished.connect(item.deleteLater)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    @Slot(str)
    def update_status_text(self, text: str):
        self.clear_messages()
        self.status_label.setText(text)
        self.status_label.adjustSize()
        self.status_label.move(
            int((self.width() - self.status_label.width()) / 2),
            int((self.height() - self.status_label.height()) / 2)
        )
        self.status_label.show()
    
    def clear_messages(self):
        for item in self.items:
            self.fade_out_and_die(item)
        self.items.clear()
        
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
        
    def resizeEvent(self, event):
        # 창 크기가 변경될 때마다 레이아웃을 다시 계산
        super().resizeEvent(event)
        self._update_layout()

    def mousePressEvent(self, event):
        if not self.config_manager.get("stt_overlay_style.is_draggable", True):
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.resize_edge = self.get_edge(event.position().toPoint())
            if self.resize_edge != Qt.Edges():
                self.resizing = True
                self.resize_start_geometry = self.geometry()
                self.resize_start_global_pos = event.globalPosition().toPoint()
            else:
                self.dragging = True
                self.drag_start_position = event.globalPosition()
    
    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.pos() + (event.globalPosition() - self.drag_start_position).toPoint())
            self.drag_start_position = event.globalPosition()
        elif self.resizing:
            new_rect = QRect(self.resize_start_geometry)
            delta = event.globalPosition().toPoint() - self.resize_start_global_pos
            if self.resize_edge & Qt.Edge.LeftEdge: new_rect.setLeft(self.resize_start_geometry.left() + delta.x())
            if self.resize_edge & Qt.Edge.RightEdge: new_rect.setRight(self.resize_start_geometry.right() + delta.x())
            if self.resize_edge & Qt.Edge.TopEdge: new_rect.setTop(self.resize_start_geometry.top() + delta.y())
            if self.resize_edge & Qt.Edge.BottomEdge: new_rect.setBottom(self.resize_start_geometry.bottom() + delta.y())
            
            if new_rect.width() > self.minimumWidth() and new_rect.height() > self.minimumHeight():
                self.setGeometry(new_rect)
        else:
            self.update_cursor(event.position().toPoint())
    
    def mouseReleaseEvent(self, event):
        if self.dragging or self.resizing:
            self.dragging = self.resizing = False
            self.unsetCursor()
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
        edge = Qt.Edges()
        m = self.RESIZE_MARGIN
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
        self.config_manager.save()

    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)