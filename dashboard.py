
import streamlit as st
import json
import random
import psutil
import os
import time
import subprocess
from datetime import datetime

import genetic_algorithm as ga

# ── LIVE CLOUD PRICES ────────────────────────────────────

aws_price = round(random.uniform(0.10, 0.25), 4)
gcp_price = round(random.uniform(0.06, 0.15), 4)
azure_price = round(random.uniform(0.09, 0.22), 4)

prices = {
    "AWS": aws_price,
    "GCP": gcp_price,
    "Azure": azure_price
}

best = min(prices, key=prices.get)


# ── LIVE SYSTEM METRICS ───────────────────────────────────

cpu = psutil.cpu_percent(interval=0.1)
ram = psutil.virtual_memory().percent
net = round(
    psutil.net_io_counters().bytes_recv / (1024 * 1024), 1
)
disk = psutil.disk_usage('/').percent

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
MIGRATION_METRICS_FILE = os.path.join(BASE_DIR, "migration_metrics.json")

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

        target_score = sum(vv
