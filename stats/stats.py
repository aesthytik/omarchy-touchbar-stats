#!/usr/bin/env python3
"""Touch Bar Stats: AI usage limits and system stats across the whole Touch Bar.

Draws through tiny-dfr-plus's takeover socket. AI numbers come from the usage
records Omarchy's Agents panel keeps in ~/.local/state/omarchy/agents/usage/;
system numbers from /proc and /sys. A tap on the bar closes it.
"""
import glob
import json
import os
import select
import socket
import struct
import subprocess
import time

import cairo

W, H = 1085, 30              # logical pixels; tiny-dfr scales them 2x to 2170x60
TAKEOVER = b"\0tiny-dfr-takeover"
SEND_EVERY = 0.2             # tiny-dfr drops a takeover after 0.5 s without frames
SAMPLE_EVERY = 1.0
USAGE_DIR = os.path.expanduser("~/.local/state/omarchy/agents/usage")
USAGE_REFRESH = 300          # ask Omarchy to refresh limits when older than this (s)
FONT = "Ubuntu"              # shipped with tiny-dfr; fontconfig falls back otherwise

LABEL = (0.55, 0.58, 0.66)
VALUE = (0.95, 0.96, 0.98)
DIVIDER = (0.22, 0.23, 0.28)
TRACK = (0.20, 0.21, 0.25)
GOOD, WARN, BAD = (0.45, 0.85, 0.45), (0.98, 0.78, 0.30), (0.98, 0.40, 0.40)
AI_ACCENT = (0.85, 0.55, 1.0)


def level_color(frac):
    return GOOD if frac < 0.6 else WARN if frac < 0.85 else BAD


# ---- system samples -------------------------------------------------------

class System:
    def __init__(self):
        self.prev_cpu = self._cpu_times()
        self.prev_net = (time.monotonic(), self._net_bytes())
        self.cpu = 0.0
        self.down = self.up = 0.0
        self.temp_path = self._find_temp()
        self.battery = self._find_battery()

    @staticmethod
    def _cpu_times():
        with open("/proc/stat") as f:
            vals = [int(v) for v in f.readline().split()[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        return sum(vals), idle

    @staticmethod
    def _net_bytes():
        rx = tx = 0
        with open("/proc/net/dev") as f:
            for line in f.readlines()[2:]:
                name, data = line.split(":", 1)
                if name.strip() == "lo":
                    continue
                fields = data.split()
                rx += int(fields[0])
                tx += int(fields[8])
        return rx, tx

    @staticmethod
    def _find_temp():
        for hw in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                if open(hw + "/name").read().strip() in ("coretemp", "k10temp", "zenpower"):
                    return hw + "/temp1_input"
            except OSError:
                pass
        zones = glob.glob("/sys/class/thermal/thermal_zone*/temp")
        return zones[0] if zones else None

    @staticmethod
    def _find_battery():
        for ps in glob.glob("/sys/class/power_supply/*"):
            try:
                if open(ps + "/type").read().strip() == "Battery":
                    return ps
            except OSError:
                pass
        return None

    def sample(self):
        total, idle = self._cpu_times()
        pt, pi = self.prev_cpu
        if total > pt:
            self.cpu = 1.0 - (idle - pi) / (total - pt)
        self.prev_cpu = (total, idle)

        now, (rx, tx) = time.monotonic(), self._net_bytes()
        t0, (rx0, tx0) = self.prev_net
        if now > t0:
            self.down, self.up = max(0, rx - rx0) / (now - t0), max(0, tx - tx0) / (now - t0)
        self.prev_net = (now, (rx, tx))

        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                mem[k] = int(v.split()[0]) * 1024
        self.mem_total = mem.get("MemTotal", 1)
        self.mem_used = self.mem_total - mem.get("MemAvailable", 0)

        self.temp = None
        if self.temp_path:
            try:
                self.temp = int(open(self.temp_path).read()) / 1000
            except (OSError, ValueError):
                pass

        self.bat = self.charging = None
        if self.battery:
            try:
                self.bat = int(open(self.battery + "/capacity").read()) / 100
                self.charging = open(self.battery + "/status").read().strip() in ("Charging", "Full")
            except (OSError, ValueError):
                pass


# ---- AI usage -------------------------------------------------------------

def load_ai():
    """Signed-in agents that report limits, Claude first."""
    agents = []
    for path in glob.glob(os.path.join(USAGE_DIR, "*.json")):
        try:
            if os.path.getsize(path) > 1_000_000:
                continue
            with open(path) as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        limits = [l for l in d.get("limits") or [] if isinstance(l.get("percent"), (int, float))]
        if not d.get("ready") or not limits:
            continue
        agents.append({
            "id": str(d.get("id", ""))[:32],
            "name": str(d.get("name", d.get("id", "")))[:16],
            "limits": [(str(l.get("label", ""))[:24], max(0.0, min(1.0, float(l["percent"])))) for l in limits[:2]],
            "tokens": d.get("todayTotalTokens") if isinstance(d.get("todayTotalTokens"), int) else 0,
            "stale": bool(d.get("limitsStale")),
        })
    agents.sort(key=lambda a: (a["id"] != "claude", a["id"] != "codex", a["name"]))
    return agents[:3]


def usage_age():
    files = glob.glob(os.path.join(USAGE_DIR, "*.json"))
    if not files:
        return float("inf")
    return time.time() - max(os.path.getmtime(f) for f in files)


def refresh_usage():
    """Ask Omarchy to refresh agent limits in the background (no-op without it)."""
    try:
        subprocess.Popen(["omarchy", "agent", "usage", "update", "--limits-only"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


# ---- drawing --------------------------------------------------------------

def short_limit(label):
    l = label.lower()
    if "5-hour" in l or "session" in l:
        return "5h"
    if "week" in l or "7-day" in l:
        return "wk"
    if "720h" in l or "month" in l:
        return "mo"
    return label[:3].lower()


def human_bytes(n, rate=False):
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1000 or unit == "T":
            s = ("%.0f" if n >= 10 or unit == "B" else "%.1f") % n
            return s + unit
        n /= 1000.0


def human_count(n):
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= size:
            return ("%.1f" % (n / size)).rstrip("0").rstrip(".") + unit
    return str(n)


class Painter:
    def __init__(self):
        self.surface = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        self.c = cairo.Context(self.surface)
        self.c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        fo = cairo.FontOptions()
        fo.set_antialias(cairo.ANTIALIAS_GRAY)
        fo.set_hint_style(cairo.HINT_STYLE_FULL)
        self.c.set_font_options(fo)
        self.x = 0.0

    def text(self, s, size, color, y=None):
        c = self.c
        c.set_font_size(size)
        c.set_source_rgb(*color)
        ext = c.text_extents(s)
        c.move_to(round(self.x), round(y if y is not None else (H + size * 0.72) / 2))
        c.show_text(s)
        self.x += ext.x_advance
        return ext.x_advance

    def gap(self, px):
        self.x += px

    def meter(self, frac, width=34, color=None):
        c = self.c
        top, h = H / 2 - 3, 6
        c.set_source_rgb(*TRACK)
        self._round_rect(self.x, top, width, h)
        c.fill()
        if frac > 0:
            c.set_source_rgb(*(color or level_color(frac)))
            self._round_rect(self.x, top, max(h, width * frac), h)
            c.fill()
        self.x += width

    def _round_rect(self, x, y, w, h):
        r = h / 2
        c = self.c
        c.new_sub_path()
        c.arc(x + w - r, y + r, r, -1.5708, 1.5708)
        c.arc(x + r, y + r, r, 1.5708, 4.7124)
        c.close_path()

    def arrow(self, up, color):
        """Small filled triangle; the bundled font has no arrow glyphs."""
        c, x, mid = self.c, self.x, H / 2
        c.set_source_rgb(*color)
        if up:
            c.move_to(x, mid + 3); c.line_to(x + 7, mid + 3); c.line_to(x + 3.5, mid - 4)
        else:
            c.move_to(x, mid - 3); c.line_to(x + 7, mid - 3); c.line_to(x + 3.5, mid + 4)
        c.close_path()
        c.fill()
        self.x += 9

    def bolt(self, color):
        c, x, y = self.c, self.x, H / 2 - 6
        c.set_source_rgb(*color)
        for dx, dy in ((4, 0), (0, 7), (3, 7), (2, 12), (7, 4), (4, 4), (6, 0)):
            c.line_to(x + dx, y + dy)
        c.close_path()
        c.fill()
        self.x += 8

    def divider(self):
        self.gap(10)
        self.c.set_source_rgb(*DIVIDER)
        self.c.rectangle(round(self.x), 7, 1, H - 14)
        self.c.fill()
        self.gap(11)

    def frame(self, system, agents):
        c = self.c
        c.set_source_rgb(0, 0, 0)
        c.paint()
        self.x = 8

        # AI
        self.text("AI", 9, AI_ACCENT)
        self.gap(8)
        if not agents:
            self.text("no agent usage yet", 11, LABEL)
        for i, a in enumerate(agents):
            if i:
                self.gap(14)
            self.text(a["name"], 12, VALUE)
            for label, frac in a["limits"]:
                self.gap(7)
                self.text(short_limit(label), 9, LABEL)
                self.gap(4)
                self.meter(frac, 28)
                self.gap(4)
                self.text("%d%%" % round(frac * 100), 11, level_color(frac) if frac >= 0.85 else VALUE)
            if a["tokens"]:
                self.gap(7)
                self.text(human_count(a["tokens"]), 11, VALUE)
                self.gap(2)
                self.text("tok", 9, LABEL)
            if a["stale"]:
                self.gap(3)
                self.text("*", 11, WARN)
        self.divider()

        # system
        def stat(label, frac, value, unit=""):
            self.text(label, 9, LABEL)
            self.gap(5)
            if frac is not None:
                self.meter(frac, 26)
                self.gap(5)
            self.text(value, 12, VALUE)
            if unit:
                self.gap(1)
                self.text(unit, 9, LABEL)
            self.gap(14)

        s = system
        stat("CPU", s.cpu, "%d%%" % round(s.cpu * 100))
        mf = s.mem_used / s.mem_total
        stat("RAM", mf, "%.1f" % (s.mem_used / 2**30), "/%.0fG" % (s.mem_total / 2**30))
        if s.temp is not None:
            stat("TEMP", min(1.0, max(0.0, (s.temp - 30) / 70)), "%d°" % round(s.temp))
        if s.bat is not None:
            frac = s.bat
            self.text("BAT", 9, LABEL)
            self.gap(5)
            self.meter(frac, 26, GOOD if s.charging else (BAD if frac < 0.15 else WARN if frac < 0.3 else GOOD))
            self.gap(5)
            self.text("%d%%" % round(frac * 100), 12, VALUE)
            if s.charging:
                self.gap(3)
                self.bolt(WARN)
            self.gap(14)
        self.text("NET", 9, LABEL)
        self.gap(5)
        self.arrow(False, GOOD)
        self.text(human_bytes(s.down), 12, VALUE)
        self.gap(6)
        self.arrow(True, AI_ACCENT)
        self.text(human_bytes(s.up), 12, VALUE)

        # clock on the right
        clock = time.strftime("%H:%M")
        c.set_font_size(12)
        self.x = W - 8 - c.text_extents(clock).x_advance
        self.text(clock, 12, LABEL)
        self.surface.flush()
        return rgb332(self.surface)


_R = bytes((v >> 5) << 5 for v in range(256))
_G = bytes((v >> 5) << 2 for v in range(256))
_B = bytes(v >> 6 for v in range(256))


def rgb332(surface):
    data = bytes(surface.get_data())     # BGRx, little-endian RGB24
    stride = surface.get_stride()
    out = bytearray(W * H)
    for y in range(H):
        row = data[y * stride:y * stride + W * 4]
        r = row[2::4].translate(_R)
        g = row[1::4].translate(_G)
        b = row[0::4].translate(_B)
        o = y * W
        out[o:o + W] = (int.from_bytes(r, "big") | int.from_bytes(g, "big") | int.from_bytes(b, "big")).to_bytes(W, "big")
    return bytes(out)


def main():
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind("")                       # autobind, so tiny-dfr can send touches back
    sock.setblocking(False)
    header = b"TDT1" + struct.pack("<HH", W, H)
    system, painter = System(), Painter()
    if usage_age() > USAGE_REFRESH:
        refresh_usage()
    last_refresh = time.monotonic()
    time.sleep(0.25)                    # let the first CPU/net sample span some time
    system.sample()
    frame = painter.frame(system, load_ai())
    next_sample = time.monotonic() + SAMPLE_EVERY
    while True:
        now = time.monotonic()
        if now >= next_sample:
            system.sample()
            frame = painter.frame(system, load_ai())
            next_sample = now + SAMPLE_EVERY
            if now - last_refresh > USAGE_REFRESH and usage_age() > USAGE_REFRESH:
                refresh_usage()
                last_refresh = now
        try:
            sock.sendto(header + frame, TAKEOVER)
        except (ConnectionRefusedError, FileNotFoundError, BlockingIOError):
            pass
        r, _, _ = select.select([sock], [], [], SEND_EVERY)
        if r:
            try:
                msg = sock.recv(64)
            except BlockingIOError:
                continue
            if len(msg) == 11 and msg[:4] == b"TDE1" and msg[4] == 2:
                return                  # a tap on the bar closes the stats


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
