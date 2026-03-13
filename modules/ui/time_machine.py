import streamlit as st
import os
import json
import glob
import pandas as pd
import plotly.express as px

def show_time_machine(rosters_dir, jsons_dir, weather_path, emps):
    st.title("🕰️ Roster Time Machine")
    st.subheader("Analyze, Compare, and Restore previous versions of your operations.")
    
    files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime, reverse=True)
    
    if not files:
        st.info("No historical rosters found. Generate a roster to start creating backup points.")
        return

    # 1. VIEW SELECTOR
    view_mode = st.radio("Choose Visualization Mode", ["🖼️ Snapshot Gallery", "📈 Timeline View", "🗓️ Comparison View", "📦 Version List"], horizontal=True)
    st.divider()

    # 2. DATA PREP
    latest_file = files[0]
    with open(latest_file, 'r') as f: live_roster = json.load(f)

    if view_mode == "📈 Timeline View":
        st.write("### 📈 Chronological Flight Path")
        st.caption("Tracking the evolution of Roster Complexity & AI Overrides over time.")
        
        timeline_data = []
        for f_path in reversed(files): # Chronological order
            with open(f_path, 'r') as f: d = json.load(f)
            m = d.get("metadata", {})
            timeline_data.append({
                "Version": str(m.get("timestamp")),
                "Generated": m.get("generated_at"),
                "Overrides": len(m.get("weather_snapshot", [])),
                "Type": m.get("status", "FEASIBLE")
            })
        
        df_tl = pd.DataFrame(timeline_data)
        
        fig_tl = px.line(
            df_tl, x="Generated", y="Overrides", text="Version",
            title="AI Operations Intensity (Number of active Overrides per version)",
            markers=True, template="plotly_dark", height=400,
            color_discrete_sequence=["#3498db"]
        )
        fig_tl.update_traces(textposition="top center")
        st.plotly_chart(fig_tl, width="stretch")
        
        st.info("💡 **Insight:** Peaks in the graph represent periods of high operational complexity (e.g., mass sick leaves or peak events).")
        
        st.write("#### 🛰️ Version Trajectory")
        for item in timeline_data[::-1]: # Newest first
            with st.container(border=True):
                c1, c2 = st.columns([1, 5])
                c1.write(f"**v_{item['Version']}**")
                status_color = "🔵" if item["Type"] == "OPTIMAL" else "🟢"
                c2.write(f"{status_color} {item['Generated']} — {item['Overrides']} Overrides active.")

    elif view_mode == "🗓️ Comparison View":
        st.write("### 🔍 Side-by-Side Comparison")
        st.caption("Compare a historical 'Ghost' roster (left) with your current 'Live' roster (right).")
        
        selected_f = st.selectbox("Select Version to Compare", files, format_func=lambda x: f"Version {os.path.basename(x).split('_')[-1].replace('.json', '')} (Generated: {json.load(open(x))['metadata']['generated_at']})")
        
        with open(selected_f, 'r') as f: historical = json.load(f)
        
        # Comparison Metrics
        c1, c2, c3 = st.columns(3)
        h_meta = historical.get("metadata", {})
        l_meta = live_roster.get("metadata", {})
        
        diff_count = 0
        all_dates = sorted(historical["assignments"].keys())
        for d in all_dates:
            for eid in emps["employees"]:
                if historical["assignments"][d].get(eid) != live_roster["assignments"].get(d, {}).get(eid):
                    diff_count += 1

        c1.metric("Selected Points", h_meta.get("timestamp"))
        c2.metric("Total Shifts", len(all_dates) * len(emps["employees"]))
        c3.metric("Shift Deviations", diff_count, delta=f"{diff_count} changes", delta_color="inverse")

        st.divider()
        left_col, right_col = st.columns(2)
        
        EM_MAP = {"Morning": "☀️", "Evening": "🌆", "Night": "🌑", "12hDay": "🔥", "12hNight": "🌌", "—": "💤"}

        with left_col:
            st.subheader("📜 Historical Ghost")
            h_data = []
            for eid, edata in emps["employees"].items():
                row = {"Staff": edata["name"]}
                for d in all_dates:
                    val = historical["assignments"][d].get(eid, "—")
                    row[d] = f"{EM_MAP.get(val, val)} {val}"
                h_data.append(row)
            st.dataframe(pd.DataFrame(h_data), hide_index=True)

        with right_col:
            st.subheader("🚀 Live Roster")
            l_data = []
            for eid, edata in emps["employees"].items():
                row = {"Staff": edata["name"]}
                for d in all_dates:
                    h_val = historical["assignments"][d].get(eid, "—")
                    l_val = live_roster["assignments"].get(d, {}).get(eid, "—")
                    display = f"{EM_MAP.get(l_val, l_val)} {l_val}"
                    if h_val != l_val:
                        display = f"🔄 {display}"
                    row[d] = display
                l_data.append(row)
            
            def color_diff(val):
                return 'background-color: rgba(255, 165, 0, 0.2); font-weight: bold' if "🔄" in str(val) else ''
            
            st.dataframe(pd.DataFrame(l_data).style.applymap(color_diff), hide_index=True)
        
        st.divider()
        if st.button("⏪ RESTORE SELECTED VERSION", type="primary", width="stretch"):
            with open(weather_path, 'w') as f:
                json.dump({"daily_overrides": h_meta.get("weather_snapshot", [])}, f, indent=2)
            st.success("State restored! Re-run the engine to apply.")
            st.rerun()

    elif view_mode == "🖼️ Snapshot Gallery":
        st.write("### 🖼️ Visual Snapshot Gallery")
        cols = st.columns(3)
        for i, f_path in enumerate(files[:12]): # Show last 12
            with open(f_path, 'r') as f: data = json.load(f)
            meta = data.get("metadata", {})
            ts = meta.get("timestamp")
            
            with cols[i % 3]:
                with st.container(border=True):
                    st.write(f"**📦 Version {ts}**")
                    st.caption(f"📅 {meta.get('generated_at')}")
                    
                    shifts_active = 0
                    for day in data["assignments"].values():
                        shifts_active += len(day)
                    
                    density = (shifts_active / (len(emps["employees"]) * 7)) * 100
                    st.progress(min(density/100, 1.0), text=f"Work Density: {int(density)}%")
                    
                    overrides = meta.get("weather_snapshot", [])
                    st.write(f"🧠 {len(overrides)} AI Overrides")
                    
                    if st.button("⏪ Restore", key=f"gal_res_{ts}"):
                        with open(weather_path, 'w') as f:
                            json.dump({"daily_overrides": overrides}, f, indent=2)
                        st.rerun()

    elif view_mode == "📦 Version List":
        for f_path in files:
            f_name = os.path.basename(f_path)
            with open(f_path, 'r') as f: data = json.load(f)
            meta = data.get("metadata", {})
            ts = meta.get("timestamp", "Unknown")
            gen_at = meta.get("generated_at", "Unknown")
            weather_snap = meta.get("weather_snapshot", [])
            
            with st.expander(f"📦 Version {ts} (Generated: {gen_at})"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write("**Weather Snapshot at this point:**")
                    if not weather_snap:
                        st.caption("No overrides active.")
                    else:
                        for rule in weather_snap:
                            st.code(f"{rule.get('employee', 'Global')}: {rule.get('reason', 'Surge')}")
                
                with col2:
                    if st.button("⏪ Restore this state", key=f"restore_{ts}"):
                        with open(weather_path, 'w') as f:
                            json.dump({"daily_overrides": weather_snap}, f, indent=2)
                        st.success(f"Restored weather to version {ts}. Please re-run the engine.")
                        st.rerun()
                
                st.download_button("📥 Download This JSON", data=json.dumps(data, indent=2), file_name=f_name, key=f"dl_{ts}")
