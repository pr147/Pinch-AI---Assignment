# ===========================================
# IMPORTING LIBRARIES
# ===========================================

import asyncio
import threading
import numpy as np
from datetime import datetime, timezone
from collections import deque
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import smtplib
from email.message import EmailMessage

# ===========================================
# 1. EVENT/METRIC SIMULATION & INGESTION
# ===========================================

# 1a. Simulate diverse streams of metrics
def generate_metrics():
    requests = np.random.poisson(lam=5) + 1
    errors = np.random.binomial(n=requests, p=0.2)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu_usage": float(np.clip(np.random.normal(50, 10), 0, 100)),
        "memory_usage": float(np.clip(np.random.normal(70, 15), 0, 100)),
        "latency_ms": float(np.random.lognormal(mean=2.5, sigma=0.5)),
        "requests": int(requests),
        "errors": int(errors),
    }

# ==================================
# Optional: Fetch metrics from API
# ==================================
#
# import requests
# def fetch_metrics_from_api():
#     """
#     Fetch metrics from an external API. Currently commented out.
#     Uncomment to use real metrics instead of simulation.
#     """
#     try:
#         response = requests.get("https://your-metrics-api.com/metrics")
#         response.raise_for_status()
#         data = response.json()
#         return {
#             "timestamp": datetime.now(timezone.utc).isoformat(),
#             "cpu_usage": data.get("cpu_usage", 0),
#             "memory_usage": data.get("memory_usage", 0),
#             "latency_ms": data.get("latency_ms", 0),
#             "requests": data.get("requests", 0),
#             "errors": data.get("errors", 0),
#         }
#     except Exception as e:
#         print(f"Failed to fetch API metrics: {e}")
#         return generate_metrics()  # fallback to simulated metrics


# 1b. Pipeline to continuously ingest metrics
MAX_POINTS = 500
timestamps = deque(maxlen=MAX_POINTS)
cpu_vals, mem_vals, lat_vals = deque(maxlen=MAX_POINTS), deque(maxlen=MAX_POINTS), deque(maxlen=MAX_POINTS)
req_vals, err_vals, success_vals = deque(maxlen=MAX_POINTS), deque(maxlen=MAX_POINTS), deque(maxlen=MAX_POINTS)

# Background Producer
# For simulation, it produces 1000 events in 2 minutes
async def produce_events(total_events=1000, duration=120):
    interval = duration / total_events
    cum_success, cum_errors = 0, 0
    for _ in range(total_events):

        # --- Use simulated metrics for now ---
        m = generate_metrics()

        # --- Uncomment the next line to switch to API metrics ---
        # m = fetch_metrics_from_api()
        
        ts = datetime.fromisoformat(m["timestamp"])
        timestamps.append(ts)
        cpu_vals.append(m["cpu_usage"])
        mem_vals.append(m["memory_usage"])
        lat_vals.append(m["latency_ms"])
        successes = m["requests"] - m["errors"]
        cum_success += successes
        cum_errors += m["errors"]
        req_vals.append(m["requests"])
        err_vals.append(cum_errors)
        success_vals.append(cum_success)
        await asyncio.sleep(interval)

def start_background_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(produce_events())

threading.Thread(target=start_background_loop, daemon=True).start()

# ===========================
# 2. REAL-TIME VISUALIZATION
# ===========================

app = dash.Dash(__name__)
app.title = "Live Metrics Dashboard"

CARD_STYLE = {
    "backgroundColor": "white",
    "padding": "15px",
    "borderRadius": "12px",
    "boxShadow": "0px 2px 6px rgba(0,0,0,0.1)",
}

KPI_CARD_STYLE = {
    "backgroundColor": "white",
    "padding": "20px",
    "borderRadius": "12px",
    "boxShadow": "0px 2px 6px rgba(0,0,0,0.1)",
    "textAlign": "center",
}

# 2a. Dynamic charts updating in real-time
# 2b. User interaction (metric selection can be added if needed)

app.layout = html.Div(
    style={"backgroundColor": "#f5f7fa", "padding": "20px", "fontFamily": "Arial, sans-serif"},
    children=[
        html.H1("Live Metrics Dashboard", style={"textAlign": "center", "color": "#333"}),

        html.Div(id="kpi-cards", style={"display": "grid", "gridTemplateColumns": "repeat(5, 1fr)", "gap": "20px", "marginBottom": "20px"}),

        # --- Metric selectors ---
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr", "gap": "20px", "marginBottom": "20px"},
            children=[
                html.Div(
                    children=[
                        html.Label("Select Metrics for Line Chart", style={"color": "#333", "fontWeight": "bold"}),
                        dcc.Dropdown(
                            id="metric-selector",
                            options=[
                                {"label": "CPU", "value": "cpu"},
                                {"label": "Memory", "value": "memory"},
                                {"label": "Latency p50", "value": "p50"},
                                {"label": "Latency p95", "value": "p95"},
                                {"label": "Latency p99", "value": "p99"},
                                {"label": "Error Rate (%)", "value": "error_rate"},
                                {"label": "RPS", "value": "rps"},
                            ],
                            value=["cpu", "memory"],
                            multi=True,
                        ),
                    ],
                    style=CARD_STYLE,
                ),
            ],
        ),

        # --- Dropdowns for Pie, Bar, Latency selection ---
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "20px", "marginBottom": "20px"},
            children=[
                html.Div(
                    children=[
                        html.Label("Pie Chart Mode", style={"fontWeight": "bold"}),
                        dcc.Dropdown(
                            id="pie-mode",
                            options=[
                                {"label": "Cumulative Success vs Errors", "value": "cumulative"},
                                {"label": "Latest Success vs Errors", "value": "latest"},
                            ],
                            value="cumulative",
                            clearable=False,
                        ),
                    ],
                    style=CARD_STYLE,
                ),
                html.Div(
                    children=[
                        html.Label("Bar Chart Mode", style={"fontWeight": "bold"}),
                        dcc.Dropdown(
                            id="bar-mode",
                            options=[
                                {"label": "Cumulative Metrics Snapshot", "value": "cumulative"},
                                {"label": "Latest Metrics Snapshot", "value": "latest"},
                            ],
                            value="latest",
                            clearable=False,
                        ),
                    ],
                    style=CARD_STYLE,
                ),
                html.Div(
                    children=[
                        html.Label("Latency Percentiles", style={"fontWeight": "bold"}),
                        dcc.Dropdown(
                            id="latency-percentiles-selector",
                            options=[
                                {"label": "p50", "value": "p50"},
                                {"label": "p95", "value": "p95"},
                                {"label": "p99", "value": "p99"},
                            ],
                            value=["p50", "p95", "p99"],
                            multi=True,
                            clearable=False,
                        ),
                    ],
                    style=CARD_STYLE,
                ),
            ],
        ),

        dcc.Interval(id="interval-update", interval=1000, n_intervals=0),

        # --- Charts ---
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "20px"},
            children=[
                html.Div([dcc.Graph(id="line-chart")], style=CARD_STYLE),
                html.Div([dcc.Graph(id="bar-chart")], style=CARD_STYLE),
                html.Div([dcc.Graph(id="pie-chart")], style=CARD_STYLE),
                html.Div([dcc.Graph(id="gauge-chart")], style=CARD_STYLE),
                html.Div([dcc.Graph(id="latency-percentiles")], style=CARD_STYLE),
                html.Div([dcc.Graph(id="error-rate-trend")], style=CARD_STYLE),
                html.Div([dcc.Graph(id="throughput-chart")], style=CARD_STYLE),
            ],
        ),

        # --- Alert panel ---
        html.Div(
            style={**CARD_STYLE, "marginTop": "20px"},
            children=[
                html.H3("🚨 Recent Alerts"),
                html.Ul(id="alert-panel", style={"maxHeight": "300px", "overflowY": "scroll"})
            ]
        ),

        dcc.Interval(id="interval-alerts", interval=1000, n_intervals=0),
    ],
)

# ===========================
# 3. ALERTING MECHANISM
# ===========================

CPU_THRESHOLD = 60.0          # CPU % threshold (for simulation, i have chosen 60% as the threshold - though the problem says 80%, it can be chanaged)
ERROR_RATE_THRESHOLD = 10.0   # Error rate % threshold
ALERT_COOLDOWN = 120          # Seconds between repeated alerts (2 minutes)
SUSTAIN_DURATION = 300        # Duration in seconds for sustained alerts (5 minutes)

# Track alert state for CPU and error rate
alert_state = {
    "cpu": {"last_alert": None, "breach_start": None, "alert_sent": False},
    "error_rate": {"last_alert": None, "breach_start": None, "alert_sent": False},
}

EMAIL_FROM = "your_email@example.com"
EMAIL_TO = "alert_recipient@example.com"
SMTP_SERVER = "smtp.example.com"
SMTP_PORT = 587 #TLS
SMTP_USER = "your_email@example.com"
SMTP_PASS = "your_password"

ALERT_LOG_FILE = "alert_log.txt"

# 3. Core alert function: log + email
def log_alert(message: str):
    """Append alert message to log file with timestamp."""
    ts = datetime.now(timezone.utc).isoformat()
    with open(ALERT_LOG_FILE, "a") as f:
        f.write(f"{ts} - {message}\n")

def send_email_alert(subject, body):
    """
    Sends an email alert and logs the alert to a file.
    
    3  : Alerting mechanism
    3a : Threshold-based
    3b : Minimal latency
    """
    log_alert(f"{subject}: {body}")  # Log to file

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[{datetime.now(timezone.utc).isoformat()}] Alert sent: {subject}")
    except Exception as e:
        print(f"Failed to send email: {e}")

# 3a. Threshold-based alerts -> implemented along with configurable threshold policies in section 4
# 3b. Minimal latency via threading -> implemented along with configurable threshold policies in section 4

# ====================================
# 4. CONFIGURABLE THRESHOLD POLICIES
# ====================================

# 4a. Immediate alert when threshold crossed
# 4b. Sustained alert after defined duration

def check_alerts(cpu, error_rate):

    now = datetime.now(timezone.utc)

    # CPU alerts
    cpu_current = cpu[-1]
    cpu_info = alert_state["cpu"]

    # ---- 4a: Immediate alert ----
    if cpu_current > CPU_THRESHOLD:  
        if cpu_info["last_alert"] is None or (now - cpu_info["last_alert"]).total_seconds() > ALERT_COOLDOWN:
            threading.Thread(
                target=send_email_alert,
                args=(
                    "🔥 CPU Threshold Exceeded",
                    f"CPU usage is {cpu_current:.1f}% (threshold {CPU_THRESHOLD}%)"
                ),
                daemon=True
            ).start()
            cpu_info["last_alert"] = now  # update last alert timestamp

    # ---- 4b: Sustained alert ----
    if cpu_current > CPU_THRESHOLD:
        if cpu_info["breach_start"] is None:
            cpu_info["breach_start"] = now  # start tracking breach duration
        elif not cpu_info["alert_sent"] and (now - cpu_info["breach_start"]).total_seconds() >= SUSTAIN_DURATION:
            threading.Thread(
                target=send_email_alert,
                args=(
                    "🔥 CPU Threshold Sustained",
                    f"CPU usage sustained above {CPU_THRESHOLD}% for {SUSTAIN_DURATION//60} minutes (current: {cpu_current:.1f}%)"
                ),
                daemon=True
            ).start()
            cpu_info["alert_sent"] = True
            cpu_info["last_alert"] = now
    else:
        cpu_info["breach_start"] = None
        cpu_info["alert_sent"] = False

    # Error rate alerts
    err_current = error_rate[-1]
    err_info = alert_state["error_rate"]

    # ---- 4a: Immediate alert ----
    if err_current > ERROR_RATE_THRESHOLD:  
        if err_info["last_alert"] is None or (now - err_info["last_alert"]).total_seconds() > ALERT_COOLDOWN:
            threading.Thread(
                target=send_email_alert,
                args=(
                    "⚠️ Error Rate Spike",
                    f"Error rate is {err_current:.1f}% (threshold {ERROR_RATE_THRESHOLD}%)"
                ),
                daemon=True
            ).start()
            err_info["last_alert"] = now  # update last alert timestamp

    # ---- 4b: Sustained alert ----
    if err_current > ERROR_RATE_THRESHOLD:
        if err_info["breach_start"] is None:
            err_info["breach_start"] = now  # start tracking breach duration
        elif not err_info["alert_sent"] and (now - err_info["breach_start"]).total_seconds() >= SUSTAIN_DURATION:
            threading.Thread(
                target=send_email_alert,
                args=(
                    "⚠️ Error Rate Sustained",
                    f"Error rate sustained above {ERROR_RATE_THRESHOLD}% for {SUSTAIN_DURATION//60} minutes (current: {err_current:.1f}%)"
                ),
                daemon=True
            ).start()
            err_info["alert_sent"] = True
            err_info["last_alert"] = now
    else:
        err_info["breach_start"] = None
        err_info["alert_sent"] = False

# ===========================
# DASH CALLBACK
# ===========================
@app.callback(
    [
        Output("kpi-cards", "children"),
        Output("line-chart", "figure"),
        Output("bar-chart", "figure"),
        Output("pie-chart", "figure"),
        Output("gauge-chart", "figure"),
        Output("latency-percentiles", "figure"),
        Output("error-rate-trend", "figure"),
        Output("throughput-chart", "figure"),
    ],
    [
        Input("metric-selector", "value"),
        Input("pie-mode", "value"),
        Input("bar-mode", "value"),
        Input("latency-percentiles-selector", "value"),
        Input("interval-update", "n_intervals"),
    ],
)
def update_charts(selected_metrics, pie_mode, bar_mode, latency_selection, _):
    if not timestamps:
        empty_fig = {"data": [], "layout": {"template": "plotly_white"}}
        return [], empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig

    ts = list(timestamps)
    cpu = list(cpu_vals)
    mem = list(mem_vals)
    lat = list(lat_vals)
    errs = list(err_vals)
    succ = list(success_vals)
    req = list(req_vals)

    total = [s + e for s, e in zip(succ, errs)]
    error_rate = [(e / t * 100) if t > 0 else 0 for e, t in zip(errs, total)]

    # Trigger alerts asynchronously
    check_alerts(cpu, error_rate)

    # Latency percentiles
    p50, p95, p99 = [], [], []
    for i in range(1, len(lat) + 1):
        p50.append(float(np.percentile(lat[:i], 50)))
        p95.append(float(np.percentile(lat[:i], 95)))
        p99.append(float(np.percentile(lat[:i], 99)))

    # Throughput (RPS)
    rps = []
    for i in range(1, len(ts)):
        delta = (ts[i] - ts[i - 1]).total_seconds()
        rps.append(req[i] / delta if delta > 0 else 0)
    rps = [0] + rps

    # --- KPI Cards ---
    kpis = [
        html.Div([html.H4("CPU %"), html.H2(f"{cpu[-1]:.1f}%")], style=KPI_CARD_STYLE),
        html.Div([html.H4("Memory %"), html.H2(f"{mem[-1]:.1f}%")], style=KPI_CARD_STYLE),
        html.Div([html.H4("Error Rate"), html.H2(f"{error_rate[-1]:.1f}%")], style=KPI_CARD_STYLE),
        html.Div([html.H4("RPS"), html.H2(f"{rps[-1]:.1f}")], style=KPI_CARD_STYLE),
        html.Div([html.H4("Latency p95"), html.H2(f"{p95[-1]:.1f} ms")], style=KPI_CARD_STYLE),
    ]

    # --- Line Chart ---
    traces = []
    if "cpu" in selected_metrics:
        traces.append({"x": ts, "y": cpu, "type": "line", "name": "CPU %"})
    if "memory" in selected_metrics:
        traces.append({"x": ts, "y": mem, "type": "line", "name": "Memory %"})
    if "p50" in selected_metrics:
        traces.append({"x": ts, "y": p50, "type": "line", "name": "Latency p50"})
    if "p95" in selected_metrics:
        traces.append({"x": ts, "y": p95, "type": "line", "name": "Latency p95"})
    if "p99" in selected_metrics:
        traces.append({"x": ts, "y": p99, "type": "line", "name": "Latency p99"})
    if "error_rate" in selected_metrics:
        traces.append({"x": ts, "y": error_rate, "type": "line", "name": "Error Rate (%)"})
    if "rps" in selected_metrics:
        traces.append({"x": ts, "y": rps, "type": "line", "name": "RPS"})

    line_fig = {"data": traces, "layout": {"title": {"text": "Selected Metrics Over Time", "x": 0.5},
                                           "xaxis": {"title": "Time"}, "yaxis": {"title": "Value"},
                                           "template": "plotly_white", "uirevision": "constant"}}

    # --- Bar Chart ---
    if bar_mode == "latest":
        bar_data = [{"x": ["CPU", "Memory", "Latency p95", "Error Rate %"],
                     "y": [cpu[-1], mem[-1], p95[-1], error_rate[-1]], "type": "bar"}]
    else:
        bar_data = [{"x": ["Avg CPU", "Avg Memory", "p95 Latency", "Total Errors"],
                     "y": [np.mean(cpu), np.mean(mem), np.mean(p95), errs[-1]], "type": "bar"}]

    bar_fig = {"data": bar_data,
               "layout": {"title": {"text": "Metrics Snapshot", "x": 0.5},
                          "xaxis": {"title": "Metric"}, "yaxis": {"title": "Value"},
                          "template": "plotly_white", "uirevision": "constant"}}

    # --- Pie Chart ---
    if pie_mode == "latest":
        latest_success = (succ[-1] - errs[-1]) if succ else 0
        pie_vals = [latest_success, errs[-1]]
        labels = ["Success", "Errors"]
        title_text = "Success vs Errors (Latest Distribution)"
    else:
        pie_vals = [sum(succ), sum(errs)]
        labels = ["Success", "Errors"]
        title_text = "Success vs Errors (Overall Distribution)"

    pie_fig = {"data": [{"labels": labels, "values": pie_vals, "type": "pie",
                         "hole": 0.4, "textinfo": "label+percent", "insidetextorientation": "radial"}],
               "layout": {"title": {"text": title_text, "x": 0.5}, "template": "plotly_white", "uirevision": "constant"}}

    # --- Gauge Chart ---
    gauge_fig = {"data": [{"type": "indicator", "mode": "gauge+number",
                            "value": cpu[-1], "title": {"text": "CPU Utilization"},
                            "gauge": {"axis": {"range": [0, 100]}, "bar": {"color": "blue"}}}],
                  "layout": {"template": "plotly_white", "uirevision": "constant"}}

    # --- Latency Percentiles ---
    traces = []
    if "p50" in latency_selection:
        traces.append({"x": ts, "y": p50, "type": "line", "name": "p50"})
    if "p95" in latency_selection:
        traces.append({"x": ts, "y": p95, "type": "line", "name": "p95"})
    if "p99" in latency_selection:
        traces.append({"x": ts, "y": p99, "type": "line", "name": "p99"})

    latency_fig = {"data": traces,
                   "layout": {"title": {"text": "Latency Percentiles"}, "xaxis": {"title": "Time"},
                              "yaxis": {"title": "Latency (ms)"}, "template": "plotly_white", "uirevision": "constant"}}

    # --- Error Rate Trend ---
    err_fig = {"data": [{"x": ts, "y": error_rate, "type": "line", "name": "Error Rate %"}],
               "layout": {"title": {"text": "Error Rate Trend", "x": 0.5},
                          "xaxis": {"title": "Time"}, "yaxis": {"title": "Error Rate (%)"},
                          "template": "plotly_white", "uirevision": "constant"}}

    # --- Throughput Chart ---
    throughput_fig = {"data": [{"x": ts, "y": rps, "type": "line", "name": "RPS"}],
                      "layout": {"title": {"text": "Throughput (Requests per Second)", "x": 0.5},
                                 "xaxis": {"title": "Time"}, "yaxis": {"title": "Requests/sec"},
                                 "template": "plotly_white", "uirevision": "constant"}}

    return kpis, line_fig, bar_fig, pie_fig, gauge_fig, latency_fig, err_fig, throughput_fig

# ============================================
# ALERT PANEL CALLBACK WITH BACKGROUND COLOR
# ============================================

@app.callback(
    Output("alert-panel", "children"),
    Input("interval-alerts", "n_intervals")
)
def update_alert_panel(_):
    try:
        with open(ALERT_LOG_FILE, "r") as f:
            lines = f.readlines()
        recent_alerts = lines[-10:][::-1]

        alert_items = []
        for line in recent_alerts:
            line = line.strip()
            # Background color coding based on alert type
            if "CPU Threshold Exceeded" in line:
                bg_color = "#ffcccc"  # light red
            elif "Error Rate Spike" in line:
                bg_color = "#ffe0b3"  # light orange
            else:
                bg_color = "#f0f0f0"  # light gray

            alert_items.append(
                html.Li(
                    line,
                    style={
                        "backgroundColor": bg_color,
                        "padding": "5px 10px",
                        "borderRadius": "5px",
                        "marginBottom": "3px"
                    }
                )
            )
        return alert_items
    except FileNotFoundError:
        return []

# ===========================
# MAIN
# ===========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)