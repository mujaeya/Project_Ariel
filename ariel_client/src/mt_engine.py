# ariel_client/src/mt_engine.py (이 코드로 전체 교체)
import deepl
import logging
from .config_manager import ConfigManager

logger = logging.getLogger("root")

class MTEngine:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._translator = None
        self.usage = None

    def _get_translator(self):
        """API 키를 사용하여 DeepL 번역기 인스턴스를 생성하거나 캐시된 인스턴스를 반환합니다."""
        if self._translator is None:
            api_key = self.config_manager.get("deepl_api_key")
            if not api_key:
                logger.error("DeepL API 키가 설정되지 않았습니다.")
                return None
            try:
                self._translator = deepl.Translator(api_key)
                logger.info("DeepL 번역기 인스턴스가 성공적으로 생성되었습니다.")
            except Exception as e:
                logger.error(f"DeepL 번역기 생성 실패: {e}", exc_info=True)
                return None
        return self._translator

    def translate_text(self, text, source_lang=None, target_lang='EN-US'):
        """
        주어진 텍스트를 번역합니다. 단일 문자열 또는 문자열 리스트를 처리할 수 있습니다.
        [수정] deepl.TextResult 객체가 아닌, 실제 텍스트(str)를 반환하도록 수정합니다.
        """
        translator = self._get_translator()
        if not translator:
            # 번역기 초기화 실패 시 원본 텍스트나 None을 반환할 수 있습니다.
            # 여기서는 원본 텍스트를 그대로 반환하도록 처리합니다.
            return text if isinstance(text, str) else [str(t) for t in text]

        if target_lang and target_lang.upper() == 'EN':
            target_lang = 'EN-US'
            logger.debug("번역 대상 언어 'EN'을 'EN-US'로 조정했습니다.")

        try:
            result = translator.translate_text(
                text,
                source_lang=source_lang,
                target_lang=target_lang
            )

            # [핵심 수정] 결과가 리스트인지 단일 객체인지 확인하고 .text 속성을 추출합니다.
            if isinstance(result, list):
                return [r.text for r in result]
            elif result:
                return result.text
            else:
                return None

        except deepl.DeepLException as e:
            logger.error(f"DeepL 번역 API 오류: {e}")
            if "target_lang" in str(e):
                logger.error("잘못된 'target_lang' 코드일 수 있습니다. 설정을 확인해주세요.")
            return None
        except Exception as e:
            logger.error(f"번역 중 알 수 없는 오류 발생: {e}", exc_info=True)
            return None

    def get_usage(self):
        """현재 DeepL API 사용량 정보를 가져옵니다."""
        translator = self._get_translator()
        if translator:
            try:
                self.usage = translator.get_usage()
                return self.usage
            except deepl.DeepLException as e:
                logger.error(f"DeepL 사용량 조회 실패: {e}")
                return None
        return None