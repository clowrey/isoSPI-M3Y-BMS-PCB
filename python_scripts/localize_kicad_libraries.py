#!/usr/bin/env python3
"""
Localize KiCad symbol, footprint, and 3D model references for this project.

The script is intentionally project-scoped: it copies only items referenced by
CellKeeper.kicad_sch / CellKeeper.kicad_pcb, preserves existing project-local
libraries, and rewrites external references to a new CellKeeper_Local library.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
SCH = PROJECT / "CellKeeper.kicad_sch"
PCB = PROJECT / "CellKeeper.kicad_pcb"
SYM_TABLE = PROJECT / "sym-lib-table"
FP_TABLE = PROJECT / "fp-lib-table"
LOCAL_SYM_LIB = PROJECT / "CellKeeper_Local.kicad_sym"
LOCAL_FP_LIB = PROJECT / "CellKeeper_Local.pretty"
LOCAL_3D_DIR = PROJECT / "CellKeeper.3dshapes"

LOCAL_SYM_NICK = "CellKeeper_Local"
LOCAL_FP_NICK = "CellKeeper_Local"

KICAD_ROOTS = {
    "KICAD6": Path(r"C:\Program Files\KiCad\6.0\share\kicad"),
    "KICAD7": Path(r"C:\Program Files\KiCad\7.0\share\kicad"),
    "KICAD7.99": Path(r"C:\Program Files\KiCad\7.99\share\kicad"),
    "KICAD8": Path(r"C:\Program Files\KiCad\8.0\share\kicad"),
    "KICAD9": Path(r"C:\Program Files\KiCad\9.0\share\kicad"),
    "KICAD10": Path(r"C:\Program Files\KiCad\10.0\share\kicad"),
}

LOCAL_SYM_LIBS = {"BMS_Library", "RP2350_80QFN", LOCAL_SYM_NICK}
LOCAL_FP_LIBS = {"BMS_Library", "RP2350_80QFN_minimal", LOCAL_FP_NICK}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str, dry_run: bool) -> None:
    if not dry_run:
        path.write_text(text, encoding="utf-8", newline="\n")


def find_matching_paren(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return idx + 1
    raise ValueError(f"unbalanced parentheses at offset {start}")


def top_level_blocks(parent_block: str, token: str) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    depth = 0
    in_string = False
    escaped = False
    idx = 0
    while idx < len(parent_block):
        ch = parent_block[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            idx += 1
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            if depth == 1 and parent_block.startswith(f"({token}", idx):
                end = find_matching_paren(parent_block, idx)
                blocks.append((idx, end, parent_block[idx:end]))
                idx = end
                continue
            depth += 1
        elif ch == ")":
            depth -= 1
        idx += 1
    return blocks


def safe_local_name(lib: str, name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_+.\-]", "_", f"{lib}__{name}")


def split_lib_id(value: str) -> tuple[str, str] | None:
    if ":" not in value:
        return None
    lib, name = value.split(":", 1)
    return lib, name


def collect_symbol_ids(sch_text: str) -> set[str]:
    return set(re.findall(r'\(lib_id "([^"]+:[^"]+)"\)', sch_text))


def collect_footprint_ids(sch_text: str, pcb_text: str) -> set[str]:
    ids = set(re.findall(r'\(footprint "([^"]+:[^"]+)"', pcb_text))
    ids.update(re.findall(r'\(property "Footprint" "([^"]+:[^"]+)"', sch_text))
    return ids


def instance_blocks(text: str, token: str) -> list[str]:
    blocks: list[str] = []
    idx = 0
    needle = f"\n\t({token}"
    while True:
        start = text.find(needle, idx)
        if start < 0:
            break
        start += 1
        try:
            end = find_matching_paren(text, start)
        except ValueError:
            idx = start + len(needle)
            continue
        blocks.append(text[start:end])
        idx = end
    return blocks


def block_property(block: str, name: str) -> str | None:
    match = re.search(r'\(property "' + re.escape(name) + r'" "([^"]*)"', block)
    return match.group(1) if match else None


def align_stale_schematic_footprints(sch_text: str, pcb_text: str, fp_map: dict[str, str]) -> dict[str, str]:
    pcb_by_ref: dict[str, str] = {}
    for block in instance_blocks(pcb_text, "footprint"):
        fp_match = re.search(r'\(footprint "([^"]+:[^"]+)"', block)
        ref = block_property(block, "Reference")
        if fp_match and ref:
            pcb_by_ref[ref] = fp_match.group(1)

    aliases: dict[str, str] = {}
    for block in instance_blocks(sch_text, "symbol"):
        sch_fp = block_property(block, "Footprint")
        ref = block_property(block, "Reference")
        if not sch_fp or sch_fp not in fp_map or not ref:
            continue
        pcb_fp = pcb_by_ref.get(ref)
        if pcb_fp and pcb_fp in fp_map and pcb_fp != sch_fp:
            aliases[sch_fp] = fp_map[pcb_fp]

    return aliases


def align_symbol_default_footprints(sch_text: str, fp_map: dict[str, str]) -> dict[str, str]:
    lib_start = sch_text.find("(lib_symbols")
    if lib_start < 0:
        return {}
    lib_end = find_matching_paren(sch_text, lib_start)
    lib_block = sch_text[lib_start:lib_end]

    defaults: dict[str, str] = {}
    for _start, _end, block in top_level_blocks(lib_block, "symbol"):
        symbol_match = re.search(r'\(symbol\s+"([^"]+)"', block)
        footprint = block_property(block, "Footprint")
        if symbol_match and footprint:
            defaults[symbol_match.group(1)] = footprint

    aliases: dict[str, str] = {}
    for block in instance_blocks(sch_text, "symbol"):
        lib_id_match = re.search(r'\(lib_id "([^"]+)"\)', block)
        instance_fp = block_property(block, "Footprint")
        if not lib_id_match or not instance_fp:
            continue
        default_fp = defaults.get(lib_id_match.group(1))
        if (
            default_fp
            and default_fp != instance_fp
            and default_fp in fp_map
            and instance_fp in fp_map
        ):
            aliases[default_fp] = fp_map[instance_fp]
    return aliases


def symbol_map(symbol_ids: set[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for old_id in sorted(symbol_ids):
        lib, name = old_id.split(":", 1)
        if lib in LOCAL_SYM_LIBS:
            continue
        mapping[old_id] = f"{LOCAL_SYM_NICK}:{safe_local_name(lib, name)}"
    return mapping


def footprint_map(footprint_ids: set[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for old_id in sorted(footprint_ids):
        lib, name = old_id.split(":", 1)
        if lib in LOCAL_FP_LIBS:
            continue
        mapping[old_id] = f"{LOCAL_FP_NICK}:{safe_local_name(lib, name)}"
    return mapping


def rewrite_symbol_block(block: str, old_id: str, new_id: str, fp_map: dict[str, str]) -> str:
    old_lib, old_name = old_id.split(":", 1)
    _new_lib, new_name = new_id.split(":", 1)
    updated = block
    updated = re.sub(
        r'(\(symbol\s+")' + re.escape(old_id) + r'(")',
        rf"\1{new_id}\2",
        updated,
        count=1,
    )
    updated = re.sub(
        r'(\(symbol\s+")' + re.escape(old_name) + r'(?=(_|\b|"))',
        rf"\1{new_name}",
        updated,
    )
    updated = re.sub(
        r'(\(extends\s+")' + re.escape(old_name) + r'(")',
        rf"\1{new_name}\2",
        updated,
    )
    for old_fp, new_fp in fp_map.items():
        updated = updated.replace(f'"{old_fp}"', f'"{new_fp}"')
    return updated


def build_local_symbol_library(sch_text: str, sym_map: dict[str, str], fp_map: dict[str, str]) -> tuple[str, list[str]]:
    lib_start = sch_text.find("(lib_symbols")
    if lib_start < 0:
        raise ValueError("CellKeeper.kicad_sch does not contain a lib_symbols block")
    lib_end = find_matching_paren(sch_text, lib_start)
    lib_block = sch_text[lib_start:lib_end]

    symbols_by_id: dict[str, str] = {}
    for _start, _end, block in top_level_blocks(lib_block, "symbol"):
        match = re.search(r'\(symbol\s+"([^"]+)"', block)
        if match:
            symbols_by_id[match.group(1)] = block

    missing = sorted(old_id for old_id in sym_map if old_id not in symbols_by_id)
    blocks = []
    for old_id in sorted(sym_map):
        if old_id not in symbols_by_id:
            continue
        block = rewrite_symbol_block(symbols_by_id[old_id], old_id, sym_map[old_id], fp_map)
        # Library files store symbol names without the library nickname; the
        # schematic cache keeps the fully-qualified nickname:name form.
        block = block.replace(f'(symbol "{LOCAL_SYM_NICK}:', '(symbol "', 1)
        blocks.append(block)
    body = "\n".join(blocks)
    if body:
        body = "\n" + body.replace("\n\t\t", "\n\t") + "\n"
    text = (
        "(kicad_symbol_lib\n"
        "\t(version 20251024)\n"
        "\t(generator \"localize_kicad_libraries.py\")\n"
        "\t(generator_version \"10.0\")"
        f"{body})\n"
    )
    return text, missing


def rewrite_schematic(sch_text: str, sym_map: dict[str, str], fp_map: dict[str, str]) -> str:
    updated = sch_text
    for old_id, new_id in sym_map.items():
        updated = updated.replace(f'(lib_id "{old_id}")', f'(lib_id "{new_id}")')
        updated = updated.replace(f'(symbol "{old_id}"', f'(symbol "{new_id}"')
        old_name = old_id.split(":", 1)[1]
        new_name = new_id.split(":", 1)[1]
        updated = re.sub(
            r'(\(symbol\s+")' + re.escape(old_name) + r'(?=(_|\b|"))',
            rf"\1{new_name}",
            updated,
        )
        updated = re.sub(
            r'(\(extends\s+")' + re.escape(old_name) + r'(")',
            rf"\1{new_name}\2",
            updated,
        )
    for old_fp, new_fp in fp_map.items():
        updated = updated.replace(f'"{old_fp}"', f'"{new_fp}"')
    return updated


def rewrite_pcb_footprints(pcb_text: str, fp_map: dict[str, str]) -> str:
    updated = pcb_text
    for old_fp, new_fp in fp_map.items():
        updated = updated.replace(f'(footprint "{old_fp}"', f'(footprint "{new_fp}"')
    return updated


def resolve_footprint_source(lib: str, name: str) -> Path | None:
    candidates = [
        PROJECT / f"{lib}.pretty" / f"{name}.kicad_mod",
        PROJECT.parent / f"{lib}.pretty" / f"{name}.kicad_mod",
    ]
    candidates.extend(PROJECT.glob(f"*.pretty/{name}.kicad_mod"))
    candidates.extend(PROJECT.parent.glob(f"*.pretty/{name}.kicad_mod"))
    for root in KICAD_ROOTS.values():
        candidates.append(root / "footprints" / f"{lib}.pretty" / f"{name}.kicad_mod")
    for path in candidates:
        if path.exists():
            return path
    return None


def extract_pcb_footprint(pcb_text: str, footprint_id: str) -> str | None:
    needle = f'(footprint "{footprint_id}"'
    start = pcb_text.find(needle)
    if start < 0:
        return None
    end = find_matching_paren(pcb_text, start)
    return pcb_text[start:end]


def block_first_string(block: str, key: str) -> str | None:
    match = re.search(r'\(' + re.escape(key) + r'\s+"([^"]+)"', block)
    return match.group(1) if match else None


def strip_library_child_blocks(block: str, keys: set[str]) -> str:
    chunks: list[str] = []
    idx = 0
    while idx < len(block):
        if block[idx] == "(":
            token = re.match(r"\(([A-Za-z0-9_]+)", block[idx:])
            if token and token.group(1) in keys:
                end = find_matching_paren(block, idx)
                idx = end
                continue
        chunks.append(block[idx])
        idx += 1
    return "".join(chunks)


def deboardify_footprint(block: str, old_name: str, new_name: str) -> str:
    text = rewrite_footprint_name(block, old_name, new_name)

    # The first board-level (at ...) fixes placement; library footprints should
    # keep relative coordinates only.
    text = re.sub(r'\n\t+\(at [-0-9.]+ [-0-9.]+(?: [-0-9.]+)?\)', "", text, count=1)
    text = re.sub(r'\n\t+\(uuid "[^"]+"\)', "", text)
    text = re.sub(r'\n\t+\(path "[^"]*"\)', "", text)
    text = re.sub(r'\n\t+\(sheetname "[^"]*"\)', "", text)
    text = re.sub(r'\n\t+\(sheetfile "[^"]*"\)', "", text)
    text = re.sub(r'\s+\(net \d+ "[^"]*"\)', "", text)

    text = re.sub(
        r'(\(property "Reference" )"[^"]+"',
        r'\1"REF**"',
        text,
        count=1,
    )
    text = re.sub(
        r'(\(property "Value" )"[^"]+"',
        rf'\1"{new_name}"',
        text,
        count=1,
    )
    return text


def rewrite_footprint_name(text: str, old_name: str, new_name: str) -> str:
    return re.sub(
        r'(\(footprint\s+")' + re.escape(old_name) + r'(")',
        rf"\1{new_name}\2",
        text,
        count=1,
    )


def resolve_model_path(raw: str) -> Path | None:
    value = raw.replace("/", "\\")
    env_match = re.match(r"^\$\{(KICAD\d+)_3DMODEL_DIR\}\\(.+)$", value)
    if env_match:
        tail = Path(env_match.group(2))
        candidate = try_model_candidates(tail, KICAD_ROOTS.get(env_match.group(1)))
        if candidate:
            return candidate

    if value.startswith("${BMS}\\"):
        tail = value[len("${BMS}\\") :]
        for base in (PROJECT / "bms.3dshapes", PROJECT.parent / "bms.3dshapes"):
            candidate = base / tail
            if candidate.exists():
                return candidate

    path = Path(value)
    if path.is_absolute() and path.exists():
        return path

    candidate = (PROJECT / raw).resolve()
    if candidate.exists():
        return candidate
    name = Path(value).name
    candidate = find_model_by_name(name)
    if candidate:
        return candidate
    return None


MODEL_NAME_CACHE: dict[str, Path | None] = {}


def model_name_variants(name: str) -> list[str]:
    stem = Path(name).stem
    suffix = Path(name).suffix
    variants = [name]
    for ext in (suffix, suffix.lower(), suffix.upper(), ".step", ".STEP", ".stp", ".STP", ".wrl", ".WRL"):
        candidate = stem + ext
        if candidate not in variants:
            variants.append(candidate)
    return variants


def try_model_candidates(tail: Path, preferred_root: Path | None = None) -> Path | None:
    roots = []
    if preferred_root is not None:
        roots.append(preferred_root)
    roots.extend(root for root in KICAD_ROOTS.values() if root not in roots)

    tail_parts = tail.parts
    for root in roots:
        for variant in model_name_variants(tail.name):
            candidate = root / "3dmodels" / Path(*tail_parts[:-1]) / variant
            if candidate.exists():
                return candidate
    return find_model_by_name(tail.name)


def find_model_by_name(name: str) -> Path | None:
    if name in MODEL_NAME_CACHE:
        return MODEL_NAME_CACHE[name]
    variants = set(model_name_variants(name))
    for root in KICAD_ROOTS.values():
        if not root.exists():
            continue
        for base in (root / "3dmodels", root / "demos"):
            if not base.exists():
                continue
            for variant in variants:
                matches = list(base.rglob(variant))
                if matches:
                    MODEL_NAME_CACHE[name] = matches[0]
                    return matches[0]
    MODEL_NAME_CACHE[name] = None
    return None


def copy_and_rewrite_models(text: str, dry_run: bool) -> tuple[str, dict[str, Path], list[str]]:
    copied: dict[str, Path] = {}
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        raw = match.group(1)
        if raw.startswith("${KIPRJMOD}/CellKeeper.3dshapes/"):
            return match.group(0)

        source = resolve_model_path(raw)
        if source is None:
            if raw not in missing:
                missing.append(raw)
            return match.group(0)

        dest_name = source.name
        dest = LOCAL_3D_DIR / dest_name
        if dest.exists() and source.resolve() != dest.resolve() and dest.stat().st_size != source.stat().st_size:
            dest_name = f"{source.parent.name}__{source.name}"
            dest = LOCAL_3D_DIR / dest_name
        copied[raw] = dest
        if not dry_run:
            LOCAL_3D_DIR.mkdir(exist_ok=True)
            if not dest.exists():
                shutil.copy2(source, dest)
        return f'(model "${{KIPRJMOD}}/CellKeeper.3dshapes/{dest_name}"'

    rewritten = re.sub(r'\(model "([^"]+)"', replace, text)
    return rewritten, copied, missing


def copy_local_footprints(fp_map: dict[str, str], pcb_text: str, dry_run: bool) -> tuple[list[str], list[Path]]:
    missing: list[str] = []
    written: list[Path] = []
    planned_destinations: set[str] = set()
    if not dry_run:
        LOCAL_FP_LIB.mkdir(exist_ok=True)

    for old_fp, new_fp in sorted(fp_map.items()):
        lib, old_name = old_fp.split(":", 1)
        _new_lib, new_name = new_fp.split(":", 1)
        if new_name in planned_destinations:
            continue
        planned_destinations.add(new_name)
        source = resolve_footprint_source(lib, old_name)
        if source is None:
            text = extract_pcb_footprint(pcb_text, old_fp)
            if text is None:
                missing.append(old_fp)
                continue
            text = deboardify_footprint(text, old_name, new_name)
        else:
            text = read_text(source)
            text = rewrite_footprint_name(text, old_name, new_name)
        text, _copied, model_missing = copy_and_rewrite_models(text, dry_run)
        missing.extend(f"{old_fp} model {item}" for item in model_missing)

        dest = LOCAL_FP_LIB / f"{new_name}.kicad_mod"
        if not dry_run:
            dest.write_text(text, encoding="utf-8", newline="\n")
        written.append(dest)
    return missing, written


def ensure_table_entry(table_text: str, nick: str, uri: str) -> str:
    if f'(name "{nick}")' in table_text:
        return table_text
    insert = f'\t(lib (name "{nick}") (type "KiCad") (uri "{uri}") (options "") (descr ""))\n'
    end = table_text.rfind(")\n")
    if end < 0:
        return table_text + "\n" + insert + ")\n"
    return table_text[:end] + insert + table_text[end:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes")
    args = parser.parse_args()
    dry_run = not args.apply

    sch_text = read_text(SCH)
    pcb_text = read_text(PCB)

    sym_ids = collect_symbol_ids(sch_text)
    fp_ids = collect_footprint_ids(sch_text, pcb_text)
    sym_map = symbol_map(sym_ids)
    fp_map = footprint_map(fp_ids)
    fp_map.update(align_stale_schematic_footprints(sch_text, pcb_text, fp_map))
    fp_map.update(align_symbol_default_footprints(sch_text, fp_map))
    stale_tps5430_fp = "easyeda2kicad:ESOP-8_L4.9-W3.9-P1.27-LS6.0-TL-EP"
    actual_tps5430_fp = "Package_SO:TI_SO-PowerPAD-8_ThermalVias"
    if stale_tps5430_fp in fp_map and actual_tps5430_fp in fp_map:
        fp_map[stale_tps5430_fp] = fp_map[actual_tps5430_fp]

    local_sym_text, missing_symbols = build_local_symbol_library(sch_text, sym_map, fp_map)
    fp_missing, fp_written = copy_local_footprints(fp_map, pcb_text, dry_run)

    sch_text = rewrite_schematic(sch_text, sym_map, fp_map)
    pcb_text = rewrite_pcb_footprints(pcb_text, fp_map)
    pcb_text, model_copied, model_missing = copy_and_rewrite_models(pcb_text, dry_run)

    sym_table = ensure_table_entry(
        read_text(SYM_TABLE),
        LOCAL_SYM_NICK,
        "${KIPRJMOD}/CellKeeper_Local.kicad_sym",
    )
    fp_table = ensure_table_entry(
        read_text(FP_TABLE),
        LOCAL_FP_NICK,
        "${KIPRJMOD}/CellKeeper_Local.pretty",
    )

    if not dry_run:
        if sym_map or not LOCAL_SYM_LIB.exists():
            write_text(LOCAL_SYM_LIB, local_sym_text, dry_run)
        write_text(SCH, sch_text, dry_run)
        write_text(PCB, pcb_text, dry_run)
        write_text(SYM_TABLE, sym_table, dry_run)
        write_text(FP_TABLE, fp_table, dry_run)

    print("Mode:", "dry-run" if dry_run else "apply")
    print(f"External symbol IDs localized: {len(sym_map)}")
    print(f"External footprint IDs localized: {len(fp_map)}")
    print(f"Footprint files written: {len(fp_written)}")
    print(f"3D model references copied/relinked: {len(model_copied)}")
    print(f"Missing embedded symbol definitions: {len(missing_symbols)}")
    print(f"Missing footprint sources/model refs from footprints: {len(fp_missing)}")
    print(f"Missing PCB model sources: {len(model_missing)}")

    if missing_symbols:
        print("\nMissing symbols:")
        for item in missing_symbols:
            print(f"  {item}")
    if fp_missing:
        print("\nMissing footprint/model sources:")
        for item in sorted(set(fp_missing)):
            print(f"  {item}")
    if model_missing:
        print("\nMissing PCB model sources:")
        for item in sorted(set(model_missing)):
            print(f"  {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
