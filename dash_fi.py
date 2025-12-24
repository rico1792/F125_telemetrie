
# dash_fi.py
from dash import Dash, dcc, html, Input, Output, State
import plotly.graph_objs as go
import time
import threading
import os
import pandas as pd

# Buffer + stats/snapshot + logger
from telemetry_store import telemetry_buf, telemetry_stat, dump_snapshot, get_logger, snapshot
# Capture démarrée en thread dans ce même process
from telemetry_capture import run_capture

# --------- Config ---------
UPDATE_INTERVAL_MS = 600  # 300..1000 selon ta machine
RESTART_MARGIN_MS = 50.0  # anti-jitter temps (ms)
RESTART_MARGIN_DIST = 5.0  # anti-jitter distance (m)
POINTS_GL_THRESHOLD = 20000  # seuil WebGL auto
DECIMATE_1 = 80000  # décimation 1/2 au-delà
DECIMATE_2 = 150000  # décimation 1/4 au-delà

# fenêtre glissante par tour (appliquée au tour courant)
SLIDING_WINDOW_SEC = float(os.getenv("SLIDING_WINDOW_SEC", "120"))
STALL_WARN_S = 1.5

LAP_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf"
]

app = Dash(__name__)
app.title = "F1 Live Telemetry"
_logger = get_logger()

# Injecter un peu de CSS pour styliser le Dropdown (lisible sur fond sombre)
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
        /* Anciennes classes Dash (react-select v1) */
        .Select-control {
            background-color: #222 !important;
            color: #EEE !important;
            border-color: #444 !important;
        }
        .Select-placeholder, .Select--single > .Select-control .Select-value {
            color: #DDD !important;
        }
        .Select-menu-outer {
            background-color: #222 !important;
            border-color: #444 !important;
            color: #EEE !important;
        }
        .Select-option {
            background-color: #222 !important;
            color: #EEE !important;
        }
        .Select-option.is-focused, .Select-option.is-selected {
            background-color: #333 !important;
            color: #FFF !important;
        }
        /* Nouvelles classes (react-select v2/v3) */
        .Select__control {
            background-color: #222 !important;
            color: #EEE !important;
            border-color: #444 !important;
        }
        .Select__placeholder, .Select__single-value {
            color: #DDD !important;
        }
        .Select__menu {
            background-color: #222 !important;
            color: #EEE !important;
            border: 1px solid #444 !important;
        }
        .Select__option {
            background-color: #222 !important;
            color: #EEE !important;
        }
        .Select__option--is-focused, .Select__option--is-selected {
            background-color: #333 !important;
            color: #FFF !important;
        }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""


def make_empty_fig(title, y_title=None,
                   note="Aucune donnée (en attente de la capture UDP)"):
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis_title="Temps (s)",
        yaxis_title=(y_title or ""),
        annotations=[dict(
            text=note, x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font=dict(size=14, color="gray")
        )],
        template="plotly_dark",
        uirevision="fixed",
    )
    return fig


app.layout = html.Div([
    html.H2("F1 Live Telemetry Dashboard"),
    html.Div(id="status_bar", style={
             "margin": "8px 0", "fontFamily": "monospace"}),

    # Boutons snapshot et export
    html.Div([
        html.Button("Dump snapshot (debug)", id="btn_dump", n_clicks=0),
        html.Div(id="dump_status", style={"marginTop": "6px"})
    ], style={"margin": "8px 0"}),

    html.Div([
        html.Label("Superposer des laps antérieurs"),
        dcc.Dropdown(
            id="overlay_laps",
            multi=True,
            placeholder="Choisis des laps à superposer",
            style={"color": "#EEE", "backgroundColor": "#222"}  # lisibilité
        ),
        html.Button("Exporter CSV", id="btn_export", n_clicks=0,
                    style={"marginLeft": "12px"}),
        dcc.Download(id="download_csv"),
    ], style={"margin": "8px 0"}),

    dcc.Interval(id="update", interval=UPDATE_INTERVAL_MS, n_intervals=0),
    dcc.Graph(id="speed_graph"),
    dcc.Graph(id="rpm_graph"),
    dcc.Graph(id="gear_graph"),
    dcc.Graph(id="throttle_brake_graph"),
], style={"padding": "10px", "backgroundColor": "#111", "color": "#EEE"})


# --- État global pour conserver les figures si pas de nouveau point ---
_last_render_ts = 0.0
_prev_figs = None  # tuple (status, speed_fig, rpm_fig, gear_fig, tb_fig)

# Index incrémental des segments par tour
_laps_index = {}       # lap -> [segment(list de points)]
_last_buf_len = 0      # nombre de points déjà intégrés

# --- nouvel état : clé des overlays pour déclencher un redraw sans nouveaux points
_last_overlay_key = ""


@app.callback(Output("dump_status", "children"), Input("btn_dump", "n_clicks"))
def do_dump(n):
    if not n:
        return ""
    path = dump_snapshot(max_points=30000, filename_prefix="snapshot_manual")
    if path:
        return f"Snapshot écrit: {path}"
    return "Snapshot: erreur (voir logs)"


def _update_laps_index(new_points):
    """Met à jour _laps_index avec les nouveaux points uniquement."""
    global _laps_index
    last_t_ms = {}
    last_dist = {}

    # init des derniers t_ms/dist par lap à partir de l’index
    for lap, segs in _laps_index.items():
        if segs and segs[-1]:
            p_last = segs[-1][-1]
            last_t_ms[lap] = float(p_last.get("t_game_ms", 0.0))
            last_dist[lap] = float(p_last.get("lapDist", 0.0))

    restart_cnt_local = 0
    for p in new_points:
        lap = p.get("lap", None)
        if lap is None:
            continue
        try:
            t_ms = float(p.get("t_game_ms", 0.0))
        except Exception:
            t_ms = 0.0
        try:
            dist = float(p.get("lapDist", 0.0))
        except Exception:
            dist = 0.0

        if lap not in _laps_index:
            _laps_index[lap] = [[p]]
            last_t_ms[lap] = t_ms
            last_dist[lap] = dist
            continue

        # mêmes règles “anti-jitter” que la version initiale
        jump_back = (t_ms < (last_t_ms.get(lap, 0.0) - RESTART_MARGIN_MS))
        zero_reset = (last_t_ms.get(lap, 0.0) >
                      RESTART_MARGIN_MS) and (t_ms == 0.0)
        dist_back = (dist < (last_dist.get(lap, 0.0) - RESTART_MARGIN_DIST))

        if jump_back or zero_reset or dist_back:
            _laps_index[lap].append([p])
            restart_cnt_local += 1
        else:
            _laps_index[lap][-1].append(p)

        last_t_ms[lap] = t_ms
        last_dist[lap] = dist

    return restart_cnt_local


# Alimente les options du Dropdown avec les laps connus (sauf le tour courant)
@app.callback(Output("overlay_laps", "options"), Input("update", "n_intervals"))
def update_overlay_options(_):
    laps = sorted(_laps_index.keys())
    latest = max(laps) if laps else None
    opts = [{"label": f"Lap {int(l)}", "value": int(l)}
            for l in laps if l != latest]
    return opts


@app.callback(
    Output("status_bar", "children"),
    Output("speed_graph", "figure"),
    Output("rpm_graph", "figure"),
    Output("gear_graph", "figure"),
    Output("throttle_brake_graph", "figure"),
    Input("update", "n_intervals"),
    Input("overlay_laps", "value"),
)
def update_graphs(_, overlay_value):
    global _last_render_ts, _prev_figs, _laps_index, _last_buf_len
    global _last_overlay_key

    t_start = time.perf_counter()

    # Figures de secours (jamais undefined)
    speed_fig = make_empty_fig("Vitesse (km/h)", "km/h")
    rpm_fig = make_empty_fig("Régime moteur (RPM)", "RPM")
    gear_fig = make_empty_fig("Rapport engagé", "Gear")
    tb_fig = make_empty_fig("Pédales (Throttle / Brake)", "0..1")

    try:
        # lecture atomique du buffer + stats
        buf, stat = snapshot()
        now = time.time()

        if not buf:
            status = "Buffer: 0 points\nDernière mise à jour: —"
            _prev_figs = (status, speed_fig, rpm_fig, gear_fig, tb_fig)
            return status, speed_fig, rpm_fig, gear_fig, tb_fig

        last_ts = buf[-1].get("t", 0.0)
        stalled_for = now - float(stat.get("last_append_wall", last_ts))
        stall_msg = f"\nFlux inactif: {stalled_for:.1f}s" if stalled_for > STALL_WARN_S else ""

        # Overlays (cast robuste en int)
        raw_overlays = overlay_value or []
        overlay_laps = []
        for v in raw_overlays:
            try:
                overlay_laps.append(int(v))
            except Exception:
                pass

        # clé courante des overlays (ordonnée)
        overlay_key = ",".join(map(str, sorted(overlay_laps)))

        # Si aucun nouveau point ET overlay identique -> réutiliser les figs précédentes
        if (last_ts <= _last_render_ts) and _prev_figs is not None and (overlay_key == _last_overlay_key):
            status_prev, s_prev, r_prev, g_prev, t_prev = _prev_figs
            status = (
                status_prev.split("\n")[0] +
                f"\nDernière mise à jour: {time.strftime('%H:%M:%S', time.localtime(_last_render_ts))}{stall_msg}"
            )
            return status, s_prev, r_prev, g_prev, t_prev

        # --- Mise à jour incrémentale de l’index des segments ---
        buf_len = len(buf)
        new_points = buf[_last_buf_len:buf_len] if buf_len > _last_buf_len else []
        restart_cnt = _update_laps_index(new_points)
        _last_buf_len = buf_len

        # Laps connus et tour courant
        all_laps = sorted(_laps_index.keys())
        latest_lap = max(all_laps) if all_laps else None

        def segment_coverage(seg):
            ds = [float(x.get("lapDist", 0.0)) for x in seg]
            cov_d = (max(ds) - min(ds)) if ds else 0.0
            if cov_d >= 0.1:
                return cov_d
            ts = [float(x.get("t_game_ms", 0.0)) for x in seg]
            return (max(ts) - min(ts)) if ts else 0.0

        # Tour courant: dernier segment
        current_pts = _laps_index.get(
            latest_lap, [[]])[-1] if latest_lap is not None else []

        # Overlays sélectionnés
        overlay_pts_by_lap = {}
        for lap in overlay_laps:
            segs = _laps_index.get(lap, [])
            if segs:
                overlay_pts_by_lap[lap] = max(segs, key=segment_coverage)

        # --- Construction des figures ---
        x_title = "Temps de tour (s)"
        total_points = 0
        i = 0

        # 1) Tour courant
        pts = current_pts
        if pts:
            x_raw_s = [float(pp.get("t_game_ms", 0.0)) / 1000.0 for pp in pts]
            if x_raw_s:
                t0_s = x_raw_s[0]
                x_s = [xi - t0_s for xi in x_raw_s]
                max_x = x_s[-1] if x_s else 0.0

                # Fenêtre glissante
                if SLIDING_WINDOW_SEC > 0.0 and max_x > SLIDING_WINDOW_SEC:
                    threshold = max_x - SLIDING_WINDOW_SEC
                    cut = next((idx for idx, xv in enumerate(
                        x_s) if xv >= threshold), 0)
                    x_s = x_s[cut:]
                    pts = pts[cut:]

                speed = [int(pp.get("speed", 0)) for pp in pts]
                rpm_vals = [int(pp.get("rpm", 0)) for pp in pts]
                gear_vals = [int(pp.get("gear", 0)) for pp in pts]
                thr = [float(pp.get("throttle", 0.0)) for pp in pts]
                brk = [float(pp.get("brake", 0.0)) for pp in pts]

                total_points += len(pts)
                ScatterClass = go.Scattergl if total_points > POINTS_GL_THRESHOLD else go.Scatter
                dec = 1
                if total_points > DECIMATE_1:
                    dec = 2
                if total_points > DECIMATE_2:
                    dec = 4

                x_plot = x_s[::dec]
                speed_plot = speed[::dec]
                rpm_plot = rpm_vals[::dec]
                gear_plot = gear_vals[::dec]
                thr_plot = thr[::dec]
                brk_plot = brk[::dec]

                col = LAP_COLORS[i % len(LAP_COLORS)]
                grp = f"lap{latest_lap}"

                speed_fig.add_trace(ScatterClass(
                    x=x_plot, y=speed_plot, mode="lines",
                    name=f"Lap {latest_lap}",
                    line=dict(width=2, color=col),
                    legendgroup=grp,
                    hovertemplate="t=%{x:.3f}s<br>speed=%{y} km/h<extra></extra>",
                ))
                rpm_fig.add_trace(ScatterClass(
                    x=x_plot, y=rpm_plot, mode="lines",
                    name=f"Lap {latest_lap}",
                    line=dict(width=2, color=col),
                    legendgroup=grp,
                    hovertemplate="t=%{x:.3f}s<br>rpm=%{y}<extra></extra>",
                ))
                gear_fig.add_trace(ScatterClass(
                    x=x_plot, y=gear_plot, mode="lines+markers",
                    name=f"Lap {latest_lap}",
                    line=dict(width=2, color=col),
                    marker=dict(size=4, color=col),
                    legendgroup=grp,
                    hovertemplate="t=%{x:.3f}s<br>gear=%{y}<extra></extra>",
                ))
                tb_fig.add_trace(ScatterClass(
                    x=x_plot, y=thr_plot, mode="lines",
                    name=f"Throttle (Lap {latest_lap})",
                    line=dict(width=2, color=col, dash="solid"),
                    legendgroup=grp,
                    hovertemplate="t=%{x:.3f}s<br>throttle=%{y:.2f}<extra></extra>",
                ))
                tb_fig.add_trace(ScatterClass(
                    x=x_plot, y=brk_plot, mode="lines",
                    name=f"Brake (Lap {latest_lap})",
                    line=dict(width=2, color=col, dash="dot"),
                    legendgroup=grp,
                    hovertemplate="t=%{x:.3f}s<br>brake=%{y:.2f}<extra></extra>",
                ))

        # 2) Overlays sélectionnés
        for lap in overlay_pts_by_lap:
            i += 1
            pts = overlay_pts_by_lap[lap]
            if not pts:
                continue

            x_raw_s = [float(pp.get("t_game_ms", 0.0)) / 1000.0 for pp in pts]
            if not x_raw_s:
                continue

            t0_s = x_raw_s[0]
            x_s = [xi - t0_s for xi in x_raw_s]

            speed = [int(pp.get("speed", 0)) for pp in pts]
            rpm_vals = [int(pp.get("rpm", 0)) for pp in pts]
            gear_vals = [int(pp.get("gear", 0)) for pp in pts]
            thr = [float(pp.get("throttle", 0.0)) for pp in pts]
            brk = [float(pp.get("brake", 0.0)) for pp in pts]

            total_points += len(pts)
            ScatterClass = go.Scattergl if total_points > POINTS_GL_THRESHOLD else go.Scatter
            dec = 1
            if total_points > DECIMATE_1:
                dec = 2
            if total_points > DECIMATE_2:
                dec = 4

            x_plot = x_s[::dec]
            speed_plot = speed[::dec]
            rpm_plot = rpm_vals[::dec]
            gear_plot = gear_vals[::dec]
            thr_plot = thr[::dec]
            brk_plot = brk[::dec]

            col = LAP_COLORS[i % len(LAP_COLORS)]
            grp = f"lap{lap}"

            speed_fig.add_trace(ScatterClass(
                x=x_plot, y=speed_plot, mode="lines",
                name=f"Lap {lap}",
                line=dict(width=1.5, color=col),
                legendgroup=grp,
                hovertemplate="t=%{x:.3f}s<br>speed=%{y} km/h<extra></extra>",
            ))
            rpm_fig.add_trace(ScatterClass(
                x=x_plot, y=rpm_plot, mode="lines",
                name=f"Lap {lap}",
                line=dict(width=1.5, color=col),
                legendgroup=grp,
                hovertemplate="t=%{x:.3f}s<br>rpm=%{y}<extra></extra>",
            ))
            gear_fig.add_trace(ScatterClass(
                x=x_plot, y=gear_plot, mode="lines+markers",
                name=f"Lap {lap}",
                line=dict(width=1.5, color=col),
                marker=dict(size=3, color=col),
                legendgroup=grp,
                hovertemplate="t=%{x:.3f}s<br>gear=%{y}<extra></extra>",
            ))
            tb_fig.add_trace(ScatterClass(
                x=x_plot, y=thr_plot, mode="lines",
                name=f"Throttle (Lap {lap})",
                line=dict(width=1.5, color=col, dash="solid"),
                legendgroup=grp,
                hovertemplate="t=%{x:.3f}s<br>throttle=%{y:.2f}<extra></extra>",
            ))
            tb_fig.add_trace(ScatterClass(
                x=x_plot, y=brk_plot, mode="lines",
                name=f"Brake (Lap {lap})",
                line=dict(width=1.5, color=col, dash="dot"),
                legendgroup=grp,
                hovertemplate="t=%{x:.3f}s<br>brake=%{y:.2f}<extra></extra>",
            ))

        # Layouts + repère x=0
        speed_fig.update_layout(title="Vitesse (km/h)", xaxis_title=x_title, yaxis_title="km/h",
                                template="plotly_dark", uirevision="fixed")
        rpm_fig.update_layout(title="Régime moteur (RPM)", xaxis_title=x_title, yaxis_title="RPM",
                              template="plotly_dark", uirevision="fixed")
        gear_fig.update_layout(title="Rapport engagé", xaxis_title=x_title, yaxis_title="Gear",
                               template="plotly_dark", yaxis=dict(dtick=1), uirevision="fixed")
        tb_fig.update_layout(title="Pédales (Throttle / Brake)", xaxis_title=x_title, yaxis_title="0..1",
                             template="plotly_dark", uirevision="fixed")
        for fig in (speed_fig, rpm_fig, gear_fig, tb_fig):
            fig.add_vline(x=0.0, line_color="#FFD166",
                          line_width=2.0, line_dash="dash")

        # Statut + instrumentation temps
        t_end = time.perf_counter()
        duration_ms = (t_end - t_start) * 1000.0
        laps_list = (
            [latest_lap] if latest_lap is not None else []) + overlay_laps
        status = (
            f"Buffer: {len(buf)} points\n"
            f"Laps affichés: {len(laps_list)} ({', '.join(map(str, laps_list))})\n"
            f"Restart détectés: {restart_cnt}\n"
            f"Points total (affichés): {total_points}\n"
            f"callback={duration_ms:.1f} ms\n"
            f"Dernière mise à jour: {time.strftime('%H:%M:%S', time.localtime(last_ts))}{stall_msg}"
        )

        if duration_ms > 400.0:
            _logger.warning("Dash callback slow: %.1f ms (buf=%d, laps=%s, points=%d)",
                            duration_ms, len(buf), laps_list, total_points)

        # Mémoriser pour le prochain tick + overlay key
        _prev_figs = (status, speed_fig, rpm_fig, gear_fig, tb_fig)
        _last_render_ts = last_ts
        _last_overlay_key = overlay_key
        return status, speed_fig, rpm_fig, gear_fig, tb_fig

    except Exception as e:
        _logger.error("update_graphs ERROR: %s", e, exc_info=True)
        status = f"Erreur callback — {type(e).__name__}: {e}"
        _prev_figs = (status, speed_fig, rpm_fig, gear_fig, tb_fig)
        return status, speed_fig, rpm_fig, gear_fig, tb_fig


# Export CSV (tout le buffer)
@app.callback(Output("download_csv", "data"),
              Input("btn_export", "n_clicks"),
              prevent_initial_call=True)
def export_csv(n_clicks):
    buf, _ = snapshot()
    if not buf:
        return None
    df = pd.DataFrame(buf)
    # garantir l’ordre des colonnes
    cols = ["t", "t_game_ms", "speed", "rpm", "gear",
            "throttle", "brake", "lap", "invalid", "lapDist"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]
    filename = time.strftime("telemetry_%Y%m%d_%H%M%S.csv")
    return dcc.send_data_frame(df.to_csv, filename, index=False)


def start_capture_in_background():
    th = threading.Thread(target=run_capture, daemon=True)
    th.start()
    return th


if __name__ == "__main__":
    start_capture_in_background()
    app.run(host="127.0.0.1", port=8050, debug=True, use_reloader=False)
