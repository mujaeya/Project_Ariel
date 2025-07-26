# ariel_client/src/constants.py

"""
프로젝트 전반에서 사용되는 언어 및 기타 상수들을 중앙에서 관리합니다.
"""

# 프로젝트에서 공식적으로 지원하는 언어 목록 (총 16개)
# 키: Qt가 사용하는 ISO 639-1 또는 639-2 코드 (UI 번역 파일명과 일치)
# 값:
#   - name_en: UI 언어 선택 드롭다운에 표시될 영어 이름
#   - name_native: UI 언어 선택 드롭다운에 표시될 원어 이름
#   - deepl_code: DeepL API가 번역을 위해 사용하는 언어 코드
_LANGUAGES = {
    "en": {"name_en": "English", "name_native": "English", "deepl_code": "EN"},
    "ko": {"name_en": "Korean", "name_native": "한국어", "deepl_code": "KO"},
    "ja": {"name_en": "Japanese", "name_native": "日本語", "deepl_code": "JA"},
    "ar": {"name_en": "Arabic", "name_native": "العربية", "deepl_code": "AR"},
    "cs": {"name_en": "Czech", "name_native": "Čeština", "deepl_code": "CS"},
    "de": {"name_en": "German", "name_native": "Deutsch", "deepl_code": "DE"},
    "el": {"name_en": "Greek", "name_native": "Ελληνικά", "deepl_code": "EL"},
    "es": {"name_en": "Spanish", "name_native": "Español", "deepl_code": "ES"},
    "fr": {"name_en": "French", "name_native": "Français", "deepl_code": "FR"},
    "he": {"name_en": "Hebrew", "name_native": "עברית", "deepl_code": "HE"},
    "id": {"name_en": "Indonesian", "name_native": "Bahasa Indonesia", "deepl_code": "ID"},
    "it": {"name_en": "Italian", "name_native": "Italiano", "deepl_code": "IT"},
    "pt": {"name_en": "Portuguese", "name_native": "Português", "deepl_code": "PT"},
    "ru": {"name_en": "Russian", "name_native": "Русский", "deepl_code": "RU"},
    "tr": {"name_en": "Turkish", "name_native": "Türkçe", "deepl_code": "TR"},
    "uk": {"name_en": "Ukrainian", "name_native": "Українська", "deepl_code": "UK"},
}

# UI 드롭다운에 일관된 순서로 표시하기 위해 영어 이름을 기준으로 정렬
LANGUAGES = dict(sorted(_LANGUAGES.items(), key=lambda item: item[1]['name_en']))

# STT/OCR 번역 언어 선택을 위한 목록
# DeepL 지원 언어 목록 (소스용 - 'Auto Detect' 포함)
DEEPL_LANGUAGES_SOURCE = {
    "Auto Detect": "auto",
    **{info["name_en"]: info["deepl_code"] for info in LANGUAGES.values()}
}

# DeepL 지원 언어 목록 (타겟용 - 'Auto Detect' 대신 'System Language' 포함)
DEEPL_LANGUAGES_TARGET = {
    "System Language": "auto",
    **{info["name_en"]: info["deepl_code"] for info in LANGUAGES.values()}
}

# UI 언어 선택을 위한 목록
UI_LANGUAGES = {
    "Auto Detect": "auto",
    **{f"{info['name_native']} ({info['name_en']})": code for code, info in LANGUAGES.items()}
}