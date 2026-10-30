
import streamlit as st
import json
import os
import time
import subprocess
from datetime import datetime

import genetic_algorithm as ga

st.set_page_config(
    page_title="AI Migration Dashboard",
    page_icon="🚀",
    layout="wide"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VM1_HISTORY = os.path.join(BASE_DIR, "price_history_vm1.json")
VM2_HISTORY = os.path.join(BASE_DIR, "price_history_vm2.json")
MIGRATION_SCRIPT = os.path.join(BASE_DIR, "migrate.sh")
LOG_FILE = os.path.join(BASE_DIR, "migration_log.txt")

# Local container mapping
CONTAINER_1 = "counter-src"
CONTAINER_2 = "counter-dst"


# ── LOAD CONTAINER METRICS ────────────────────────────────

def get_metrics(filename):
    try:
        if not os.path.exists(filename):
            return None

        with open(filename, "r") as f:
            history = json.load(f)

        if not history:
            return None

        return history[-1]

    except (OSError, json.JSONDecodeError, TypeError):
        return None


container1 = get_metrics(VM1_HISTORY)
container2 = get_metrics(VM2_HISTORY)


# ── GENETIC ALGORITHM ─────────────────────────────────────

def get_ga_recommendation():
    try:
        forecast = ga.build_forecast()

        current_node = ga.CURRENT_NODE
        current_index = ga.NODES.index(current_node)

        best_plan = ga.run_ga(forecast, current_index)
        recommended_node = ga.NODES[best_plan[0]]

        current_score = sum(
            ga.step_score(state)
            for state in forecast[current_node]
        ) / len(forecast[current_node])

        target_score = sum(
            ga.step_score(state)
            for state in forecast[recommended_node]
        ) / len(forecast[recommended_node])

        improvement = current_score - target_score

        if recommended_node == current_node:
            decision = f"STAY on {current_node}"
        elif improvement < ga.MIN_IMPROVEMENT:
            decision = f"STAY on {current_node}"
        else:
            decision = f"MIGRATE to {recommended_node}"

        return {
            "recommended": recommended_node,
            "decision": decision,
            "improvement": improvement,
            "current": current_node
        }

    except (OSError, ValueError, KeyError, TypeError) as error:
        return {
            "recommended": None,
            "decision": "Metrics unavailable",
            "improvement": 0,
            "current": ga.CURRENT_NODE,
            "error": str(error)
        }


recommendation = get_ga_recommendation()


# ── CONTAINER STATUS ─────────────────────────────────────

def get_container_status(container_name):
    try:
        result = subprocess.run(
            [
                "sudo", "podman", "inspect",
                "--format", "{{.State.Status}}",
                container_name
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return result.stdout.strip()

        return "not found"

    except (subprocess.SubprocessError, OSError):
        return "unavailable"


status1 = get_container_status(CONTAINER_1)
status2 = get_container_status(CONTAINER_2)


# ── MIGRATION HISTORY ─────────────────────────────────────

def get_history():
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()[-10:]

            return [
                line.strip()
                for line in reversed(lines)
                if line.strip()
            ]

    except OSError:
        pass

    return []


# ════════════════════════════════════════════════════════
#                    DASHBOARD UI
# ════════════════════════════════════════════════════════

st.markdown(
    "<h1 style='text-align:center'>AI Live Container Migration Dashboard</h1>",
    unsafe_allow_html=True
)

st.markdown(
    "<p style='text-align:center;color:gray'>"
    "Local container monitoring and migration"
    "</p>",
    unsafe_allow_html=True
)

st.divider()


# ── CONTAINER PRICES ──────────────────────────────────────

st.subheader("Container Price Comparison")

c1, c2 = st.columns(2)

price1 = container1.get("price") if container1 else None
price2 = container2.get("price") if container2 else None

with c1:
    st.metric(
        "Container 1",
        f"${price1:.3f}/hr" if price1 is not None else "No data"
    )

    if price1 is not None:
        st.progress(min(price1 / 20.0, 1.0))

with c2:
    st.metric(
        "Container 2",
        f"${price2:.3f}/hr" if price2 is not None else "No data"
    )

    if price2 is not None:
        st.progress(min(price2 / 20.0, 1.0))


if recommendation["recommended"]:
    st.success(
        f"GA Recommendation: {recommendation['decision']}"
    )

    st.write(
        f"Estimated score improvement: "
        f"{recommendation['improvement']:.4f}"
    )
else:
    st.warning(
        f"GA Recommendation unavailable: "
        f"{recommendation.get('error', 'Check metric files')}"
    )

st.divider()


# ── CONTAINER METRICS ─────────────────────────────────────

st.subheader("Container Performance Metrics")

m1, m2 = st.columns(2)

with m1:
    st.markdown("### Container 1 — counter-src")

    if container1:
        st.metric("CPU", f"{container1['cpu']:.2f}%")
        st.metric("RAM", f"{container1['ram']:.2f}%")
        st.metric(
            "Network",
            f"{container1['network_mbps']:.3f} Mbps"
        )

        st.progress(
            min(container1["cpu"] / 100, 1.0),
            text=f"CPU: {container1['cpu']:.2f}%"
        )

        st.progress(
            min(container1["ram"] / 100, 1.0),
            text=f"RAM: {container1['ram']:.2f}%"
        )

        st.caption(f"Last updated: {container1.get('timestamp', 'N/A')}")
    else:
        st.warning("No metrics available for Container 1")


with m2:
    st.markdown("### Container 2 — counter-dst")

    if container2:
        st.metric("CPU", f"{container2['cpu']:.2f}%")
        st.metric("RAM", f"{container2['ram']:.2f}%")
        st.metric(
            "Network",
            f"{container2['network_mbps']:.3f} Mbps"
        )

        st.progress(
            min(container2["cpu"] / 100, 1.0),
            text=f"CPU: {container2['cpu']:.2f}%"
        )

        st.progress(
            min(container2["ram"] / 100, 1.0),
            text=f"RAM: {container2['ram']:.2f}%"
        )

        st.caption(f"Last updated: {container2.get('timestamp', 'N/A')}")
    else:
        st.warning("No metrics available for Container 2")

st.divider()


# ── LOCAL CONTAINER STATUS ────────────────────────────────

st.subheader("Local Containers")

s1, s2 = st.columns(2)

with s1:
    st.metric(
        "Container 1",
        status1.upper(),
        CONTAINER_1
    )

with s2:
    st.metric(
        "Container 2",
        status2.upper(),
        CONTAINER_2
    )

st.divider()


# ── MIGRATION ─────────────────────────────────────────────

st.subheader("Container Migration")

st.write(
    "Run the local Podman checkpoint and restore process "
    "using migrate.sh."
)

if st.button("Run Local Migration", type="primary"):

    if not os.path.exists(MIGRATION_SCRIPT):
        st.error("migrate.sh was not found.")
    else:
        with st.spinner("Running container migration..."):

            result = subprocess.run(
                ["bash", MIGRATION_SCRIPT],
                capture_output=True,
                text=True,
                cwd=BASE_DIR
            )

            output = result.stdout + "\n" + result.stderr

            with open(LOG_FILE, "a") as f:
                f.write(
                    f"\n[{datetime.now().isoformat(timespec='seconds')}]\n"
                )
                f.write(output)
                f.write("\n")

        if result.returncode == 0:
            st.success("Migration script completed successfully.")
        else:
            st.error(
                f"Migration failed with exit code {result.returncode}."
            )

        st.code(output)


st.divider()


# ── MIGRATION LOG ─────────────────────────────────────────

st.subheader("Migration Log")

history = get_history()

if history:
    for line in history:
        st.code(line)
else:
    st.info("No migrations recorded yet.")


st.divider()

st.caption(
    f"Updated: {datetime.now().strftime('%H:%M:%S')} "
    "| Auto-refresh every 5 seconds"
)

time.sleep(5)
st.rerun()
