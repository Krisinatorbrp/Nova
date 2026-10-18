"""Draws the particle orb into a transparent RGBA frame (numpy). Used by the desktop widget.

The sphere sits in the middle; a band of sparks stretches out to the left and right.
While the assistant talks, the band widens and the sphere pulses.
"""
import math
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

STATES = {
    "idle":      (1.0, 0.10), "thinking": (2.4, 0.35), "acting": (3.0, 0.45),
    "waiting":   (0.8, 0.25), "listening": (1.8, 0.55),
}
AMBER = np.array([1.0, 0.66, 0.18], np.float32)


def hex_rgb(h):
    h = (h or "#2896FF").lstrip("#")
    try:
        return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)
    except ValueError:
        return np.array([0.16, 0.59, 1.0], np.float32)


def _font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


class OrbRenderer:
    PAD = 32                       # light buffer border, so sprites never need bounds checks

    def __init__(self, diameter=170, color="#2896FF", name="Nova"):
        self.name = name
        self.color = hex_rgb(color)
        self.state = "idle"
        self.speed, self.energy = 1.0, 0.1
        self.hue = self.color.copy()
        self.t = 0.0
        self.level = 0.0
        self.kick_v = 0.0
        self.boost = 0.0
        self.speaking = False
        self.speak_until = 0.0
        self.last = time.time()
        # transcript bubble
        self.show_transcript = True
        self.bubble_text, self.bubble_start, self.bubble_until = "", 0.0, 0.0
        self.hover = False
        self.listening = False             # microphone is on
        rng = np.random.default_rng(7)
        n = 320
        i = np.arange(n)
        y = 1 - i / (n - 1) * 2
        r = np.sqrt(1 - y * y)
        th = i * 2.399963
        self.P = np.stack([np.cos(th) * r, y, np.sin(th) * r]).astype(np.float32)
        self.seed = rng.random(n).astype(np.float32) * 100
        self.psize = (0.6 + rng.random(n) * 0.9).astype(np.float32)
        m = 150                                     # the horizontal spark band
        self.sa = (rng.random(m) * math.tau).astype(np.float32)
        self.sr = (1.15 + rng.random(m) ** 1.6 * 1.9).astype(np.float32)
        self.sv = (0.2 + rng.random(m) * 0.6).astype(np.float32)
        self.sy = ((rng.random(m) - 0.5) * 0.10).astype(np.float32)
        self.ss = (0.4 + rng.random(m) * 0.8).astype(np.float32)
        self.sseed = (rng.random(m) * 100).astype(np.float32)
        self.resize(diameter)

    # ---------- geometry ----------
    def resize(self, diameter, scale=1.0):
        self.D = int(diameter)
        self.scale = scale
        self.W = int(self.D * 3.1)                 # wide: room for the sparks left and right
        self.SH = int(self.D * 1.25)               # sphere area
        self.BH = int(118 * scale)                 # transcript area underneath
        self.H = self.SH + self.BH
        self.cx, self.cy = self.W / 2, self.SH / 2
        # glow sprites (gaussian blobs) for radii 1..16, stored flat: all particles of one size
        # are drawn together with numpy (no Python loop per particle)
        P = self.PAD
        self.WP, self.HP = self.W + 2 * P, self.SH + 2 * P          # padded light buffer
        self.kern = {}
        for r in range(1, 17):
            yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
            d2 = (xx * xx + yy * yy).astype(np.float32) / (r * r)
            k = np.exp(-d2 * 3.2) * 0.9 + np.exp(-d2 * 16) * 0.8
            self.kern[r] = ((yy * self.WP + xx).ravel().astype(np.int64), k.ravel().astype(np.float32))
        yy, xx = np.mgrid[0:self.SH, 0:self.W].astype(np.float32)
        d = np.sqrt((xx - self.cx) ** 2 + ((yy - self.cy) * 1.0) ** 2) / (self.D * 0.5)
        self.glow = (np.exp(-d * d * 1.6) * 0.55).astype(np.float32)
        band = np.exp(-((yy - self.cy) / (self.D * 0.07)) ** 2) * np.exp(-(np.abs(xx - self.cx) / (self.D * 1.3)) ** 2)
        self.band = (band * 0.18).astype(np.float32)
        # soft fade towards the window edges so nothing ever gets cut off hard (x2.1 = tone-map gain)
        tx = np.clip((self.W / 2 - np.abs(xx - self.cx)) / (self.W * 0.14), 0, 1)
        ty = np.clip((self.SH / 2 - np.abs(yy - self.cy)) / (self.SH * 0.12), 0, 1)
        self.edge = (((tx * ty) ** 1.5) * 2.1).astype(np.float32)
        # reused buffers (no big allocations per frame)
        self._f = np.empty((self.SH, self.W, 4), np.float32)
        self._out = np.zeros((self.H, self.W, 4), np.uint8)
        self.f_name = _font(["seguisb.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"], int(11 * scale))
        self.f_text = _font(["segoeui.ttf", "DejaVuSans.ttf"], int(13 * scale))
        self.f_icon = _font(["seguisym.ttf", "segoeui.ttf", "DejaVuSans.ttf"], int(14 * scale))
        self._bubble_cache = None

    def buttons(self):
        """(name, cx, cy, radius) of the hover buttons, in window pixels."""
        r = int(14 * self.scale)
        y = int(self.cy + self.D * 0.43)
        g = int(34 * self.scale)
        return [("chat", int(self.cx - g), y, r), ("mic", int(self.cx), y, r), ("menu", int(self.cx + g), y, r)]

    def bubble_rect(self):
        bw = min(self.W - 8, max(int(250 * self.scale), int(self.D * 2.1)))
        x0 = int((self.W - bw) / 2)
        y0 = self.SH + int(4 * self.scale)
        return x0, y0, x0 + bw, y0 + self._bubble_height(bw)

    def over_orb(self, x, y):
        """Is this window point on the visible part (sphere, buttons or bubble)?"""
        if math.hypot(x - self.cx, (y - self.cy)) < self.D * 0.62:
            return True
        if self.bubble_visible():
            x0, y0, x1, y1 = self.bubble_rect()
            return x0 <= x <= x1 and y0 <= y <= y1
        return False

    # ---------- events ----------
    def set_state(self, s):
        self.state = s if s in STATES else "idle"

    def set_color(self, hexcolor):
        self.color = hex_rgb(hexcolor)
        self._bubble_cache = None

    def say(self, text, ms):
        now = time.time()
        continuing = self.bubble_text and text.startswith(self.bubble_text[:20]) and now < self.bubble_until
        self.speak_until = max(self.speak_until, now + ms / 1000) if continuing else now + ms / 1000
        self.kick_v = 1
        if not continuing:
            self.bubble_start = now          # new answer: type it out from the start
        self.bubble_text = text
        self.bubble_until = now + ms / 1000 + 3.0
        self._bubble_cache = None

    def note(self, text, ms):
        """Show a short note in the bubble without making the orb 'talk'."""
        now = time.time()
        self.bubble_text, self.bubble_start, self.bubble_until = text, now, now + ms / 1000
        self._bubble_cache = None

    def stream(self, text):
        """Answer still coming in: keep the bubble growing and the orb talking."""
        now = time.time()
        if not (self.bubble_text and text.startswith(self.bubble_text[:20]) and now < self.bubble_until):
            self.bubble_start = now
        self.bubble_text = text
        self.bubble_until = now + 6
        self.speak_until = max(self.speak_until, now + 1.2)

    def voice(self, ev):
        if ev == "start":
            self.speaking, self.kick_v = True, 1
        elif ev == "word":
            self.kick_v = 1
        elif ev == "end":
            self.speaking, self.speak_until = False, 0

    def pulse(self):
        self.boost = 1

    def bubble_visible(self):
        return self.show_transcript and self.bubble_text and time.time() < self.bubble_until

    # ---------- drawing ----------
    def _splat_all(self, px, py, size, w_hue, w_white):
        """Adds every particle's glow sprite at once.

        Light is kept as two fields: one tinted with the orb colour and one white,
        so a single pass serves all three colour channels."""
        P = self.PAD
        xi = px.astype(np.int64)
        yi = py.astype(np.int64)
        keep = (xi >= -16) & (xi < self.W + 16) & (yi >= -16) & (yi < self.SH + 16)
        rad = np.clip(size.astype(np.int64), 1, 16)
        base = (yi + P) * self.WP + (xi + P)
        idx, wh, ww = [], [], []
        for r in np.unique(rad[keep]):
            sel = keep & (rad == r)
            off, k = self.kern[int(r)]
            idx.append((base[sel][:, None] + off[None, :]).ravel())
            wh.append((w_hue[sel][:, None] * k[None, :]).ravel())
            ww.append((w_white[sel][:, None] * k[None, :]).ravel())
        n = self.HP * self.WP
        if not idx:
            z = np.zeros((self.SH, self.W), np.float32)
            return z, z
        idx = np.concatenate(idx)
        fh = np.bincount(idx, np.concatenate(wh), n).reshape(self.HP, self.WP)
        fw = np.bincount(idx, np.concatenate(ww), n).reshape(self.HP, self.WP)
        crop = (slice(P, P + self.SH), slice(P, P + self.W))
        return fh[crop].astype(np.float32), fw[crop].astype(np.float32)

    def frame(self):
        """Returns an (H, W, 4) uint8 premultiplied BGRA frame (reused between calls)."""
        now = time.time()
        dt = min(now - self.last, 0.05)
        self.last = now
        sp_t, en_t = STATES[self.state]
        k = 1 - 0.03 ** dt
        self.speed += (sp_t - self.speed) * k
        self.energy += (en_t - self.energy) * k
        target_hue = AMBER if self.state == "waiting" else self.color
        self.hue += (target_hue - self.hue) * k
        self.boost *= 0.08 ** dt
        self.kick_v *= 0.02 ** dt
        talking = self.speaking or now < self.speak_until
        env = (0.35 + 0.65 * abs(math.sin(now * 17) * (0.5 + 0.5 * math.sin(now * 4.3))) + self.kick_v * 0.5) if talking else 0
        self.level += (min(env, 1.2) - self.level) * (1 - (0.0005 if talking else 0.02) ** dt)
        self.t += dt * (self.speed + self.level * 1.5 + self.boost)
        t, e, lv = self.t, self.energy, self.level

        hue = self.hue

        # sphere
        R = self.D * 0.36 * (1 + lv * 0.10 + self.boost * 0.06)
        x, y, z = self.P
        wob = (1 + (np.sin(self.seed * 1.7 + t * (0.6 + e)) * 0.5) * (0.08 + e * 0.35)
               + lv * 0.22 * np.sin(y * 6 + t * 9 + self.seed))
        x, y, z = x * wob, y * wob, z * wob
        ry, rx = t * 0.35, 0.45 + math.sin(t * 0.13) * 0.25
        x1 = x * math.cos(ry) - z * math.sin(ry)
        z1 = x * math.sin(ry) + z * math.cos(ry)
        y1 = y * math.cos(rx) - z1 * math.sin(rx)
        z2 = y * math.sin(rx) + z1 * math.cos(rx)
        persp = 1 / (1.9 - z2 * 0.6)
        px = self.cx + x1 * R * persp * 1.3
        py = self.cy + y1 * R * persp * 1.3
        depth = (z2 + 1) / 2
        base = self.D * 0.020
        sizes = base * self.psize * (0.45 + depth * 0.9) * (1 + lv * 0.5)
        alpha = 0.18 + depth * 0.7
        # light adds up, so the drawing order does not matter (no depth sort needed)
        s_hue, s_white = alpha * 0.8, alpha * depth * 0.35

        # the horizontal spark band (stretches further while speaking)
        self.sa += self.sv * 0.004 * (1 + self.speed * 1.5 + lv * 3) * (dt * 60)
        spread = 1 + lv * 0.55 + e * 0.15
        rr = R * self.sr * spread * (1 + 0.15 * np.sin(t * 3 + self.sseed) * lv)
        sxp = self.cx + np.cos(self.sa) * rr * 1.25
        syp = self.cy + (np.sin(self.sa) * rr * 0.10 + self.sy * self.D)
        sd = (np.sin(self.sa) + 1) / 2
        flick = 0.4 + 0.6 * (0.5 + 0.5 * np.sin(self.sseed * 3 + t * 2.2))
        far = np.clip(1.4 - (self.sr - 1.15) / 1.9, 0.25, 1.0)
        s_int = (0.25 + sd * 0.6) * flick * far

        fh, fw = self._splat_all(
            np.concatenate([px, sxp]), np.concatenate([py, syp]),
            np.concatenate([sizes, base * self.ss * (0.5 + sd * 0.7)]),
            np.concatenate([s_hue, s_int * 0.9]), np.concatenate([s_white, s_int * 0.25 * sd]))
        fh += self.glow * (0.20 + lv * 0.25 + e * 0.1) + self.band * (0.6 + lv * 1.6)
        fh *= self.edge
        fw *= self.edge

        # tone map light into colour + transparency (premultiplied), straight into BGRA order
        f = self._f
        hue4 = np.array([hue[2], hue[1], hue[0], hue.max()], np.float32)   # alpha = brightest channel
        np.multiply(fh[..., None], hue4, out=f)
        f += fw[..., None]
        np.negative(f, out=f)
        np.exp(f, out=f)
        np.subtract(1.0, f, out=f)
        f *= 255.0
        out = self._out
        out[:self.SH] = f
        out[self.SH:] = 0
        # transcript bubble + hover buttons (only the small area they cover)
        ov = self._overlay(now)
        if ov is not None:
            y0, x0, arr = ov
            y1, x1 = y0 + arr.shape[0], x0 + arr.shape[1]
            reg = out[y0:y1, x0:x1].astype(np.float32)
            reg *= 1.0 - arr[..., 3:] / 255.0
            reg += arr
            out[y0:y1, x0:x1] = np.minimum(reg, 255.0)
        return out

    def _overlay(self, now):
        show_b = self.bubble_visible()
        if not (show_b or self.hover or self.listening):
            return None
        chars = int((now - self.bubble_start) * 85) + 1 if show_b else 0
        fade_q = round(min(1.0, (self.bubble_until - now) / 0.6), 1) if show_b else 0
        key = (self.hover, self.listening, show_b, min(chars, len(self.bubble_text) + 1), fade_q, tuple(self.color))
        if self._bubble_cache and self._bubble_cache[0] == key:
            return self._bubble_cache[1]
        ov = self._draw_overlay(now, show_b)
        self._bubble_cache = (key, ov)
        return ov

    def active(self):
        """Is something moving that needs the full frame rate?"""
        return (self.state != "idle" or self.speaking or time.time() < self.speak_until
                or self.hover or self.listening or self.bubble_visible() or self.boost > 0.05
                or self.level > 0.02)

    def _draw_overlay(self, now, show_b):
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cr, cg, cb = (int(v * 255) for v in self.color)
        if self.hover or self.listening:
            for name, x, y, r in self.buttons():
                if not self.hover and name != "mic":
                    continue                                  # while listening, the mic stays visible
                hot = name == "mic" and self.listening
                d.ellipse([x - r, y - r, x + r, y + r], fill=(200, 40, 70, 235) if hot else (4, 18, 36, 225),
                          outline=(255, 120, 140, 255) if hot else (cr, cg, cb, 200), width=max(1, int(self.scale)))
                s = r * 0.45
                if name == "mic":
                    w = max(2, int(1.6 * self.scale))
                    d.rounded_rectangle([x - s * 0.42, y - s * 1.05, x + s * 0.42, y + s * 0.25], radius=s * 0.42, outline=(240, 248, 255, 255), width=w)
                    d.arc([x - s * 0.8, y - s * 0.6, x + s * 0.8, y + s * 0.65], 20, 160, fill=(240, 248, 255, 255), width=w)
                    d.line([x, y + s * 0.65, x, y + s * 1.05], fill=(240, 248, 255, 255), width=w)
                elif name == "chat":
                    d.ellipse([x - s, y - s * 0.85, x + s, y + s * 0.85], outline=(230, 245, 255, 255), width=max(2, int(1.6 * self.scale)))
                    d.polygon([(x - s * 0.7, y + s * 0.4), (x - s * 0.9, y + s * 1.2), (x - s * 0.1, y + s * 0.75)], fill=(230, 245, 255, 255))
                else:
                    for dx in (-s, 0, s):
                        d.ellipse([x + dx - 1.6 * self.scale, y - 1.6 * self.scale, x + dx + 1.6 * self.scale, y + 1.6 * self.scale], fill=(230, 245, 255, 255))
        if show_b:
            x0, y0, x1, y1 = self.bubble_rect()
            fade = min(1.0, (self.bubble_until - now) / 0.6)
            d.rounded_rectangle([x0, y0, x1, y1], radius=int(14 * self.scale),
                                fill=(4, 14, 28, int(232 * fade)), outline=(cr, cg, cb, int(110 * fade)), width=1)
            pad = int(11 * self.scale)
            d.text((x0 + pad, y0 + pad - 2), self.name.upper(), font=self.f_name, fill=(cr, cg, cb, int(255 * fade)))
            shown = self.bubble_text[: int((now - self.bubble_start) * 85) + 1]
            yy = y0 + pad + int(15 * self.scale)
            for line in self._wrap(shown, x1 - x0 - 2 * pad)[:4]:
                d.text((x0 + pad, yy), line, font=self.f_text, fill=(225, 244, 255, int(255 * fade)))
                yy += int(17 * self.scale)
        box = img.getbbox()
        if not box:
            return None
        x0, y0, x1, y1 = box
        a = np.asarray(img.crop(box), np.float32)[..., [2, 1, 0, 3]]   # BGRA, only the drawn area
        a[..., :3] *= a[..., 3:] / 255.0             # premultiply
        return y0, x0, np.ascontiguousarray(a)

    def _bubble_height(self, width):
        pad = int(11 * self.scale)
        lines = min(4, len(self._wrap(self.bubble_text, width - 2 * pad)))
        return min(self.BH - 6, 2 * pad + int(15 * self.scale) + lines * int(17 * self.scale))

    def _wrap(self, text, width):
        words, lines, cur = text.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if self.f_text.getlength(test) <= width or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) > 4:
            lines = lines[:4]
            lines[3] = lines[3][: max(0, len(lines[3]) - 1)] + "…"
        return lines
