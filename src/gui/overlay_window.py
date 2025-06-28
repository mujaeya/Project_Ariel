import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsOpacityEffect, QSizePolicy, QPushButton
from PySide6.QtCore import Qt, Slot, QPoint
from PySide6.QtGui import QFont, QCursor, QColor

from config_manager import ConfigManager

class TranslationItem(QWidget):
    """번역 결과 한 줄을 표시하는 커스텀 위젯 (실시간 미리보기 및 클립보드 복사 개선)"""
    def __init__(self, original_text, translated_text, config_manager, temp_config=None):
        super().__init__()
        # 미리보기용 임시 config가 있으면 그것을 사용, 없으면 메인 config 사용
        self.config_manager = config_manager
        self.current_config = temp_config if temp_config is not None else self.config_manager.config

        self.original_text = original_text
        self.translated_text = translated_text
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("translationItem")

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.top_layout = QHBoxLayout()
        self.top_layout.setContentsMargins(8, 8, 8, 2)
        self.top_layout.setSpacing(8)

        self.translated_label = QLabel(translated_text)
        self.translated_label.setWordWrap(True)
        self.translated_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.translated_label.setTextFormat(Qt.TextFormat.RichText)

        self.copy_button = QPushButton()
        self.copy_button.setFixedSize(18, 18)
        self.copy_button.setToolTip("번역 결과 복사")
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.clicked.connect(self.copy_to_clipboard)

        self.top_layout.addWidget(self.translated_label, 1)
        self.top_layout.addWidget(self.copy_button)

        self.original_label = QLabel(original_text)
        self.original_label.setWordWrap(True)
        self.original_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        self.layout.addLayout(self.top_layout)
        self.layout.addWidget(self.original_label)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.update_styles()

    def copy_to_clipboard(self):
        """pyperclip 라이브러리를 사용하여 안정적으로 클립보드에 복사합니다."""
        try:
            import pyperclip
            pyperclip.copy(self.translated_text)
            print(f"클립보드에 복사됨: {self.translated_text}")
        except ImportError:
            print("오류: pyperclip 라이브러리가 설치되지 않았습니다. 'pip install pyperclip'을 실행해주세요.")
        except Exception as e:
            print(f"클립보드 복사 중 오류 발생: {e}")

    def _adjust_color(self, color, amount):
        """QColor를 사용하여 색상을 안전하게 조절하고, RGBA 문자열로 반환합니다."""
        q_color = QColor(color)
        if not q_color.isValid(): return color
        
        h, s, l, a = q_color.getHslF()
        l = max(0.0, min(1.0, l + amount / 255.0))
        
        new_color = QColor.fromHslF(h, s, l, a)
        return f"rgba({new_color.red()}, {new_color.green()}, {new_color.blue()}, {new_color.alpha()})"

    def update_styles(self):
        """스타일시트를 사용하여 위젯의 모든 외형을 설정합니다."""
        # current_config를 사용하여 스타일을 동적으로 적용
        font_family = self.current_config.get("overlay_font_family", "Malgun Gothic")
        font_size = self.current_config.get("overlay_font_size", 18)
        font_color = self.current_config.get("overlay_font_color", "#FFFFFF")
        bg_color = self.current_config.get("overlay_bg_color", "rgba(0, 0, 0, 160)")
        show_original = self.current_config.get("show_original_text", True)
        original_font_size_offset = self.current_config.get("original_text_font_size_offset", -4)
        original_font_color = self.current_config.get("original_text_font_color", "#BBBBBB")

        button_bg_color = self._adjust_color(bg_color, 25)
        button_hover_color = self._adjust_color(bg_color, 50)
        button_pressed_color = self._adjust_color(bg_color, 15)

        self.setStyleSheet(f"""
            #translationItem {{
                background-color: {bg_color};
                border-radius: 5px;
            }}
            QLabel {{
                background-color: transparent;
            }}
            #translated_label {{
                color: {font_color};
                font-family: "{font_family}";
                font-size: {font_size}px;
                font-weight: bold;
            }}
            #original_label {{
                color: {original_font_color};
                font-family: "{font_family}";
                font-size: {font_size + original_font_size_offset}px;
                padding: 0px 8px 5px 8px;
            }}
            QPushButton {{
                background-color: {button_bg_color};
                border: none;
                border-radius: 3px;
                /* 아이콘을 위한 임시 스타일 (나중에 이미지로 교체 가능) */
                color: {font_color};
                font-weight: bold;
                font-size: 10px;
                qproperty-text: "📋";
            }}
            QPushButton:hover {{
                background-color: {button_hover_color};
            }}
            QPushButton:pressed {{
                background-color: {button_pressed_color};
            }}
        """)

        self.translated_label.setObjectName("translated_label")
        self.original_label.setObjectName("original_label")

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
        self.status_layout.setContentsMargins(0, 0, 0, 0)
        self.status_layout.addStretch(1)
        self.status_label = QLabel()
        self.status_layout.addWidget(self.status_label)
        
        self.translation_items = []
        self.main_layout.addStretch(1)
        self.update_styles()
        
        self.dragging = False
        self.resizing = False
        self.drag_start_position = QPoint()
        self.resize_edge = 0

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
                self.resize_start_geometry = self.geometry()
                self.resize_start_pos = event.globalPosition().toPoint()
            else:
                self.dragging = True
                self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self.resizing:
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            geom = self.geometry()
            if self.resize_edge & Qt.Edge.LeftEdge: geom.setLeft(self.resize_start_geometry.left() + delta.x())
            if self.resize_edge & Qt.Edge.RightEdge: geom.setRight(self.resize_start_geometry.right() + delta.x())
            if self.resize_edge & Qt.Edge.TopEdge: geom.setTop(self.resize_start_geometry.top() + delta.y())
            if self.resize_edge & Qt.Edge.BottomEdge: geom.setBottom(self.resize_start_geometry.bottom() + delta.y())
            if geom.width() < self.minimumWidth() or geom.height() < self.minimumHeight(): return
            self.setGeometry(geom)
        elif self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_start_position)
        else:
            edge = self.get_edge(pos)
            if (edge == (Qt.Edge.LeftEdge | Qt.Edge.TopEdge)) or (edge == (Qt.Edge.RightEdge | Qt.Edge.BottomEdge)): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (edge == (Qt.Edge.RightEdge | Qt.Edge.TopEdge)) or (edge == (Qt.Edge.LeftEdge | Qt.Edge.BottomEdge)): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif (edge == Qt.Edge.LeftEdge) or (edge == Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif (edge == Qt.Edge.TopEdge) or (edge == Qt.Edge.BottomEdge): self.setCursor(Qt.CursorShape.SizeVerCursor)
            else: self.unsetCursor()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.resizing or self.dragging:
            self.config_manager.set("overlay_pos_x", self.pos().x())
            self.config_manager.set("overlay_pos_y", self.pos().y())
            self.config_manager.set("overlay_width", self.width())
            self.config_manager.set("overlay_height", self.height())
            
        self.dragging = False
        self.resizing = False
        self.unsetCursor()
        event.accept()

    def update_styles(self):
        font = QFont(self.config_manager.get("overlay_font_family", "Malgun Gothic"), 10)
        font.setItalic(True)
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
        
        # 실제 오버레이 창에서는 temp_config를 사용하지 않음
        item = TranslationItem(original, translated, self.config_manager)
        insert_index = 0
        self.main_layout.insertWidget(insert_index, item)
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
            insert_index = self.main_layout.count() - 1
            self.main_layout.insertLayout(insert_index, self.status_layout)