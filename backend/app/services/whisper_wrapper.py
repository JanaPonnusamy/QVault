
from faster_whisper import WhisperModel


class WhisperWrapper:

    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            cls._model = WhisperModel(
                "base",
                device="cpu",
                compute_type="int8"
            )
        return cls._model

    @classmethod
    def transcribe_file(cls, audio_path):
        model = cls.get_model()
        segments, info = model.transcribe(audio_path)

        lines = []
        for segment in segments:
            lines.append(segment.text.strip())

        return "\n".join(lines)
