import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np
    from PIL import Image

    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False

from src.verify_heatmap import verify_heatmap_r_value


def _color_from_r(r: float) -> tuple[int, int, int]:
    # Simple blue -> red interpolation used to synthesize test images.
    ratio = (r + 1.0) / 2.0
    ratio = max(0.0, min(1.0, ratio))
    rch = int(255 * ratio)
    bch = int(255 * (1.0 - ratio))
    return rch, 0, bch


@unittest.skipUnless(_HAS_DEPS, "numpy/Pillow are required for heatmap verification tests")
class TestVerifyHeatmap(unittest.TestCase):
    def _make_synthetic_heatmap(self, r_value: float) -> Path:
        h, w = 120, 160
        img = np.full((h, w, 3), 255, dtype=np.uint8)

        # Heatmap panel on left.
        heat_color = np.array(_color_from_r(r_value), dtype=np.uint8)
        img[:, :120, :] = heat_color[None, None, :]

        # Legend on right (vertical).
        for y in range(h):
            r = 1.0 - 2.0 * (y / (h - 1))
            img[y, 130:150, :] = np.array(_color_from_r(r), dtype=np.uint8)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.close()
        Image.fromarray(img).save(tmp.name)
        return Path(tmp.name)

    def test_verify_pass(self) -> None:
        path = self._make_synthetic_heatmap(0.4)
        try:
            out = verify_heatmap_r_value(
                proposed_r=0.4,
                image_path=str(path),
                tolerance=0.08,
                min_support_pixels=20,
                min_support_fraction=0.01,
            )
            self.assertTrue(out["verified"])
        finally:
            path.unlink(missing_ok=True)

    def test_verify_fail(self) -> None:
        path = self._make_synthetic_heatmap(0.4)
        try:
            out = verify_heatmap_r_value(
                proposed_r=-0.9,
                image_path=str(path),
                tolerance=0.05,
                min_support_pixels=20,
                min_support_fraction=0.01,
            )
            self.assertFalse(out["verified"])
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
