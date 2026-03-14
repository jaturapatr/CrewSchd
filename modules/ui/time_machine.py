import streamlit as st
import os
import json
import glob
import pandas as pd
import plotly.express as px
from datetime import date

def show_time_machine(rosters_dir, jsons_dir, weather_path, emps):
    st.title("🕰️ Roster Time Machine")
    st.subheader("Analyze, Compare, and Restore previous versions (4h Blocks).")
    
    files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime, reverse=True)
    
    if not files:
        st.info("No historical rosters found.")
        return

    view_mode = st.radio("Choose Visualization Mode", ["🖼️ Snapshot Gallery", "📈 Timeline View", "🗓️ Comparison View", "📦 Version List"], horizontal=True)
    st.divider()

    latest_file = files[0]
    with open(latest_file, 'r') as f: live_roster = json.load(f)

    if view_mode == "📈 Timeline View":
        st.write("### 📈 Chronological Flight Path")
        timeline_data = []
        for f_path in reversed(files):
            with open(f_path, 'r') as f: d = json.load(f)
            m = d.get("metadata", {})
            timeline_data.append({
                "Version": str(m.get("timestamp")),
                "Generated": m.get("generated_at"),
                "Overrides": len(m.get("weather_snapshot", [])),
                "Type": m.get("status", "FEASIBLE")
            })
        df_tl = pd.DataFrame(timeline_data)
        fig_tl = px.line(df_tl, x="Generated", y="Overrides", text="Version", title="AI Operations Intensity", markers=True, template="plotly_dark", height=400)
        st.plotly_chart(fig_tl, width="stretch")

    elif view_mode == "🗓️ Comparison View":
        st.write("### 🔍 Side-by-Side Comparison")
        selected_f = st.selectbox("Select Version to Compare", files, format_func=lambda x: f"Version {os.path.basename(x).split('_')[-1].replace('.json', '')} (Generated: {json.load(open(x))['metadata']['generated_at']})")
        with open(selected_f, 'r') as f: historical = json.load(f)
        
        h_meta = historical.get("metadata", {})
        diff_count = 0
        all_dates = sorted(historical["assignments"].keys())
        for d in all_dates:
            for eid in emps["employees"]:
                if set(historical["assignments"][d].get(eid, [])) != set(live_roster["assignments"].get(d, {}).get(eid, [])):
                    diff_count += 1

        c1, c2, c3 = st.columns(3)
        c1.metric("Selected Points", h_meta.get("timestamp"))
        c2.metric("Total Days Analyzed", len(all_dates))
        c3.metric("Shift Deviations", diff_count, delta=f"{diff_count} changes", delta_color="inverse")

        st.divider()
        left_col, right_col = st.columns(2)
        
        BLOCK_MAP = {"00:00": "🌑", "04:00": "🌅", "08:00": "☀️", "12:00": "🌤️", "16:00": "🌇", "20:00": "🌌"}

        def format_blocks(b_list):
            if not b_list: return "💤 OFF"
            return " + ".join([BLOCK_MAP.get(b, b) for b in sorted(b_list)])

        with left_col:
            st.subheader(f"📜 Historical (v_{h_meta.get('timestamp')})")
            h_data = []
            for eid, edata in emps["employees"].items():
                row = {"Staff": edata["name"]}
                for d in all_dates:
                    row[date.fromisoformat(d).strftime('%a [%d/%m/%y]')] = format_blocks(historical["assignments"][d].get(eid, []))
                h_data.append(row)
            st.dataframe(pd.DataFrame(h_data), hide_index=True)

        with right_col:
            st.subheader("🚀 Live Roster")
            l_data = []
            for eid, edata in emps["employees"].items():
                row = {"Staff": edata["name"]}
                for d in all_dates:
                    h_val = set(historical["assignments"][d].get(eid, []))
                    l_val = set(live_roster["assignments"].get(d, {}).get(eid, []))
                    display = format_blocks(list(l_val))
                    if h_val != l_val:
                        display = f"🔄 {display}"
                    row[date.fromisoformat(d).strftime('%a [%d/%m/%y]')] = display
                l_data.append(row)
            st.dataframe(pd.DataFrame(l_data).style.map(lambda x: 'background-color: rgba(255, 165, 0, 0.2);' if "🔄" in str(x) else ''), hide_index=True)

    elif view_mode == "🖼️ Snapshot Gallery":
        cols = st.columns(3)
        for i, f_path in enumerate(files[:12]):
            with open(f_path, 'r') as f: data = json.load(f)
            meta = data.get("metadata", {})
            ts = meta.get("timestamp")
            with cols[i % 3]:
                with st.container(border=True):
                    st.write(f"**📦 Version {ts}**")
                    st.caption(f"📅 {meta.get('generated_at')}")
                    if st.button("⏪ Restore", key=f"gal_res_{ts}"):
                        with open(weather_path, 'w') as f: json.dump({"daily_overrides": meta.get("weather_snapshot", [])}, f, indent=2)
                        st.rerun()

    elif view_mode == "📦 Version List":
        for f_path in files:
            with open(f_path, 'r') as f: data = json.load(f)
            meta = data.get("metadata", {})
            ts = meta.get("timestamp", "Unknown")
            with st.expander(f"📦 Version {ts} (Generated: {meta.get('generated_at')})"):
                st.download_button("📥 Download This JSON", data=json.dumps(data, indent=2), file_name=os.path.basename(f_path), key=f"dl_{ts}")
