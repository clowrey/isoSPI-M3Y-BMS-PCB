from __future__ import annotations

from pathlib import Path

from build123d import Box, Color, Compound, Pos, Rot, export_step, fillet, import_step


PROJECT = Path(__file__).resolve().parents[1]
SHAPES_DIR = PROJECT / "CellKeeper.3dshapes"
STEP_PATH = SHAPES_DIR / "RJ45_Amphenol_RJHSE538X-02.step"
HC_STEP_PATH = SHAPES_DIR / "HC-RJ45-5JA-2-2-Y.STEP"

# Dimensions are in millimeters. The footprint origin, outer envelope, and pin
# centers match KiCad's RJ45_Amphenol_RJHSE538X-02 footprint/model alignment.
BODY_X_MIN = -4.705
BODY_X_MAX = 27.555
BODY_Y_MIN = -7.75
BODY_Y_MAX = 8.30
BODY_Z_MIN = 0.00
BODY_Z_MAX = 13.46

SECOND_PORT_OFFSET_X_MM = 15.75
PORT_CONTACT_PITCH_MM = 1.016
PORT_CONTACT_COUNT = 8
PORT_OPENING_WIDTH_MM = 12.70
PORT_OPENING_X_MIN = -2.79
PORT_OPENING_Z_MIN = 2.20
PORT_OPENING_Z_MAX = 10.45
PORT_CAVITY_DEPTH_MM = 5.70

CONTACT_PIN_COORDS = (
    *[(index * PORT_CONTACT_PITCH_MM, 0.0 if index % 2 == 0 else 1.78) for index in range(PORT_CONTACT_COUNT)],
    *[
        (SECOND_PORT_OFFSET_X_MM + index * PORT_CONTACT_PITCH_MM, 0.0 if index % 2 == 0 else 1.78)
        for index in range(PORT_CONTACT_COUNT)
    ],
)
LOCATING_PIN_X_MM = (-2.79, 25.66)
LOCATING_PIN_Y_MM = -2.54
LOCATING_PIN_DIAMETER_MM = 2.35
LOCATING_PIN_Z_MIN = -3.18
LOCATING_PIN_Z_MAX = BODY_Z_MIN

SHIELD_PIN_X_MM = (-4.57, 27.43)
SHIELD_PIN_Y_MM = 0.89
SHIELD_PIN_SIZE_X_MM = 0.26
SHIELD_PIN_SIZE_Y_MM = 1.10
SHIELD_PIN_Z_MIN = -3.18
SHIELD_PIN_Z_MAX = BODY_Z_MIN

TH_PIN_SIZE_MM = 0.56
TH_PIN_Z_MIN = -3.18
TH_PIN_Z_MAX = BODY_Z_MIN

LED_PIN_COORDS = (
    (-3.30, 6.60),
    (-1.01, 6.60),
    (8.13, 6.60),
    (10.42, 6.60),
    (12.45, 6.60),
    (14.74, 6.60),
    (23.88, 6.60),
    (26.17, 6.60),
)

BODY_COLOR = (0.70, 0.70, 0.68)
BODY_DARK_COLOR = (0.06, 0.06, 0.06)
SHIELD_COLOR = (0.73, 0.73, 0.70)
CONTACT_GOLD = (1.00, 0.72, 0.12)
LED_YELLOW = (1.00, 0.90, 0.05)
LED_GREEN = (0.08, 0.85, 0.16)
PIN_COLOR = (0.76, 0.76, 0.72)
FRONT_FACE_Y_MM = BODY_Y_MIN


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


def make_body():
    body = Pos(-2.85, -7.293, 3.48) * Rot(90, 0, 0) * import_step(HC_STEP_PATH)
    body.color = Color(*BODY_COLOR)
    return body


def make_front_details() -> list:
    parts = []
    for port_x in (0.0, SECOND_PORT_OFFSET_X_MM):
        x_min = port_x + PORT_OPENING_X_MIN
        x_max = x_min + PORT_OPENING_WIDTH_MM

        parts.extend(
            [
                # Dark internal walls make the two connector openings visible
                # without depending on hidden faces inside an imported STEP.
                box_from_extents(x_min, x_max, BODY_Y_MIN + 0.02, BODY_Y_MIN + 0.10, PORT_OPENING_Z_MIN, PORT_OPENING_Z_MAX, BODY_DARK_COLOR),
                box_from_extents(x_min, x_max, BODY_Y_MIN - 0.02, BODY_Y_MIN + 0.12, PORT_OPENING_Z_MAX, PORT_OPENING_Z_MAX + 0.28, BODY_DARK_COLOR),
                box_from_extents(x_min, x_max, BODY_Y_MIN - 0.02, BODY_Y_MIN + 0.12, PORT_OPENING_Z_MIN - 0.28, PORT_OPENING_Z_MIN, BODY_DARK_COLOR),
                box_from_extents(x_min - 0.28, x_min, BODY_Y_MIN - 0.02, BODY_Y_MIN + 0.12, PORT_OPENING_Z_MIN, PORT_OPENING_Z_MAX, BODY_DARK_COLOR),
                box_from_extents(x_max, x_max + 0.28, BODY_Y_MIN - 0.02, BODY_Y_MIN + 0.12, PORT_OPENING_Z_MIN, PORT_OPENING_Z_MAX, BODY_DARK_COLOR),
                # LED lenses are the two raised windows above each opening.
                softened_box((port_x - 1.95, BODY_Y_MIN - 0.03, 11.35), (2.10, 0.10, 1.05), LED_YELLOW, 0.08),
                softened_box((port_x + 9.05, BODY_Y_MIN - 0.03, 11.35), (2.10, 0.10, 1.05), LED_GREEN, 0.08),
            ]
        )

    return parts


def make_contact_pins(x_offset: float) -> list:
    parts = []
    for index in range(PORT_CONTACT_COUNT):
        contact_x = x_offset + index * PORT_CONTACT_PITCH_MM
        parts.append(
            with_color(
                Pos(contact_x, FRONT_FACE_Y_MM - 0.04, 7.40) * Box(0.34, 0.08, 2.30),
                CONTACT_GOLD,
            )
        )
    return parts


def make_bottom_features() -> list:
    parts = []

    for x, y in (
        *CONTACT_PIN_COORDS,
        *LED_PIN_COORDS,
    ):
        parts.append(
            with_color(
                Pos(x, y, (TH_PIN_Z_MIN + TH_PIN_Z_MAX) / 2.0) * Box(TH_PIN_SIZE_MM, TH_PIN_SIZE_MM, TH_PIN_Z_MAX - TH_PIN_Z_MIN),
                PIN_COLOR,
            )
        )

    for pin_x in SHIELD_PIN_X_MM:
        parts.append(
            with_color(
                Pos(pin_x, SHIELD_PIN_Y_MM, (SHIELD_PIN_Z_MIN + SHIELD_PIN_Z_MAX) / 2.0)
                * Box(SHIELD_PIN_SIZE_X_MM, SHIELD_PIN_SIZE_Y_MM, SHIELD_PIN_Z_MAX - SHIELD_PIN_Z_MIN),
                SHIELD_COLOR,
            )
        )

    return parts


def make_shield_details() -> list:
    # Keep shield details to visible side/top strips only. A full front sheet
    # makes the cut jack openings look like a second body nested inside.
    return [
        box_from_extents(BODY_X_MIN, BODY_X_MAX, BODY_Y_MAX - 0.18, BODY_Y_MAX, BODY_Z_MIN, BODY_Z_MAX, SHIELD_COLOR),
        box_from_extents(BODY_X_MIN, BODY_X_MIN + 0.18, BODY_Y_MIN, BODY_Y_MAX, BODY_Z_MIN, BODY_Z_MAX, SHIELD_COLOR),
        box_from_extents(BODY_X_MAX - 0.18, BODY_X_MAX, BODY_Y_MIN, BODY_Y_MAX, BODY_Z_MIN, BODY_Z_MAX, SHIELD_COLOR),
        box_from_extents(BODY_X_MIN, BODY_X_MAX, BODY_Y_MIN + 0.16, BODY_Y_MAX, BODY_Z_MAX - 0.16, BODY_Z_MAX, SHIELD_COLOR),
    ]


def make_model() -> Compound:
    return Compound(children=[make_body()])


def main() -> None:
    SHAPES_DIR.mkdir(parents=True, exist_ok=True)
    export_step(make_model(), STEP_PATH)
    print(f"Wrote {STEP_PATH}")


if __name__ == "__main__":
    main()
