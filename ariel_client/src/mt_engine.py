# ariel_client/src/mt_engine.py (이 코드로 전체 교체)
import deepl
# [수정] 상대 경로로 변경
from .config_manager import ConfigManager

class MTEngine:
    """
    DeepL API를 사용하여 텍스트를 번역합니다.
    """
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.api_key = self.config_manager.get("deepl_api_key")

        if not self.api_key:
            raise ValueError("DeepL API 키가 설정되지 않았습니다.")

        try:
            self.translator = deepl.Translator(self.api_key)
            # API 키 유효성 검사를 위해 간단한 호출 실행
            self.translator.get_usage().character
        except Exception as e:
            raise ConnectionError(f"DeepL 번역기 초기화 실패: {e}. API 키가 유효한지 확인하세요.")

    def translate_text_multi(self, text: str, target_langs: list, **kwargs) -> dict:
        """
        주어진 텍스트를 여러 목표 언어로 동시에 번역합니다.
        """
        if not text or not isinstance(text, str) or not target_langs:
            return {}

        results = {}
        try:
            for lang in target_langs:
                # DeepL API는 formality 등 추가 옵션을 지원할 수 있음
                result = self.translator.translate_text(text, target_lang=lang, **kwargs)
                results[lang] = result.text
            return results

        except deepl.DeepLException as e:
            print(f"DeepL API 다중 번역 오류: {e}")
            return {lang: "[번역 오류]" for lang in target_langs}
        except Exception as e:
            print(f"번역 중 예기치 않은 오류 발생: {e}")
            return {lang: "[번역 중 오류 발생]" for lang in target_langs}