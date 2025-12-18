import streamlit as st
from CommuTech_core import(get_now_snapshot, get_planned_windows, compute_commute_exposure, compute_route_reliability)

st.set_page_config(page_title="CommuTech Beta", layout="wide")

lookahead = st.sidebar.slider("Lookahead (days)", 1, 7, 3)
am_start, am_end = 7,10
pm_start, pm_end = 16,19

now_tab, risk_tab, timeline_tab = st.tabs(["Now", "Commute risk", "Timeline"])

with now_tab:
    get_now_snapshot() #summary and worst line
    
with risk_tab:
    get_planned_windows(), compute_commute_exposure()
    #st.bar_chart
    #text recommendation
    
with timeline_tab:
    #heatmap/ gantt-style chart
