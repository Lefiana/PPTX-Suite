"""
core/image_processor.py
All image operations:
  • Multi-pass OpenCV face detection with strict sanity guards
  • Aspect-ratio-correct cropping driven by layout_config values
  • Manual face-centre override path
  • Placeholder generation for missing portrait files
  • PIL thumbnails for tkinter preview canvases
"""
from __future__ import annotations
import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

_DETECTION_PASSES = [
    (1.10, 6, (100, 100)),   # strict – high confidence
    (1.05, 4, (80,  80)),    # medium
    (1.05, 3, (50,  50)),    # loose  – last resort
]


class ImageProcessor:
    """Stateless helper; create once and reuse across the application."""

    def __init__(self) -> None:
        self._cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def crop_to_stream(
        self,
        image_path: str,
        target_ratio: float,
        fd_config: dict,
        manual_face_center: tuple | None = None,
    ) -> io.BytesIO:
        """
        Returns a BytesIO JPEG of the cropped portrait.

        Args:
            image_path:         Path to source image (or missing placeholder).
            target_ratio:       width / height from layout_config["portrait"].
            fd_config:          dict from layout_config["face_detection"].
            manual_face_center: (x, y) in original-image pixel coords, or None.
        """
        rgb = self._safe_open(image_path)
        if rgb is None:
            rgb = self._make_placeholder(target_ratio)

        img_w, img_h = rgb.size

        if manual_face_center is not None:
            best_face = self._face_from_manual(manual_face_center, img_w)
        else:
            best_face = self._detect_face(rgb, img_w, img_h, fd_config)

        cropped = self._apply_crop(rgb, best_face, img_w, img_h, target_ratio, fd_config)
        return self._to_jpeg_stream(cropped)

    def get_preview_pil(
        self,
        image_path: str,
        target_ratio: float,
        fd_config: dict,
        manual_face_center: tuple | None = None,
        preview_size: tuple = (280, 380),
    ) -> Image.Image:
        """Cropped portrait as a PIL Image sized for the tkinter preview label."""
        stream = self.crop_to_stream(image_path, target_ratio, fd_config, manual_face_center)
        img = Image.open(stream).convert("RGB")
        img.thumbnail(preview_size, Image.LANCZOS)
        return img

    def get_original_resized(
        self,
        image_path: str,
        max_size: tuple = (380, 500),
    ) -> Image.Image | None:
        """Full uncropped image scaled to max_size for the click canvas."""
        rgb = self._safe_open(image_path)
        if rgb is None:
            return None
        rgb.thumbnail(max_size, Image.LANCZOS)
        return rgb

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _safe_open(image_path: str) -> Image.Image | None:
        try:
            p = Path(image_path)
            if not p.exists():
                return None
            with Image.open(p) as img:
                return ImageOps.exif_transpose(img).convert("RGB")
        except Exception:
            return None

    @staticmethod
    def _make_placeholder(target_ratio: float) -> Image.Image:
        """Grey card used when the source image is missing."""
        w, h = 400, int(400 / target_ratio)
        img  = Image.new("RGB", (w, h), color=(210, 210, 210))
        draw = ImageDraw.Draw(img)
        text = "NO\nPHOTO"
        bbox = draw.textbbox((0, 0), text, align="center")
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((w - tw) // 2, (h - th) // 2), text, fill=(130, 130, 130), align="center")
        return img

    def _detect_face(
        self,
        rgb: Image.Image,
        img_w: int,
        img_h: int,
        fd_config: dict,
    ) -> tuple | None:
        min_frac = fd_config.get("min_face_fraction", 0.08)
        max_frac = fd_config.get("max_face_fraction", 0.80)
        h_margin = fd_config.get("horizontal_margin",  0.15)
        v_limit  = fd_config.get("vertical_limit",     0.60)

        gray = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2GRAY)

        for scale, neighbours, min_sz in _DETECTION_PASSES:
            faces = self._cascade.detectMultiScale(
                gray, scaleFactor=scale, minNeighbors=neighbours, minSize=min_sz,
            )
            valid = []
            for (x, y, w, h) in faces:
                cx = x + w / 2
                if not (img_w * h_margin < cx < img_w * (1 - h_margin)): continue
                if y > img_h * v_limit:                                 continue
                if w < img_w * min_frac:                                 continue
                if w > img_w * max_frac:                                 continue
                valid.append((x, y, w, h))
            if valid:
                return max(valid, key=lambda f: f[2] * f[3])
        return None

    @staticmethod
    def _face_from_manual(center: tuple, img_w: int) -> tuple:
        """Synthesises a face rect from a user-clicked centre point."""
        fcx, fcy = center
        fw = int(img_w * 0.13)   # assume face is ~13% of image width
        fh = fw
        return (max(0, fcx - fw // 2), max(0, fcy - fh // 2), fw, fh)

    @staticmethod
    def _apply_crop(
        rgb: Image.Image,
        face: tuple | None,
        img_w: int,
        img_h: int,
        target_ratio: float,
        fd_config: dict,
    ) -> Image.Image:
        top_pad       = fd_config.get("top_padding_factor",    0.70)
        bot_pad       = fd_config.get("bottom_padding_factor", 2.80)
        min_crop_frac = fd_config.get("min_crop_fraction",     0.55)

        if face is not None:
            fx, fy, fw, fh = face
            crop_top    = max(0,     fy - int(fh * top_pad))
            crop_bottom = min(img_h, fy + fh + int(fh * bot_pad))
            
            crop_top, crop_bottom = ImageProcessor._enforce_min_crop_height(
                crop_top, crop_bottom, img_h, min_crop_frac
            )
            
            crop_h      = crop_bottom - crop_top
            crop_w      = int(crop_h * target_ratio)
            face_cx     = fx + fw // 2
            crop_left   = face_cx - crop_w // 2
            crop_right  = crop_left + crop_w

            # Clamp
            if crop_left < 0:
                crop_right -= crop_left; crop_left = 0
            if crop_right > img_w:
                crop_left -= crop_right - img_w; crop_right = img_w
            crop_left  = max(0, crop_left)
            crop_right = min(img_w, crop_right)

            return rgb.crop((crop_left, crop_top, crop_right, crop_bottom))

        # ── Fallback: aspect-correct centre crop (no zoom) ────────────────────
        if img_w / img_h > target_ratio:
            new_w = int(img_h * target_ratio)
            left  = (img_w - new_w) // 2
            return rgb.crop((left, 0, left + new_w, img_h))
        else:
            new_h = int(img_w / target_ratio)
            top   = (img_h - new_h) // 2
            return rgb.crop((0, top, img_w, top + new_h))

    @staticmethod
    def _enforce_min_crop_height(
        crop_top: int, crop_bottom: int, img_h: int, min_crop_frac: float,
    ) -> tuple[int, int]:
        """
        Expands (crop_top, crop_bottom) symmetrically so crop height never
        drops below min_crop_frac * img_h. Guards against over-zoomed crops
        from oversized detected face boxes. Clamps to image bounds.
        """
        crop_h     = crop_bottom - crop_top
        min_crop_h = int(img_h * min_crop_frac)
        if crop_h >= min_crop_h:
            return crop_top, crop_bottom
        
        deficit      = min_crop_h - crop_h
        crop_top    -= deficit // 2
        crop_bottom += deficit - deficit // 2
        
        if crop_top < 0:
            crop_bottom -= crop_top    # push shortfall onto the bottom
            crop_top = 0
        if crop_bottom > img_h:
            crop_top -= (crop_bottom - img_h)   # push shortfall onto the top
            crop_bottom = img_h
            
        crop_top    = max(0, crop_top)
        crop_bottom = min(img_h, crop_bottom)
        return crop_top, crop_bottom

    @staticmethod
    def _to_jpeg_stream(img: Image.Image) -> io.BytesIO:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        return buf