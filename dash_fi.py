
# dash_fi.py
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objs as go
import time
import threading

# Buffer partagé
from telemetry_store import telemetry_buf

# >>> Import de la boucle de capture (ne démarre rien à l'import grâce au if __name__ == "__main__" dans telemetry_capture.py)
from telemetry_capture import run_capture

SHOW_LAP_OVERLAYS = True  # mets False pour désactiver tous les overlays lap

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
    try:
        # --- Snapshot du deque pour éviter les mutations concurrentes ---
        buf = list(telemetry_buf)

        # --- Buffer vide -> placeholders ---
        if not buf:
            status = "Buffer: 0 points\n Dernière mise à jour: —"
            return (
                status,
                make_empty_fig("Vitesse (km/h)", "km/h"),
                make_empty_fig("Régime moteur (RPM)", "RPM"),
                make_empty_fig("Rapport engagé", "Gear"),
                make_empty_fig("Pédales (Throttle / Brake)",
                               "0..1", note="Aucune donnée (pédales)")
            )

        # --- Grouper par lap tous les points où le chrono du jeu > 0 ---
        #     => on superpose tous les tours sur l'axe X = temps de lap (s)
        # dict: lap_num -> list of points (dans l'ordre d'arrivée)
        laps_data = {}
        for p in buf:
            lap_num = p.get("lap")
            t_game_ms = p.get("t_game_ms", 0.0)
            if lap_num is None or t_game_ms <= 0.0:
                continue  # chrono arrêté: on ignore
            laps_data.setdefault(lap_num, []).append(p)

        # --- Si aucun tour avec chrono qui tourne -> placeholders ---
        if not laps_data:
            last_ts_wall = buf[-1]["t"]
            status = (
                f"Buffer: {len(buf)} points\n"
                f"Dernière mise à jour: {time.strftime('%H:%M:%S', time.localtime(last_ts_wall))}\n"
                "Chrono arrêté (t_game=0) — en attente du passage de la ligne de départ"
            )
            return (
                status,
                make_empty_fig("Vitesse (km/h)", "km/h", note="Chrono arrêté"),
                make_empty_fig("Régime moteur (RPM)",
                               "RPM", note="Chrono arrêté"),
                make_empty_fig("Rapport engagé", "Gear", note="Chrono arrêté"),
                make_empty_fig("Pédales (Throttle / Brake)",
                               "0..1", note="Chrono arrêté"),
            )

        # --- Préparer les figures et une palette de couleurs par lap ---
        # Palette simple et cohérente pour tous les graphes
        lap_colors = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
            "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
            "#bcbd22", "#17becf"
        ]

        def color_for_lap(idx):
            return lap_colors[idx % len(lap_colors)]

        x_title = "Temps de tour (s)"
        speed_fig = go.Figure()
        rpm_fig = go.Figure()
        gear_fig = go.Figure()
        tb_fig = go.Figure()

        # --- Construire les traces pour CHAQUE lap (overlay), X recalé à 0 ---
        # Tri des laps pour un ordre stable (croissant)
        sorted_laps = sorted(laps_data.keys())
        for li, lap_num in enumerate(sorted_laps):
            pts = laps_data[lap_num]
            # Axe X brut (secondes) puis recalage pour que le 1er point soit exactement 0.0
            x_raw = [p["t_game_ms"] / 1000.0 for p in pts]
            x0 = x_raw[0]
            x = [xi - x0 for xi in x_raw]

            # Séries Y
            speed = [p.get("speed", 0) for p in pts]
            rpm = [p.get("rpm", 0) for p in pts]
            gear = [p.get("gear", 0) for p in pts]
            throttle = [p.get("throttle", 0) for p in pts]
            brake = [p.get("brake", 0) for p in pts]

            col = color_for_lap(li)
            grp = f"lap{lap_num}"

            # Vitesse
            speed_fig.add_trace(go.Scatter(
                x=x, y=speed, mode="lines",
                name=f"Lap {lap_num}",
                line=dict(width=2, color=col),
                legendgroup=grp,
                hovertemplate="t=%{x:.3f}s<br>speed=%{y} km/h<extra></extra>",
            ))

            # RPM
            rpm_fig.add_trace(go.Scatter(
                x=x, y=rpm, mode="lines",
                name=f"Lap {lap_num}",
                line=dict(width=2, color=col),
                legendgroup=grp,
                hovertemplate="t=%{x:.3f}s<br>rpm=%{y}<extra></extra>",
            ))

            # Gear
            gear_fig.add_trace(go.Scatter(
                x=x, y=gear, mode="lines+markers",
                name=f"Lap {lap_num}",
                line=dict(width=2, color=col),
                marker=dict(size=4, color=col),
                legendgroup=grp,
                hovertemplate="t=%{x:.3f}s<br>gear=%{y}<extra></extra>",
            ))

            # Pédales : on trace 2 courbes par lap (Throttle/Brake) avec styles distincts
            tb_fig.add_trace(go.Scatter(
                x=x, y=throttle, mode="lines",
                name=f"Throttle (Lap {lap_num})",
                line=dict(width=2, color=col, dash="solid"),
                legendgroup=grp,
                hovertemplate="t=%{x:.3f}s<br>throttle=%{y:.2f}<extra></extra>",
            ))
            tb_fig.add_trace(go.Scatter(
                x=x, y=brake, mode="lines",
                name=f"Brake (Lap {lap_num})",
                line=dict(width=2, color=col, dash="dot"),
                legendgroup=grp,
                hovertemplate="t=%{x:.3f}s<br>brake=%{y:.2f}<extra></extra>",
            ))

        # --- Layout commun (thème sombre, titres, axe X en secondes) ---
        speed_fig.update_layout(
            title="Vitesse (km/h)", xaxis_title=x_title, yaxis_title="km/h", template="plotly_dark")
        rpm_fig.update_layout(title="Régime moteur (RPM)",
                              xaxis_title=x_title, yaxis_title="RPM", template="plotly_dark")
        gear_fig.update_layout(title="Rapport engagé", xaxis_title=x_title, yaxis_title="Gear",
                               template="plotly_dark", yaxis=dict(dtick=1))
        tb_fig.update_layout(title="Pédales (Throttle / Brake)",
                             xaxis_title=x_title, yaxis_title="0..1", template="plotly_dark")

        # --- Repère visuel "départ" : vline à x=0 (commune à tous) ---
        for fig in (speed_fig, rpm_fig, gear_fig, tb_fig):
            fig.add_vline(x=0.0, line_color="#FFD166",
                          line_width=2.0, line_dash="dash")

        # --- Statut : nombre de laps visibles et dernière mise à jour ---
        last_ts_wall = buf[-1]["t"]
        status = (
            f"Laps visibles: {len(sorted_laps)} | Points total: {sum(len(laps_data[l]) for l in sorted_laps)}\n"
            f"Dernière mise à jour: {time.strftime('%H:%M:%S', time.localtime(last_ts_wall))}"
        )

        return status, speed_fig, rpm_fig, gear_fig, tb_fig

    except Exception as e:
        # Filet de sécurité : retour de placeholders avec message (évite "server did not respond")
        print("[dash] update_graphs ERROR:", type(e).__name__, e)
        status = "Erreur callback — voir console"
        return (
            status,
            make_empty_fig("Vitesse (km/h)", "km/h", note=str(e)),
            make_empty_fig("Régime moteur (RPM)", "RPM", note=str(e)),
            make_empty_fig("Rapport engagé", "Gear", note=str(e)),
            make_empty_fig("Pédales (Throttle / Brake)", "0..1", note=str(e)),
        )


def start_capture_in_background():
    th = threading.Thread(target=run_capture, daemon=True)
    th.start()
    return th


if __name__ == "__main__":
    start_capture_in_background()
    app.run(host="127.0.0.1", port=8050, debug=True, use_reloader=False)
