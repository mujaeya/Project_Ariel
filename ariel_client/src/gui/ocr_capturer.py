# ariel_client/src/gui/ocr_capturer.py (이 코드로 전체 교체)
import logging
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, Signal, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QGuiApplication

logger = logging.getLogger(__name__)

class OcrCapturer(QWidget):
    """화면의 특정 영역을 캡처하기 위한 반투명 오버레이 위젯입니다."""
    region_selected = Signal(QRect)
    # [수정] 창이 닫힐 때 발생하는 시그널들을 명시적으로 정의합니다.
    finished = Signal()
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__()
        # 모든 모니터를 포함하는 가상 데스크톱의 전체 크기를 가져옵니다.
        screens = QGuiApplication.screens()
        if not screens:
            raise RuntimeError("사용 가능한 화면을 찾을 수 없습니다.")
        
        # 모든 화면을 포함하는 가상 지오메트리 계산
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
            self.hide() # 즉시 숨겨서 뒷 배경이 보이도록 함
            
            capture_rect = QRect(self.start_point, self.end_point).normalized()
            
            # 너무 작은 영역은 무시
            if capture_rect.width() > 10 and capture_rect.height() > 10:
                logger.info(f"OCR 영역 선택 완료: {capture_rect}")
                self.region_selected.emit(capture_rect)
            else:
                logger.info("선택한 영역이 너무 작아 무시합니다.")
                self.cancelled.emit() # 유효하지 않은 선택도 취소로 간주
            
            self.close() # 작업 완료 후 창 닫기

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 전체 화면을 50% 투명도의 검은색으로 덮습니다.
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))

        if not self.start_point.isNull() and not self.end_point.isNull():
            selection_rect = QRect(self.start_point, self.end_point).normalized()
            
            # 선택된 영역은 투명하게 만듭니다 (배경을 지웁니다).
            painter.eraseRect(selection_rect)
            
            # 선택 영역 테두리를 그립니다.
            pen = QPen(QColor(0, 120, 215, 255), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(selection_rect)

    def closeEvent(self, event):
        """창이 어떤 이유로든 닫힐 때 finished 시그널을 보냅니다."""
        self.finished.emit()
        super().closeEvent(event)