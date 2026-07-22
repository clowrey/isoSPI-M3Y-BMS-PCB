from pathlib import Path
import math
import re


PROJECT = Path(__file__).resolve().parents[1]
SVG_PATH = PROJECT / "graphics" / "raspberry-pi-svgrepo-com.svg"
WRL_PATH = PROJECT / "CellKeeper.3dshapes" / "RP2354B_QFN80_logo.wrl"
MARKER = "# RP2354B visual top marking generated locally"


def tokenize_path(path_data: str) -> list[str]:
    return re.findall(
        r"[MmLlHhVvCcSsQqTtZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?",
        path_data,
    )


def cubic_point(p0, p1, p2, p3, t):
    mt = 1.0 - t
    return (
        mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0],
        mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1],
    )


def quad_point(p0, p1, p2, t):
    mt = 1.0 - t
    return (
        mt**2 * p0[0] + 2 * mt * t * p1[0] + t**2 * p2[0],
        mt**2 * p0[1] + 2 * mt * t * p1[1] + t**2 * p2[1],
    )


def parse_svg_path(path_data: str) -> list[list[tuple[float, float]]]:
    tokens = tokenize_path(path_data)
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

    def line_to(point) -> None:
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
                last_cubic_ctrl = None
                last_quad_ctrl = None
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
                for step in range(1, 13):
                    contour.append(cubic_point(cur, p1, p2, p3, step / 12.0))
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
                for step in range(1, 13):
                    contour.append(cubic_point(cur, p1, p2, p3, step / 12.0))
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
                for step in range(1, 13):
                    contour.append(quad_point(cur, p1, p2, step / 12.0))
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
                for step in range(1, 13):
                    contour.append(quad_point(cur, p1, p2, step / 12.0))
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


def format_logo_mesh(contours: list[list[tuple[float, float]]]) -> str:
    all_points = [point for contour in contours for point in contour]
    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0

    scale = 1.34 / max(max_x - min_x, max_y - min_y)
    logo_center_x = 0.0
    logo_center_y = 0.62
    z = 0.3372
    resolution = 118
    cell = max(max_x - min_x, max_y - min_y) / resolution
    rows = math.ceil((max_y - min_y) / cell)
    cols = math.ceil((max_x - min_x) / cell)
    points: list[tuple[float, float, float]] = []
    indices: list[int] = []

    def is_filled(x: float, y: float) -> bool:
        inside = False
        for contour in contours:
            if point_in_poly(x, y, contour):
                inside = not inside
        return inside

    def add_rect(x0: float, y0: float, x1: float, y1: float) -> None:
        base = len(points)
        for sx, sy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            wx = (sx - center_x) * scale + logo_center_x
            wy = (center_y - sy) * scale + logo_center_y
            points.append((wx, wy, z))
        indices.extend([base, base + 1, base + 2, base + 3, -1])

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

    point_text = ",".join(f"{x:.5f} {y:.5f} {z:.5f}" for x, y, z in points)
    index_text = ",".join(str(index) for index in indices)
    print(f"Contours: {len(contours)}, logo rectangles: {len(indices) // 5}, points: {len(points)}")
    return (
        "Shape {\n"
        "  appearance Appearance { material Material { diffuseColor 0.74 0.74 0.68 emissiveColor 0.10 0.10 0.09 } }\n"
        f"  geometry IndexedFaceSet {{ solid FALSE coordIndex [{index_text}] coord Coordinate {{ point [{point_text}] }} }}\n"
        "}\n"
    )


def main() -> None:
    svg = SVG_PATH.read_text(encoding="utf-8")
    match = re.search(r'<path[^>]*\sd="([^"]+)"', svg)
    if not match:
        raise ValueError(f"No SVG path data found in {SVG_PATH}")

    logo_mesh = format_logo_mesh(parse_svg_path(match.group(1)))
    marking = f"""
{MARKER}
# Raspberry Pi logo generated from graphics/raspberry-pi-svgrepo-com.svg

{logo_mesh}
Transform {{
  translation 0.0 -0.42 0.33730
  children [
    Shape {{
      appearance Appearance {{ material Material {{ diffuseColor 0.74 0.74 0.68 emissiveColor 0.10 0.10 0.09 }} }}
      geometry Text {{ string ["RP2354B"] fontStyle FontStyle {{ family ["SANS"] style "BOLD" size 0.27 justify ["MIDDLE" "MIDDLE"] }} }}
    }}
  ]
}}

Transform {{
  translation 0.0 -0.76 0.33730
  children [
    Shape {{
      appearance Appearance {{ material Material {{ diffuseColor 0.74 0.74 0.68 emissiveColor 0.10 0.10 0.09 }} }}
      geometry Text {{ string ["QFN-80"] fontStyle FontStyle {{ family ["SANS"] size 0.18 justify ["MIDDLE" "MIDDLE"] }} }}
    }}
  ]
}}
"""

    old_wrl = WRL_PATH.read_text(encoding="utf-8")
    base = old_wrl.split(MARKER, 1)[0].rstrip() + "\n"
    WRL_PATH.write_text(base + marking, encoding="utf-8")
    print(f"Wrote {WRL_PATH}")


if __name__ == "__main__":
    main()
