"""Generate DictateMe app icons - waveform bars, readable at all sizes."""
from PIL import Image, ImageDraw
import io
import struct
import os

DIR = os.path.dirname(os.path.abspath(__file__))

BG = (14, 14, 18)
ACCENT = (255, 186, 8)
WHITE = (242, 240, 237)


def draw_icon(size, for_tray=False):
    """Waveform bars icon that stays readable even at small sizes."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = max(1, int(size * 0.04))
    color = WHITE if for_tray else ACCENT

    if not for_tray:
        r = int(size * 0.22)
        draw.rounded_rectangle(
            [margin, margin, size - margin, size - margin],
            radius=r, fill=BG
        )
        for i in range(min(6, size // 20)):
            alpha = max(0, 10 - i * 2)
            draw.rounded_rectangle(
                [margin + i, margin + i, size - margin - i, size - margin - i],
                radius=max(0, r - i),
                outline=(255, 255, 255, alpha)
            )

    cx = size / 2
    cy = size / 2

    # Adaptive bar count and width based on icon size
    if size <= 24:
        num_bars = 5
        height_ratios = [0.35, 0.70, 1.0, 0.65, 0.30]
    elif size <= 48:
        num_bars = 5
        height_ratios = [0.30, 0.65, 1.0, 0.60, 0.25]
    else:
        num_bars = 7
        height_ratios = [0.30, 0.55, 0.80, 1.0, 0.75, 0.50, 0.25]

    # Make bars wider at small sizes so they're visible
    if size <= 24:
        bar_w_ratio = 0.12
        total_w_ratio = 0.60
    elif size <= 48:
        bar_w_ratio = 0.10
        total_w_ratio = 0.55
    else:
        bar_w_ratio = 0.065
        total_w_ratio = 0.52

    total_w = size * total_w_ratio
    bar_w = size * bar_w_ratio
    gap = (total_w - bar_w * num_bars) / max(1, num_bars - 1)
    start_x = cx - total_w / 2
    max_h = size * 0.48

    for i in range(num_bars):
        h = max_h * height_ratios[i]
        x = start_x + i * (bar_w + gap)
        y_top = cy - h / 2
        y_bot = cy + h / 2
        br = bar_w / 2

        bar_color = color
        if not for_tray and num_bars >= 7:
            edge_dist = abs(i - (num_bars - 1) / 2) / ((num_bars - 1) / 2)
            r_val = int(ACCENT[0] * (1 - edge_dist * 0.15))
            g_val = int(ACCENT[1] * (1 - edge_dist * 0.1))
            bar_color = (r_val, g_val, ACCENT[2])

        draw.rounded_rectangle(
            [int(x), int(y_top), int(x + bar_w), int(y_bot)],
            radius=max(1, int(br)),
            fill=bar_color
        )

    return img


# Generate PNGs
for name, sz in {"32x32.png": 32, "128x128.png": 128, "128x128@2x.png": 256}.items():
    draw_icon(sz).save(os.path.join(DIR, name), "PNG")
    print(f"  Saved {name} ({sz}x{sz})")

# Build proper multi-size ICO with PNG entries
ico_sizes = [16, 24, 32, 48, 64, 128, 256]
png_entries = []
for s in ico_sizes:
    buf = io.BytesIO()
    draw_icon(s).save(buf, format="PNG")
    png_entries.append(buf.getvalue())

header = struct.pack('<HHH', 0, 1, len(ico_sizes))
data_offset = 6 + len(ico_sizes) * 16
entries = b''
image_data = b''
for i, s in enumerate(ico_sizes):
    w = 0 if s >= 256 else s
    png = png_entries[i]
    entries += struct.pack('<BBBBHHIH', w, w, 0, 0, 1, 32, len(png), data_offset + len(image_data))
    image_data += png

with open(os.path.join(DIR, "icon.ico"), "wb") as f:
    f.write(header + entries + image_data)
print(f"  Saved icon.ico ({len(ico_sizes)} sizes, {len(header + entries + image_data)} bytes)")

# icns (256px PNG fallback)
draw_icon(256).save(os.path.join(DIR, "icon.icns"), "PNG")
print("  Saved icon.icns")

# Tray icons
draw_icon(32, for_tray=True).save(os.path.join(DIR, "icon-idle.png"), "PNG")
draw_icon(64, for_tray=True).save(os.path.join(DIR, "icon-idle@2x.png"), "PNG")
print("  Saved tray icons")

print("\nAll icons generated!")
