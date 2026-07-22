from __future__ import annotations

from pathlib import Path

from build123d import Box, Color, Compound, Cylinder, Location, Plane, Polygon, Pos, Text, TextAlign, export_step, extrude, fillet


PROJECT = Path(__file__).resolve().parents[1]
SHAPES_DIR = PROJECT / "CellKeeper.3dshapes"
STEP_PATH = SHAPES_DIR / "S44B-RAD1AK.stp"

# Dimensions are in millimeters. The primary envelope comes from the drawing
# supplied for the S44B-RAD1AK and matches the existing STEP alignment.
BODY_X_MIN = -47.18
BODY_X_MAX = 14.16
BODY_Y_MIN = -29.90
BODY_Y_MAX = 13.00
BODY_Z_MIN = 0.10
BODY_Z_MAX = 37.40

FRONT_FACE_X_MIN = -43.18
FRONT_FACE_X_MAX = 10.16
INNER_FACE_X_MIN = -40.68
INNER_FACE_X_MAX = 7.66
INNER_CAVITY_X_MIN = -38.70
INNER_CAVITY_X_MAX = 5.70
INNER_CAVITY_Z_MIN = 10.30
INNER_CAVITY_Z_MAX = 34.20
SOCKET_FACE_Y = BODY_Y_MIN
SOCKET_CAVITY_DEPTH = 22.50
SOCKET_BACK_WALL_Y = SOCKET_FACE_Y + SOCKET_CAVITY_DEPTH
SOCKET_CONTACT_PROTRUSION = 8.00

PIN_SIZE = 1.10
PIN_Z_MIN = -5.00
PIN_Z_MAX = BODY_Z_MIN

LOWER_PEG_SIZE = 3.40
LOWER_PEG_Z_MIN = PIN_Z_MIN
LOWER_PEG_Z_MAX = BODY_Z_MIN
BOTTOM_BOSS_SIZE = 4.80
BOTTOM_BOSS_Z_MIN = -1.70
BOTTOM_BOSS_Z_MAX = BODY_Z_MIN

HOUSING_COLOR = (0.68, 0.68, 0.64)
DARK_PLASTIC_COLOR = (0.055, 0.055, 0.055)
METAL_COLOR = (0.78, 0.76, 0.70)
MARKING_COLOR = (0.15, 0.15, 0.15)


PIN_POSITIONS = [
    *[(index * -2.54, 0.00) for index in range(14)],
    *[(index * -2.54, 3.00) for index in range(14)],
    *[(x, 7.00) for x in (-2.54, -6.01, -9.51, -13.01, -16.51, -20.01, -23.51, -27.01, -30.48)],
    *[(x, 11.00) for x in (-4.26, -9.51, -13.01, -16.51, -20.01, -23.51, -28.76)],
]


def with_color(part, color: tuple[float, float, float]):
    part.color = Color(*color)
    return part


def softened_box(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    color: tuple[float, float, float],
    radius: float = 0.0,
):
    part = Pos(*center) * Box(*size)
    if radius > 0.0:
        try:
            part = fillet(part.edges(), radius)
        except Exception:
            # Tiny decorative boxes can fail to fillet if OpenCascade considers
            # the requested radius too large for an adjacent edge.
            pass
    return with_color(part, color)


def box_from_extents(
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    z_min: float,
    z_max: float,
    color: tuple[float, float, float],
    radius: float = 0.0,
):
    return softened_box(
        ((x_min + x_max) / 2.0, (y_min + y_max) / 2.0, (z_min + z_max) / 2.0),
        (x_max - x_min, y_max - y_min, z_max - z_min),
        color,
        radius,
    )


def front_box(
    x_min: float,
    x_max: float,
    z_min: float,
    z_max: float,
    color: tuple[float, float, float],
    y_offset: float = 0.0,
    depth: float = 0.34,
    radius: float = 0.0,
):
    y_center = SOCKET_FACE_Y - y_offset
    return softened_box(
        ((x_min + x_max) / 2.0, y_center, (z_min + z_max) / 2.0),
        (x_max - x_min, depth, z_max - z_min),
        color,
        radius,
    )


def make_body():
    """Build the main molded shell from the drawing's side silhouette."""
    side_profile_yz = [
        (BODY_Y_MIN, BODY_Z_MIN),
        (BODY_Y_MIN, BODY_Z_MAX),
        (-0.60, BODY_Z_MAX),
        (-0.60, 29.40),
        (BODY_Y_MAX, 29.40),
        (BODY_Y_MAX, 18.10),
        (5.60, 11.40),
        (5.60, 6.20),
        (-4.10, BODY_Z_MIN),
    ]
    profile = Plane.YZ * Polygon(*side_profile_yz)
    body_width = FRONT_FACE_X_MAX - FRONT_FACE_X_MIN
    body = Pos(FRONT_FACE_X_MAX, 0.0, 0.0) * extrude(profile, amount=body_width)
    cavity_cut = box_from_extents(
        INNER_CAVITY_X_MIN,
        INNER_CAVITY_X_MAX,
        SOCKET_FACE_Y - 0.50,
        SOCKET_BACK_WALL_Y,
        INNER_CAVITY_Z_MIN,
        INNER_CAVITY_Z_MAX,
        DARK_PLASTIC_COLOR,
    )
    body = body - cavity_cut
    body = body.solids()[0]
    body.color = Color(*HOUSING_COLOR)
    return body


def make_pins() -> list:
    parts = []
    pin_center_z = (PIN_Z_MIN + PIN_Z_MAX) / 2.0
    pin_height = PIN_Z_MAX - PIN_Z_MIN

    for x, y in PIN_POSITIONS:
        parts.append(with_color(Pos(x, y, pin_center_z) * Box(PIN_SIZE, PIN_SIZE, pin_height), METAL_COLOR))

    for x, y in ((-43.18, -11.50), (10.16, -11.50)):
        parts.append(
            with_color(
                Pos(x, y, (LOWER_PEG_Z_MIN + LOWER_PEG_Z_MAX) / 2.0)
                * Box(LOWER_PEG_SIZE, LOWER_PEG_SIZE, LOWER_PEG_Z_MAX - LOWER_PEG_Z_MIN),
                METAL_COLOR,
            )
        )

    for x, y in ((-33.02, -11.50), (0.00, -11.50)):
        parts.append(
            softened_box(
                (x, y, (BOTTOM_BOSS_Z_MIN + BOTTOM_BOSS_Z_MAX) / 2.0),
                (BOTTOM_BOSS_SIZE, BOTTOM_BOSS_SIZE, BOTTOM_BOSS_Z_MAX - BOTTOM_BOSS_Z_MIN),
                HOUSING_COLOR,
                0.50,
            )
        )

    return parts


def make_front_face_details() -> list:
    parts = []

    # Raised rectangular bezel around the mating cavity.
    parts.extend(
        [
            front_box(INNER_FACE_X_MIN, INNER_FACE_X_MAX, 33.85, 36.80, HOUSING_COLOR, 0.42, 0.95, 0.40),
            front_box(INNER_FACE_X_MIN, INNER_FACE_X_MAX, 7.20, 10.60, HOUSING_COLOR, 0.42, 0.95, 0.40),
            front_box(INNER_FACE_X_MIN, INNER_FACE_X_MIN + 2.15, 7.20, 36.80, HOUSING_COLOR, 0.42, 0.95, 0.40),
            front_box(INNER_FACE_X_MAX - 2.15, INNER_FACE_X_MAX, 7.20, 36.80, HOUSING_COLOR, 0.42, 0.95, 0.40),
        ]
    )

    # Draw the 22.5 mm deep socket as dark interior surfaces and put the metal
    # contacts 8 mm forward from the new back wall of that void.
    parts.extend(
        [
            box_from_extents(
                INNER_CAVITY_X_MIN,
                INNER_CAVITY_X_MAX,
                SOCKET_BACK_WALL_Y - 0.06,
                SOCKET_BACK_WALL_Y,
                INNER_CAVITY_Z_MIN,
                INNER_CAVITY_Z_MAX,
                DARK_PLASTIC_COLOR,
            ),
            box_from_extents(
                INNER_CAVITY_X_MIN,
                INNER_CAVITY_X_MAX,
                SOCKET_FACE_Y,
                SOCKET_BACK_WALL_Y,
                INNER_CAVITY_Z_MAX - 0.06,
                INNER_CAVITY_Z_MAX,
                DARK_PLASTIC_COLOR,
            ),
            box_from_extents(
                INNER_CAVITY_X_MIN,
                INNER_CAVITY_X_MAX,
                SOCKET_FACE_Y,
                SOCKET_BACK_WALL_Y,
                INNER_CAVITY_Z_MIN,
                INNER_CAVITY_Z_MIN + 0.06,
                DARK_PLASTIC_COLOR,
            ),
            box_from_extents(
                INNER_CAVITY_X_MIN,
                INNER_CAVITY_X_MIN + 0.06,
                SOCKET_FACE_Y,
                SOCKET_BACK_WALL_Y,
                INNER_CAVITY_Z_MIN,
                INNER_CAVITY_Z_MAX,
                DARK_PLASTIC_COLOR,
            ),
            box_from_extents(
                INNER_CAVITY_X_MAX - 0.06,
                INNER_CAVITY_X_MAX,
                SOCKET_FACE_Y,
                SOCKET_BACK_WALL_Y,
                INNER_CAVITY_Z_MIN,
                INNER_CAVITY_Z_MAX,
                DARK_PLASTIC_COLOR,
            ),
        ]
    )

    contact_center_y = SOCKET_BACK_WALL_Y - SOCKET_CONTACT_PROTRUSION / 2.0
    for x in [index * -2.54 for index in range(14)]:
        parts.append(softened_box((x, contact_center_y, 14.15), (0.64, SOCKET_CONTACT_PROTRUSION, 1.80), METAL_COLOR, 0.06))
        parts.append(softened_box((x, contact_center_y, 19.15), (0.64, SOCKET_CONTACT_PROTRUSION, 1.80), METAL_COLOR, 0.06))
        parts.append(softened_box((x, contact_center_y, 25.70), (1.50, SOCKET_CONTACT_PROTRUSION, 3.10), METAL_COLOR, 0.08))

    for x in (-31.50, -1.50):
        parts.append(softened_box((x, contact_center_y, 31.80), (2.80, SOCKET_CONTACT_PROTRUSION, 4.30), METAL_COLOR, 0.12))

    # Three lower latch/inspection slots visible on the lower face.
    for x, width in ((-34.40, 3.60), (-16.50, 4.20), (1.20, 3.60)):
        parts.append(front_box(x - width / 2.0, x + width / 2.0, 4.70, 5.55, DARK_PLASTIC_COLOR, 1.05, 0.10, 0.25))

    # Small cavity-number markers around the connector face.
    for x, z in ((-39.00, 29.60), (-39.20, 21.40), (-39.45, 13.10), (5.95, 29.60), (6.15, 21.40), (6.30, 13.10)):
        parts.append(front_box(x - 0.80, x + 0.80, z - 0.55, z + 0.55, MARKING_COLOR, 1.08, 0.06, 0.10))

    return parts


def make_top_and_side_details() -> list:
    parts = []

    # Tall side towers and the upper hood lip from the drawing's top/front views.
    parts.extend(
        [
            box_from_extents(BODY_X_MIN, BODY_X_MIN + 4.20, -24.50, BODY_Y_MAX, 9.00, BODY_Z_MAX, HOUSING_COLOR, 0.75),
            box_from_extents(BODY_X_MAX - 4.20, BODY_X_MAX, -24.50, BODY_Y_MAX, 9.00, BODY_Z_MAX, HOUSING_COLOR, 0.75),
            box_from_extents(-36.80, 3.80, -29.90, -25.10, 26.00, BODY_Z_MAX, HOUSING_COLOR, 0.45),
            box_from_extents(-39.60, 6.60, -27.40, -24.90, 33.40, BODY_Z_MAX + 0.55, HOUSING_COLOR, 0.35),
        ]
    )

    # Recessed top cavity and the visible row of vertical terminal blades.
    parts.append(box_from_extents(-36.20, 3.20, -24.82, -24.66, 27.30, 36.30, DARK_PLASTIC_COLOR, 0.0))
    for x in [index * -2.54 for index in range(14)]:
        parts.append(softened_box((x, -24.48, 31.20), (0.62, 0.16, 7.20), METAL_COLOR, 0.05))

    # Side mounting ears with dark center marks for the drawing's phi 2.4 holes.
    for x, rotation in ((BODY_X_MIN + 1.40, (0, 90, 0)), (BODY_X_MAX - 1.40, (0, 90, 0))):
        parts.append(with_color(Location((x, -11.50, 20.00), rotation) * Cylinder(3.15, 0.72), HOUSING_COLOR))
        parts.append(with_color(Location((x, -11.50, 20.00), rotation) * Cylinder(1.20, 0.78), DARK_PLASTIC_COLOR))

    # Small upper latch tabs seen along the top edge of the mating face.
    for x in (-34.60, -24.60, -14.60, -4.60):
        parts.append(softened_box((x, BODY_Y_MIN - 0.25, 37.80), (4.40, 1.30, 1.50), HOUSING_COLOR, 0.35))

    return parts


def make_marking() -> list:
    parts = []
    try:
        text = Location((-16.50, BODY_Y_MIN - 1.12, 23.00), (90, 0, 0)) * Text(
            "JSP",
            font_size=3.30,
            font="Arial",
            text_align=(TextAlign.CENTER, TextAlign.CENTER),
        )
        marking = extrude(text, amount=0.06)
        marking.color = Color(*MARKING_COLOR)
        parts.append(marking)
    except Exception:
        pass
    return parts


def make_model() -> Compound:
    parts = [make_body()]
    parts.extend(make_pins())
    parts.extend(make_front_face_details())
    parts.extend(make_top_and_side_details())
    parts.extend(make_marking())

    return Compound(children=parts)


def main() -> None:
    SHAPES_DIR.mkdir(parents=True, exist_ok=True)
    export_step(make_model(), STEP_PATH)
    print(f"Wrote {STEP_PATH}")


if __name__ == "__main__":
    main()
