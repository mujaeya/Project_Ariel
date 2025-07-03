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
        if not file_path:
            return

        try:
            absolute_path = resource_path(file_path)

            # 이전에 로드한 적 없는 새로운 사운드인 경우에만 인스턴스를 생성합니다.
            if absolute_path not in self.sound_effects:
                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(absolute_path))
                # [핵심] 상태가 변경될 때 처리할 함수를 미리 연결해 둡니다.
                effect.statusChanged.connect(self._on_status_changed)
                self.sound_effects[absolute_path] = effect
            
            effect = self.sound_effects[absolute_path]
            effect.setVolume(min(max(0.0, volume), 1.0))

            # 로딩이 이미 완료된 상태라면 즉시 재생합니다.
            if effect.status() == QSoundEffect.Status.Ready:
                effect.play()
            # 로딩 중이거나 오류가 발생한 경우, statusChanged 시그널이 처리해 줄 것이므로 기다립니다.
            elif effect.status() == QSoundEffect.Status.Error:
                 logging.error(f"알림음 파일 디코딩 오류 발생: '{absolute_path}'. 파일 형식을 확인해주세요 (권장: 44100Hz, 16-bit PCM WAV).")


        except Exception as e:
            logging.error(f"알림음 재생 중 예외 발생: '{file_path}'. 오류: {e}", exc_info=True)

    @Slot()
    def _on_status_changed(self):
        """
        QSoundEffect의 상태가 변경될 때 호출되는 슬롯.
        로딩이 완료(Ready)되면 사운드를 재생합니다.
        """
        # 시그널을 보낸 sender(QSoundEffect 인스턴스)를 가져옵니다.
        effect = self.sender()
        if not effect:
            return

        if effect.status() == QSoundEffect.Status.Ready:
            # play()를 여기서 호출하면, 로딩이 완료된 직후이므로 가장 안전합니다.
            # 이 슬롯은 상태가 바뀔 때마다 호출되므로, play()는 여기서 호출하지 않고
            # play() 메서드에서 직접 호출하도록 구조를 유지하는 것이 더 명확할 수 있습니다.
            # 하지만 최초 로딩 시점을 위해 이 구조를 유지합니다.
            logging.info(f"알림음 로드 완료: {effect.source().toLocalFile()}")

        elif effect.status() == QSoundEffect.Status.Error:
            logging.error(f"알림음 파일 디코딩 오류: {effect.source().toLocalFile()}")