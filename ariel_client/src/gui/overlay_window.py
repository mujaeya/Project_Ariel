import logging
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QMenu, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QPropertyAnimation
from PySide6.QtGui import QCursor, QGuiApplication, QAction, QColor

logger = logging.getLogger(__name__)

class OcrPatchWindow(QWidget):
    """[핵심 수정] 개별 OCR 번역 결과를 표시하는 작은 독립 창"""
    def __init__(self, patch_info: dict, style_config: dict):
        super().__init__()
        # 프레임 없는 최상위 투명 창으로 설정
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # 마우스 이벤트를 통과시켜 아래 창을 클릭할 수 있게 함
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True) 

        # 인식된 영역의 좌표와 크기를 그대로 창에 적용
        self.setGeometry(patch_info["rect"])

        # 스타일 설정에서 배경색을 가져와 불투명하게 만듦
        bg_color = QColor(style_config.get("background_color", "#ffffff"))
        bg_color.setAlpha(255)

        self.label = QLabel(patch_info["translated"], self)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 레이아웃을 사용하여 라벨이 창 크기에 맞게 조절되도록 함
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.label)
        
        self.setStyleSheet(f"""
            OcrPatchWindow {{
                background-color: {bg_color.name()};
                border: 1px solid #111;
            }}
            QLabel {{
                background-color: transparent;
                color: {style_config.get("font_color", "#000000")};
                font-size: {style_config.get("font_size", 16)}pt;
                font-weight: bold;
                border: none;
            }}
        """)
        
        # 일정 시간 후 자동으로 사라지는 타이머
        self.fade_out_timer = QTimer(self)
        self.fade_out_timer.setSingleShot(True)
        self.fade_out_timer.timeout.connect(self.close) # 창을 닫으면 자동으로 소멸
        self.fade_out_timer.start(style_config.get("display_duration_ms", 4000))

class TranslationItem(QWidget):
    """개별 번역 결과를 표시하는 위젯. 애니메이션 효과가 적용됩니다."""
    def __init__(self, original_text: str, translated_text: str, source: str, style_config: dict):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        self.original_text = original_text
        self.translated_text = translated_text
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        
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
        layout.addWidget(label)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.setStyleSheet(f"""
            background-color: {style_config.get("background_color", "rgba(20, 20, 20, 0.8)")};
            color: {style_config.get("font_color", "#ffffff")};
            font-size: {style_config.get("font_size", 14)}pt;
            border-radius: 6px;
        """)

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        copy_original_action = context_menu.addAction("원문 복사")
        copy_translated_action = context_menu.addAction("번역문 복사")
        
        if not self.original_text:
            copy_original_action.setEnabled(False)
            copy_translated_action.setEnabled(False)

        copy_original_action.triggered.connect(lambda: QApplication.clipboard().setText(self.original_text))
        copy_translated_action.triggered.connect(lambda: QApplication.clipboard().setText(self.translated_text))
        
        context_menu.exec(event.globalPos())

class OverlayWindow(QWidget):
    """[핵심 수정] STT 전용 오버레이 창으로 역할 변경"""
    RESIZE_MARGIN = 10
    
    def __init__(self, mode: str, config_manager, parent=None):
        super().__init__(parent)
        # mode 파라미터는 유지하되, 내부에서는 'stt'만 처리
        self.mode = 'stt'
        self.config_manager = config_manager
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # OCR 모드 설정 로직 제거, STT 모드만 설정
        self.setup_stt_mode()

    def setup_stt_mode(self):
        """STT 모드에 필요한 UI와 변수를 설정합니다."""
        self.style_config = self.config_manager.get("stt_overlay_style", {})
        
        pos_x = self.config_manager.get("stt_overlay_pos_x")
        pos_y = self.config_manager.get("stt_overlay_pos_y")
        width = self.config_manager.get("stt_overlay_width", 800)
        height = self.config_manager.get("stt_overlay_height", 250)
        
        if pos_x is None or pos_y is None:
            screen_rect = QGuiApplication.primaryScreen().availableGeometry()
            pos_x = screen_rect.center().x() - width / 2
            pos_y = screen_rect.bottom() - height - 50
        
        self.setGeometry(int(pos_x), int(pos_y), width, height)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)
        self.main_layout.addStretch(1)
        
        self.setMouseTracking(True)
        self.items = []
        self.dragging = False
        self.resizing = False
        self.drag_start_position = QPoint()
        self.resize_edge = Qt.Edges()

    def add_stt_message(self, original: str, translated: str, is_system: bool = False):
        """새 STT 자막을 애니메이션과 함께 추가하고, 오래된 자막은 제거합니다."""
        item = TranslationItem(original, translated, "system" if is_system else "stt", self.style_config)
        self.main_layout.insertWidget(self.main_layout.count() - 1, item)
        self.items.append(item)

        fade_in = QPropertyAnimation(item.opacity_effect, b"opacity")
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.start()

        max_messages = self.style_config.get("max_messages", 5)
        if len(self.items) > max_messages:
            old_item = self.items.pop(0)
            fade_out = QPropertyAnimation(old_item.opacity_effect, b"opacity")
            fade_out.setDuration(300)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.finished.connect(old_item.deleteLater)
            fade_out.start()

    def clear_stt_messages(self):
        while self.items:
            self.items.pop(0).deleteLater()
    
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
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
            delta = event.globalPosition() - self.drag_start_position
            self.move(self.pos() + delta.toPoint())
            self.drag_start_position = event.globalPosition()
        elif self.resizing:
            new_rect = QRect(self.resize_start_geometry)
            delta = event.globalPosition().toPoint() - self.resize_start_global_pos
            if self.resize_edge & Qt.Edge.LeftEdge: new_rect.setLeft(self.resize_start_geometry.left() + delta.x())
            if self.resize_edge & Qt.Edge.RightEdge: new_rect.setRight(self.resize_start_geometry.right() + delta.x())
            if self.resize_edge & Qt.Edge.TopEdge: new_rect.setTop(self.resize_start_geometry.top() + delta.y())
            if self.resize_edge & Qt.Edge.BottomEdge: new_rect.setBottom(self.resize_start_geometry.bottom() + delta.y())
            if new_rect.width() > self.minimumWidth() and new_rect.height() > self.minimumHeight(): self.setGeometry(new_rect)
        else:
            edge = self.get_edge(event.position().toPoint())
            if (edge & Qt.Edge.TopEdge and edge & Qt.Edge.LeftEdge) or (edge & Qt.Edge.BottomEdge and edge & Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (edge & Qt.Edge.TopEdge and edge & Qt.Edge.RightEdge) or (edge & Qt.Edge.BottomEdge and edge & Qt.Edge.LeftEdge): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge): self.setCursor(Qt.CursorShape.SizeVerCursor)
            else: self.unsetCursor()
    
    def mouseReleaseEvent(self, event):
        if self.dragging or self.resizing:
            self.dragging = self.resizing = False
            self.unsetCursor()
            geom = self.geometry()
            self.config_manager.set("stt_overlay_pos_x", geom.x())
            self.config_manager.set("stt_overlay_pos_y", geom.y())
            self.config_manager.set("stt_overlay_width", geom.width())
            self.config_manager.set("stt_overlay_height", geom.height())
            logger.info(f"STT 오버레이 위치/크기 저장됨: {geom}")

    def get_edge(self, pos: QPoint):
        edge = Qt.Edges()
        if pos.x() < self.RESIZE_MARGIN: edge |= Qt.Edge.LeftEdge
        if pos.x() > self.width() - self.RESIZE_MARGIN: edge |= Qt.Edge.RightEdge
        if pos.y() < self.RESIZE_MARGIN: edge |= Qt.Edge.TopEdge
        if pos.y() > self.height() - self.RESIZE_MARGIN: edge |= Qt.Edge.BottomEdge
        return edge

    def closeEvent(self, event):
        geom = self.geometry()
        self.config_manager.set("stt_overlay_pos_x", geom.x())
        self.config_manager.set("stt_overlay_pos_y", geom.y())
        self.config_manager.set("stt_overlay_width", geom.width())
        self.config_manager.set("stt_overlay_height", geom.height())
        super().closeEvent(event)