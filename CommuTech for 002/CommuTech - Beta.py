'''
reference: stations.json and lines.json: https://gist.github.com/paulcuth/1111303
reference: used CRS codes for battersea power station and nine elms: https://techforum.tfl.gov.uk/t/crs-codes-and-other-three-letter-codes-for-battersea-power-station-and-nine-elms/1923
'''

import json
from pathlib import Path
import streamlit as st
import random
import os
import requests
from datetime import datetime

#app config:
st.set_page_config(page_title="CommuTech (Beta)",page_icon="🚇",layout="wide",)
st.title("🚇 CommuTech (Beta)")
st.markdown("_Smarter planning for London commutes_")

#API STUFF:
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

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
INTERCHANGE_PRIORITY = [
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
    "Waterloo & City",]

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

#API HELPERS:
TFL_BASE = "https://api.tfl.gov.uk"
def get_tfl_key() -> str | None:
    return os.getenv("TFL_API_KEY")
def tfl_get(path: str, params: dict | None = None):
    """Simple GET wrapper with app_key added automatically."""
    key = get_tfl_key()
    if not key:
        return None, "Missing API key"
    params = params or {}
    params["app_key"] = key
    url = f"{TFL_BASE}{path}"
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}: {r.text[:200]}"
        return r.json(), None
    except Exception as e:
        return None, str(e)

def severity_weight(desc: str) -> int:
    """Lower is better. Rough weighting (Phase 2 heuristic)."""
    if not desc:
        return 1
    d = desc.lower()
    if "good" in d:
        return 0
    if "minor" in d:
        return 2
    if "part" in d or "reduced" in d:
        return 4
    if "severe" in d:
        return 6
    if "suspended" in d or "closed" in d:
        return 8
    return 3#fallback

def line_score(line_obj: dict) -> int:
    """
    Combined score = severity weight + number of disruption messages.
    Higher score => worse line.
    """
    statuses = line_obj.get("lineStatuses") or []
    if not statuses:
        return 1
    #using the worst status entry if multiple
    worst = max(statuses, key=lambda s: severity_weight(s.get("statusSeverityDescription", "")))
    sev = severity_weight(worst.get("statusSeverityDescription", ""))
    #counting messages (reason texts)
    msg_count = sum(1 for s in statuses if (s.get("reason") or "").strip())
    return sev + msg_count

def fetch_tube_status():
    """Returns list of line objects."""
    data, err = tfl_get("/Line/Mode/tube/Status")
    return data, err

def stoppoint_search(station_name: str):
    """Returns StopPoint search results for a station name."""
    data, err = tfl_get(f"/StopPoint/Search/{station_name}")
    return data, err

def stoppoint_arrivals(stop_id: str):
    """Returns arrivals list for a StopPoint id."""
    data, err = tfl_get(f"/StopPoint/{stop_id}/Arrivals")
    return data, err

#data quality badge!:
def compute_data_quality(stations: dict, lines_raw: dict):
    """
    Returns: (status, details)\n
      status: "OK" or "WARN"\n
      details: list[str] of issues\n
    """
    issues = []
    #stations missing from lines.json
    missing_lines = [sid for sid in stations.keys() if sid not in lines_raw]
    if missing_lines:
        issues.append(f"{len(missing_lines)} station codes missing from lines.json (e.g., {', '.join(missing_lines[:5])}{'...' if len(missing_lines) > 5 else ''})")
    #line codes not recognised
    known_codes = set(LINE_NAME.keys())
    unknown_codes = set()
    for sid, codes in lines_raw.items():
        for c in codes:
            if c not in known_codes:
                unknown_codes.add(c)
    if unknown_codes:
        issues.append(f"Unknown line codes detected: {', '.join(sorted(unknown_codes))}")
    #zone values out of expected range
    out_of_range = []
    for sid, meta in stations.items():
        for z in meta.get("zones", []):
            if z < 1 or z > 9:
                out_of_range.append((sid, z))
    if out_of_range:
        sample = ", ".join([f"{sid}:{z}" for sid, z in out_of_range[:5]])
        issues.append(f"Zone values out of expected range (1–9): {sample}{'...' if len(out_of_range) > 5 else ''}")
    status = "OK" if not issues else "WARN"
    return status, issues

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
journey_ready = not (from_code == PLACEHOLDER or to_code == PLACEHOLDER)

from_name = to_name = None
from_lines = to_lines = []
if journey_ready:
    from_name = stations[from_code]["name"]
    to_name = stations[to_code]["name"]
    from_lines = expand_line_codes(lines_raw.get(from_code, []))
    to_lines = expand_line_codes(lines_raw.get(to_code, []))
if not journey_ready:
    st.info("Select your **From** and **To** stations to personalise your CommuTech Cockpit and Journey Summary.")

#CommuTech Cockpit Code (triple alliteration, how fun):
st.markdown("### 🧭 CommuTech Cockpit")
st.caption("Your personalised service radar.")

api_key_present = get_tfl_key() is not None

#manual refresh button
colA, colB = st.columns([1, 3])
with colA:
    refresh = st.button("🔄 Refresh live data")
with colB:
    if not api_key_present:
        st.warning("Live features disabled until a TfL API key is set (TFL_API_KEY). Basic features still work.")

#session cache for live data
if "live" not in st.session_state:
    st.session_state["live"] = {"status": None, "status_ts": None, "arrivals": None, "arrivals_ts": None, "dest_stop": None}

#fetching on demand
if refresh and api_key_present:
    tube_status, err = fetch_tube_status()
    if err:
        st.session_state["live"]["status"] = None
        st.session_state["live"]["status_ts"] = None
        st.error(f"Couldn’t load Tube status: {err}")
    else:
        st.session_state["live"]["status"] = tube_status
        st.session_state["live"]["status_ts"] = datetime.now().strftime("%H:%M:%S")

#network pulse for API 
tube_status = st.session_state["live"]["status"]
ts = st.session_state["live"]["status_ts"]

if not api_key_present:
    st.info("Set `TFL_API_KEY` to enable live status + arrivals.")
elif tube_status is None:
    st.info("Click **Refresh live data** to load the Network Pulse.")
else:
    #computing headline metrics
    scored = []
    good = 0
    disrupted = 0
    for ln in tube_status:
        statuses = ln.get("lineStatuses") or []
        desc = (statuses[0].get("statusSeverityDescription") if statuses else "") or ""
        if "Good Service" in desc:
            good += 1
        else:
            disrupted += 1
        scored.append((line_score(ln), ln.get("name", "Unknown"), desc))

    scored_sorted = sorted(scored, key=lambda x: x[0])
    best3 = scored_sorted[:3]
    worst3 = list(reversed(scored_sorted[-3:]))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Lines monitored", str(len(tube_status)))
    m2.metric("Good service", str(good))
    m3.metric("Disrupted", str(disrupted))
    m4.metric("Last refreshed", ts)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top 3 best")
        for score, name, desc in best3:
            st.write(f"✅ **{name}** — {desc} (score {score})")
    with c2:
        st.subheader("Top 3 worst")
        for score, name, desc in worst3:
            st.write(f"⚠️ **{name}** — {desc} (score {score})")
            
    #JOURNEY ZOOM-IN + ARRIVALS PREVIEW:
    if journey_ready:
    
        st.divider()
        st.subheader("Your commute zoom-in")
    
        # relevant lines (union + highlight intersection)
        rel_union = sorted(set(from_lines).union(set(to_lines)))
        rel_intersection = sorted(set(from_lines).intersection(set(to_lines)))
    
        if rel_union:
            st.write("**Relevant lines:**", ", ".join(rel_union))
        if rel_intersection:
            st.success("Direct line(s): " + ", ".join(rel_intersection))
    
        # status filtered to relevant lines
        name_to_obj = {ln.get("name"): ln for ln in tube_status}
        rel_status = []
        for ln_name in rel_union:
            obj = name_to_obj.get(ln_name)
            if not obj:
                continue
            statuses = obj.get("lineStatuses") or []
            desc = (statuses[0].get("statusSeverityDescription") if statuses else "") or "Unknown"
            rel_status.append((line_score(obj), ln_name, desc))
    
        if rel_status:
            rel_status.sort(key=lambda x: x[0])  # best -> worst
            for score, ln_name, desc in rel_status:
                tag = "DIRECT" if ln_name in rel_intersection else "RELEVANT"
                st.write(f"**{ln_name}** — {desc}  ·  _{tag}_  ·  score {score}")
    
        # Arrivals preview (destination only): fetch on refresh
        if refresh:
            search, err = stoppoint_search(to_name)
            if err:
                st.error(f"StopPoint search failed: {err}")
            else:
                matches = (search.get("matches") if isinstance(search, dict) else []) or []
                stop_id = matches[0].get("id") if matches else None
                st.session_state["live"]["dest_stop"] = stop_id
    
                if stop_id:
                    arr, err2 = stoppoint_arrivals(stop_id)
                    if err2:
                        st.error(f"Arrivals fetch failed: {err2}")
                        st.session_state["live"]["arrivals"] = None
                        st.session_state["live"]["arrivals_ts"] = None
                    else:
                        st.session_state["live"]["arrivals"] = arr
                        st.session_state["live"]["arrivals_ts"] = datetime.now().strftime("%H:%M:%S")
    
        arrivals = st.session_state["live"]["arrivals"]
        at = st.session_state["live"]["arrivals_ts"]
    
        if arrivals:
            arrivals_sorted = sorted(arrivals, key=lambda a: a.get("timeToStation", 10**9))
            st.write(f"**Next trains at {to_name} (preview)** · refreshed {at}")
            for a in arrivals_sorted[:3]:
                line = a.get("lineName", "—")
                dest = a.get("destinationName", "—")
                tts = a.get("timeToStation", None)
                mins = f"{max(0, int(tts)//60)} min" if isinstance(tts, int) else "—"
                st.write(f"🚆 **{line}** to **{dest}** — {mins}")
        else:
            st.caption("Arrivals preview appears after you click **Refresh live data**.")
        
        if api_key_present and journey_ready:
            arrivals = st.session_state["live"]["arrivals"]
            at = st.session_state["live"]["arrivals_ts"]

            st.subheader(f"Arrivals at {to_name}")
            if not arrivals:
                st.info("Click **Refresh live data** to load arrivals.")
            else:
                arrivals_sorted = sorted(arrivals, key=lambda a: a.get("timeToStation", 10**9))[:20]
                rows = []
                for a in arrivals_sorted:
                    tts = a.get("timeToStation", None)
                    mins = f"{max(0, int(tts)//60)}" if isinstance(tts, int) else ""
                    rows.append({
                        "Line": a.get("lineName", ""),
                        "Destination": a.get("destinationName", ""),
                        "ETA (min)": mins,
                        "Platform": a.get("platformName", ""),})
                st.caption(f"Last refreshed: {at}")
                st.dataframe(rows, use_container_width=True)

#basic integrity check for phase 1:
missing_lines = sorted([c for c in stations.keys() if c not in lines_raw])
missing_stations = sorted([c for c in lines_raw.keys() if c not in stations])

with st.expander("Basic data checks", expanded=False):
    st.write(f"Stations loaded: **{len(stations)}**")
    st.write(f"Lines entries loaded: **{len(lines_raw)}**")
    if missing_lines:
        st.warning(f"{len(missing_lines)} station codes are missing from lines.json (showing first 15): {missing_lines[:15]}")
    if missing_stations:
        st.warning(f"{len(missing_stations)} line entries have no matching station in stations.json (first 15): {missing_stations[:15]}")
    if not missing_lines and not missing_stations:
        st.success("Station codes match between stations.json and lines.json ✅")
with st.expander("Complex data checks", expanded=False):
    if not api_key_present:
        st.info("Data unavailable until a TfL API key is set (TFL_API_KEY).")
    else:
        st.write("TfL API key detected ✅")
        live = st.session_state.get("live", {})
        tube_status_live = live.get("status")
        tube_status_ts = live.get("status_ts")
        arrivals_live = live.get("arrivals")
        arrivals_ts = live.get("arrivals_ts")
        #1 tube status summary
        if tube_status_live is None:
            st.info("Tube status unavailable until you click **Refresh live data**.")
        else:
            good = 0
            disrupted = 0
            for ln in tube_status_live:
                statuses = ln.get("lineStatuses") or []
                desc = (statuses[0].get("statusSeverityDescription") if statuses else "") or ""
                if "Good Service" in desc:
                    good += 1
                else:
                    disrupted += 1
            st.write(f"Lines returned: **{len(tube_status_live)}**")
            st.write(f"Good service: **{good}**")
            st.write(f"Disrupted: **{disrupted}**")
            st.caption(f"Last refreshed (status): {tube_status_ts}")
        st.divider()
        #2rrivals summary
        if not journey_ready:
            st.info("Arrivals summary appears once you select **From** and **To**.")
        else:
            st.write(f"Arrivals station: **{to_name}**")
            if not arrivals_live:
                st.info("Arrivals unavailable until you click **Refresh live data**.")
            else:
                st.write(f"Arrivals rows returned: **{len(arrivals_live)}**")
                #3 quick “next train” summary
                next_tts = min(
                    (a.get("timeToStation") for a in arrivals_live if isinstance(a.get("timeToStation"), int)),
                    default=None)
                if next_tts is not None:
                    st.write(f"Next train ETA: **{max(0, int(next_tts)//60)} min**")
                lines_present = {a.get("lineName") for a in arrivals_live if a.get("lineName")}
                st.write(f"Lines represented: **{len(lines_present)}**")
                st.caption(f"Last refreshed (arrivals): {arrivals_ts}")

    ####NEW DATA QUALITY BADGE
    status, issues = compute_data_quality(stations, lines_raw)
    if status == "OK":
        badge_text = "✅ Data Quality: OK"
        tooltip = "All checks passed: station codes match, line codes recognised, zones within 1–9."
    else:
        badge_text = "⚠️ Data Quality: Needs review"
        tooltip = " | ".join(issues)
    st.markdown(
        f"""
<div style="margin-top: 8px;">
<span title="{tooltip}"
                style="
                  display:inline-block;
                  padding:6px 10px;
                  border-radius:999px;
                  font-weight:600;
                  border:1px solid rgba(255,255,255,0.2);
                  background: rgba(255,255,255,0.06);
                  cursor: help;">
            {badge_text}
</span>
<span style="opacity:0.65; margin-left:8px; font-size: 0.9em;">
            (hover for details)
</span>
</div>
        """,
        unsafe_allow_html=True)


if journey_ready:
    #compute outputs:
    from_zones = stations[from_code]["zones"]
    to_zones = stations[to_code]["zones"]
    
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

