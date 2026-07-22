from __future__ import annotations

import math
import re
from pathlib import Path

from build123d import Align, Box, Color, Compound, Cylinder, Location, Pos, Text, TextAlign, export_step, extrude, import_svg
from PIL import Image, ImageDraw, ImageFont, ImageOps


PROJECT = Path(__file__).resolve().parents[1]
SOURCE_TEXTURE = PROJECT / "graphics" / "raspberry-pi-rp2354b.jpg"
SOURCE_LOGO_SVG = PROJECT / "graphics" / "raspberry-pi-svgrepo-com.svg"
SHAPES_DIR = PROJECT / "CellKeeper.3dshapes"
STEP_PATH = SHAPES_DIR / "RP2354B_QFN80.step"
WRL_PATH = SHAPES_DIR / "RP2354B_QFN80_logo.wrl"
TEXTURE_PATH = SHAPES_DIR / "RP2354B_QFN80_texture.jpg"

BODY_X_MM = 10.0
BODY_Y_MM = 10.0
BODY_Z_MM = 0.8
LEAD_COUNT_PER_SIDE = 20
LEAD_PITCH_MM = 0.4
LEAD_WIDTH_MM = 0.22
LEAD_LENGTH_MM = 0.78
LEAD_Z_MM = 0.05
MM_TO_KICAD_WRL = 1.0 / 2.54
IC_BODY_COLOR = (0.148, 0.145, 0.145)
LEAD_COLOR = (0.82, 0.80, 0.75)
MARKING_COLOR = (0.74, 0.74, 0.68)
MARKING_Z_MM = BODY_Z_MM + 0.035
STEP_MARKING_HEIGHT_MM = 0.025
LOGO_Z_MM = MARKING_Z_MM + 0.018
LOGO_SIZE_MM = 5.04
LOGO_CENTER_X_MM = 0.0
LOGO_CENTER_Y_MM = 1.35
LOGO_MESH_RESOLUTION = 320
DOT_CENTER_X_MM = -3.72
DOT_CENTER_Y_MM = 3.10
DOT_RADIUS_MM = 0.30
TEXT_LINE_1_LEFT = "RP2354B0A4"
TEXT_LINE_1_RIGHT = "19"
TEXT_LINE_2_LEFT = "P6AM88.3D"
TEXT_LINE_2_RIGHT = "24"
TEXT_LEFT_X_MM = -4.15
TEXT_RIGHT_X_MM = 4.15
TEXT_LINE_1_Y_MM = -2.45
TEXT_LINE_2_Y_MM = -3.75
TEXT_SIZE_MM = 1.08
TEXT_MASK_SIZE = 650


def make_step_model() -> Compound:
    """Create a simple RP2354B QFN-80 package for mechanical STEP export."""
    body = Pos(0, 0, BODY_Z_MM / 2) * Box(BODY_X_MM, BODY_Y_MM, BODY_Z_MM)
    body.color = Color(*IC_BODY_COLOR)
    parts = [body]
    lead_span_start = -((LEAD_COUNT_PER_SIDE - 1) * LEAD_PITCH_MM) / 2.0
    bottom_z = -LEAD_Z_MM / 2.0
    side_z = 0.12

    for idx in range(LEAD_COUNT_PER_SIDE):
        offset = lead_span_start + idx * LEAD_PITCH_MM
        for termination in (
            # Bottom pads sit under the body and do not protrude past the QFN outline.
            Pos(offset, -BODY_Y_MM / 2 + LEAD_LENGTH_MM / 2, bottom_z) * Box(LEAD_WIDTH_MM, LEAD_LENGTH_MM, LEAD_Z_MM),
            Pos(offset, BODY_Y_MM / 2 - LEAD_LENGTH_MM / 2, bottom_z) * Box(LEAD_WIDTH_MM, LEAD_LENGTH_MM, LEAD_Z_MM),
            Pos(-BODY_X_MM / 2 + LEAD_LENGTH_MM / 2, offset, bottom_z) * Box(LEAD_LENGTH_MM, LEAD_WIDTH_MM, LEAD_Z_MM),
            Pos(BODY_X_MM / 2 - LEAD_LENGTH_MM / 2, offset, bottom_z) * Box(LEAD_LENGTH_MM, LEAD_WIDTH_MM, LEAD_Z_MM),
            # Tiny side terminations are flush with the package sides.
            Pos(offset, -BODY_Y_MM / 2, side_z) * Box(LEAD_WIDTH_MM, 0.04, 0.24),
            Pos(offset, BODY_Y_MM / 2, side_z) * Box(LEAD_WIDTH_MM, 0.04, 0.24),
            Pos(-BODY_X_MM / 2, offset, side_z) * Box(0.04, LEAD_WIDTH_MM, 0.24),
            Pos(BODY_X_MM / 2, offset, side_z) * Box(0.04, LEAD_WIDTH_MM, 0.24),
        ):
            termination.color = Color(*LEAD_COLOR)
            parts.append(termination)

    parts.extend(make_step_markings())
    return Compound(children=parts)


def prepare_texture() -> None:
    SHAPES_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE_TEXTURE) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image = ImageOps.fit(image, (1024, 1024), method=Image.Resampling.LANCZOS)
        image.save(TEXTURE_PATH, quality=95, optimize=True)


def wrl_point(x_mm: float, y_mm: float, z_mm: float) -> tuple[float, float, float]:
    return (x_mm * MM_TO_KICAD_WRL, y_mm * MM_TO_KICAD_WRL, z_mm * MM_TO_KICAD_WRL)


def append_cuboid(
    points: list[tuple[float, float, float]],
    faces: list[list[int]],
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> None:
    cx, cy, cz = center
    sx, sy, sz = (value / 2.0 for value in size)
    corners = [
        wrl_point(cx - sx, cy - sy, cz - sz),
        wrl_point(cx + sx, cy - sy, cz - sz),
        wrl_point(cx + sx, cy + sy, cz - sz),
        wrl_point(cx - sx, cy + sy, cz - sz),
        wrl_point(cx - sx, cy - sy, cz + sz),
        wrl_point(cx + sx, cy - sy, cz + sz),
        wrl_point(cx + sx, cy + sy, cz + sz),
        wrl_point(cx - sx, cy + sy, cz + sz),
    ]
    base = len(points)
    points.extend(corners)
    faces.extend(
        [
            [base + 0, base + 1, base + 2, base + 3],
            [base + 4, base + 7, base + 6, base + 5],
            [base + 0, base + 4, base + 5, base + 1],
            [base + 1, base + 5, base + 6, base + 2],
            [base + 2, base + 6, base + 7, base + 3],
            [base + 3, base + 7, base + 4, base + 0],
        ]
    )


def format_points(points: list[tuple[float, float, float]]) -> str:
    return ",".join(f"{x:.6f} {y:.6f} {z:.6f}" for x, y, z in points)


def format_faces(faces: list[list[int]]) -> str:
    return ",".join(",".join(str(index) for index in face) + ",-1" for face in faces)


def tokenize_svg_path(path_data: str) -> list[str]:
    return re.findall(
        r"[MmLlHhVvCcSsQqTtZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?",
        path_data,
    )


def cubic_point(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    mt = 1.0 - t
    return (
        mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0],
        mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1],
    )


def quad_point(p0, p1, p2, t: float) -> tuple[float, float]:
    mt = 1.0 - t
    return (
        mt**2 * p0[0] + 2 * mt * t * p1[0] + t**2 * p2[0],
        mt**2 * p0[1] + 2 * mt * t * p1[1] + t**2 * p2[1],
    )


def parse_svg_path(path_data: str) -> list[list[tuple[float, float]]]:
    tokens = tokenize_svg_path(path_data)
    i = 0
    cmd = None
    cur = (0.0, 0.0)
    start = None
    contour: list[tuple[float, float]] = []
    contours: list[list[tuple[float, float]]] = []
    last_cubic_ctrl = None
    last_quad_ctrl = None

    def is_cmd(token: str) -> bool:
        return len(token) == 1 and token.isalpha()

    def number() -> float:
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value

    def close_contour() -> None:
        nonlocal contour, start
        if contour:
            if start is not None and contour[-1] != start:
                contour.append(start)
            contours.append(contour)
        contour = []
        start = None

    def line_to(point: tuple[float, float]) -> None:
        nonlocal cur, contour
        if not contour:
            contour.append(cur)
        contour.append(point)
        cur = point

    while i < len(tokens):
        if is_cmd(tokens[i]):
            cmd = tokens[i]
            i += 1
        if cmd is None:
            raise ValueError("Malformed SVG path")

        if cmd in "Mm":
            rel = cmd == "m"
            first = True
            while i < len(tokens) and not is_cmd(tokens[i]):
                x, y = number(), number()
                point = (cur[0] + x, cur[1] + y) if rel else (x, y)
                if first:
                    close_contour()
                    cur = point
                    start = point
                    contour = [point]
                    first = False
                else:
                    line_to(point)
            cmd = "l" if rel else "L"
        elif cmd in "Ll":
            rel = cmd == "l"
            while i < len(tokens) and not is_cmd(tokens[i]):
                x, y = number(), number()
                line_to((cur[0] + x, cur[1] + y) if rel else (x, y))
            last_cubic_ctrl = None
            last_quad_ctrl = None
        elif cmd in "Hh":
            rel = cmd == "h"
            while i < len(tokens) and not is_cmd(tokens[i]):
                x = number()
                line_to((cur[0] + x, cur[1]) if rel else (x, cur[1]))
            last_cubic_ctrl = None
            last_quad_ctrl = None
        elif cmd in "Vv":
            rel = cmd == "v"
            while i < len(tokens) and not is_cmd(tokens[i]):
                y = number()
                line_to((cur[0], cur[1] + y) if rel else (cur[0], y))
            last_cubic_ctrl = None
            last_quad_ctrl = None
        elif cmd in "Cc":
            rel = cmd == "c"
            while i < len(tokens) and not is_cmd(tokens[i]):
                vals = [number() for _ in range(6)]
                p1 = (cur[0] + vals[0], cur[1] + vals[1]) if rel else (vals[0], vals[1])
                p2 = (cur[0] + vals[2], cur[1] + vals[3]) if rel else (vals[2], vals[3])
                p3 = (cur[0] + vals[4], cur[1] + vals[5]) if rel else (vals[4], vals[5])
                if not contour:
                    contour.append(cur)
                for step in range(1, 17):
                    contour.append(cubic_point(cur, p1, p2, p3, step / 16.0))
                cur = p3
                last_cubic_ctrl = p2
                last_quad_ctrl = None
        elif cmd in "Ss":
            rel = cmd == "s"
            while i < len(tokens) and not is_cmd(tokens[i]):
                vals = [number() for _ in range(4)]
                p1 = (
                    (2 * cur[0] - last_cubic_ctrl[0], 2 * cur[1] - last_cubic_ctrl[1])
                    if last_cubic_ctrl
                    else cur
                )
                p2 = (cur[0] + vals[0], cur[1] + vals[1]) if rel else (vals[0], vals[1])
                p3 = (cur[0] + vals[2], cur[1] + vals[3]) if rel else (vals[2], vals[3])
                if not contour:
                    contour.append(cur)
                for step in range(1, 17):
                    contour.append(cubic_point(cur, p1, p2, p3, step / 16.0))
                cur = p3
                last_cubic_ctrl = p2
                last_quad_ctrl = None
        elif cmd in "Qq":
            rel = cmd == "q"
            while i < len(tokens) and not is_cmd(tokens[i]):
                vals = [number() for _ in range(4)]
                p1 = (cur[0] + vals[0], cur[1] + vals[1]) if rel else (vals[0], vals[1])
                p2 = (cur[0] + vals[2], cur[1] + vals[3]) if rel else (vals[2], vals[3])
                if not contour:
                    contour.append(cur)
                for step in range(1, 17):
                    contour.append(quad_point(cur, p1, p2, step / 16.0))
                cur = p2
                last_quad_ctrl = p1
                last_cubic_ctrl = None
        elif cmd in "Tt":
            rel = cmd == "t"
            while i < len(tokens) and not is_cmd(tokens[i]):
                x, y = number(), number()
                p1 = (
                    (2 * cur[0] - last_quad_ctrl[0], 2 * cur[1] - last_quad_ctrl[1])
                    if last_quad_ctrl
                    else cur
                )
                p2 = (cur[0] + x, cur[1] + y) if rel else (x, y)
                if not contour:
                    contour.append(cur)
                for step in range(1, 17):
                    contour.append(quad_point(cur, p1, p2, step / 16.0))
                cur = p2
                last_quad_ctrl = p1
                last_cubic_ctrl = None
        elif cmd in "Zz":
            close_contour()
            cur = start if start is not None else cur
            last_cubic_ctrl = None
            last_quad_ctrl = None
        else:
            raise ValueError(f"Unsupported SVG path command: {cmd}")

    close_contour()
    return [contour for contour in contours if len(contour) >= 4]


def point_in_poly(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi + 1e-20) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def extract_logo_contours() -> list[list[tuple[float, float]]]:
    svg = SOURCE_LOGO_SVG.read_text(encoding="utf-8")
    match = re.search(r'<path[^>]*\sd="([^"]+)"', svg)
    if not match:
        raise ValueError(f"No SVG path data found in {SOURCE_LOGO_SVG}")
    return parse_svg_path(match.group(1))


def make_colored_box(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    z_offset: float = 0.0,
):
    mark = Pos(center_x, center_y, BODY_Z_MM + STEP_MARKING_HEIGHT_MM / 2.0 + z_offset) * Box(
        width,
        height,
        STEP_MARKING_HEIGHT_MM,
    )
    mark.color = Color(*MARKING_COLOR)
    return mark


def make_step_logo_markings() -> list:
    contours = extract_logo_contours()
    all_points = [point for contour in contours for point in contour]
    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    source_size = max(max_x - min_x, max_y - min_y)
    cell = source_size / LOGO_MESH_RESOLUTION
    scale = LOGO_SIZE_MM / source_size
    markings = []

    def is_filled(x: float, y: float) -> bool:
        inside = False
        for contour in contours:
            if point_in_poly(x, y, contour):
                inside = not inside
        return inside

    def add_rect(x0_svg: float, y0_svg: float, x1_svg: float, y1_svg: float) -> None:
        x0 = (x0_svg - center_x) * scale + LOGO_CENTER_X_MM
        x1 = (x1_svg - center_x) * scale + LOGO_CENTER_X_MM
        y0 = (center_y - y0_svg) * scale + LOGO_CENTER_Y_MM
        y1 = (center_y - y1_svg) * scale + LOGO_CENTER_Y_MM
        markings.append(
            make_colored_box(
                (x0 + x1) / 2.0,
                (y0 + y1) / 2.0,
                abs(x1 - x0),
                abs(y1 - y0),
                0.010,
            )
        )

    rows = math.ceil((max_y - min_y) / cell)
    cols = math.ceil((max_x - min_x) / cell)
    for row in range(rows):
        y0 = min_y + row * cell
        y1 = min(y0 + cell, max_y)
        col = 0
        while col < cols:
            x0 = min_x + col * cell
            if is_filled(x0 + cell / 2.0, y0 + cell / 2.0):
                start_col = col
                col += 1
                while col < cols:
                    x_next = min_x + col * cell
                    if not is_filled(x_next + cell / 2.0, y0 + cell / 2.0):
                        break
                    col += 1
                add_rect(min_x + start_col * cell, y0, min(min_x + col * cell, max_x), y1)
            else:
                col += 1
    return markings


def make_step_dot_marking():
    dot = Pos(DOT_CENTER_X_MM, DOT_CENTER_Y_MM, BODY_Z_MM + STEP_MARKING_HEIGHT_MM / 2.0 + 0.015) * Cylinder(
        DOT_RADIUS_MM,
        STEP_MARKING_HEIGHT_MM,
    )
    dot.color = Color(*MARKING_COLOR)
    return dot


def mask_to_step_markings(mask: Image.Image, threshold: int = 80) -> list:
    width, height = mask.size
    cell_x = BODY_X_MM / width
    cell_y = BODY_Y_MM / height
    markings = []

    def add_rect(x0_px: int, y_px: int, x1_px: int) -> None:
        x0 = -BODY_X_MM / 2.0 + x0_px * cell_x
        x1 = -BODY_X_MM / 2.0 + x1_px * cell_x
        y0 = BODY_Y_MM / 2.0 - (y_px + 1) * cell_y
        y1 = BODY_Y_MM / 2.0 - y_px * cell_y
        markings.append(
            make_colored_box(
                (x0 + x1) / 2.0,
                (y0 + y1) / 2.0,
                abs(x1 - x0),
                abs(y1 - y0),
                0.020,
            )
        )

    for y_px in range(height):
        x_px = 0
        while x_px < width:
            if mask.getpixel((x_px, y_px)) > threshold:
                start_x = x_px
                x_px += 1
                while x_px < width and mask.getpixel((x_px, y_px)) > threshold:
                    x_px += 1
                add_rect(start_x, y_px, x_px)
            else:
                x_px += 1
    return markings


def make_text_mask() -> Image.Image:
    mask = Image.new("L", (TEXT_MASK_SIZE, TEXT_MASK_SIZE), 0)
    draw = ImageDraw.Draw(mask)
    draw_text_mm(draw, TEXT_LINE_1_LEFT, -4.15, -2.45, 0.84)
    draw_text_mm(draw, TEXT_LINE_1_RIGHT, 3.85, -2.45, 0.84, "center")
    draw_text_mm(draw, TEXT_LINE_2_LEFT, -4.15, -3.78, 0.76)
    draw_text_mm(draw, TEXT_LINE_2_RIGHT, 3.85, -3.78, 0.76, "center")
    return mask


def make_step_text_markings() -> list:
    return mask_to_step_markings(make_text_mask())


def make_step_markings() -> list:
    markings = make_step_logo_markings()
    markings.append(make_step_dot_marking())
    markings.extend(make_step_text_markings())
    return markings


def make_logo_overlay() -> str:
    contours = extract_logo_contours()
    all_points = [point for contour in contours for point in contour]
    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    source_size = max(max_x - min_x, max_y - min_y)
    cell = source_size / LOGO_MESH_RESOLUTION

    points: list[tuple[float, float, float]] = []
    faces: list[list[int]] = []

    def is_filled(x: float, y: float) -> bool:
        inside = False
        for contour in contours:
            if point_in_poly(x, y, contour):
                inside = not inside
        return inside

    def add_rect(x0_svg: float, y0_svg: float, x1_svg: float, y1_svg: float) -> None:
        base = len(points)
        scale = LOGO_SIZE_MM / source_size
        points.extend(
            [
                wrl_point((x0_svg - center_x) * scale + LOGO_CENTER_X_MM, (center_y - y0_svg) * scale + LOGO_CENTER_Y_MM, LOGO_Z_MM),
                wrl_point((x1_svg - center_x) * scale + LOGO_CENTER_X_MM, (center_y - y0_svg) * scale + LOGO_CENTER_Y_MM, LOGO_Z_MM),
                wrl_point((x1_svg - center_x) * scale + LOGO_CENTER_X_MM, (center_y - y1_svg) * scale + LOGO_CENTER_Y_MM, LOGO_Z_MM),
                wrl_point((x0_svg - center_x) * scale + LOGO_CENTER_X_MM, (center_y - y1_svg) * scale + LOGO_CENTER_Y_MM, LOGO_Z_MM),
            ]
        )
        faces.append([base, base + 1, base + 2, base + 3])

    rows = math.ceil((max_y - min_y) / cell)
    cols = math.ceil((max_x - min_x) / cell)
    for row in range(rows):
        y0 = min_y + row * cell
        y1 = min(y0 + cell, max_y)
        col = 0
        while col < cols:
            x0 = min_x + col * cell
            if is_filled(x0 + cell / 2.0, y0 + cell / 2.0):
                start_col = col
                col += 1
                while col < cols:
                    x_next = min_x + col * cell
                    if not is_filled(x_next + cell / 2.0, y0 + cell / 2.0):
                        break
                    col += 1
                add_rect(min_x + start_col * cell, y0, min(min_x + col * cell, max_x), y1)
            else:
                col += 1

    return f"""Shape {{
  appearance Appearance {{
    material Material {{ diffuseColor {MARKING_COLOR[0]} {MARKING_COLOR[1]} {MARKING_COLOR[2]} emissiveColor 0.08 0.08 0.07 shininess 0.05 }}
  }}
  geometry IndexedFaceSet {{
    solid FALSE
    coordIndex [{format_faces(faces)}]
    coord Coordinate {{ point [{format_points(points)}] }}
  }}
}}
"""


def make_vector_dot() -> str:
    points = [wrl_point(DOT_CENTER_X_MM, DOT_CENTER_Y_MM, MARKING_Z_MM + 0.006)]
    faces: list[list[int]] = []
    segments = 72
    for idx in range(segments):
        angle = 2.0 * math.pi * idx / segments
        points.append(
            wrl_point(
                DOT_CENTER_X_MM + math.cos(angle) * DOT_RADIUS_MM,
                DOT_CENTER_Y_MM + math.sin(angle) * DOT_RADIUS_MM,
                MARKING_Z_MM + 0.006,
            )
        )
    for idx in range(segments):
        faces.append([0, idx + 1, 1 + ((idx + 1) % segments)])

    return f"""Shape {{
  appearance Appearance {{
    material Material {{ diffuseColor {MARKING_COLOR[0]} {MARKING_COLOR[1]} {MARKING_COLOR[2]} emissiveColor 0.08 0.08 0.07 shininess 0.05 }}
  }}
  geometry IndexedFaceSet {{
    solid FALSE
    coordIndex [{format_faces(faces)}]
    coord Coordinate {{ point [{format_points(points)}] }}
  }}
}}
"""


def find_bold_font(size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf"),
    ]
    for font_path in font_candidates:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size_px)
    return ImageFont.load_default()


def draw_text_mm(
    draw: ImageDraw.ImageDraw,
    text: str,
    x_mm: float,
    y_mm: float,
    size_mm: float,
    justify: str = "left",
) -> None:
    px_per_mm = TEXT_MASK_SIZE / BODY_X_MM
    font = find_bold_font(round(size_mm * px_per_mm))
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x_px = round((x_mm + BODY_X_MM / 2.0) * px_per_mm)
    y_px = round((BODY_Y_MM / 2.0 - y_mm) * px_per_mm)
    if justify == "center":
        x_px -= text_width // 2
    draw.text((x_px, y_px - text_height // 2 - bbox[1]), text, fill=255, font=font)


def mesh_from_mask(mask: Image.Image, threshold: int = 80) -> str:
    points: list[tuple[float, float, float]] = []
    faces: list[list[int]] = []
    width, height = mask.size
    cell_x = BODY_X_MM / width
    cell_y = BODY_Y_MM / height

    def add_rect(x0_px: int, y_px: int, x1_px: int) -> None:
        base = len(points)
        x0 = -BODY_X_MM / 2.0 + x0_px * cell_x
        x1 = -BODY_X_MM / 2.0 + x1_px * cell_x
        y0 = BODY_Y_MM / 2.0 - (y_px + 1) * cell_y
        y1 = BODY_Y_MM / 2.0 - y_px * cell_y
        points.extend(
            [
                wrl_point(x0, y0, MARKING_Z_MM + 0.012),
                wrl_point(x1, y0, MARKING_Z_MM + 0.012),
                wrl_point(x1, y1, MARKING_Z_MM + 0.012),
                wrl_point(x0, y1, MARKING_Z_MM + 0.012),
            ]
        )
        faces.append([base, base + 1, base + 2, base + 3])

    for y_px in range(height):
        x_px = 0
        while x_px < width:
            if mask.getpixel((x_px, y_px)) > threshold:
                start_x = x_px
                x_px += 1
                while x_px < width and mask.getpixel((x_px, y_px)) > threshold:
                    x_px += 1
                add_rect(start_x, y_px, x_px)
            else:
                x_px += 1

    return f"""Shape {{
  appearance Appearance {{
    material Material {{ diffuseColor {MARKING_COLOR[0]} {MARKING_COLOR[1]} {MARKING_COLOR[2]} emissiveColor 0.08 0.08 0.07 shininess 0.05 }}
  }}
  geometry IndexedFaceSet {{
    solid FALSE
    coordIndex [{format_faces(faces)}]
    coord Coordinate {{ point [{format_points(points)}] }}
  }}
}}
"""


def make_clean_text_overlay() -> str:
    mask = Image.new("L", (TEXT_MASK_SIZE, TEXT_MASK_SIZE), 0)
    draw = ImageDraw.Draw(mask)
    draw_text_mm(draw, TEXT_LINE_1_LEFT, -4.15, -2.45, 0.84)
    draw_text_mm(draw, TEXT_LINE_1_RIGHT, 3.85, -2.45, 0.84, "center")
    draw_text_mm(draw, TEXT_LINE_2_LEFT, -4.15, -3.78, 0.76)
    draw_text_mm(draw, TEXT_LINE_2_RIGHT, 3.85, -3.78, 0.76, "center")
    return mesh_from_mask(mask)


def write_wrl() -> None:
    content = "\n".join(
        [
            "#VRML V2.0 utf8",
            "# RP2354B QFN-80 top marking overlay generated by python_scripts/generate_rp2354b_model.py",
            "# The chip body is the STEP model; this WRL contains raised SVG logo/dot geometry plus crisp text.",
            make_logo_overlay(),
            make_vector_dot(),
            make_clean_text_overlay(),
        ]
    )
    WRL_PATH.write_text(content, encoding="utf-8")


def color_marking(part):
    part.color = Color(*MARKING_COLOR)
    return part


def make_lightweight_logo_markings() -> list:
    """Use the real SVG outline as a smooth STEP body instead of raster boxes."""
    logo_face = import_svg(SOURCE_LOGO_SVG, align=(Align.CENTER, Align.CENTER))[0]
    bounds = logo_face.bounding_box()
    scale = LOGO_SIZE_MM / max(bounds.size.X, bounds.size.Y)
    logo_face = logo_face.scale(scale)
    logo_face = logo_face.moved(Location((LOGO_CENTER_X_MM, LOGO_CENTER_Y_MM, BODY_Z_MM + 0.006)))
    logo = extrude(logo_face, amount=STEP_MARKING_HEIGHT_MM)
    logo.color = Color(*MARKING_COLOR)
    return [logo]


def make_lightweight_text_marking(
    text: str,
    x_mm: float,
    y_mm: float,
    size_mm: float,
    horizontal_align: TextAlign,
):
    font_path = Path("C:/Windows/Fonts/arialbd.ttf")
    sketch = Pos(x_mm, y_mm, BODY_Z_MM + 0.003) * Text(
        text,
        font_size=size_mm,
        font="Arial",
        font_path=font_path if font_path.exists() else None,
        text_align=(horizontal_align, TextAlign.CENTER),
    )
    part = extrude(sketch, amount=STEP_MARKING_HEIGHT_MM)
    return color_marking(part)


def make_lightweight_text_markings() -> list:
    return [
        make_lightweight_text_marking(TEXT_LINE_1_LEFT, TEXT_LEFT_X_MM, TEXT_LINE_1_Y_MM, TEXT_SIZE_MM, TextAlign.LEFT),
        make_lightweight_text_marking(TEXT_LINE_1_RIGHT, TEXT_RIGHT_X_MM, TEXT_LINE_1_Y_MM, TEXT_SIZE_MM, TextAlign.RIGHT),
        make_lightweight_text_marking(TEXT_LINE_2_LEFT, TEXT_LEFT_X_MM, TEXT_LINE_2_Y_MM, TEXT_SIZE_MM, TextAlign.LEFT),
        make_lightweight_text_marking(TEXT_LINE_2_RIGHT, TEXT_RIGHT_X_MM, TEXT_LINE_2_Y_MM, TEXT_SIZE_MM, TextAlign.RIGHT),
    ]


def make_step_markings() -> list:
    return [
        *make_lightweight_logo_markings(),
        make_step_dot_marking(),
        *make_lightweight_text_markings(),
    ]


def main() -> None:
    if not SOURCE_TEXTURE.exists():
        raise FileNotFoundError(SOURCE_TEXTURE)

    SHAPES_DIR.mkdir(parents=True, exist_ok=True)
    export_step(make_step_model(), STEP_PATH)

    print(f"Wrote {STEP_PATH}")


if __name__ == "__main__":
    main()
