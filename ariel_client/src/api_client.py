# ariel_client/src/api_client.py
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, base_url: str):
        if not base_url:
            raise ValueError("API 서버의 URL이 설정되지 않았습니다.")
        self.base_url = base_url
        self.session = requests.Session()
        logger.info(f"API 클라이언트가 서버({self.base_url})를 대상으로 초기화되었습니다.")

    def stt(self, audio_bytes: bytes, language: str) -> Optional[Dict[str, Any]]:
        """
        오디오 데이터와 언어 코드를 백엔드 서버로 보내고, STT 결과를 받아옵니다.
        이 메소드는 새로운 백엔드 API 명세에 맞춰 수정되었습니다.
        """
        try:
            stt_url = f"{self.base_url}/api/v1/stt"
            # 백엔드는 'audio_file'과 'language' 두 파라미터를 기대합니다.
            files = {'audio_file': ('recorded_audio.wav', audio_bytes, 'audio/wav')}
            data = {'language': language}

            logger.debug(f"STT API 요청 전송: url={stt_url}, language={language}")
            # 백엔드 모델 로딩 시간을 고려하여 타임아웃을 20초로 유지합니다.
            response = self.session.post(stt_url, files=files, data=data, timeout=20)
            response.raise_for_status()

            result = response.json()
            # 로그에는 텍스트의 일부만 기록하여 과도한 로그 생성을 방지합니다.
            logger.info(f"STT 결과 수신: {result.get('text', '')[:30]}...")
            return result

        except requests.exceptions.ReadTimeout:
            logger.error(f"STT API 요청 시간 초과 (20초). 백엔드 서버 상태를 확인하세요.")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"STT API 요청 실패: {e}")
            return None
        except Exception as e:
            logger.error(f"STT 응답 처리 중 알 수 없는 오류 발생: {e}", exc_info=True)
            return None

    def ocr(self, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        이미지 데이터를 백엔드 서버로 보내고, OCR 결과를 받아옵니다.
        """
        try:
            ocr_url = f"{self.base_url}/api/v1/ocr"
            files = {'image_file': ('capture.png', image_bytes, 'image/png')}
            
            logger.debug("OCR API 요청 전송")
            response = self.session.post(ocr_url, files=files, timeout=10)
            response.raise_for_status()

            result = response.json()
            logger.info(f"OCR 결과 수신: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OCR API 요청 실패: {e}")
            return None
        except Exception as e:
            logger.error(f"OCR 응답 처리 중 알 수 없는 오류 발생: {e}", exc_info=True)
            return None