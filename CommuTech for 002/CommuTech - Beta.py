'''
reference: stations.json and lines.json: https://gist.github.com/paulcuth/1111303
reference: used CRS codes for battersea power station and nine elms: https://techforum.tfl.gov.uk/t/crs-codes-and-other-three-letter-codes-for-battersea-power-station-and-nine-elms/1923
'''

import json
from pathlib import Path
import streamlit as st
import random

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

#commute-smart recommender logic:
INTERCHANGE_PRIORITY = {
    "Jubilee",
    "Central",
    "Northern",
    "Victoria",
    "Piccadilly",
    "District",
    "Circle",
    "Hammersmith & City",
    "Metropolitan",
    "Bakerloo",
    "Waterloo & City",}

#phase 2: CommuTech Cockpit pipeline
st.markdown("#### 🧭 CommuTech Cockpit (Phase 2)")
st.caption("Your personalised service radar.")
st.info("Phase 2 placeholder: live service status + arrivals + disruption insights (API) and ML predictions will appear here.")
#reference: https://www.google.com/url?sa=t&source=web&rct=j&opi=89978449&url=https://www.london.gov.uk/media/107475/download&ved=2ahUKEwiht77b39ORAxXWTkEAHfKQCDAQFnoECBgQAQ&usg=AOvVaw3RtmOGoB1-GSkm7g0RqnGI
PEAK_FARE_BY_ZONES_KEY = {#zone 1 ranges
    "1": 2.90,
    "12": 3.50,
    "123": 3.80,
    "1234": 4.60,
    "12345": 5.20,
    "123456": 5.80,
    "1234567": 6.70,
    "12345678": 8.20,
    "123456789": 8.30,

    #outer-zone equivalents (non-zone-1)
    "2": 2.10, "3": 2.10, "4": 2.10, "5": 2.10, "6": 2.10,
    "23": 2.30, "34": 2.30, "45": 2.30, "56": 2.30,
    "234": 3.00, "345": 3.00, "456": 3.00,
    "2345": 3.20, "3456": 3.20,
    "23456": 3.60,
    "234567": 4.90,
    "2345678": 5.60,
    "23456789": 5.60,
    "34567": 4.00,
    "345678": 4.80,
    "3456789": 5.00,
    "4567": 3.20,
    "45678": 4.00,
    "456789": 4.10,
    "567": 2.90,
    "5678": 3.20,
    "56789": 3.50,
    "67": 2.20,
    "678": 2.90,
    "6789": 3.00,
    "7": 2.00,
    "78": 2.20,
    "789": 2.30,
    "89": 2.20,}

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

#commute-smart recommender logic:
def suggest_interchange_line(union_lines: list[str]) -> str | None:
    """
    Pick the highest priority line that exists in the union.\n
    Returns the line name (e.g., 'Jubilee') or None. \n
    """
    union_set = set(union_lines)
    for line in INTERCHANGE_PRIORITY:
        if line in union_set:
            return line
    return None #BOSCH IM THE GOAT

#fare logic defs:
def zones_key(min_zone: int, max_zone: int) -> str:
    """Return the contiguous zones key like '2345' for min=2 max=5."""
    return "".join(str(z) for z in range(min_zone, max_zone + 1))

def fare_range_for_station_pair(origin_zones: list[int], dest_zones: list[int]):
    """
    For boundary stations (e.g. 2|3), try all zone combinations and return:
    - min fare + its zones key
    - max fare + its zones key
    This is Phase 1: zone-based estimate only (no route graph).
    """
    fares = []
    for oz in origin_zones:
        for dz in dest_zones:
            mn, mx = min(oz, dz), max(oz, dz)
            key = zones_key(mn, mx)
            fare = PEAK_FARE_BY_ZONES_KEY.get(key)
            if fare is not None:
                fares.append((fare, key))

    if not fares:
        return None, None, None, None

    fares.sort(key=lambda t: t[0])
    min_fare, min_key = fares[0]
    max_fare, max_key = fares[-1]
    return min_fare, max_fare, min_key, max_key

def price_band(fare: float) -> str:
    """Simple Phase 1 buckets."""
    if fare <= 2.30:
        return "Cheaper"
    if fare <= 4.00:
        return "Mid"
    return "Expensive"

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
#fancy UI for downdrops (dont spend too long on this):
PLACEHOLDER = "Select station"
from_options = [PLACEHOLDER] + sorted_codes
to_options = [PLACEHOLDER] + sorted_codes
from_code = st.sidebar.selectbox(
    "From",
    options=from_options,
    format_func=lambda c: PLACEHOLDER if c == PLACEHOLDER else labels[c],
    index=0,)
to_code = st.sidebar.selectbox(
    "To",
    options=to_options,
    format_func=lambda c: PLACEHOLDER if c == PLACEHOLDER else labels[c],
    index=0,)
if from_code == PLACEHOLDER or to_code == PLACEHOLDER:
    st.info("Select your **From** and **To** stations to see the journey summary.")
    st.stop()

#compute outputs:
from_name = stations[from_code]["name"]
to_name = stations[to_code]["name"]
from_zones = stations[from_code]["zones"]
to_zones = stations[to_code]["zones"]
from_lines = expand_line_codes(lines_raw.get(from_code, []))
to_lines = expand_line_codes(lines_raw.get(to_code, []))
intersection = sorted(set(from_lines).intersection(set(to_lines)))
union = sorted(set(from_lines).union(set(to_lines)))
journey_hint = None
if intersection:
    #if there are shared lines, randomly picking ONE
    recommended_line = random.choice(intersection)
    recommended = [recommended_line]
else:
    origin_pick = random.choice(from_lines) if from_lines else None
    dest_pick = random.choice(to_lines) if to_lines else None
    #recommended "target" line is the destination line - post 002 submission
    recommended_line = dest_pick
    recommended = [recommended_line] if recommended_line else []
    if origin_pick and dest_pick:
        journey_hint = f"Start on **{origin_pick}**, then interchange onto **{dest_pick}** to reach **{to_name}**."
    elif dest_pick:
        journey_hint = f"Interchange onto **{dest_pick}** to reach **{to_name}**."
    else:
        journey_hint = "No line suggestion available for this journey."

#zone summary:
min_fare, max_fare, min_key, max_key = fare_range_for_station_pair(from_zones, to_zones)

if min_fare is None:
    zone_summary = "Fare estimate unavailable (zone key not found)"
    fare_text = "—"
    band_text = "—"
else:
    #avg fare for boundary ambiguity
    avg_fare = (min_fare + max_fare) / 2

    if min_fare == max_fare:
        zone_summary = f"Zones key: **{min_key}**"
        fare_text = f"£{min_fare:.2f}"
    else:
        zone_summary = f"Best-case key: **{min_key}** • Worst-case key: **{max_key}**"
        fare_text = f"£{min_fare:.2f} – £{max_fare:.2f} (avg £{avg_fare:.2f})"

    band_text = price_band(avg_fare) #using mean or average instead of best or worst case

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
    st.write("**Peak fare estimate (Phase 1):**", fare_text)
    st.write("**Relative price score:**", band_text)
    st.caption(
        "Phase 1 uses a zones-based fare table. Because boundary stations can be treated as either zone, "
        "we use the mean of best/worst zone-interpretations as a simple estimate (may not always match TfL). "
        "Phase 2 will use TfL Single Fare Finder.")
    st.write("**Recommended line:**")
    if journey_hint:
        st.caption(journey_hint)
    st.write(", ".join(recommended) if recommended else "—")

st.divider()
st.subheader("Next steps for Phase 1")

st.write(
    "- Add a **basic routing layer** (Phase 1.5): simplest graph-based route or interchange station hints\n"
    "- Polish UI: 'Commute summary' card styling + clearer wording\n"
    "- Phase 2: CommuTech Cockpit (live status + arrivals + route sequence via Unified API)\n")

