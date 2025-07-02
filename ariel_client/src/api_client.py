# ariel_client/src/api_client.py (새 파일)
import requests
import logging

class ApiClient:
    def __init__(self, base_url: str):
        if not base_url:
            raise ValueError("API 서버의 URL이 설정되지 않았습니다.")
        self.base_url = base_url
        logging.info(f"API 클라이언트가 서버({self.base_url})를 대상으로 초기화되었습니다.")

    def send_image_for_ocr(self, image_bytes: bytes) -> str | None:
        """
        이미지 데이터를 백엔드 서버로 보내고, OCR 텍스트 결과를 받아옵니다.
        """
        try:
            files = {'image_file': ('capture.png', image_bytes, 'image/png')}
            response = requests.post(f"{self.base_url}/api/v1/ocr", files=files, timeout=10)

            if response.status_code == 200:
                result = response.json()
                logging.info(f"OCR 결과 수신: {result.get('text')}")
                return result.get("text")
            else:
                logging.error(f"OCR 서버 오류: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"OCR API 요청 실패: {e}")
            return None

    def send_audio_for_stt(self, audio_bytes: bytes) -> str | None:
        """
        오디오 데이터(WAV)를 백엔드 서버로 보내고, STT 텍스트 결과를 받아옵니다.
        """
        try:
            # 파일 이름은 API 요구사항에 따라 아무거나 지정해도 괜찮습니다.
            files = {'audio_file': ('recorded_audio.wav', audio_bytes, 'audio/wav')}
            response = requests.post(f"{self.base_url}/api/v1/stt", files=files, timeout=20) # 타임아웃을 넉넉하게 설정

            if response.status_code == 200:
                result = response.json()
                logging.info(f"STT 결과 수신: {result.get('text')}")
                return result.get("text")
            else:
                logging.error(f"STT 서버 오류: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"STT API 요청 실패: {e}")
            return None

    # STT(음성인식)를 위한 웹소켓 통신 기능은 나중에 여기에 추가됩니다.