# ariel_client/src/gui/overlay_window.py (이 코드로 전체 교체)
import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect, QSizePolicy
from PySide6.QtCore import Qt, Slot, QPoint, QRect
from PySide6.QtGui import QFont, QCursor, QGuiApplication

from ..config_manager import ConfigManager

class TranslationItem(QWidget):
    """
    개별 번역 결과를 표시하는 위젯 (원본 + 번역본).
    이 위젯의 디자인은 그대로 유지됩니다.
    """
    def __init__(self, original_text, translated_results: dict, config_manager, source: str):
        super().__init__()
        self.config_manager = config_manager
        # [수정] 현재 프로필 설정을 한 번만 가져오도록 수정
        self.current_config = self.config_manager.get_active_profile()
        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("translationItem")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 10, 12, 10) # 여백 조정
        self.layout.setSpacing(5)

        # [수정] 좀 더 명확한 소스 표시
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
    RESIZE_MARGIN = 10 # 리사이즈 감지 영역 확대

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        
        # --- 기본 윈도우 설정 ---
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        # --- [핵심 수정] main_layout 정의 및 적용 ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15) # 전체 여백
        self.main_layout.setSpacing(10) # 위젯 간 간격

        # --- 지능형 오버레이 허브 레이아웃 ---
        self.ocr_item_layout = QVBoxLayout()
        self.stt_item_layout = QVBoxLayout()
        
        # --- 상태 알림 시스템 레이아웃 ---
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setVisible(False)

        # --- 레이아웃 조립 ---
        self.main_layout.addLayout(self.ocr_item_layout)
        self.main_layout.addLayout(self.stt_item_layout)
        self.main_layout.addWidget(self.status_label)
        self.main_layout.addStretch(1)

        self.stt_items = []
        self.ocr_item = None
        
        # --- 창 이동 및 크기 조절 관련 변수 ---
        self.dragging = False
        self.resizing = False
        self.resize_edge = 0
        self.drag_start_position = QPoint()

        # --- 저장된 위치/크기 복원 ---
        self.load_geometry()

    def load_geometry(self):
        pos_x = self.config_manager.get("overlay_pos_x")
        pos_y = self.config_manager.get("overlay_pos_y")
        width = self.config_manager.get("overlay_width", 800)
        height = self.config_manager.get("overlay_height", 250)
        
        self.resize(width, height)
        
        if pos_x is not None and pos_y is not None:
            self.move(pos_x, pos_y)
        else:
            self.move_to_center()
    
    def move_to_center(self):
        if QGuiApplication.primaryScreen():
            screen_geo = QGuiApplication.primaryScreen().geometry()
            self.move(screen_geo.center() - self.rect().center())

    @Slot(str)
    def update_status(self, message: str):
        """상태 메시지를 업데이트합니다 (예: '번역 중...')"""
        font_size = self.config_manager.get("overlay_font_size", 18)
        self.status_label.setText(f"<i>{message}</i>" if message else "")
        self.status_label.setStyleSheet(f"""
            color: #CCCCCC; 
            font-size: {font_size-1}pt; 
            background-color: rgba(20, 20, 20, 0.8); 
            border-radius: 5px; 
            padding: 8px 12px;
        """)
        self.status_label.setVisible(bool(message))

    @Slot(str, dict, str)
    def add_translation(self, original, results, source):
        """소스(ocr/stt)에 따라 번역 결과를 추가/교체합니다."""
        if source == "ocr":
            # 기존 OCR 아이템 제거 (Replace)
            if self.ocr_item:
                self.ocr_item.deleteLater()
            
            self.ocr_item = TranslationItem(original, results, self.config_manager, source)
            self.ocr_item_layout.addWidget(self.ocr_item)
        
        elif source == "stt":
            item = TranslationItem(original, results, self.config_manager, source)
            self.stt_item_layout.insertWidget(0, item) # 새 아이템을 맨 위에 추가
            self.stt_items.insert(0, item)

            # 최대 개수 초과 시 가장 오래된 아이템 제거
            if len(self.stt_items) > self.MAX_STT_ITEMS:
                old_item = self.stt_items.pop()
                old_item.deleteLater()

            self.update_stt_opacity()

    def update_stt_opacity(self):
        """STT 아이템들의 투명도를 최신순으로 조절합니다."""
        for i, item in enumerate(self.stt_items):
            # 최신 아이템(i=0)은 1.0, 그 다음은 0.7, 0.4 순
            opacity = 1.0 - (i * 0.3)
            item.opacity_effect.setOpacity(max(0.2, opacity))

    def clear_all(self):
        if self.ocr_item:
            self.ocr_item.deleteLater()
            self.ocr_item = None
        for item in self.stt_items:
            item.deleteLater()
        self.stt_items.clear()

    # --- 마우스 이벤트 핸들러 (창 이동 및 크기 조절) ---

    def get_edge(self, pos: QPoint):
        """마우스 위치가 어느 모서리에 있는지 확인합니다."""
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
                # 크기 조절 시작 위치 저장
                self.resize_start_geometry = self.geometry()
                self.resize_start_global_pos = event.globalPosition().toPoint()
            else:
                self.dragging = True
                self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_start_position)
        elif self.resizing:
            new_rect = QRect(self.resize_start_geometry)
            delta = event.globalPosition().toPoint() - self.resize_start_global_pos

            if self.resize_edge & Qt.Edge.LeftEdge:
                new_rect.setLeft(self.resize_start_geometry.left() + delta.x())
            if self.resize_edge & Qt.Edge.RightEdge:
                new_rect.setRight(self.resize_start_geometry.right() + delta.x())
            if self.resize_edge & Qt.Edge.TopEdge:
                new_rect.setTop(self.resize_start_geometry.top() + delta.y())
            if self.resize_edge & Qt.Edge.BottomEdge:
                new_rect.setBottom(self.resize_start_geometry.bottom() + delta.y())
            
            # 최소 크기 제한
            if new_rect.width() < 200: new_rect.setWidth(200)
            if new_rect.height() < 50: new_rect.setHeight(50)

            self.setGeometry(new_rect)
        else:
            edge = self.get_edge(event.position().toPoint())
            if (edge == (Qt.Edge.TopEdge | Qt.Edge.LeftEdge)) or (edge == (Qt.Edge.BottomEdge | Qt.Edge.RightEdge)):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (edge == (Qt.Edge.TopEdge | Qt.Edge.RightEdge)) or (edge == (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge)):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.unsetCursor()
        event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.resizing = False
        self.unsetCursor()
        # 변경된 위치와 크기 설정 파일에 저장
        self.config_manager.set("overlay_pos_x", self.pos().x())
        self.config_manager.set("overlay_pos_y", self.pos().y())
        self.config_manager.set("overlay_width", self.width())
        self.config_manager.set("overlay_height", self.height())
        event.accept()