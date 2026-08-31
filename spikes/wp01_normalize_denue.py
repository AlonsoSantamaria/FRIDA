"""Bounded WP01-only DENUE normalization and edition comparison."""
from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path

KEEP = (
    "id", "clee", "codigo_act", "nombre_act", "per_ocu", "nom_vial",
    "nomb_asent", "cve_mun", "municipio", "cve_loc", "localidad",
    "ageb", "manzana", "latitud", "longitud", "fecha_alta",
)


def rows(zip_path: Path):
    with zipfile.ZipFile(zip_path) as archive:
        member = next(name for name in archive.namelist() if name.endswith("denue_inegi_22_.csv"))
        with archive.open(member) as raw:
            reader = csv.DictReader((line.decode("cp1252") for line in raw))
            return [{field: row.get(field, "").strip() for field in KEEP} for row in reader]


def location(row):
    return tuple(row[k] for k in ("nom_vial", "nomb_asent", "cve_mun", "cve_loc", "ageb", "manzana", "latitud", "longitud"))


def main(raw_2025: Path, raw_2026: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=False)
    old, new = rows(raw_2025), rows(raw_2026)
    for edition, data in (("2025_05", old), ("2026_05_corrected", new)):
        with (out_dir / f"denue_qro_{edition}_minimal.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=("edition",) + KEEP)
            writer.writeheader()
            writer.writerows({"edition": edition, **row} for row in data)
    before, after = ({r["clee"]: r for r in data} for data in (old, new))
    fields = ("clee", "prior_id", "current_id", "classification")
    comparison = []
    for clee in sorted(before.keys() | after.keys()):
        a, b = before.get(clee), after.get(clee)
        if not a:
            label = "DIRECTORY_ADDITION"
        elif not b:
            label = "DIRECTORY_REMOVAL"
        elif a["codigo_act"] != b["codigo_act"]:
            label = "CLASSIFICATION_CHANGED"
        elif location(a) != location(b):
            label = "LOCATION_CHANGED"
        else:
            label = "MATCHED_UNCHANGED"
        comparison.append({"clee": clee, "prior_id": a["id"] if a else "", "current_id": b["id"] if b else "", "classification": label})
    with (out_dir / "denue_qro_0525_0526_comparison.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(comparison)
    counts = {}
    for row in comparison:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    print({"2025_records": len(old), "2026_records": len(new), "comparison": counts,
           "identifier_changed_or_unresolved": "Not inferable without retaining prohibited business-name fields; no such inference was made.",
           "edition_correction_affected": "Requires official correction CLEE list to be joined before any affected records are labeled."})


if __name__ == "__main__":
    main(*(Path(arg) for arg in sys.argv[1:]))
