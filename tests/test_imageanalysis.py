"""Unit tests for the vision-free render analysis (run: python -m unittest discover tests)."""
import unittest

import numpy as np

from molmcp.common import imageanalysis as ia
from molmcp.common.colornames import nearest_color_name, hue_family


def blank(w=300, h=200, bg=(0, 0, 0)):
    img = np.zeros((h, w, 4), np.uint8)
    img[..., :3] = bg
    img[..., 3] = 255
    return img


class TestAnalyzeRender(unittest.TestCase):
    def test_empty_frame(self):
        a = ia.analyze_render(blank())
        self.assertTrue(a["empty"])
        self.assertIn("empty", a["summary"].lower())

    def test_blob_and_clipping(self):
        img = blank()
        yy, xx = np.mgrid[0:200, 0:300]
        img[(xx - 120) ** 2 + (yy - 100) ** 2 < 50 ** 2] = (0, 255, 0, 255)
        img[0:20, 200:260] = (255, 0, 0, 255)
        a = ia.analyze_render(img, grid_cols=30, grid_rows=10)
        self.assertFalse(a["empty"])
        self.assertIn("top", a["clipped_edges"])
        self.assertNotIn("left", a["clipped_edges"])
        self.assertEqual(a["palette"][0]["name"], "green")
        self.assertAlmostEqual(a["palette"][0]["share"] + a["palette"][1]["share"], 1.0, places=2)
        self.assertEqual(len(a["ascii"]), 10)
        self.assertEqual(len(a["ascii"][0]), 30)
        self.assertLess(a["offset_from_centre_frac"][0], 0)  # blob left of centre

    def test_white_background_detected(self):
        img = blank(bg=(255, 255, 255))
        img[50:150, 50:150] = (0, 0, 200, 255)
        a = ia.analyze_render(img)
        self.assertEqual(a["background"]["name"], "white")
        self.assertAlmostEqual(a["coverage"], 100 * 100 / (300 * 200), places=3)

    def test_transparent_background(self):
        img = np.zeros((100, 100, 4), np.uint8)
        img[20:40, 20:40] = (255, 0, 0, 255)
        a = ia.analyze_render(img)
        self.assertTrue(a["background"]["transparent"])
        self.assertAlmostEqual(a["coverage"], 0.04, places=3)


class TestSegmentation(unittest.TestCase):
    def test_items_and_contacts(self):
        img = blank()
        img[50:150, 50:150] = (40, 200, 40, 255)
        img[50:150, 150:250] = (200, 40, 40, 255)
        legend = {"#28c828": "A-item", "#c82828": "B-item", "#2828c8": "C-item"}
        seg = ia.analyze_segmentation(img, legend, grid_cols=30, grid_rows=10)
        vis = {it["label"]: it["visible"] for it in seg["items"]}
        self.assertTrue(vis["A-item"] and vis["B-item"])
        self.assertFalse(vis["C-item"])
        self.assertEqual(seg["contacts_2d"][0]["boundary_px"], 100)
        self.assertEqual(seg["unassigned_pixels"], 0)
        self.assertIn("C-item", seg["summary"])

    def test_antialiased_pixels_assigned_by_nearest(self):
        img = blank()
        img[50:150, 50:150] = (40, 200, 40, 255)
        img[100, 149] = (60, 180, 50, 255)  # slightly off colour at the edge
        seg = ia.analyze_segmentation(img, {"#28c828": "x"})
        self.assertEqual(seg["items"][0]["pixels"], 100 * 100)

    def test_id_colors_unique(self):
        cols = ia.id_colors(60)
        self.assertEqual(len(set(cols)), 60)
        self.assertNotIn((0, 0, 0), cols)

    def test_occlusion_report(self):
        comp = {"items": [{"label": "a", "pixels": 50}, {"label": "b", "pixels": 100}]}
        rep = ia.occlusion_report(comp, {"a": 100, "b": 100})
        self.assertEqual(rep[0]["label"], "a")
        self.assertAlmostEqual(rep[0]["occluded_fraction"], 0.5)


class TestDiff(unittest.TestCase):
    def test_identical_and_changed(self):
        a = blank()
        a[20:60, 20:60] = (255, 255, 255, 255)
        self.assertEqual(ia.diff_images(a, a)["changed_pixels"], 0)
        b = a.copy()
        b[20:60, 20:60] = (255, 0, 0, 255)
        d = ia.diff_images(a, b)
        self.assertEqual(d["changed_pixels"], 1600)
        self.assertEqual(d["bbox"]["px"], [20, 20, 60, 60])

    def test_resize_mismatch(self):
        a = blank(300, 200)
        b = blank(150, 100)
        self.assertTrue(ia.diff_images(a, b)["resized_b"])


class TestColors(unittest.TestCase):
    def test_names(self):
        self.assertEqual(nearest_color_name((0, 128, 255))[0], "marine")
        self.assertEqual(nearest_color_name((255, 153, 153))[0], "salmon")
        self.assertEqual(hue_family((255, 0, 0)), "red")
        self.assertEqual(hue_family((10, 10, 10)), "black")
        self.assertEqual(hue_family((240, 240, 240)), "white")
        self.assertEqual(hue_family((200, 200, 200)), "grey")


if __name__ == "__main__":
    unittest.main()


class TestRound3Fixes(unittest.TestCase):
    """Regressions found by the second QA fleet (transparent flip, watermark banner, grid parsing, guard regex)."""

    def _frame(self, w=400, h=300, bg=(255, 255, 255)):
        import numpy as np
        a = np.zeros((h, w, 4), dtype=np.uint8)
        a[:, :, :3] = bg
        a[:, :, 3] = 255
        return a

    def test_single_non_opaque_pixel_does_not_flip_to_transparent(self):
        from molmcp.common import imageanalysis as ia
        a = self._frame()
        a[100:200, 150:250, :3] = (200, 30, 30)       # red block
        a[10, 10, 3] = 254                            # one stray pixel
        bg, transparent, _ = ia.estimate_background(a)
        self.assertFalse(transparent)
        self.assertEqual(bg, (255, 255, 255))
        r = ia.analyze_render(a)
        self.assertLess(r["coverage"], 0.2)
        self.assertEqual(r["clipped_edges"], [])

    def test_really_transparent_frame_is_detected(self):
        from molmcp.common import imageanalysis as ia
        a = self._frame()
        a[:, :, 3] = 0
        a[100:200, 150:250, 3] = 255
        a[100:200, 150:250, :3] = (0, 0, 255)
        bg, transparent, _ = ia.estimate_background(a)
        self.assertTrue(transparent)
        r = ia.analyze_render(a)
        self.assertTrue(r["background"]["transparent"])
        self.assertAlmostEqual(r["coverage"], 10000 / 120000.0, places=3)

    def test_watermark_band_is_detected_and_masked(self):
        from molmcp.common import imageanalysis as ia
        a = self._frame(800, 600)
        a[200:400, 300:500, :3] = (200, 30, 30)       # molecule
        # grey text banner: 15 px high, 70 % wide, starting at the left edge, as the unlicensed build draws it
        import numpy as np
        rng = np.random.RandomState(0)
        band = rng.rand(15, 560) < 0.45
        a[420:435, 0:560, :3][band] = (130, 130, 130)
        mask, info = ia.detect_watermark(a, (255, 255, 255), False)
        self.assertIsNotNone(info)
        self.assertEqual(info["rows"][0], 420)
        plain = ia.analyze_render(a)
        masked = ia.analyze_render(a, mask_watermark=True)
        self.assertIn("left", plain["clipped_edges"] + plain["touching_edges"])
        self.assertEqual(masked["clipped_edges"] + masked["touching_edges"], [])
        self.assertEqual([p["family"] for p in masked["palette"]].count("grey"), 0)
        self.assertTrue(masked["watermark"]["detected"])
        none = ia.analyze_render(self._frame(), mask_watermark=True)
        self.assertFalse(none["watermark"]["detected"])

    def test_diff_images_masks_moving_banner(self):
        from molmcp.common import imageanalysis as ia
        a = self._frame(800, 600)
        a[200:400, 300:500, :3] = (30, 30, 200)
        b = a.copy()
        a[420:435, 0:560, :3] = (130, 130, 130)
        b[300:315, 0:560, :3] = (130, 130, 130)
        d = ia.diff_images(a, b, mask_watermark=True)
        self.assertTrue(d["watermark_masked"])
        self.assertEqual(d["changed_pixels"], 0)

    def test_grid_parsing(self):
        from molmcp.common import server_common as sc
        self.assertEqual(sc._grid("48x20"), (48, 20))
        self.assertEqual(sc._grid("1000x1"), (160, 4))
        with self.assertRaises(ValueError):
            sc._grid("wide")
        self.assertIn("error", sc._grid_or_error("abc")[2])

    def test_dangerous_guard_word_boundaries(self):
        from molmcp.common import server_common as sc
        rx = sc.DANGEROUS["pymol"]
        for ok_cmd in ("rms_cur a, b", "rms a, b", "cdx", "pipeline", "quiet_mode", "pythonic_thing"):
            self.assertIsNone(rx.match(ok_cmd), ok_cmd)
        for bad in ("quit", "q", "cd /tmp", "pip install x", "python", "cmd.quit()", "/print(1)", "@file.pml", "system ls", "reinitialize", "exit"):
            self.assertIsNotNone(rx.match(bad), bad)
