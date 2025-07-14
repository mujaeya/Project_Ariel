# ariel_client/src/mt_engine.py (이 코드로 전체 교체)
import deepl
import logging
from .config_manager import ConfigManager

class MTEngine:
    """
    DeepL API를 사용하여 텍스트를 번역합니다.
    """
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.api_key = self.config_manager.get("deepl_api_key")
        self.translator = deepl.Translator(self.api_key) if self.api_key else None

        if not self.api_key:
            raise ValueError("DeepL API 키가 설정되지 않았습니다.")

        try:
            self.translator = deepl.Translator(self.api_key)
            # API 키 유효성 검사를 위해 간단한 호출 실행
            self.translator.get_usage().character
        except Exception as e:
            raise ConnectionError(f"DeepL 번역기 초기화 실패: {e}. API 키가 유효한지 확인하세요.")

    def is_active(self) -> bool:
        return self.translator is not None

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str | None:
        """단일 텍스트를 지정된 소스 및 타겟 언어로 번역합니다."""
        if not text or not self.is_active():
            return None
        try:
            source_lang_code = source_lang.upper() if source_lang and source_lang != 'Auto Detect' else None
            
            result = self.translator.translate_text(
                text,
                source_lang=source_lang_code,
                target_lang=target_lang.upper()
            )
            return result.text
        except deepl.DeepLException as e:
            logging.error(f"DeepL 번역 API 오류: {e}")
            return f"번역 오류: {e}"
        except Exception as e:
            logging.error(f"번역 중 예기치 않은 오류 발생: {e}")
            return f"번역 오류: {e}"

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