#!/usr/bin/env python
"""Render Scene Prompt UI overlay to show what it looks like."""

from PIL import Image, ImageDraw, ImageFont

# Colors
NVIDIA_GREEN = (118, 185, 0)
BG_COLOR = (20, 20, 30)
TEXT_COLOR = (240, 240, 240)

# Create a mock camera frame (800x600)
width, height = 800, 600
canvas = Image.new("RGBA", (width, height), BG_COLOR + (255,))
draw = ImageDraw.Draw(canvas)

# Try to load fonts (fallback to default if not available)
try:
    font_small = ImageFont.truetype("arial.ttf", 18)
    font_tiny = ImageFont.truetype("arial.ttf", 12)
except:
    font_small = ImageFont.load_default()
    font_tiny = ImageFont.load_default()

print("=" * 70)
print("SCENE PROMPT UI OVERLAY - RENDERING TEST")
print("=" * 70)
print()

# Test 1: Display mode - no prompt set (startup state)
print("TEST 1: Display mode - No prompt set (startup)")
print("  Shows: '(no prompt)' + 'Press P to edit'")
print()

x, y = 20, 20
box_width = 400
box_height = 35

draw.rectangle(
    (x, y, x + box_width, y + box_height),
    fill=(30, 30, 40, 240),
    outline=(100, 100, 120),
    width=2,
)
draw.text(
    (x + 10, y + 8),
    "(no prompt)",
    fill=(120, 120, 120),
    font=font_small,
)
draw.text(
    (x + 10, y + box_height - 20),
    "Press P to edit",
    fill=(150, 150, 150),
    font=font_tiny,
)

canvas.save(f"{width}x{height}_01_startup.png")
print(f"  ✓ Saved: {width}x{height}_01_startup.png")
print()

# Test 2: Display mode - prompt set
print("TEST 2: Display mode - Prompt already set")
print("  Shows: 'Heavy rain on wet road...' + 'Press P to edit'")
print()

canvas = Image.new("RGBA", (width, height), BG_COLOR + (255,))
draw = ImageDraw.Draw(canvas)

draw.rectangle(
    (x, y, x + box_width, y + box_height),
    fill=(30, 30, 40, 240),
    outline=(100, 100, 120),
    width=2,
)
draw.text(
    (x + 10, y + 8),
    "Heavy rain on wet road with wind...",
    fill=(200, 200, 200),
    font=font_small,
)
draw.text(
    (x + 10, y + box_height - 20),
    "Press P to edit",
    fill=(150, 150, 150),
    font=font_tiny,
)

canvas.save(f"{width}x{height}_02_display.png")
print(f"  ✓ Saved: {width}x{height}_02_display.png")
print()

# Test 3: Edit mode - user typing
print("TEST 3: Edit mode - User typing prompt")
print("  Shows: Input field with text + blinking cursor + instructions")
print()

canvas = Image.new("RGBA", (width, height), BG_COLOR + (255,))
draw = ImageDraw.Draw(canvas)

box_height = 50

draw.rectangle(
    (x, y, x + box_width, y + box_height),
    fill=(30, 30, 40, 240),
    outline=NVIDIA_GREEN,
    width=2,
)
draw.text(
    (x + 10, y + 8),
    "heavy rain|",
    fill=NVIDIA_GREEN,
    font=font_small,
)
draw.text(
    (x + 10, y + box_height + 5),
    "Press Enter to send, Esc to cancel",
    fill=(150, 150, 150),
    font=font_tiny,
)

canvas.save(f"{width}x{height}_03_edit.png")
print(f"  ✓ Saved: {width}x{height}_03_edit.png")
print()

print("=" * 70)
print("RENDER RESULTS")
print("=" * 70)
print()
print("Position: Top-left corner, 20px margin")
print("Width: 400px, Height: 35px (display) or 50px (edit)")
print()
print("1. STARTUP STATE (no prompt set):")
print("   ┌──────────────────────────────────────┐")
print("   │ (no prompt)                          │")
print("   │                   Press P to edit    │")
print("   └──────────────────────────────────────┘")
print()
print("2. AFTER PROMPT SENT:")
print("   ┌──────────────────────────────────────┐")
print("   │ Heavy rain on wet road with wind...  │")
print("   │                   Press P to edit    │")
print("   └──────────────────────────────────────┘")
print()
print("3. EDITING (P pressed):")
print("   ┌──────────────────────────────────────┐  ← GREEN outline (NVIDIA_GREEN)")
print("   │ heavy rain|                          │")
print("   ├──────────────────────────────────────┤")
print("   │ Press Enter to send, Esc to cancel   │")
print("   └──────────────────────────────────────┘")
print()
print("=" * 70)
print("ALWAYS VISIBLE: Yes (even at startup with no prompt)")
print("KEYBOARD: P=edit, Type=input, Backspace=delete, Enter=send, Esc=cancel")
print("ASYNC: Send happens in background thread, non-blocking")
print("=" * 70)
