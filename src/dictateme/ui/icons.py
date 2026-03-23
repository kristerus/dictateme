"""Icon generation for the system tray.

Generates simple colored circle icons programmatically to avoid
shipping image assets. Icons indicate the current application state.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

# Icon size (system tray typically uses 16x16 or 32x32)
ICON_SIZE = 64

# Colors for each state
COLORS = {
    "idle": "#4CAF50",        # Green
    "recording": "#F44336",   # Red
    "processing": "#FF9800",  # Orange
    "loading": "#9E9E9E",     # Gray
    "error": "#F44336",       # Red
}


def create_icon(state: str = "idle") -> Image.Image:
    """Create a tray icon for the given state.

    Draws a filled circle with a state-dependent color on a
    transparent background.

    Args:
        state: One of 'idle', 'recording', 'processing', 'loading', 'error'.

    Returns:
        PIL Image suitable for pystray.
    """
    color = COLORS.get(state, COLORS["idle"])
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw filled circle with slight padding
    padding = 4
    draw.ellipse(
        [padding, padding, ICON_SIZE - padding, ICON_SIZE - padding],
        fill=color,
        outline="#FFFFFF",
        width=2,
    )

    # Add inner indicator for recording (pulsing dot effect)
    if state == "recording":
        inner_pad = ICON_SIZE // 4
        draw.ellipse(
            [inner_pad, inner_pad, ICON_SIZE - inner_pad, ICON_SIZE - inner_pad],
            fill="#FFFFFF",
        )

    return img
