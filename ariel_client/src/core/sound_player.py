# ariel_client/src/core/sound_player.py (이 코드로 전체 교체)
import logging
from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtMultimedia import QSoundEffect

from ..config_manager import ConfigManager
from ..utils import resource_path

logger = logging.getLogger(__name__)

class SoundPlayer(QObject):
    """
    설정과 연동하여 알림음 볼륨을 적용하고,
    지정된 오디오 파일을 안정적으로 재생하는 유틸리티 클래스.
    """
    def __init__(self, config_manager: ConfigManager, parent: QObject | None = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.sound_effects = {}
        self.update_volume() # [추가] 초기 볼륨 설정

    def play(self, sound_path_key: str):
        """
        설정 키에 해당하는 사운드 파일 경로를 찾아 현재 볼륨을 적용하여 재생합니다.
        sound_path_key: config에 저장된 사운드 파일의 키 (예: "sound_stt_start")
        """
        sound_path = self.config_manager.get(sound_path_key)

        if not sound_path:
            logger.warning(f"Sound key '{sound_path_key}' not found in settings.")
            return

        try:
            absolute_path = resource_path(sound_path)

            if absolute_path not in self.sound_effects:
                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(absolute_path))
                effect.statusChanged.connect(self._play_when_ready)
                self.sound_effects[absolute_path] = effect
            
            effect = self.sound_effects[absolute_path]
            
            # [수정] 볼륨 설정은 update_volume 슬롯에서 중앙 관리하므로 여기서는 설정만 확인
            volume_float = max(0.0, min(1.0, self.current_volume / 100.0))
            effect.setVolume(volume_float)

            if effect.status() == QSoundEffect.Status.Ready:
                effect.play()
            elif effect.status() == QSoundEffect.Status.Error:
                 logger.error(f"Error decoding sound file: '{absolute_path}'.")

        except Exception as e:
            logger.error(f"Exception while playing sound '{sound_path_key}': {e}", exc_info=True)

    @Slot()
    def update_volume(self):
        """[추가] 설정 파일에서 현재 볼륨 값을 읽어와 모든 사운드 이펙트에 적용합니다."""
        # [수정] 설정 키 변경: sound_master_volume -> notification_volume
        self.current_volume = self.config_manager.get("notification_volume", 80)
        volume_float = max(0.0, min(1.0, self.current_volume / 100.0))
        
        for effect in self.sound_effects.values():
            effect.setVolume(volume_float)
        logger.debug(f"Sound volume updated to: {self.current_volume}%")


    @Slot()
    def _play_when_ready(self):
        """QSoundEffect의 상태가 Ready로 변경되었을 때만 play()를 호출하는 슬롯."""
        effect = self.sender()
        if effect and isinstance(effect, QSoundEffect) and effect.status() == QSoundEffect.Status.Ready:
            logger.info(f"Sound loaded, playing: {effect.source().toLocalFile()}")
            effect.play()
            try:
                # [개선] 재생 후에는 더 이상 신호를 받을 필요가 없으므로 연결을 끊음
                effect.statusChanged.disconnect(self._play_when_ready)
            except (RuntimeError, TypeError):
                pass # 이미 끊어졌거나 유효하지 않은 객체면 무시