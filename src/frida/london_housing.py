"""GLA housing-led population projection adapter (context, never observed fact)."""
from __future__ import annotations
from datetime import UTC, datetime
from hashlib import sha256
import io, json, zipfile
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from .london_observation import LondonSnapshot

LONDON_HOUSING_LED = "LONDON_GLA_HOUSING_LED_SW8"
URL = "https://data.london.gov.uk/download/2zp76/q43/gla_2024_housing_led_central_msoa_la_level.xlsx"
NS = {"x":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

def _cell_value(cell):
    inline=cell.find("x:is",NS)
    if inline is not None: return "".join(inline.itertext())
    value=cell.find("x:v",NS)
    return value.text if value is not None else ""

def _column(ref: str) -> str:
    return "".join(c for c in ref if c.isalpha())

def normalize_housing_led_xlsx(payload: bytes, *, retrieved_at: datetime | None=None) -> LondonSnapshot:
    with zipfile.ZipFile(io.BytesIO(payload)) as workbook:
        root=ET.fromstring(workbook.read("xl/worksheets/sheet4.xml"))
    totals={"Lambeth":{}, "Wandsworth":{}}; header=None
    for row in root.findall(".//x:sheetData/x:row",NS):
        values={_column(c.attrib.get("r", "")):_cell_value(c) for c in row.findall("x:c",NS)}
        if header is None:
            if "area_name" in values.values(): header={value:key for key,value in values.items()}; continue
            continue
        area=values.get(header["gss_name"], "").strip()
        age=values.get(header["age"], "").strip(); sex=values.get(header["sex"], "").strip()
        if area not in totals or values.get(header["area_code"], "") != "total" or values.get(header["area_name"], "") != "total" or sex != "persons": continue
        for year,col in header.items():
            if year.isdigit() and values.get(col, ""):
                totals[area][year]=totals[area].get(year,0)+round(float(values[col]))
    rows=[{"borough":borough,"persons":totals[borough]} for borough in totals]
    if any(not row["persons"] for row in rows): raise ValueError("GLA housing-led workbook has no complete SW8 borough context")
    state={"kind":"housing_led_population_projection","scope":"Lambeth and Wandsworth context for SW8/Battersea","projection_release":"GLA 2024-based, published August 2026","boroughs":sorted(rows,key=lambda r:r["borough"])}
    canonical=json.dumps(state,sort_keys=True,separators=(",",":"))
    return LondonSnapshot(LONDON_HOUSING_LED,"Greater London Authority Demography",URL,retrieved_at or datetime.now(tz=UTC),"2026-08-28",{"coverage":"Lambeth and Wandsworth; borough context only","kind":"housing-led population projection"},state,sha256(canonical.encode()).hexdigest(),"london-housing-led-v1","london-housing-led-normalization-v1")

def fetch_housing_led() -> LondonSnapshot:
    request=Request(URL,headers={"Accept":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","User-Agent":"FRIDA/1.0 official-observation"})
    with urlopen(request,timeout=60) as response: return normalize_housing_led_xlsx(response.read())
