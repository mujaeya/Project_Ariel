# src/languages.py (새 파일)
LANGUAGES = {
    "ko": {
        "setup_window_title": "Ariel 설정",
        "profile_page_title": "프로필",
        "profile_page_nav_text": "프로필",
        "api_page_title": "연동 서비스",
        "api_page_nav_text": "연동 서비스",
        # ... 다른 모든 UI 텍스트 추가 ...
    },
    "en": {
        "setup_window_title": "Ariel Settings",
        "profile_page_title": "Profiles",
        "profile_page_nav_text": "Profiles",
        "api_page_title": "API & Services",
        "api_page_nav_text": "API & Services",
        # ...
    }
}

class Translator:
    def __init__(self, language_code="ko"):
        self.lang = LANGUAGES.get(language_code, LANGUAGES["en"])

    def tr(self, key):
        return self.lang.get(key, key) # 번역이 없으면 키 자체를 반환