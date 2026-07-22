# CellKeeper BMS — Rev1

KiCad PCB design for the **CellKeeper Battery Management System**, a replacement BMS controller for battery packs using the isoSPI protocol.

## Overview

- **MCU:** Raspberry Pi RP2354B (dual Cortex-M33 @ 150 MHz)
- **Current sensing:** TI INA228 (20-bit ADC, shunt-based)
- **Pack voltage:** 6-channel monitoring via precision dividers
- **BMB communication:** isoSPI master with galvanic isolation (Manchester encoding via PIO)
- **CAN bus:** 500 kbps, hardware transceiver
- **Contactor control:** 4-channel PWM outputs with inrush limiting
- **Input:** 12 V nominal; rated for up to 400 V DC pack voltage

## Repository Contents

| Path | Description |
|------|-------------|
| `CellKeeper.kicad_pro` | KiCad project file |
| `CellKeeper.kicad_sch` | Schematic |
| `CellKeeper.kicad_pcb` | PCB layout |
| `CellKeeper_Local.kicad_sym` / `CellKeeper_Local.pretty/` | Local symbol and footprint libraries |
| `CellKeeper.3dshapes/` | 3D models |
| `graphics/` | Silkscreen artwork and images |
| `production/` | Manufacturing outputs |
| `python_scripts/` | Utility scripts |

## Getting Started

1. Install [KiCad 10.0+](https://www.kicad.org/download/)
2. Clone this repository
3. Open `CellKeeper.kicad_pro` — project libraries load from the local `sym-lib-table` and `fp-lib-table`

## Safety

⚠️ This board interfaces with 400 V battery packs that can deliver **lethal** current. Only qualified personnel should work on high-voltage systems. This is a Rev1 development design — untested, no warranty, use at your own risk.

## Acknowledgments

- **Damien Maguire & Tom de Bree** — Original BATMan BMS software

## License

GPL-3.0 — see [LICENSE](LICENSE).
