"""Generate DictateMe app icons - modern stylized waveform mic design."""
from PIL import Image, ImageDraw, ImageFilter
import math
import os

DIR = os.path.dirname(os.path.abspath(__file__))

# Colors
BG = (14, 14, 18)
ACCENT = (255, 186, 8)       # #FFBA08
ACCENT_SOFT = (255, 210, 80)
WHITE = (242, 240, 237)


def draw_icon(size, for_tray=False):
    """Modern icon: stylized 'D' made of sound wave bars."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = max(1, int(size * 0.04))
    color = WHITE if for_tray else ACCENT

    if not for_tray:
        # Background: rounded square with subtle gradient feel
        r = int(size * 0.22)
        # Dark background
        draw.rounded_rectangle(
            [margin, margin, size - margin, size - margin],
            radius=r, fill=BG
        )
        # Very subtle inner glow at top
        for i in range(min(8, size // 16)):
            alpha = max(0, 12 - i * 2)
            draw.rounded_rectangle(
                [margin + i, margin + i, size - margin - i, size - margin - i],
                radius=max(0, r - i),
                outline=(255, 255, 255, alpha)
            )

    cx = size / 2
    cy = size / 2

    # Draw stylized sound wave bars forming a subtle "D" / mic shape
    # 7 vertical bars with varying heights that form a waveform pattern
    num_bars = 7
    total_w = size * 0.52
    bar_w = total_w / (num_bars * 1.8)
    gap = (total_w - bar_w * num_bars) / (num_bars - 1)
    start_x = cx - total_w / 2

    # Heights follow a waveform/mic capsule envelope
    # Center bars taller, edges shorter - like a sound wave
    height_ratios = [0.30, 0.55, 0.80, 1.0, 0.75, 0.50, 0.25]
    max_h = size * 0.48

    for i in range(num_bars):
        h = max_h * height_ratios[i]
        x = start_x + i * (bar_w + gap)
        y_top = cy - h / 2
        y_bot = cy + h / 2
        br = bar_w / 2  # fully rounded ends

        bar_color = color
        # Slight alpha gradient for depth (edges dimmer)
        if not for_tray:
            edge_dist = abs(i - 3) / 3.0  # 0 at center, 1 at edges
            r_val = int(ACCENT[0] * (1 - edge_dist * 0.15))
            g_val = int(ACCENT[1] * (1 - edge_dist * 0.1))
            b_val = int(ACCENT[2])
            bar_color = (r_val, g_val, b_val)

        draw.rounded_rectangle(
            [int(x), int(y_top), int(x + bar_w), int(y_bot)],
            radius=int(br),
            fill=bar_color
        )

    # Small dot below the bars (like a mic stand point)
    dot_r = max(1, int(size * 0.025))
    dot_y = cy + max_h / 2 + size * 0.08
    if not for_tray:
        draw.ellipse(
            [int(cx - dot_r), int(dot_y - dot_r), int(cx + dot_r), int(dot_y + dot_r)],
            fill=(*ACCENT, 120)
        )

    return img


# Generate all required sizes
sizes = {
    "32x32.png": 32,
    "128x128.png": 128,
    "128x128@2x.png": 256,
}

for name, sz in sizes.items():
    icon = draw_icon(sz)
    path = os.path.join(DIR, name)
    icon.save(path, "PNG")
    print(f"  Saved {name} ({sz}x{sz})")

# icon.ico (multi-size Windows icon)
ico_sizes = [16, 24, 32, 48, 64, 128, 256]
ico_images = [draw_icon(s) for s in ico_sizes]
ico_path = os.path.join(DIR, "icon.ico")
ico_images[0].save(
    ico_path, format="ICO",
    sizes=[(s, s) for s in ico_sizes],
    append_images=ico_images[1:]
)
print(f"  Saved icon.ico (multi-size)")

# icon.icns (use 256px PNG as fallback)
icon_256 = draw_icon(256)
icon_256.save(os.path.join(DIR, "icon.icns"), "PNG")
print(f"  Saved icon.icns (256x256)")

# Tray icons (white on transparent)
tray = draw_icon(32, for_tray=True)
tray.save(os.path.join(DIR, "icon-idle.png"), "PNG")
print(f"  Saved icon-idle.png (tray 32x32)")

tray_hi = draw_icon(64, for_tray=True)
tray_hi.save(os.path.join(DIR, "icon-idle@2x.png"), "PNG")
print(f"  Saved icon-idle@2x.png (tray 64x64)")

print("\nAll icons generated!")
