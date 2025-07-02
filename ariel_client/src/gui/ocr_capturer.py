import logging
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QColor

class OcrCapturer(QWidget):
    region_selected = Signal(QRect)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # [핵심 수정] 모든 모니터를 포함하는 가상 스크린의 전체 영역을 가져옴
        virtual_desktop_rect = QRect()
        for screen in QApplication.screens():
            virtual_desktop_rect = virtual_desktop_rect.united(screen.geometry())
        
        self.setGeometry(virtual_desktop_rect)

        self.begin = QPoint()
        self.end = QPoint()

    def paintEvent(self, event):
        """반투명한 검은 오버레이와 선택 영역을 그리는 이벤트"""
        painter = QPainter(self)
        # 반투명 배경
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        # 사용자가 드래그하는 동안 선택 영역 표시
        if not self.begin.isNull() and not self.end.isNull():
            selection_rect = QRect(self.begin, self.end).normalized()
            # 선택된 영역은 투명하게 만듦
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selection_rect, Qt.GlobalColor.transparent)
            
            # 선택 영역 테두리 그리기
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor("#33A1FF"), 2, Qt.PenStyle.SolidLine) # 파란색 테두리
            painter.setPen(pen)
            painter.drawRect(selection_rect)

    def mousePressEvent(self, event):
        self.begin = event.position().toPoint()
        self.end = self.begin
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event):
        self.end = event.position().toPoint()
        self.close() # 영역 선택이 끝나면 즉시 창을 닫음

        selection_rect = QRect(self.begin, self.end).normalized()
        
        # [핵심 변경] 너무 작은 영역은 무시하고, 유효한 영역만 시그널로 전달
        if selection_rect.width() > 10 and selection_rect.height() > 10:
            logging.info(f"감시 영역 선택 완료: {selection_rect}")
            self.region_selected.emit(selection_rect)
        else:
            logging.warning("선택된 영역이 너무 작아 감시를 시작하지 않습니다.")

    def keyPressEvent(self, event):
        """ESC 키를 누르면 캡처를 취소하고 창을 닫습니다."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()