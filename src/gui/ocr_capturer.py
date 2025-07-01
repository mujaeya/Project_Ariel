# src/gui/ocr_capturer.py (이 코드로 전체 교체)
import sys
from PySide6.QtWidgets import QWidget, QApplication, QMessageBox
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QColor
import mss
from PIL import Image
import pytesseract
import logging

class OcrCapturer(QWidget):
    """
    화면의 특정 영역을 캡처하고 OCR을 통해 텍스트를 추출하는 위젯.
    (Pillow 대신 mss 라이브러리를 사용하여 안정성 향상)
    """
    text_captured = Signal(str)

    def __init__(self, tesseract_cmd_path=None):
        super().__init__()

        if tesseract_cmd_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(self.screen_geometry)

        self.begin = QPoint()
        self.end = QPoint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if not self.begin.isNull() and not self.end.isNull():
            selection_rect = QRect(self.begin, self.end).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selection_rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            
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
        self.close()
        self.capture_screen()

    def capture_screen(self):
        """선택된 영역을 캡처하고 텍스트를 추출합니다. (mss 라이브러리 사용)"""
        selection_rect = QRect(self.begin, self.end).normalized()
        dpr = self.devicePixelRatioF()
        
        capture_rect = {
            "top": int(selection_rect.y() * dpr),
            "left": int(selection_rect.x() * dpr),
            "width": int(selection_rect.width() * dpr),
            "height": int(selection_rect.height() * dpr)
        }
        
        # 너비나 높이가 0이면 캡처 시도 안 함
        if capture_rect["width"] <= 0 or capture_rect["height"] <= 0:
            logging.warning("선택된 영역이 없어 OCR 캡처를 건너뜁니다.")
            return

        try:
            with mss.mss() as sct:
                sct_img = sct.grab(capture_rect)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            extracted_text = pytesseract.image_to_string(img, lang='kor+eng')
            
            if extracted_text.strip():
                logging.info(f"OCR 추출 텍스트: {extracted_text.strip()}")
                self.text_captured.emit(extracted_text.strip())
            else:
                logging.info("OCR: 텍스트를 찾지 못했습니다.")

        except FileNotFoundError:
            logging.error("OCR 오류: Tesseract를 찾을 수 없습니다.")
            QMessageBox.critical(self, "OCR 오류", "Tesseract를 찾을 수 없습니다.\n설정에서 tesseract.exe 경로를 올바르게 지정했는지 확인해주세요.")
        except Exception as e:
            error_msg = str(e)
            logging.error(f"OCR 캡처 중 오류 발생: {error_msg}")
            # [핵심] 상세한 권한 오류 안내
            if "access" in error_msg.lower() or "denied" in error_msg.lower() or "[WinError 5]" in error_msg:
                 QMessageBox.critical(self, "OCR 권한 오류",
                                     "화면을 캡처할 수 없습니다 (Access is denied).\n\n"
                                     "이 문제는 주로 다른 프로그램이 화면 보호 기능을 사용 중일 때 발생합니다.\n"
                                     "실행 중인 보안 프로그램, 안티 바이러스, 게임의 안티치트 등을 확인해주세요.")
            else:
                 QMessageBox.critical(self, "OCR 오류", f"화면 번역 중 예기치 않은 오류가 발생했습니다:\n{error_msg}")