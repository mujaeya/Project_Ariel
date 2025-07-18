# ariel_client/src/api_client.py (수정 후)
import logging
import requests

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, base_url: str):
        if not base_url:
            raise ValueError("API 서버의 URL이 설정되지 않았습니다.")
        self.base_url = base_url
        self.session = requests.Session()
        logger.info(f"API 클라이언트가 서버({self.base_url})를 대상으로 초기화되었습니다.")

    def stt(self, audio_bytes: bytes, model_name: str) -> str:
        """
        오디오 데이터를 백엔드 서버로 보내고, STT 텍스트 결과를 받아옵니다.
        """
        try:
            stt_url = f"{self.base_url}/api/v1/stt"

            # [수정] 백엔드 엔드포인트의 파라미터 이름('audio_file')과 정확히 일치시킵니다.
            files = {'audio_file': ('recorded_audio.wav', audio_bytes, 'audio/wav')}
            # 참고: 현재 백엔드는 'model' 파라미터를 사용하지 않으나, 추후 확장을 위해 data 필드를 유지합니다.
            data = {'model': model_name} 

            logger.debug(f"STT API 요청 전송: model={model_name}")
            response = self.session.post(stt_url, files=files, data=data, timeout=20)
            response.raise_for_status()

            result = response.json()
            text = result.get("text", "")
            logger.info(f"STT 결과 수신: '{text}'")
            return text

        except requests.exceptions.RequestException as e:
            logger.error(f"STT API 요청 실패: {e}", exc_info=True)
            return ""
        except Exception as e:
            logger.error(f"STT 응답 처리 중 알 수 없는 오류 발생: {e}", exc_info=True)
            return ""

    def ocr(self, image_bytes: bytes) -> str:
        """
        이미지 데이터를 백엔드 서버로 보내고, OCR 텍스트 결과를 받아옵니다.
        (참고: 현재 TranslationWorker는 이 함수 대신 로컬 pytesseract를 사용하고 있습니다.)
        """
        try:
            ocr_url = f"{self.base_url}/api/v1/ocr"
            files = {'image_file': ('capture.png', image_bytes, 'image/png')}
            
            logger.debug("OCR API 요청 전송")
            response = self.session.post(ocr_url, files=files, timeout=10)
            response.raise_for_status()

            result = response.json()
            text = result.get("text", "")
            logger.info(f"OCR 결과 수신: '{text}'")
            return text
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OCR API 요청 실패: {e}", exc_info=True)
            return ""
        except Exception as e:
            logger.error(f"OCR 응답 처리 중 알 수 없는 오류 발생: {e}", exc_info=True)
            return ""