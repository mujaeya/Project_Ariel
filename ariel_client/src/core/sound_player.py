# ariel_client/src/core/sound_player.py (이 코드로 전체 교체)
import logging
from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtMultimedia import QSoundEffect

from ..utils import resource_path

class SoundPlayer(QObject):
    """
    [비동기 로딩 처리] 지정된 오디오 파일을 안정적으로 재생하는 유틸리티 클래스.
    QSoundEffect의 비동기 로딩 문제를 해결합니다.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # 여러 사운드를 동시에 재생할 수 있도록 각 파일 경로에 대해 별도의 인스턴스를 관리합니다.
        self.sound_effects = {}

    def play(self, file_path: str, volume: float = 1.0):
        """
        지정된 경로의 사운드를 재생합니다.
        내부적으로 로딩 상태를 확인하여, 로딩이 완료된 후에만 재생을 시도합니다.
        """
        if not file_path:
            return

        try:
            # resource_path를 통해 절대 경로 획득
            absolute_path = resource_path(file_path)

            # 이전에 로드한 적 없는 새로운 사운드인 경우에만 인스턴스를 생성하고 로드합니다.
            if absolute_path not in self.sound_effects:
                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(absolute_path))
                
                # [핵심] 여기서 play()를 바로 호출하지 않습니다.
                # 대신, statusChanged 시그널을 사용하여 로딩 상태를 감지합니다.
                # 하지만, 즉시 재생을 시도해야 하므로 로딩이 완료되면 재생될 수 있도록 합니다.
                # 인스턴스를 딕셔너리에 저장합니다.
                self.sound_effects[absolute_path] = effect
            
            effect = self.sound_effects[absolute_path]
            effect.setVolume(min(max(0.0, volume), 1.0))

            # [핵심 로직] 로딩 상태에 따라 다르게 처리
            if effect.status() == QSoundEffect.Status.Ready:
                # 로딩이 이미 완료된 상태라면 즉시 재생합니다.
                effect.play()
            elif effect.status() == QSoundEffect.Status.Loading:
                # 로딩 중이라면, 로딩이 끝났을 때 재생되도록 슬롯을 연결합니다.
                # 단, 한 번만 연결되도록 기존 연결을 끊고 다시 연결합니다.
                try:
                    effect.statusChanged.disconnect(self._play_when_ready)
                except RuntimeError:
                    pass # 연결이 없으면 오류 발생, 무시
                effect.statusChanged.connect(self._play_when_ready)
            elif effect.status() == QSoundEffect.Status.Error:
                 logging.error(f"알림음 파일 디코딩 오류 발생: '{absolute_path}'. 파일 형식을 확인해주세요 (권장: 44100Hz, 16-bit PCM WAV).")
            else: # Null 상태 등
                 # 로드를 시작하지 않은 상태일 수 있으므로 로드를 시도합니다.
                 effect.setSource(QUrl.fromLocalFile(absolute_path))


        except Exception as e:
            logging.error(f"알림음 재생 중 예외 발생: '{file_path}'. 오류: {e}", exc_info=True)

    @Slot()
    def _play_when_ready(self):
        """
        QSoundEffect의 상태가 Ready로 변경되었을 때만 play()를 호출하는 슬롯.
        """
        # 시그널을 보낸 sender(QSoundEffect 인스턴스)를 가져옵니다.
        effect = self.sender()
        if not effect:
            return

        if effect.status() == QSoundEffect.Status.Ready:
            logging.info(f"알림음 로드 완료, 재생 시작: {effect.source().toLocalFile()}")
            effect.play()
            # 재생 후에는 더 이상 시그널을 받을 필요가 없으므로 연결을 끊습니다.
            try:
                effect.statusChanged.disconnect(self._play_when_ready)
            except RuntimeError:
                pass
        elif effect.status() == QSoundEffect.Status.Error:
            logging.error(f"알림음 파일 비동기 로딩 중 오류: {effect.source().toLocalFile()}")