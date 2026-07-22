from __future__ import annotations

from pathlib import Path

from build123d import Box, Color, Compound, Cylinder, Pos, Torus, export_step, fillet


PROJECT = Path(__file__).resolve().parents[1]
SHAPES_DIR = PROJECT / "CellKeeper.3dshapes"
STEP_PATH = SHAPES_DIR / "XFCN_T34008_M3_Terminal_Frame_PCB.step"

# Dimensions from the T34008 M3 terminal frame drawing, in millimeters.
BODY_X_MM = 7.90
BODY_Y_MM = 7.90
BODY_HEIGHT_MM = 11.20
PIN_SPACING_X_MM = 6.90
PIN_SPACING_Y_MM = 5.00
SHEET_THICKNESS_MM = 1.00
TAB_WIDTH_MM = 1.50
OUTER_SHOULDER_FROM_TOP_MM = 6.20
INNER_SHOULDER_FROM_TOP_MM = 5.40
OUTER_SHOULDER_Z_MM = BODY_HEIGHT_MM - OUTER_SHOULDER_FROM_TOP_MM
INNER_SHOULDER_Z_MM = BODY_HEIGHT_MM - INNER_SHOULDER_FROM_TOP_MM
BEND_RADIUS_MM = 0.45
M3_THREAD_MAJOR_DIAMETER_MM = 3.00
M3_THREAD_MINOR_DIAMETER_MM = 2.50
M3_EMBOSS_DIAMETER_MM = 4.20
M3_CENTER_TOTAL_THICKNESS_MM = 2.20
M3_UNDERSIDE_EMBOSS_HEIGHT_MM = M3_CENTER_TOTAL_THICKNESS_MM - SHEET_THICKNESS_MM
SCREW_HEAD_DIAMETER_MM = 5.60
SCREW_HEAD_HEIGHT_MM = 2.20
SCREW_HEAD_UNDERSIDE_GAP_MM = 1.00
SCREW_THREAD_LENGTH_MM = 5.00
SCREW_THREAD_PITCH_MM = 0.50
SCREW_RECESS_DEPTH_MM = 0.45
SCREW_RECESS_WIDTH_MM = 0.55

METAL_COLOR = (0.74, 0.72, 0.66)
SCREW_COLOR = (0.55, 0.55, 0.52)


def with_color(part, color: tuple[float, float, float] = METAL_COLOR):
    part.color = Color(*color)
    return part


def softened(part, radius: float):
    try:
        return fillet(part.edges(), radius)
    except Exception:
        return part


def box_from_extents(x_min: float, x_max: float, y_min: float, y_max: float, z_min: float, z_max: float):
    return Pos(
        (x_min + x_max) / 2.0,
        (y_min + y_max) / 2.0,
        (z_min + z_max) / 2.0,
    ) * Box(x_max - x_min, y_max - y_min, z_max - z_min)


def fillet_outer_bend_edges(part, body_x_min: float, body_x_max: float):
    bend_edges = []
    for edge in part.edges():
        center = edge.center()
        bounds = edge.bounding_box()
        y_length = bounds.max.Y - bounds.min.Y
        is_long_side_edge = abs(y_length - BODY_Y_MM) < 1e-6
        is_top_outer_bend = abs(center.Z - BODY_HEIGHT_MM) < 1e-6 and (
            abs(center.X - body_x_min) < 1e-6 or abs(center.X - body_x_max) < 1e-6
        )
        if is_long_side_edge and is_top_outer_bend:
            bend_edges.append(edge)

    try:
        return fillet(bend_edges, BEND_RADIUS_MM)
    except Exception:
        return part


def make_m3_phillips_screw(center_x: float, center_y: float):
    head_bottom_z = BODY_HEIGHT_MM + SCREW_HEAD_UNDERSIDE_GAP_MM
    head_top_z = head_bottom_z + SCREW_HEAD_HEIGHT_MM
    thread_bottom_z = head_bottom_z - SCREW_THREAD_LENGTH_MM

    shank = Pos(center_x, center_y, (head_bottom_z + thread_bottom_z) / 2.0) * Cylinder(
        M3_THREAD_MAJOR_DIAMETER_MM / 2.0,
        SCREW_THREAD_LENGTH_MM,
    )

    head = Pos(center_x, center_y, (head_bottom_z + head_top_z) / 2.0) * Cylinder(
        SCREW_HEAD_DIAMETER_MM / 2.0,
        SCREW_HEAD_HEIGHT_MM,
    )
    head = softened(head, 0.16)

    recess_z = head_top_z - SCREW_RECESS_DEPTH_MM / 2.0 + 0.01
    recess_length = SCREW_HEAD_DIAMETER_MM * 0.72
    phillips_recess = Pos(center_x, center_y, recess_z) * Box(
        recess_length,
        SCREW_RECESS_WIDTH_MM,
        SCREW_RECESS_DEPTH_MM,
    )
    phillips_recess += Pos(center_x, center_y, recess_z) * Box(
        SCREW_RECESS_WIDTH_MM,
        recess_length,
        SCREW_RECESS_DEPTH_MM,
    )

    screw = (head + shank) - phillips_recess
    screw = softened(screw, 0.04)
    screw = with_color(screw, SCREW_COLOR)

    parts = [screw]
    thread_start_z = thread_bottom_z + SCREW_THREAD_PITCH_MM
    ring_count = int((SCREW_THREAD_LENGTH_MM - SCREW_THREAD_PITCH_MM) / SCREW_THREAD_PITCH_MM)
    for index in range(ring_count):
        thread_z = thread_start_z + index * SCREW_THREAD_PITCH_MM
        thread_ring = Pos(center_x, center_y, thread_z) * Torus(
            M3_THREAD_MAJOR_DIAMETER_MM / 2.0,
            0.025,
        )
        parts.append(with_color(thread_ring, SCREW_COLOR))

    return parts


def make_model() -> Compound:
    """Create the M3 terminal frame aligned to the KiCad footprint pad centers."""
    body_x_min = -0.50
    body_x_max = body_x_min + BODY_X_MM
    body_y_min = -(BODY_Y_MM - PIN_SPACING_Y_MM) / 2.0 - PIN_SPACING_Y_MM
    body_y_max = body_y_min + BODY_Y_MM
    top_z_min = BODY_HEIGHT_MM - SHEET_THICKNESS_MM
    center_x = PIN_SPACING_X_MM / 2.0
    center_y = -PIN_SPACING_Y_MM / 2.0

    screw_cut = Pos(center_x, center_y, BODY_HEIGHT_MM / 2.0) * Cylinder(
        M3_THREAD_MINOR_DIAMETER_MM / 2.0,
        BODY_HEIGHT_MM + M3_CENTER_TOTAL_THICKNESS_MM + 2.0,
    )

    # Form the part as one continuous 1 mm sheet: top plate, side flanges,
    # and lower mounting tabs at the four footprint hole centers.
    outer_shell = box_from_extents(body_x_min, body_x_max, body_y_min, body_y_max, top_z_min, BODY_HEIGHT_MM)
    for x_min, x_max in (
        (body_x_min, body_x_min + SHEET_THICKNESS_MM),
        (body_x_max - SHEET_THICKNESS_MM, body_x_max),
    ):
        outer_shell += box_from_extents(x_min, x_max, body_y_min, body_y_max, OUTER_SHOULDER_Z_MM, top_z_min)

    metal = fillet_outer_bend_edges(outer_shell, body_x_min, body_x_max)

    for x in (0.0, PIN_SPACING_X_MM):
        for y in (0.0, -PIN_SPACING_Y_MM):
            metal += Pos(x, y, INNER_SHOULDER_Z_MM / 2.0) * Box(
                SHEET_THICKNESS_MM,
                TAB_WIDTH_MM,
                INNER_SHOULDER_Z_MM,
            )

    emboss = Pos(center_x, center_y, top_z_min - M3_UNDERSIDE_EMBOSS_HEIGHT_MM / 2.0) * Cylinder(
        M3_EMBOSS_DIAMETER_MM / 2.0,
        M3_UNDERSIDE_EMBOSS_HEIGHT_MM,
    )
    metal += emboss
    metal = metal - screw_cut
    metal = softened(metal, 0.08)
    metal = with_color(metal)

    parts = [metal]

    # Small internal rings give the M3 threaded hole visible detail in KiCad's
    # viewer without requiring a heavy fully modeled helical thread.
    for z in (9.30, 9.80, 10.30, 10.80):
        thread_ring = Pos(center_x, center_y, z) * Torus(
            M3_THREAD_MAJOR_DIAMETER_MM / 2.0,
            0.035,
        )
        parts.append(with_color(thread_ring))

    parts.extend(make_m3_phillips_screw(center_x, center_y))

    return Compound(children=parts)


def main() -> None:
    SHAPES_DIR.mkdir(parents=True, exist_ok=True)
    export_step(make_model(), STEP_PATH)
    print(f"Wrote {STEP_PATH}")


if __name__ == "__main__":
    main()
