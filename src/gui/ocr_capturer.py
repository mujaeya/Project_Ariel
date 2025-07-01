# src/gui/ocr_capturer.py (새 파일)
import sys
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QColor, QScreen
from PIL import ImageGrab
import pytesseract

class OcrCapturer(QWidget):
    """
    화면의 특정 영역을 캡처하고 OCR을 통해 텍스트를 추출하는 위젯.
    """
    text_captured = Signal(str)

    def __init__(self, tesseract_cmd_path=None):
        super().__init__()
        
        # Tesseract 실행 파일 경로 설정 (설치 경로에 따라 변경 필요)
        if tesseract_cmd_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) # 투명 배경
        self.setCursor(Qt.CursorShape.CrossCursor) # 십자 커서

        self.screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(self.screen_geometry)

        self.begin = QPoint()
        self.end = QPoint()

    def paintEvent(self, event):
        """선택 영역을 사각형으로 그립니다."""
        painter = QPainter(self)
        # 반투명한 검은색 배경
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        # 선택된 영역만 투명하게 만듦
        if not self.begin.isNull() and not self.end.isNull():
            selection_rect = QRect(self.begin, self.end).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selection_rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            
            # 선택 영역 테두리
            pen = QPen(Qt.GlobalColor.white, 2, Qt.PenStyle.SolidLine)
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
        self.close() # 영역 선택이 끝나면 창을 닫음
        self.capture_screen()

    def capture_screen(self):
        """선택된 영역을 캡처하고 텍스트를 추출합니다."""
        selection_rect = QRect(self.begin, self.end).normalized()
        
        # 다중 모니터를 고려하여 화면 배율(DPR) 적용
        dpr = self.devicePixelRatio()
        capture_rect = (
            selection_rect.x() * dpr,
            selection_rect.y() * dpr,
            (selection_rect.x() + selection_rect.width()) * dpr,
            (selection_rect.y() + selection_rect.height()) * dpr
        )

        try:
            img = ImageGrab.grab(bbox=capture_rect)
            # OCR 수행 (한국어+영어)
            extracted_text = pytesseract.image_to_string(img, lang='kor+eng')
            
            if extracted_text.strip():
                print(f"OCR 추출 텍스트: {extracted_text.strip()}")
                self.text_captured.emit(extracted_text.strip())
            else:
                print("OCR: 텍스트를 찾지 못했습니다.")

        except FileNotFoundError:
            print("OCR 오류: Tesseract를 찾을 수 없습니다. 설치 경로를 확인하세요.")
            # 이 부분에 사용자에게 알림을 주는 로직 추가 가능 (예: QMessageBox)
        except Exception as e:
            print(f"OCR 캡처 중 오류 발생: {e}")