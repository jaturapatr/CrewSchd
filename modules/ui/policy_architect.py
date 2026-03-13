import streamlit as st
import os
import json
from Translator import translate_policy_to_json

def show_policy_architect(jsons_dir, policies, get_api_key):
    st.title("🏗️ Policy Architect")
    st.subheader("Control the Mathematical Weight of Operations")
    st.caption("Admin Only: Create and adjust penalties independently using AI or manual sliders.")

    policies_path = os.path.join(jsons_dir, 'company_policies.json')

    c1, c2 = st.columns([1, 1])

    with c1:
        st.write("### 🤖 AI Policy Designer")
        st.info("Describe a new policy or request a penalty change in plain English.")
        
        if "policy_chat_history" not in st.session_state:
            st.session_state.policy_chat_history = []

        for msg in st.session_state.policy_chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        policy_prompt = st.chat_input("e.g., Triple the penalty for Night shift extra people...")
        
        if policy_prompt:
            st.session_state.policy_chat_history.append({"role": "user", "content": policy_prompt})
            with st.spinner("AI is architecting..."):
                new_targets = translate_policy_to_json(policy_prompt, get_api_key(), policies)
                
                if "message" in new_targets:
                    st.session_state.policy_chat_history.append({"role": "assistant", "content": f"⚠️ {new_targets['message']}"})
                else:
                    policies["optimization_targets"] = new_targets
                    with open(policies_path, 'w') as f: json.dump(policies, f, indent=2)
                    st.session_state.policy_chat_history.append({"role": "assistant", "content": "✅ Policies updated successfully based on your request!"})
                st.rerun()

    with c2:
        st.write("### 🎚️ Manual Penalty Control")
        st.caption("Adjust existing policy weights directly.")
        
        updated_targets = policies.get("optimization_targets", {}).copy()
        has_changes = False

        for name, data in updated_targets.items():
            with st.container(border=True):
                st.write(f"**{name.replace('_', ' ').title()}**")
                
                penalty_key = next((k for k in data.keys() if "penalty" in k), None)
                
                if penalty_key:
                    new_val = st.slider(
                        f"Penalty ({penalty_key})", 
                        min_value=0, 
                        max_value=50000, 
                        value=int(data[penalty_key]),
                        step=100,
                        key=f"slider_{name}"
                    )
                    if new_val != data[penalty_key]:
                        updated_targets[name][penalty_key] = new_val
                        has_changes = True
                
                for k, v in data.items():
                    if k not in ["target_shift", "target_days", "shift_1", "shift_2_next_day", "tier_to_penalize", "team", penalty_key]:
                        if isinstance(v, (int, float)):
                            new_val = st.number_input(f"{k}", value=v, key=f"num_{name}_{k}")
                            if new_val != v:
                                updated_targets[name][k] = new_val
                                has_changes = True

        if has_changes:
            if st.button("💾 SAVE MANUAL CHANGES", type="primary", width="stretch"):
                policies["optimization_targets"] = updated_targets
                with open(policies_path, 'w') as f: json.dump(policies, f, indent=2)
                st.success("Manual changes saved!")
                st.rerun()


