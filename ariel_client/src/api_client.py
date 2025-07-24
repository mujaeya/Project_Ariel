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

# ariel_client/src/api_client.py

    def stt(self, audio_bytes: bytes, sample_rate: int, channels: int, model_size: str, client_id: str, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        [V12.2 수정] 오디오 데이터와 함께 모델 크기, 클라이언트 ID, 언어 코드를
        백엔드 서버로 보내고, STT 결과를 받아옵니다.
        """
        try:
            stt_url = f"{self.base_url}/api/v1/stt"
            files = {'audio_file': ('recorded_audio.wav', audio_bytes, 'audio/wav')}
            
            data = {
                'sample_rate': sample_rate,
                'channels': channels,
                'model_size': model_size,
                'client_id': client_id
            }

            if language and language != "auto":
                data['language'] = language.lower()

            logger.debug(f"STT API 요청 전송: url={stt_url}, data={data}")
            response = self.session.post(stt_url, files=files, data=data, timeout=20)
            response.raise_for_status()

            result = response.json()
            logger.info(f"STT 결과 수신: {result.get('text', '')[:30]}...")
            return result

        except requests.exceptions.ReadTimeout:
            logger.error(f"STT API 요청 시간 초과 (서버가 20초 내에 응답하지 않음). 백엔드 모델 사이즈나 성능을 확인하세요.")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"STT API 요청 실패: {e}")
            return None
        except Exception as e:
            logger.error(f"STT 응답 처리 중 알 수 없는 오류 발생: {e}")
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
            logger.error(f"OCR 응답 처리 중 알 수 없는 오류 발생: {e}")
            return None