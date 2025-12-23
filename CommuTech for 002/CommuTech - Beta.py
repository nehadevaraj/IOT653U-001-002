'''
stations.json and lines.json: https://gist.github.com/paulcuth/1111303
used CRS codes for battersea power station and nine elms: https://techforum.tfl.gov.uk/t/crs-codes-and-other-three-letter-codes-for-battersea-power-station-and-nine-elms/1923
'''

import json
from pathlib import Path
import streamlit as st

#app config:
st.set_page_config(page_title="CommuTech (Beta)",page_icon="🚇",layout="wide",)
st.title("🚇 CommuTech (Beta)")
st.caption("Phase 1: Journey setup + zones/lines (offline)")

#helpers:
LINE_NAME = {
    "B": "Bakerloo",
    "Ce": "Central",
    "Ci": "Circle",
    "D": "District",
    "H": "Hammersmith & City",
    "J": "Jubilee",
    "M": "Metropolitan",
    "N": "Northern",
    "P": "Piccadilly",
    "V": "Victoria",
    "W": "Waterloo & City",}

def parse_station_value(v: str):
    parts = [p.strip() for p in v.split("|") if p.strip()]
    name = parts[0]
    zones = [int(z) for z in parts[1:]]#1 or 2 ints
    return name, sorted(set(zones))

def format_station_label(code: str, name: str) -> str:
    return f"{name} ({code})"

def format_zones(zones: list[int]) -> str:
    if not zones:
        return "Unknown"
    if len(zones) == 1:
        return f"Zone {zones[0]}"
    return f"Zones {zones[0]}/{zones[1]}"

def expand_line_codes(codes: list[str]) -> list[str]:
    return [LINE_NAME.get(c, c) for c in codes]

def estimate_peak_fare_zone_based(origin_zones: list[int], dest_zones: list[int]) -> tuple[int, int]:
    candidates = []
    for oz in origin_zones:
        for dz in dest_zones:
            mn = min(oz, dz)
            mx = max(oz, dz)
            candidates.append((mx - mn, mn, mx))
    if not candidates:
        return (0, 0)
    _, mn, mx = min(candidates, key=lambda t: t[0])
    return mn, mx

#data loading:
@st.cache_data(show_spinner=False)
def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))

try:
    stations_raw = load_json("stations.json")
    lines_raw = load_json("lines.json")
except FileNotFoundError:
    st.error("Couldn't find stations.json and/or lines.json in this folder. Put them next to this .py file.")
    st.stop()
except json.JSONDecodeError as e:
    st.error(f"One of your JSON files isn't valid JSON: {e}")
    st.stop()

#building parsed station dict:
stations = {}
for code, v in stations_raw.items():
    name, zones = parse_station_value(v)
    stations[code] = {"name": name, "zones": zones}

#basic integrity check for phase 1:
missing_lines = sorted([c for c in stations.keys() if c not in lines_raw])
missing_stations = sorted([c for c in lines_raw.keys() if c not in stations])

with st.expander("Data checks (Phase 1)", expanded=False):
    st.write(f"Stations loaded: **{len(stations)}**")
    st.write(f"Lines entries loaded: **{len(lines_raw)}**")
    if missing_lines:
        st.warning(f"{len(missing_lines)} station codes are missing from lines.json (showing first 15): {missing_lines[:15]}")
    if missing_stations:
        st.warning(f"{len(missing_stations)} line entries have no matching station in stations.json (first 15): {missing_stations[:15]}")
    if not missing_lines and not missing_stations:
        st.success("Station codes match between stations.json and lines.json ✅")

#UI controls:
#sort dropdown by station name:
sorted_codes = sorted(stations.keys(), key=lambda c: stations[c]["name"].lower())
labels = {c: format_station_label(c, stations[c]["name"]) for c in sorted_codes}
st.sidebar.header("Journey inputs")
from_code = st.sidebar.selectbox("From", options=sorted_codes, format_func=lambda c: labels[c], index=0)
to_code = st.sidebar.selectbox("To", options=sorted_codes, format_func=lambda c: labels[c], index=1 if len(sorted_codes) > 1 else 0)

#compute outputs:
from_name = stations[from_code]["name"]
to_name = stations[to_code]["name"]
from_zones = stations[from_code]["zones"]
to_zones = stations[to_code]["zones"]
from_lines = expand_line_codes(lines_raw.get(from_code, []))
to_lines = expand_line_codes(lines_raw.get(to_code, []))
intersection = sorted(set(from_lines).intersection(set(to_lines)))
union = sorted(set(from_lines).union(set(to_lines)))
recommended = intersection if intersection else union
mn, mx = estimate_peak_fare_zone_based(from_zones, to_zones)
zone_summary = f"Estimated zone span: **{mn} → {mx}**" if mn and mx else "Zone span unavailable"

#layout:
c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("From")
    st.write(f"**{from_name}** (`{from_code}`)")
    st.write(format_zones(from_zones))
    st.write("Lines:", ", ".join(from_lines) if from_lines else "—")

with c2:
    st.subheader("To")
    st.write(f"**{to_name}** (`{to_code}`)")
    st.write(format_zones(to_zones))
    st.write("Lines:", ", ".join(to_lines) if to_lines else "—")

with c3:
    st.subheader("Journey summary")
    st.info(zone_summary)
    st.write("**Recommended line(s)** (simple):")
    st.write(", ".join(recommended) if recommended else "—")
    st.caption("Note: fare logic is Phase 1 placeholder (zone-span based). Phase 2 will align with TfL peak fare rules more precisely.")

st.divider()
st.subheader("Next steps for Phase 1")

st.write(
    "- Add a **peak fare table** (zones band → price)\n"
    "- Replace the placeholder estimate with your agreed TfL-like peak logic\n"
    "- Add a clean 'commute snapshot' section (still offline)\n")