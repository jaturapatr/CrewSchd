import streamlit as st
import os
import json
import glob
from datetime import date
import uuid

def show_marketplace(rosters_dir, jsons_dir, employees):
    st.title("🤝 Shift Marketplace")
    st.markdown("<p style='color: #888; font-style: italic; margin-top: -15px;'>Autonomous, math-validated shift swapping.</p>", unsafe_allow_html=True)
    
    # 1. Staff Identity Simulator
    st.write("### 👤 Staff Identity Simulator")
    st.caption("Select an employee to simulate logging into their personal portal.")
    
    # Format names
    emp_dict = employees.get("employees", {})
    emp_options = {eid: edata["name"] for eid, edata in emp_dict.items()}
    if not emp_options:
        st.warning("No staff found.")
        return
        
    current_eid = st.selectbox("Log in as:", options=list(emp_options.keys()), format_func=lambda x: f"{emp_options[x]} ({x})")
    current_name = emp_options[current_eid]

    # Load Roster
    files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime)
    if not files:
        st.warning("No active roster published.")
        return
        
    with open(files[-1], 'r', encoding='utf-8') as f:
        latest_roster = json.load(f)
        
    # Load Marketplace Data
    market_path = os.path.join(jsons_dir, 'marketplace.json')
    if not os.path.exists(market_path):
        with open(market_path, 'w', encoding='utf-8') as f: json.dump({"offers": []}, f)
        
    with open(market_path, 'r', encoding='utf-8') as f:
        marketplace_data = json.load(f)
    
    # Ensure cleanup of old/invalid offers based on the current roster
    valid_offers = []
    for offer in marketplace_data.get("offers", []):
        o_date = offer["date"]
        o_eid = offer["offering_eid"]
        # Check if the offeror still actually has those blocks on that date in the roster
        current_blocks = latest_roster["assignments"].get(o_date, {}).get(o_eid, [])
        if set(offer["blocks"]).issubset(set(current_blocks)):
            valid_offers.append(offer)
            
    if len(valid_offers) != len(marketplace_data.get("offers", [])):
        marketplace_data["offers"] = valid_offers
        with open(market_path, 'w', encoding='utf-8') as f: json.dump(marketplace_data, f, indent=2)

    st.divider()

    # Layout: Left = My Schedule (Offer), Right = Marketplace (Accept)
    col_me, col_market = st.columns([1, 1])

    with col_me:
        st.subheader(f"📅 {current_name}'s Schedule")
        my_shifts = []
        all_dates = sorted(latest_roster["assignments"].keys())
        for d in all_dates:
            blocks = latest_roster["assignments"][d].get(current_eid, [])
            if blocks:
                my_shifts.append({"date": d, "blocks": blocks})
                
        if not my_shifts:
            st.info("You have no shifts scheduled.")
        else:
            BLOCK_MAP = {"00:00": "🌑 00-04", "04:00": "🌅 04-08", "08:00": "☀️ 08-12", "12:00": "🌤️ 12-16", "16:00": "🌇 16-20", "20:00": "🌌 20-00"}
            for shift in my_shifts:
                d = shift["date"]
                blks = shift["blocks"]
                with st.container(border=True):
                    st.markdown(f"**{date.fromisoformat(d).strftime('%A, %b %d')}**")
                    st.write(" + ".join([BLOCK_MAP.get(b, b) for b in sorted(blks)]))
                    
                    # Check if already offered
                    is_offered = any(o["date"] == d and o["offering_eid"] == current_eid for o in valid_offers)
                    
                    if is_offered:
                        st.info("🕒 Posted on Marketplace")
                        if st.button("Cancel Offer", key=f"cancel_{d}_{current_eid}"):
                            marketplace_data["offers"] = [o for o in valid_offers if not (o["date"] == d and o["offering_eid"] == current_eid)]
                            with open(market_path, 'w', encoding='utf-8') as f: json.dump(marketplace_data, f, indent=2)
                            st.rerun()
                    else:
                        if st.button("Offer Shift", key=f"offer_{d}_{current_eid}"):
                            new_offer = {
                                "id": str(uuid.uuid4()),
                                "offering_eid": current_eid,
                                "date": d,
                                "blocks": blks,
                                "timestamp": date.today().isoformat()
                            }
                            marketplace_data["offers"].append(new_offer)
                            with open(market_path, 'w', encoding='utf-8') as f: json.dump(marketplace_data, f, indent=2)
                            st.rerun()

    with col_market:
        st.subheader("🛒 Open Shift Market")
        available_offers = [o for o in valid_offers if o["offering_eid"] != current_eid]
        
        if not available_offers:
            st.info("No shifts currently available for pickup.")
        else:
            for offer in available_offers:
                o_eid = offer["offering_eid"]
                o_name = emp_options.get(o_eid, "Unknown")
                o_date = offer["date"]
                o_blocks = offer["blocks"]
                
                with st.container(border=True):
                    st.markdown(f"**{date.fromisoformat(o_date).strftime('%A, %b %d')}**")
                    st.caption(f"Offered by: **{o_name}**")
                    st.write(" + ".join([BLOCK_MAP.get(b, b) for b in sorted(o_blocks)]))
                    
                    if st.button("Accept Shift", type="primary", key=f"accept_{offer['id']}"):
                        # --- THE MATHEMATICAL BOUNCER ---
                        with st.spinner("Engine is verifying legal compliance..."):
                            from roster_engine import validate_roster
                            
                            # Construct the proposed reality
                            proposed_roster = json.loads(json.dumps(latest_roster))
                            
                            # 1. Remove blocks from Offeror
                            for b in o_blocks:
                                if b in proposed_roster["assignments"][o_date].get(o_eid, []):
                                    proposed_roster["assignments"][o_date][o_eid].remove(b)
                                    
                            # 2. Add blocks to Acceptor (Current User)
                            if current_eid not in proposed_roster["assignments"][o_date]:
                                proposed_roster["assignments"][o_date][current_eid] = []
                            proposed_roster["assignments"][o_date][current_eid].extend(o_blocks)
                            proposed_roster["assignments"][o_date][current_eid] = sorted(list(set(proposed_roster["assignments"][o_date][current_eid])))
                            
                            branch = latest_roster["metadata"]["branch"]
                            team = latest_roster["metadata"]["team"]
                            
                            is_valid, score = validate_roster(branch, team, proposed_roster)
                            
                        if is_valid:
                            st.success("✅ **Swap Approved!** The math engine confirmed this is legally compliant.")
                            
                            # Lock in the new roster
                            import time
                            ts = int(time.time())
                            proposed_roster["metadata"]["timestamp"] = ts
                            proposed_roster["metadata"]["generated_at"] = date.today().isoformat()
                            
                            save_path = os.path.join(rosters_dir, f'roster_{proposed_roster["metadata"]["start_date"]}_{ts}.json')
                            with open(save_path, 'w', encoding='utf-8') as f: json.dump(proposed_roster, f, indent=2)
                            
                            # Remove offer from marketplace
                            marketplace_data["offers"] = [o for o in valid_offers if o["id"] != offer["id"]]
                            with open(market_path, 'w', encoding='utf-8') as f: json.dump(marketplace_data, f, indent=2)
                            
                            st.rerun()
                        else:
                            st.error("❌ **Swap Rejected!** Accepting this shift would violate a hard constraint (e.g., maximum hours, rest mandate, or no-split-shift rule).")
