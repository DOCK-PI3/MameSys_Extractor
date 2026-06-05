#!/usr/bin/env python3
"""
Genera el icono mame.ico con diseño arcade (joystick + botones).

Ejecutar:
    python generate_icon.py
"""

from PIL import Image, ImageDraw


def create_arcade_icon() -> Image.Image:
    """Crea una imagen .ico con diseño arcade."""
    img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Fondo redondeado oscuro ---
    bg_color = (43, 43, 58, 255)
    for y in range(20, 236):
        for x in range(20, 236):
            dx_left, dx_right = x - 20, 236 - x
            dy_top, dy_bottom = y - 20, 236 - y
            skip = False
            for dx, dy in [(dx_left, dy_top), (dx_right, dy_top),
                           (dx_left, dy_bottom), (dx_right, dy_bottom)]:
                if dx < 30 and dy < 30 and (30 - dx) ** 2 + (30 - dy) ** 2 > 900:
                    skip = True
            if not skip:
                img.putpixel((x, y), bg_color)

    # --- Borde glow azul ---
    for y in range(17, 239):
        for x in range(17, 239):
            dx_left, dx_right = x - 17, 239 - x
            dy_top, dy_bottom = y - 17, 239 - y
            skip = False
            for dx, dy in [(dx_left, dy_top), (dx_right, dy_top),
                           (dx_left, dy_bottom), (dx_right, dy_bottom)]:
                if dx < 33 and dy < 33 and (33 - dx) ** 2 + (33 - dy) ** 2 > 1089:
                    skip = True
            if not skip and img.getpixel((x, y))[3] == 0:
                img.putpixel((x, y), (138, 180, 248, 255))

    # --- Joystick (círculo + palo + bola) ---
    cx, cy = 128, 160
    # Base circular
    for y in range(cy - 35, cy + 36):
        for x in range(cx - 35, cx + 36):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist <= 35:
                r = max(50, int(100 - dist * 1.5))
                g = max(100, int(180 - dist * 2.5))
                b = max(150, int(248 - dist * 3))
                img.putpixel((x, y), (r, g, b, 255))
    # Palo
    for y in range(cy - 50, cy - 35):
        for x in range(cx - 6, cx + 7):
            if img.getpixel((x, y))[3] == 0:
                img.putpixel((x, y), (180, 200, 240, 255))
    # Bola roja
    bx, by = cx, cy - 57
    for y in range(by - 15, by + 16):
        for x in range(bx - 15, bx + 16):
            if (x - bx) ** 2 + (y - by) ** 2 <= 225:
                img.putpixel((x, y), (255, 80, 80, 255))

    # --- 4 botones de colores ---
    positions = [(170, 130), (190, 150), (170, 170), (150, 150)]
    colors = [(255, 200, 60), (60, 200, 100), (60, 140, 255), (255, 80, 80)]
    for (px, py), col in zip(positions, colors):
        for y in range(py - 14, py + 15):
            for x in range(px - 14, px + 15):
                dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
                if dist <= 14:
                    f = 1 - dist / 16
                    r = min(255, int(col[0] * (0.6 + 0.4 * f)))
                    g = min(255, int(col[1] * (0.6 + 0.4 * f)))
                    b = min(255, int(col[2] * (0.6 + 0.4 * f)))
                    img.putpixel((x, y), (r, g, b, 255))

    # --- Brillo superior (marquee) ---
    for y in range(30, 70):
        for x in range(60, 196):
            arch_y = 30 + ((x - 128) ** 2) / 300
            if y > arch_y:
                p = img.getpixel((x, y))
                if p[3] != 0:
                    img.putpixel((x, y), (
                        min(255, p[0] + 30),
                        min(255, p[1] + 30),
                        min(255, p[2] + 30),
                        p[3],
                    ))

    return img


if __name__ == "__main__":
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    icon = create_arcade_icon()
    icon.save("mame.ico", format="ICO", sizes=sizes)
    print("mame.ico generado correctamente!")
