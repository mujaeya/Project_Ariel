import logging
import requests

logger = logging.getLogger(__name__)

class APIClient: # 문제점 1: 클래스 이름을 APIClient로 수정 (대문자 C)
    """
    백엔드 API 서버와 통신(STT, OCR 등)을 담당하는 클라이언트입니다.
    """
    def __init__(self, base_url: str):
        if not base_url:
            raise ValueError("API 서버의 URL이 설정되지 않았습니다.")
        self.base_url = base_url
        # [개선] 여러 요청에 걸쳐 연결을 재사용하기 위해 Session 객체 사용
        self.session = requests.Session()
        logger.info(f"API 클라이언트가 서버({self.base_url})를 대상으로 초기화되었습니다.")

    def stt(self, audio_bytes: bytes, model_name: str) -> str:
        """
        오디오 데이터를 백엔드 서버로 보내고, STT 텍스트 결과를 받아옵니다.
        
        Args:
            audio_bytes (bytes): WAV 형식의 오디오 데이터
            model_name (str): 사용할 STT 모델 이름 (백엔드 전달용)

        Returns:
            str: 변환된 텍스트. 실패 시 빈 문자열.
        """
        # 문제점 2: 메서드 이름을 'stt'로 변경하고, worker에서 넘겨주는 model_name 인자 추가
        try:
            # 백엔드 API 엔드포인트
            stt_url = f"{self.base_url}/api/v1/stt"
            
            files = {'audio_file': ('recorded_audio.wav', audio_bytes, 'audio/wav')}
            # worker에서 받은 model_name을 백엔드로 전달할 수 있도록 data에 추가
            data = {'model': model_name}

            logger.debug(f"STT API 요청 전송: model={model_name}")
            # [개선] self.session을 사용하여 요청
            response = self.session.post(stt_url, files=files, data=data, timeout=20)

            # [개선] 200번대 성공 코드가 아니면 예외를 발생시켜 한번에 처리
            response.raise_for_status()

            result = response.json()
            text = result.get("text", "")
            logger.info(f"STT 결과 수신: '{text}'")
            return text

        except requests.exceptions.RequestException as e:
            logger.error(f"STT API 요청 실패: {e}", exc_info=True)
            return "" # 실패 시 빈 문자열 반환
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