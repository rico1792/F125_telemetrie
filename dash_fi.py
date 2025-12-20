
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
    print("[dash] points dans buffer:", len(
        telemetry_buf))  # <<< debug une ligne
    if not telemetry_buf:

        status = "Buffer: 0 points | Dernière mise à jour: —"
        return (
            status,
            make_empty_fig("Vitesse (km/h)", "km/h"),
            make_empty_fig("Régime moteur (RPM)", "RPM"),
            make_empty_fig("Rapport engagé", "Gear"),
            make_empty_fig("Pédales (Throttle / Brake)", "0..1",
                           note="Aucune donnée (pédales)")
        )

    # Temps relatif
    t0 = telemetry_buf[0]["t"]
    t = [x["t"] - t0 for x in telemetry_buf]
    speed = [x.get("speed", 0) for x in telemetry_buf]
    rpm = [x.get("rpm", 0) for x in telemetry_buf]
    gear = [x.get("gear", 0) for x in telemetry_buf]
    throttle = [x.get("throttle", 0.0) for x in telemetry_buf]
    brake = [x.get("brake", 0.0) for x in telemetry_buf]

    last_ts = telemetry_buf[-1]["t"]
    status = f"Buffer: {len(telemetry_buf)} points | Dernière mise à jour: {time.strftime('%H:%M:%S', time.localtime(last_ts))}"

    speed_fig = go.Figure(
        [go.Scatter(x=t, y=speed, mode="lines", name="Vitesse")])
    speed_fig.update_layout(title="Vitesse (km/h)", xaxis_title="Temps (s)",
                            yaxis_title="km/h", template="plotly_dark")

    rpm_fig = go.Figure([go.Scatter(x=t, y=rpm, mode="lines", name="RPM")])
    rpm_fig.update_layout(title="Régime moteur (RPM)",
                          xaxis_title="Temps (s)", yaxis_title="RPM", template="plotly_dark")

    gear_fig = go.Figure(
        [go.Scatter(x=t, y=gear, mode="lines+markers", name="Gear")])
    gear_fig.update_layout(title="Rapport engagé", xaxis_title="Temps (s)", yaxis_title="Gear",
                           template="plotly_dark", yaxis=dict(dtick=1))

    tb_fig = go.Figure([
        go.Scatter(x=t, y=throttle, mode="lines", name="Throttle"),
        go.Scatter(x=t, y=brake,    mode="lines", name="Brake"),
    ])
    tb_fig.update_layout(title="Pédales (Throttle / Brake)",
                         xaxis_title="Temps (s)", yaxis_title="0..1", template="plotly_dark")

    return status, speed_fig, rpm_fig, gear_fig, tb_fig


def start_capture_in_background():
    th = threading.Thread(target=run_capture, daemon=True)
    th.start()
    return th


if __name__ == "__main__":
    start_capture_in_background()
    app.run(host="127.0.0.1", port=8050, debug=True, use_reloader=False)
