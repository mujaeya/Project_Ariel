# ariel_client/src/api_client.py (이 코드로 전체 교체)
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, base_url: str):
        if not base_url:
            raise ValueError("API 서버의 URL이 설정되지 않았습니다.")
        self.base_url = base_url
        self.session = requests.Session()
        logger.info(f"API 클라이언트가 서버({self.base_url})를 대상으로 초기화되었습니다.")

    def stt(self, audio_bytes: bytes, channels: int, language: Optional[str] = None) -> str:
        """
        오디오 데이터, 채널 수, 그리고 언어 코드를 백엔드 서버로 보내고, STT 텍스트 결과를 받아옵니다.
        """
        try:
            stt_url = f"{self.base_url}/api/v1/stt"
            files = {'audio_file': ('recorded_audio.wav', audio_bytes, 'audio/wav')}
            data = {'channels': channels}

            if language:
                # [핵심 수정] API로 언어 코드를 보낼 때 항상 소문자로 변환합니다.
                data['language'] = language.lower()

            logger.debug(f"STT API 요청 전송: data={data}")
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