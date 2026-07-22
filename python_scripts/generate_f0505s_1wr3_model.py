from __future__ import annotations

from pathlib import Path

from build123d import Box, Color, Compound, Location, Pos, Text, TextAlign, export_step, extrude


PROJECT = Path(__file__).resolve().parents[1]
SHAPES_DIR = PROJECT / "CellKeeper.3dshapes"
STEP_PATH = SHAPES_DIR / "F0505S-1WR3.step"

# Dimensions from the package drawing, in millimeters.
BODY_LENGTH_Y_MM = 19.65
BODY_DEPTH_X_MM = 6.00
BODY_HEIGHT_Z_MM = 10.16
PIN_LENGTH_Z_MM = 4.10
PIN_WIDTH_MM = 0.50
PIN_ROW_TO_FRONT_X_MM = 0.90
PIN_1_TO_BODY_LEFT_Y_MM = 2.21
PIN_PITCH_MM = 2.54
PIN_ROW_CENTER_Y_MM = 3 * PIN_PITCH_MM
PART_NUMBER = "F0505S-1WR3"
TEXT_SIZE_MM = 2.25
TEXT_RAISED_HEIGHT_MM = 0.04

# KiCad footprint coordinates use pin 1 as the origin and run the SIP pin row
# along +Y. The PCB footprint only has electrical pins 1, 2, 5, and 7.
PIN_Y_POSITIONS_MM = {
    "1": 0.0,
    "2": PIN_PITCH_MM,
    "5": 4 * PIN_PITCH_MM,
    "7": 6 * PIN_PITCH_MM,
}

# Keep the footprint pin row on X=0, but put the body on the opposite side
# from the first generated model so the pins are close to the package face.
BODY_X_MIN_MM = -PIN_ROW_TO_FRONT_X_MM
BODY_X_MAX_MM = BODY_DEPTH_X_MM - PIN_ROW_TO_FRONT_X_MM
BODY_Y_MIN_MM = -PIN_1_TO_BODY_LEFT_Y_MM
BODY_Y_MAX_MM = BODY_LENGTH_Y_MM - PIN_1_TO_BODY_LEFT_Y_MM

BODY_COLOR = (0.08, 0.08, 0.08)
PIN_COLOR = (0.78, 0.76, 0.70)
MARKING_COLOR = (0.92, 0.92, 0.86)


def make_model() -> Compound:
    """Create a simple SIP DC/DC converter model aligned to the KiCad footprint."""
    body_center_x = (BODY_X_MIN_MM + BODY_X_MAX_MM) / 2.0
    body_center_y = (BODY_Y_MIN_MM + BODY_Y_MAX_MM) / 2.0
    body = Pos(body_center_x, body_center_y, BODY_HEIGHT_Z_MM / 2.0) * Box(
        BODY_DEPTH_X_MM,
        BODY_LENGTH_Y_MM,
        BODY_HEIGHT_Z_MM,
    )
    body.color = Color(*BODY_COLOR)

    parts = [body]

    for pin_y in PIN_Y_POSITIONS_MM.values():
        pin = Pos(0, pin_y, -PIN_LENGTH_Z_MM / 2.0) * Box(
            PIN_WIDTH_MM,
            PIN_WIDTH_MM,
            PIN_LENGTH_Z_MM,
        )
        pin.color = Color(*PIN_COLOR)
        parts.append(pin)

    marking_face_x = BODY_X_MAX_MM + 0.03
    marker_margin_mm = 0.90
    marker_y = BODY_Y_MIN_MM + marker_margin_mm
    marker_z = marker_margin_mm

    # The package artwork is rotated 180 degrees around Z relative to the
    # first generated model, while the pins remain aligned to the footprint.
    marker = Pos(marking_face_x, marker_y, marker_z) * Box(
        0.06,
        0.85,
        0.85,
    )
    marker.color = Color(*MARKING_COLOR)
    parts.append(marker)

    text = Location(
        (marking_face_x + TEXT_RAISED_HEIGHT_MM / 2.0, body_center_y, BODY_HEIGHT_Z_MM / 2.0),
        (0, 90, 90),
    ) * Text(
        PART_NUMBER,
        font_size=TEXT_SIZE_MM,
        font="Arial",
        text_align=(TextAlign.CENTER, TextAlign.CENTER),
    )
    text_marking = extrude(text, amount=TEXT_RAISED_HEIGHT_MM)
    text_marking.color = Color(*MARKING_COLOR)
    parts.append(text_marking)

    return Compound(children=parts)


def main() -> None:
    SHAPES_DIR.mkdir(parents=True, exist_ok=True)
    export_step(make_model(), STEP_PATH)
    print(f"Wrote {STEP_PATH}")


if __name__ == "__main__":
    main()
