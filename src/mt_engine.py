import deepl
from config_manager import ConfigManager

class MTEngine:
    """
    DeepL API를 사용하여 텍스트를 번역하는 클래스.
    """
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.api_key = self.config_manager.get("deepl_api_key")
        
        # --- 수정된 부분 시작 ---
        raw_target_lang = self.config_manager.get("target_language")
        self.target_language = self._map_deprecated_languages(raw_target_lang)
        # --- 수정된 부분 끝 ---

        if not self.api_key:
            raise ValueError("DeepL API 키가 config.json에 설정되지 않았습니다.")
            
        try:
            self.translator = deepl.Translator(self.api_key)
            self.translator.get_target_languages()
        except Exception as e:
            raise ConnectionError(f"DeepL 번역기 초기화 실패: {e}. API 키가 유효한지 확인하세요.")

    def _map_deprecated_languages(self, lang_code: str) -> str:
        """
        DeepL에서 더 이상 사용되지 않는 언어 코드를 새 코드로 매핑합니다.
        (예: "EN" -> "EN-US")
        """
        # 대소문자 구분 없이 처리하기 위해 대문자로 변환
        code = lang_code.upper()
        
        # 매핑 테이블
        lang_map = {
            "EN": "EN-US",
            "PT": "PT-PT" 
            # 필요한 경우 다른 언어 추가
        }
        
        if code in lang_map:
            new_code = lang_map[code]
            print(f"정보: 목표 언어 코드 '{lang_code}'는 '{new_code}'(으)로 자동 변환되어 사용됩니다.")
            return new_code
            
        return lang_code # 매핑에 없으면 원래 코드 반환

    def translate_text(self, text: str) -> str:
        """
        주어진 텍스트를 목표 언어로 번역합니다.
        """
        if not text or not isinstance(text, str):
            return ""

        try:
            # 여기서는 self.target_language를 사용합니다.
            result = self.translator.translate_text(
                text,
                target_lang=self.target_language
            )
            return result.text
        except deepl.DeepLException as e:
            # 오류 메시지를 더 명확하게 변경
            print(f"DeepL API 오류: {e}. 입력 텍스트 또는 언어 코드를 확인하세요.")
            return f"[번역 오류]"
        except Exception as e:
            print(f"번역 중 예기치 않은 오류 발생: {e}")
            return "[번역 중 오류 발생]"


# --- 이 파일을 직접 실행하여 테스트하는 부분 (변경 없음) ---
if __name__ == '__main__':
    try:
        config = ConfigManager()
        mt_engine = MTEngine(config)

        test_sentences = [
            "Hello and welcome to the show.",
            "It's great to be here, thank you for having me.",
            "This is a test of the translation engine."
        ]
        
        target_lang = mt_engine.target_language # 수정된 언어 코드를 가져옴
        print(f"DeepL 번역 엔진 테스트 (실제 목표 언어: {target_lang})")
        print("="*40)
        
        for sentence in test_sentences:
            print(f"원본: {sentence}")
            translated = mt_engine.translate_text(sentence)
            print(f"번역: {translated}")
            print("-"*20)
            
    except (ValueError, ConnectionError, FileNotFoundError) as e:
        print(f"오류: {e}")