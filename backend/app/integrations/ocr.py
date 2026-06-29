from functools import lru_cache

from rapidocr_onnxruntime import RapidOCR


@lru_cache(maxsize=1)
def _engine() -> RapidOCR:
    return RapidOCR()


class OCR:
    @staticmethod
    def read_image_detailed(image_path: str) -> tuple[str, float]:
        result, _ = _engine()(image_path)
        if not result:
            return "", 0.0
        lines: list[str] = []
        scores: list[float] = []
        for line in result:
            if len(line) > 1 and line[1] and str(line[1]).strip():
                lines.append(str(line[1]).rstrip())
            if len(line) > 2:
                try:
                    scores.append(float(line[2]))
                except (TypeError, ValueError):
                    pass
        text = "\n".join(lines).strip()
        confidence = round(sum(scores) / len(scores), 4) if scores else 0.0
        return text, confidence

    @staticmethod
    def read_image(image_path: str) -> str:
        text, _ = OCR.read_image_detailed(image_path)
        return text
