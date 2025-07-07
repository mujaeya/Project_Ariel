# F:/projects/Project_Ariel/ariel_client/src/gui/overlay_window.py (최종 완성본)
import logging
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QCursor, QGuiApplication

logger = logging.getLogger(__name__)

class TranslationItem(QWidget):
    """
    [개선] 개별 번역 결과를 표시하며, 우클릭 메뉴로 내용 복사 기능을 제공합니다.
    """
    def __init__(self, original_text: str, translated_text: str, source: str, style_config: dict):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # [추가] 나중에 복사할 수 있도록 원본과 번역문을 저장
        self.original_text = original_text
        self.translated_text = translated_text
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(4)
        
        label_text = ""
        if source == "system":
            label_text = f"<b>{translated_text}</b>"
        else:
            if style_config.get("show_original_text", True):
                original_style = f'font-size: {style_config.get("font_size", 14) + style_config.get("original_text_font_size_offset", -2)}pt; color: {style_config.get("original_text_font_color", "#cccccc")};'
                label_text += f'<div style="{original_style}">{original_text}</div>'
            label_text += translated_text

        label = QLabel(label_text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        self.layout.addWidget(label)
        
        self.setGraphicsEffect(QGraphicsOpacityEffect(self))
        self.setStyleSheet(f"""
            background-color: {style_config.get("background_color", "rgba(20, 20, 20, 0.8)")};
            color: {style_config.get("font_color", "#ffffff")};
            font-size: {style_config.get("font_size", 14)}pt;
            border-radius: 6px;
        """)
    def contextMenuEvent(self, event):
        """[신규] 우클릭 시 컨텍스트 메뉴를 생성합니다."""
        context_menu = QMenu(self)
        
        copy_original_action = QAction("원문 복사", self)
        copy_original_action.triggered.connect(self.copy_original)
        context_menu.addAction(copy_original_action)
        
        copy_translated_action = QAction("번역문 복사", self)
        copy_translated_action.triggered.connect(self.copy_translated)
        context_menu.addAction(copy_translated_action)
        
        # 시스템 메시지일 경우 복사 메뉴 비활성화
        if not self.original_text:
            copy_original_action.setEnabled(False)
            copy_translated_action.setEnabled(False)

        context_menu.exec(event.globalPos())

    def copy_original(self):
        """[신규] 원문을 클립보드에 복사합니다."""
        QApplication.clipboard().setText(self.original_text)
        logger.info("원문을 클립보드에 복사했습니다.")

    def copy_translated(self):
        """[신규] 번역문을 클립보드에 복사합니다."""
        QApplication.clipboard().setText(self.translated_text)
        logger.info("번역문을 클립보드에 복사했습니다.")

class OcrPatch(QLabel):
    def __init__(self, text: str, geometry: QRect, parent: QWidget, style_config: dict):
        super().__init__(text, parent)
        self.setGeometry(geometry)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setStyleSheet(f"""
            background-color: {style_config.get("background_color", "#ffffff")};
            color: {style_config.get("font_color", "#000000")};
            font-size: {style_config.get("font_size", 16)}pt;
            font-weight: bold; 
            border: 1px solid #333; 
            padding: 2px;
        """)
        self.show()

class OverlayWindow(QWidget):
    RESIZE_MARGIN = 10
    def __init__(self, mode: str, config_manager, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.config_manager = config_manager
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        if self.mode == 'stt':
            self.style_config = self.config_manager.get("stt_overlay_style", {})
            
            # 초기 위치 및 크기 설정
            pos_x = self.config_manager.get("stt_overlay_pos_x")
            pos_y = self.config_manager.get("stt_overlay_pos_y")
            width = self.config_manager.get("stt_overlay_width", 800)
            height = self.config_manager.get("stt_overlay_height", 250)
            
            # 위치 값이 없으면 화면 중앙에 배치
            if pos_x is None or pos_y is None:
                screen_rect = QGuiApplication.primaryScreen().availableGeometry()
                pos_x = screen_rect.center().x() - width / 2
                pos_y = screen_rect.center().y() - height / 2
            
            self.setGeometry(int(pos_x), int(pos_y), width, height)

            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(10, 10, 10, 10)
            self.main_layout.setSpacing(8)
            self.main_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
            self.setMouseTracking(True)
            self.items = []
            self.dragging, self.resizing = False, False
        else: # 'ocr'
            self.style_config = self.config_manager.get("ocr_overlay_style", {})
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.patches = []
            self.fade_out_timer = QTimer(self)
            self.fade_out_timer.setSingleShot(True)
            self.fade_out_timer.timeout.connect(self.hide_patches)

    def add_stt_message(self, original: str, translated: str, is_system: bool = False):
        item = TranslationItem(original, translated, "system" if is_system else "stt", self.style_config)
        self.main_layout.addWidget(item)
        self.items.insert(0, item)
        
        max_messages = self.style_config.get("max_messages", 5)
        if len(self.items) > max_messages:
            old_item = self.items.pop()
            old_item.deleteLater()
        
        # 페이드 아웃 효과
        for i, item_widget in enumerate(self.items):
            opacity = 1.0 - (i / max_messages)
            item_widget.graphicsEffect().setOpacity(opacity)

    def clear_stt_messages(self):
        while self.items: self.items.pop().deleteLater()

    def update_ocr_patches(self, patches_data: list):
        self.hide_patches()
        if not patches_data: return

        parent_rect = QRect()
        for patch_info in patches_data:
            parent_rect = parent_rect.united(patch_info["rect"])
            
        self.setGeometry(parent_rect)
        
        for patch_info in patches_data:
            relative_rect = patch_info["rect"].translated(-parent_rect.topLeft())
            self.patches.append(OcrPatch(patch_info["translated"], relative_rect, self, self.style_config))
        
        self.show()
        self.fade_out_timer.start(self.style_config.get("display_duration_ms", 4000))

    def hide_patches(self):
        while self.patches: self.patches.pop().deleteLater()
        if self.isVisible():
            self.hide()

    def mousePressEvent(self, event):
        if self.mode != 'stt' or event.button() != Qt.MouseButton.LeftButton: return
        self.resize_edge = self.get_edge(event.position().toPoint())
        if self.resize_edge != Qt.Edges():
            self.resizing = True
            self.resize_start_geometry = self.geometry()
            self.resize_start_global_pos = event.globalPosition().toPoint()
        else:
            self.dragging = True
            self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.mode != 'stt': return
        if self.dragging: 
            self.move(event.globalPosition().toPoint() - self.drag_start_position)
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
            edge = self.get_edge(event.position().toPoint())
            if (edge & Qt.Edge.TopEdge and edge & Qt.Edge.LeftEdge) or (edge & Qt.Edge.BottomEdge and edge & Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (edge & Qt.Edge.TopEdge and edge & Qt.Edge.RightEdge) or (edge & Qt.Edge.BottomEdge and edge & Qt.Edge.LeftEdge): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge): self.setCursor(Qt.CursorShape.SizeVerCursor)
            else: self.unsetCursor()
    
    def mouseReleaseEvent(self, event):
        if self.mode == 'stt' and (self.dragging or self.resizing):
            self.dragging = self.resizing = False
            self.unsetCursor()
            # 위치 및 크기 저장
            current_geom = self.geometry()
            self.config_manager.set("stt_overlay_pos_x", current_geom.x())
            self.config_manager.set("stt_overlay_pos_y", current_geom.y())
            self.config_manager.set("stt_overlay_width", current_geom.width())
            self.config_manager.set("stt_overlay_height", current_geom.height())
            logger.info(f"STT 오버레이 위치/크기 저장됨: {current_geom}")

    def get_edge(self, pos: QPoint):
        edge = Qt.Edges()
        if pos.x() < self.RESIZE_MARGIN: edge |= Qt.Edge.LeftEdge
        if pos.x() > self.width() - self.RESIZE_MARGIN: edge |= Qt.Edge.RightEdge
        if pos.y() < self.RESIZE_MARGIN: edge |= Qt.Edge.TopEdge
        if pos.y() > self.height() - self.RESIZE_MARGIN: edge |= Qt.Edge.BottomEdge
        return edge

    def closeEvent(self, event):
        # STT 오버레이가 닫힐 때 위치 저장
        if self.mode == 'stt':
            geom = self.geometry()
            self.config_manager.set("stt_overlay_pos_x", geom.x())
            self.config_manager.set("stt_overlay_pos_y", geom.y())
            self.config_manager.set("stt_overlay_width", geom.width())
            self.config_manager.set("stt_overlay_height", geom.height())
        super().closeEvent(event)