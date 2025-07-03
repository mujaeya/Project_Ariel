# ariel_client/src/gui/ocr_capturer.py (이 코드로 전체 교체)
import sys
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QGuiApplication

class OcrCapturer(QWidget):
    """화면의 특정 영역을 캡처하기 위한 반투명 오버레이 위젯입니다."""
    region_selected = Signal(QRect)
    # [버그 수정] 창이 닫힐 때 발생하는 시그널을 명시적으로 정의합니다.
    finished = Signal()

    def __init__(self):
        super().__init__()
        # 모든 모니터를 포함하는 가상 데스크톱의 전체 크기를 가져옵니다.
        geometry = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geometry)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.start_point = None
        self.end_point = None

    def keyPressEvent(self, event):
        # ESC 키를 누르면 캡처를 취소하고 창을 닫습니다.
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def mousePressEvent(self, event):
        self.start_point = event.position().toPoint()
        self.end_point = self.start_point
        self.update()

    def mouseMoveEvent(self, event):
        self.end_point = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event):
        self.close()
        # 선택된 영역이 유효한지 확인하고 시그널을 보냅니다.
        capture_rect = QRect(self.start_point, self.end_point).normalized()
        if capture_rect.width() > 10 and capture_rect.height() > 10:
            self.region_selected.emit(capture_rect)

    def paintEvent(self, event):
        painter = QPainter(self)
        # 전체 화면을 50% 투명도의 검은색으로 덮습니다.
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))

        if self.start_point and self.end_point:
            selection_rect = QRect(self.start_point, self.end_point).normalized()
            # 선택된 영역은 투명하게 만듭니다 (배경을 지웁니다).
            painter.eraseRect(selection_rect)
            # 선택 영역 테두리를 그립니다.
            painter.setPen(QPen(QColor(0, 120, 215, 255), 2, Qt.PenStyle.SolidLine))
            painter.drawRect(selection_rect)

    def closeEvent(self, event):
        """창이 닫힐 때 'finished' 시그널을 발생시킵니다."""
        self.finished.emit()
        super().closeEvent(event)