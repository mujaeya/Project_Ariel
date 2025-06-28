import deepl
from config_manager import ConfigManager

class MTEngine:
    """
    DeepL API의 formality 파라미터를 사용하여, 설정된 톤(반말/존댓말)으로 번역합니다.
    """
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.api_key = self.config_manager.get("deepl_api_key")

        if not self.api_key:
            raise ValueError("DeepL API 키가 config.json에 설정되지 않았습니다.")
            
        try:
            self.translator = deepl.Translator(self.api_key)
            self.translator.get_usage().character
        except Exception as e:
            raise ConnectionError(f"DeepL 번역기 초기화 실패: {e}. API 키가 유효한지 확인하세요.")

    @staticmethod
    def validate_api_key(api_key: str):
        """
        주어진 API 키가 유효한지 확인합니다.
        유효하지 않으면 예외를 발생시킵니다.
        """
        if not api_key:
            raise ValueError("API 키가 비어있습니다.")
        try:
            deepl.Translator(api_key).get_usage()
            return True
        except Exception as e:
            raise ConnectionError(f"API 키가 유효하지 않습니다: {e}")

    def translate_text_multi(self, text: str, target_langs: list, context: str = None, formality: str = "default") -> dict:
        """
        주어진 텍스트를 여러 목표 언어로 동시에, 설정된 formality에 맞춰 번역합니다.
        'formality' 인자가 명시적으로 추가되었습니다.
        """
        if not text or not isinstance(text, str) or not target_langs:
            return {}

        results = {}
        try:
            for lang in target_langs:
                try:
                    result = self.translator.translate_text(
                        text,
                        target_lang=lang,
                        context=context,
                        formality=formality
                    )
                except deepl.UnsupportedFormalityException:
                    print(f"정보: 언어 '{lang}'는 formality 설정을 지원하지 않아 기본값으로 번역합니다.")
                    result = self.translator.translate_text(
                        text,
                        target_lang=lang,
                        context=context
                    )
                
                results[lang] = result.text
            
            return results
            
        except deepl.DeepLException as e:
            print(f"DeepL API 다중 번역 오류: {e}")
            return {lang: f"[번역 오류]" for lang in target_langs}
        except Exception as e:
            print(f"번역 중 예기치 않은 오류 발생: {e}")
            return {lang: "[번역 중 오류 발생]" for lang in target_langs}