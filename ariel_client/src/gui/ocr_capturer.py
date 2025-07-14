# ariel_client/src/gui/ocr_capturer.py (이 코드로 전체 교체)
import logging
from PySide6.QtWidgets import QWidget, QRubberBand
from PySide6.QtCore import Qt, QRect, Signal, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QGuiApplication, QPaintEvent

logger = logging.getLogger(__name__)

class OcrCapturer(QWidget):
    """화면의 특정 영역을 캡처하기 위한 반투명 오버레이 위젯입니다."""
    region_selected = Signal(QRect)
    finished = Signal()
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__()
        screens = QGuiApplication.screens()
        if not screens:
            raise RuntimeError("사용 가능한 화면을 찾을 수 없습니다.")
        
        virtual_desktop_rect = QRect()
        for screen in screens:
            virtual_desktop_rect = virtual_desktop_rect.united(screen.geometry())

        self.setGeometry(virtual_desktop_rect)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.start_point = QPoint()
        self.end_point = QPoint()
        self._is_selecting = False

    def keyPressEvent(self, event):
        """ESC 키를 누르면 캡처를 취소합니다."""
        if event.key() == Qt.Key.Key_Escape:
            logger.info("OCR 캡처가 사용자에 의해 취소되었습니다.")
            self.cancelled.emit()
            self.close()
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_selecting = True
            self.start_point = event.position().toPoint()
            self.end_point = self.start_point
            self.update()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self.end_point = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            self.hide()
            
            capture_rect = QRect(self.start_point, self.end_point).normalized()
            
            if capture_rect.width() > 5 and capture_rect.height() > 5:
                logger.info(f"OCR 영역 선택 완료: {capture_rect}")
                self.region_selected.emit(capture_rect)
            else:
                logger.warning("선택한 영역이 너무 작아 무시합니다.")
                self.cancelled.emit()
            
            self.close()

    def paintEvent(self, event: QPaintEvent):
        """화면을 반투명하게 덮고 선택 영역만 밝게 표시합니다."""
        painter = QPainter(self)
        
        # 전체 화면을 반투명 검은색(alpha=120)으로 덮습니다.
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        
        # 선택된 영역을 가져옵니다.
        selection_rect = QRect(self.start_point, self.end_point).normalized()
        
        if self._is_selecting and not selection_rect.isNull():
            # 해당 영역의 반투명 레이어를 지워서 원래 화면이 보이게 합니다.
            painter.eraseRect(selection_rect)
            
            # 선택 영역 주위에 1px짜리 하얀색 테두리를 그립니다.
            pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(selection_rect)

    def closeEvent(self, event):
        """창이 어떤 이유로든 닫힐 때 finished 시그널을 보냅니다."""
        self.finished.emit()
        super().closeEvent(event)