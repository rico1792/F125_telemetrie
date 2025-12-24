
# dash_fi.py
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objs as go
import time
import threading

# Buffer partagé
from telemetry_store import telemetry_buf

# >>> Import de la boucle de capture (ne démarre rien à l'import grâce au if __name__ == "__main__" dans telemetry_capture.py)
from telemetry_capture import run_capture

app = Dash(__name__)
app.title = "F1 Live Telemetry"


def make_empty_fig(title, y_title=None, note="Aucune donnée (en attente de la capture UDP)"):
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis_title="Temps (s)",
        yaxis_title=(y_title or ""),
        annotations=[dict(
            text=note, x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font=dict(size=14, color="gray")
        )],
        template="plotly_dark"
    )
    return fig


app.layout = html.Div([
    html.H2("F1 Live Telemetry Dashboard"),
    html.Div(id="status_bar", style={
             "margin": "8px 0", "fontFamily": "monospace"}),
    dcc.Interval(id="update", interval=300, n_intervals=0),
    dcc.Graph(id="speed_graph"),
    dcc.Graph(id="rpm_graph"),
    dcc.Graph(id="gear_graph"),
    dcc.Graph(id="throttle_brake_graph"),
], style={"padding": "10px", "backgroundColor": "#111", "color": "#EEE"})


@app.callback(
    Output("status_bar", "children"),
    Output("speed_graph", "figure"),
    Output("rpm_graph", "figure"),
    Output("gear_graph", "figure"),
    Output("throttle_brake_graph", "figure"),
    Input("update", "n_intervals")
)
def update_graphs(_):
    # --- Snapshot du deque pour éviter "deque mutated during iteration" ---
    buf = list(telemetry_buf)

    # --- Buffer vide -> placeholders ---
    if not buf:
        status = "Buffer: 0 points\n Dernière mise à jour: —"
        return (
            status,
            make_empty_fig("Vitesse (km/h)", "km/h"),
            make_empty_fig("Régime moteur (RPM)", "RPM"),
            make_empty_fig("Rapport engagé", "Gear"),
            make_empty_fig("Pédales (Throttle / Brake)", "0..1",
                           note="Aucune donnée (pédales)")
        )

    # --- Extraction des données depuis le snapshot ---
    t0 = buf[0]["t"]
    t = [x["t"] - t0 for x in buf]
    speed = [x.get("speed", 0) for x in buf]
    rpm = [x.get("rpm", 0) for x in buf]
    gear = [x.get("gear", 0) for x in buf]
    throttle = [x.get("throttle", 0) for x in buf]
    brake = [x.get("brake", 0) for x in buf]
    laps = [x.get("lap", None) for x in buf]
    # si tu veux colorer les tours invalidés
    invalids = [x.get("invalid", 0) for x in buf]

    last_ts = buf[-1]["t"]
    status = f"Buffer: {len(buf)} points\n Dernière mise à jour: {time.strftime('%H:%M:%S', time.localtime(last_ts))}"

    # --- Détection des segments de tour ---
    lap_segments = []
    if laps and laps[0] is not None:
        start_idx = 0
        current_lap = laps[0]
        for i in range(1, len(laps)):
            if laps[i] != current_lap:
                lap_segments.append({
                    "lap": current_lap,
                    "t_start": t[start_idx],
                    "t_end": t[i-1]
                })
                start_idx = i
                current_lap = laps[i]
        lap_segments.append({
            "lap": current_lap,
            "t_start": t[start_idx],
            "t_end": t[-1]
        })

    # --- Figures de base ---
    speed_fig = go.Figure(
        [go.Scatter(x=t, y=speed, mode="lines", name="Vitesse", line=dict(width=2))])
    speed_fig.update_layout(title="Vitesse (km/h)", xaxis_title="Temps (s)",
                            yaxis_title="km/h", template="plotly_dark")

    rpm_fig = go.Figure(
        [go.Scatter(x=t, y=rpm, mode="lines", name="RPM", line=dict(width=2))])
    rpm_fig.update_layout(title="Régime moteur (RPM)",
                          xaxis_title="Temps (s)", yaxis_title="RPM", template="plotly_dark")

    gear_fig = go.Figure(
        [go.Scatter(x=t, y=gear, mode="lines+markers", name="Gear", line=dict(width=2))])
    gear_fig.update_layout(title="Rapport engagé", xaxis_title="Temps (s)", yaxis_title="Gear",
                           template="plotly_dark", yaxis=dict(dtick=1))

    tb_fig = go.Figure([
        go.Scatter(x=t, y=throttle, mode="lines",
                   name="Throttle", line=dict(width=2)),
        go.Scatter(x=t, y=brake,    mode="lines",
                   name="Brake",    line=dict(width=2)),
    ])
    tb_fig.update_layout(title="Pédales (Throttle / Brake)",
                         xaxis_title="Temps (s)", yaxis_title="0..1", template="plotly_dark")

    # --- Overlays de lap (visibles) ---
    vline_color = "#FFD166"
    band_color = "rgba(255, 209, 102, 0.16)"
    label_color = "#FFD166"

    def apply_lap_overlays(fig):
        for seg in lap_segments:
            # Ligne verticale au début du tour
            fig.add_vline(x=seg["t_start"], line_color=vline_color,
                          line_width=2.5, line_dash="dash")
            # Bande couvrant la durée du tour
            fig.add_vrect(x0=seg["t_start"], x1=seg["t_end"],
                          fillcolor=band_color, line_width=0, layer="below")
            # Annotation "Lap N"
            xmid = (seg["t_start"] + seg["t_end"]) / 2.0
            fig.add_annotation(x=xmid, y=1.05, xref="x", yref="paper",
                               text=f"Lap {seg['lap']}",
                               showarrow=False, font=dict(size=13, color=label_color))

    if lap_segments:
        for f in (speed_fig, rpm_fig, gear_fig, tb_fig):
            apply_lap_overlays(f)

    return status, speed_fig, rpm_fig, gear_fig, tb_fig


def start_capture_in_background():
    th = threading.Thread(target=run_capture, daemon=True)
    th.start()
    return th


if __name__ == "__main__":
    start_capture_in_background()
    app.run(host="127.0.0.1", port=8050, debug=True, use_reloader=False)
