import cv2
import numpy as np


def _load_gray(image_path: str, max_width: int = 800):
    img = cv2.imread(image_path)
    if img is None:
        return None, None
    h, w = img.shape[:2]
    if w > max_width:
        scale = max_width / w
        img = cv2.resize(img, (max_width, int(h * scale)))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img, gray


class FrameAnalyzer:
    @staticmethod
    def dhash(image_path: str, size: int = 8) -> str:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return ""
        resized = cv2.resize(img, (size + 1, size))
        diff = resized[:, 1:] > resized[:, :-1]
        bits = 0
        for value in diff.flatten():
            bits = (bits << 1) | int(value)
        return format(bits, "0{}x".format((size * size) // 4))

    @staticmethod
    def signature(image_path: str, size: int = 32):
        """Downscaled, normalised grayscale used for duplicate detection."""
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        return cv2.resize(img, (size, size)).astype(np.float32) / 255.0

    @staticmethod
    def difference(sig_a, sig_b) -> float:
        """Mean absolute difference (0 = identical). Sensitive to text changes,
        unlike a low-resolution hash which a uniform slide background dominates."""
        if sig_a is None or sig_b is None:
            return 1.0
        return float(np.abs(sig_a - sig_b).mean())

    @staticmethod
    def sharpness(image_path: str) -> float:
        """Laplacian variance -- higher means crisper edges (less blur)."""
        _, gray = _load_gray(image_path)
        if gray is None:
            return 0.0
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @staticmethod
    def is_blurred(image_path: str, threshold: float = 60.0) -> bool:
        """Standard Laplacian-variance blur test (lower variance = blurrier)."""
        return FrameAnalyzer.sharpness(image_path) < threshold

    @staticmethod
    def is_blank(image_path: str, std_threshold: float = 4.0) -> bool:
        """A near-solid-color frame (blank slide transition, black/white flash)
        has almost no pixel-intensity variation."""
        _, gray = _load_gray(image_path)
        if gray is None:
            return True
        return float(gray.std()) < std_threshold

    @staticmethod
    def question_probability(image_path: str) -> float:
        """Estimate the probability a frame contains a question/text slide.

        Pure image analysis: text-region density (MSER), background uniformity,
        edge density and color saturation. No OCR, no ML.
        """
        color, gray = _load_gray(image_path)
        if gray is None:
            return 0.0
        h, w = gray.shape
        area = float(h * w)

        # Text-like regions via MSER.
        text_boxes = 0
        try:
            mser = cv2.MSER_create()
            regions, _ = mser.detectRegions(gray)
            for region in regions:
                x, y, bw, bh = cv2.boundingRect(region.reshape(-1, 1, 2))
                if bh == 0:
                    continue
                aspect = bw / float(bh)
                box_area = bw * bh
                if 0.1 < aspect < 8 and 6 < bh < h * 0.12 and 20 < box_area < area * 0.04:
                    text_boxes += 1
        except cv2.error:
            text_boxes = 0
        text_score = min(text_boxes / 60.0, 1.0)

        # Background uniformity: fraction of pixels near the dominant intensity.
        # Slides sit on a uniform background (~0.5-0.9); photographic scenes are
        # far more spread out (~0.2-0.35). This is the strongest discriminator.
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
        bg_val = int(np.argmax(hist))
        lo, hi = max(0, bg_val - 18), min(256, bg_val + 19)
        bg_uniformity = float(hist[lo:hi].sum()) / area
        bg_score = float(np.clip((bg_uniformity - 0.30) / 0.50, 0.0, 1.0))

        # Low color saturation favours slides over photographic frames.
        hsv = cv2.cvtColor(color, cv2.COLOR_BGR2HSV)
        saturation = float(hsv[:, :, 1].mean()) / 255.0
        sat_score = 1.0 - min(saturation * 2.2, 1.0)

        score = 0.35 * text_score + 0.45 * bg_score + 0.20 * sat_score
        return round(float(np.clip(score, 0.0, 1.0)), 4)
