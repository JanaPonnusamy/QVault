class OCRService:
    """Reads on-screen text from video frames with RapidOCR (ONNX, pip-only,
    no external binary). The model loads lazily on first use and is shared
    process-wide, mirroring the WhisperWrapper singleton pattern."""

    ENGINE_VERSION = "rapidocr-onnxruntime-1.4.4"

    MIN_CONFIDENCE = 0.5

    _engine = None

    @classmethod
    def get_engine(cls):
        if cls._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            cls._engine = RapidOCR()

        return cls._engine

    @classmethod
    def read_frame(cls, image_path):
        """Returns the recognized text lines (confidence-filtered) for one frame."""

        engine = cls.get_engine()

        result, _ = engine(str(image_path))

        if not result:
            return []

        lines = []

        for item in result:
            # RapidOCR items: [box, text, confidence]
            if len(item) < 3:
                continue

            text = (item[1] or "").strip()
            confidence = float(item[2] or 0)

            if text and confidence >= cls.MIN_CONFIDENCE:
                lines.append(text)

        return lines

    @classmethod
    def read_frames(cls, frame_paths):
        """OCRs every frame and returns deduplicated text lines in first-seen
        order, so repeated static overlays (channel names, watermarks) appear once."""

        seen = set()
        unique_lines = []

        for frame_path in frame_paths:
            for line in cls.read_frame(frame_path):
                key = line.lower()

                if key in seen:
                    continue

                seen.add(key)
                unique_lines.append(line)

        return unique_lines
