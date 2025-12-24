
# dash_fi.py
from dash import Dash, dcc, html, Input, Output
import dash  # pour callback_context dans l'export
import plotly.graph_objs as go
import time
import threading
import os
import pandas as pd

from telemetry_store import telemetry_stat, dump_snapshot, get_logger, snapshot
from telemetry_capture import run_capture

# --------- Config ---------
UPDATE_INTERVAL_MS = 600
RESTART_MARGIN_MS = 50.0  # anti-jitter temps (ms)
RESTART_MARGIN_DIST = 5.0  # anti-jitter distance (m)
POINTS_GL_THRESHOLD = 20000  # seuil WebGL auto
DECIMATE_1 = 80000          # décimation 1/2 au-delà
DECIMATE_2 = 150000         # décimation 1/4 au-delà

# Fenêtre glissante APPLIQUÉE UNIQUEMENT AU TOUR EN COURS (player)
SLIDING_WINDOW_SEC = float(os.getenv("SLIDING_WINDOW_SEC", "120"))
STALL_WARN_S = 1.5

LAP_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf"
]

# --- assets/ pour CSS dropdown sombre ---
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
app = Dash(__name__, assets_folder=ASSETS_DIR)
app.title = "F1 Live Telemetry"
_logger = get_logger()


def make_empty_fig(title, y_title=None):
    """Figure sans annotation ; on l’ajoute dynamiquement si aucune trace n’est présente."""
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis_title="Temps (s)",
        yaxis_title=(y_title or ""),
        template="plotly_dark",
        uirevision="fixed",
    )
    return fig


def ms_to_str(ms: int) -> str:
    if not isinstance(ms, (int, float)) or ms <= 0:
        return "—"
    total_ms = int(ms)
    minutes = total_ms // 60000
    seconds = (total_ms % 60000) // 1000
    millis = total_ms % 1000
    return f"{minutes}:{seconds:02d}.{millis:03d}"


app.layout = html.Div([
    html.H2("F1 Live Telemetry Dashboard"),
    html.Div(id="status_bar", style={
             "margin": "8px 0", "fontFamily": "monospace"}),

    html.Div([
        html.Button("Dump snapshot (debug)", id="btn_dump", n_clicks=0),
        html.Div(id="dump_status", style={"marginTop": "6px"})
    ], style={"margin": "8px 0"}),

    html.Div([
        html.Label("Superposer des laps antérieurs / séries (PB/Rival)"),
        dcc.Dropdown(
            id="overlay_laps",
            multi=True,
            placeholder="Choisis des laps (ex.: 3, 4) et/ou PB, Rival",
            style={"color": "#EEE", "backgroundColor": "#222",
                   "borderColor": "#444"},
            className="dark-dropdown"
        ),
        html.Button("Exporter CSV (tout)", id="btn_export",
                    n_clicks=0, style={"marginLeft": "12px"}),
        html.Button("Exporter PB", id="btn_export_pb",
                    n_clicks=0, style={"marginLeft": "6px"}),
        html.Button("Exporter Rival", id="btn_export_rival",
                    n_clicks=0, style={"marginLeft": "6px"}),
        dcc.Download(id="download_csv"),
    ], style={"margin": "8px 0"}),

    dcc.Interval(id="update", interval=UPDATE_INTERVAL_MS, n_intervals=0),
    dcc.Graph(id="speed_graph"),
    dcc.Graph(id="rpm_graph"),
    dcc.Graph(id="gear_graph"),
    dcc.Graph(id="throttle_brake_graph"),
], style={"padding": "10px", "backgroundColor": "#111", "color": "#EEE"})

# --- État global / incrémental ---
_last_render_ts = 0.0
_prev_figs = None
_series_index = {}   # key: (who, lap) -> [segments]; segment = list[points]
_last_buf_len = 0
_last_overlay_key = ""


@app.callback(Output("dump_status", "children"), Input("btn_dump", "n_clicks"))
def do_dump(n):
    if not n:
        return ""
    path = dump_snapshot(max_points=30000, filename_prefix="snapshot_manual")
    return f"Snapshot écrit: {path}" if path else "Snapshot: erreur (voir logs)"


def _update_series_index(new_points):
    """Met à jour l'index (who, lap) avec les nouveaux points uniquement."""
    last_t_ms = {}
    last_dist = {}
    # init derniers t_ms/dist par clé existante
    for key, segs in _series_index.items():
        if segs and segs[-1]:
            p_last = segs[-1][-1]
            last_t_ms[key] = float(p_last.get("t_game_ms", 0.0))
            last_dist[key] = float(p_last.get("lapDist", 0.0))
    restart_cnt_local = 0
    for p in new_points:
        who = p.get("who", "player")
        lap = p.get("lap", None)
        if lap is None:
            continue
        key = (who, lap)
        t_ms = float(p.get("t_game_ms", 0.0) or 0.0)
        dist = float(p.get("lapDist", 0.0) or 0.0)
        if key not in _series_index:
            _series_index[key] = [[p]]
            last_t_ms[key] = t_ms
            last_dist[key] = dist
            continue
        jump_back = (t_ms < (last_t_ms.get(key, 0.0) - RESTART_MARGIN_MS))
        zero_reset = (last_t_ms.get(key, 0.0) >
                      RESTART_MARGIN_MS) and (t_ms == 0.0)
        dist_back = (dist < (last_dist.get(key, 0.0) - RESTART_MARGIN_DIST))
        if jump_back or zero_reset or dist_back:
            _series_index[key].append([p])
            restart_cnt_local += 1
        else:
            _series_index[key][-1].append(p)
        last_t_ms[key] = t_ms
        last_dist[key] = dist
    return restart_cnt_local


@app.callback(Output("overlay_laps", "options"), Input("update", "n_intervals"))
def update_overlay_options(_):
    # Proposer les laps player (numériques) + séries spéciales PB/Rival si présentes
    keys = list(_series_index.keys())  # (who, lap)
    laps_player = sorted({lap for (who, lap) in keys if who == "player"})
    opts = [{"label": f"Lap {int(l)}", "value": int(l)} for l in laps_player]

    # Lire méta Time Trial pour enrichir le label
    pb_ms = int(telemetry_stat.get("tt_pb_lap_ms", 0) or 0)
    rv_ms = int(telemetry_stat.get("tt_rival_lap_ms", 0) or 0)
    pb_valid = int(telemetry_stat.get("tt_pb_valid", 0) or 0)
    rv_valid = int(telemetry_stat.get("tt_rival_valid", 0) or 0)

    has_pb_series = any(who == "pb" for (who, lap) in keys)
    has_rival_series = any(who == "rival" for (who, lap) in keys)

    if has_pb_series:
        label_pb = f"Personal Best (PB) – {ms_to_str(pb_ms)}" if pb_ms > 0 else "Personal Best (PB)"
        if pb_valid == 0 and pb_ms > 0:  # tour invalide
            label_pb += " (invalid)"
        opts.append({"label": label_pb, "value": "PB"})

    if has_rival_series:
        label_rv = f"Rival – {ms_to_str(rv_ms)}" if rv_ms > 0 else "Rival"
        if rv_valid == 0 and rv_ms > 0:
            label_rv += " (invalid)"
        opts.append({"label": label_rv, "value": "Rival"})

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
    global _last_render_ts, _prev_figs, _last_buf_len, _last_overlay_key

    t_start = time.perf_counter()
    speed_fig = make_empty_fig("Vitesse (km/h)", "km/h")
    rpm_fig = make_empty_fig("Régime moteur (RPM)", "RPM")
    gear_fig = make_empty_fig("Rapport engagé", "Gear")
    tb_fig = make_empty_fig("Pédales (Throttle / Brake)", "0..1")

    def add_empty_note(fig):
        """Ajoute l'annotation 'Aucune donnée...' si la figure n'a aucune trace; sinon la retire."""
        if not fig.data or len(fig.data) == 0:
            fig.update_layout(annotations=[dict(
                text="Aucune donnée (en attente de la capture UDP)",
                x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                font=dict(size=14, color="gray")
            )])
        else:
            fig.update_layout(annotations=[])

    try:
        buf, stat = snapshot()
        if not buf:
            status = "Buffer: 0 points\nDernière mise à jour: —"
            for fig in (speed_fig, rpm_fig, gear_fig, tb_fig):
                add_empty_note(fig)
            _prev_figs = (status, speed_fig, rpm_fig, gear_fig, tb_fig)
            return status, speed_fig, rpm_fig, gear_fig, tb_fig

        now = time.time()
        last_ts = buf[-1].get("t", 0.0)
        stalled_for = now - float(stat.get("last_append_wall", last_ts))
        stall_msg = f"\nFlux inactif: {stalled_for:.1f}s" if stalled_for > STALL_WARN_S else ""

        # Cast robuste des overlays (ints + tokens "PB" / "Rival")
        raw_overlays = overlay_value or []
        overlay_tokens = []
        for v in raw_overlays:
            if isinstance(v, str) and v.upper() in ("PB", "RIVAL"):
                overlay_tokens.append(v.upper())
            else:
                try:
                    overlay_tokens.append(int(v))
                except Exception:
                    pass
        overlay_key = ",".join(
            map(str, sorted(overlay_tokens, key=lambda x: (isinstance(x, str), x)))
        )

        # Si pas de nouveau point ET overlay identique -> réutiliser
        if (last_ts <= _last_render_ts) and _prev_figs is not None and (overlay_key == _last_overlay_key):
            status_prev, s_prev, r_prev, g_prev, t_prev = _prev_figs
            status = status_prev.split("\n")[0] + \
                f"\nDernière mise à jour: {time.strftime('%H:%M:%S', time.localtime(_last_render_ts))}{stall_msg}"
            return status, s_prev, r_prev, g_prev, t_prev

        # Mise à jour incrémentale
        buf_len = len(buf)
        new_points = buf[_last_buf_len:buf_len] if buf_len > _last_buf_len else []
        restart_cnt = _update_series_index(new_points)
        _last_buf_len = buf_len

        # utilitaires (couverture)
        def segment_coverage(seg):
            ds = [float(x.get("lapDist", 0.0)) for x in seg]
            if ds:
                cov_d = (max(ds) - min(ds))
                if cov_d >= 0.1:
                    return cov_d
            ts = [float(x.get("t_game_ms", 0.0)) for x in seg]
            return (max(ts) - min(ts)) if ts else 0.0

        # Trouver le dernier lap du player (tour courant)
        keys = list(_series_index.keys())     # (who, lap)
        laps_player = sorted({lap for (who, lap) in keys if who == "player"})
        latest_lap = max(laps_player) if laps_player else None

        # Tour courant : dernier segment (player)
        current_pts = []
        if latest_lap is not None:
            segs = _series_index.get(("player", latest_lap), [])
            current_pts = segs[-1] if segs else []

        # Construire la liste des overlays : laps (player) + PB + Rival
        overlays = []
        for tok in overlay_tokens:
            if isinstance(tok, int):
                # lap antérieur (player) -> choisir le segment le plus large
                segs = _series_index.get(("player", tok), [])
                if segs:
                    overlays.append(
                        ("Lap " + str(tok), max(segs, key=segment_coverage)))
            elif tok == "PB":
                # meilleur segment PB
                seg_candidates = [
                    segs for (who, lap), segs in _series_index.items() if who == "pb"]
                if seg_candidates:
                    seg = max(seg_candidates, key=lambda s: segment_coverage(
                        s[-1]) if s else 0.0)
                    overlays.append(
                        ("Personal Best (PB)", seg[-1] if seg else []))
            elif tok == "RIVAL":
                seg_candidates = [
                    segs for (who, lap), segs in _series_index.items() if who == "rival"]
                if seg_candidates:
                    seg = max(seg_candidates, key=lambda s: segment_coverage(
                        s[-1]) if s else 0.0)
                    overlays.append(("Rival", seg[-1] if seg else []))

        # --- Graphs ---
        x_title = "Temps de tour (s)"
        total_points = 0
        i = 0

        # 1) Tour courant (player) — AVEC FENÊTRE GLISSANTE
        pts = current_pts
        if pts:
            x_raw_s = [float(pp.get("t_game_ms", 0.0)) / 1000.0 for pp in pts]
            if x_raw_s:
                t0_s = x_raw_s[0]
                x_s = [xi - t0_s for xi in x_raw_s]
                max_x = x_s[-1] if x_s else 0.0
                # >>> MICRO-PATCH : fenêtre glissante UNIQUEMENT pour le tour en cours <<<
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
                ))
                rpm_fig.add_trace(ScatterClass(
                    x=x_plot, y=rpm_plot, mode="lines",
                    name=f"Lap {latest_lap}",
                    line=dict(width=2, color=col),
                    legendgroup=grp,
                ))
                gear_fig.add_trace(ScatterClass(
                    x=x_plot, y=gear_plot, mode="lines+markers",
                    name=f"Lap {latest_lap}",
                    line=dict(width=2, color=col),
                    marker=dict(size=4, color=col),
                    legendgroup=grp,
                ))
                tb_fig.add_trace(ScatterClass(
                    x=x_plot, y=thr_plot, mode="lines",
                    name=f"Throttle (Lap {latest_lap})",
                    line=dict(width=2, color=col, dash="solid"),
                    legendgroup=grp,
                ))
                tb_fig.add_trace(ScatterClass(
                    x=x_plot, y=brk_plot, mode="lines",
                    name=f"Brake (Lap {latest_lap})",
                    line=dict(width=2, color=col, dash="dot"),
                    legendgroup=grp,
                ))

        # 2) Overlays (laps / PB / Rival) — SANS FENÊTRE GLISSANTE (intégralité du segment choisi)
        for label, pts in overlays:
            i += 1
            if not pts:
                continue
            x_raw_s = [float(pp.get("t_game_ms", 0.0)) / 1000.0 for pp in pts]
            if not x_raw_s:
                continue
            t0_s = x_raw_s[0]
            x_s = [xi - t0_s for xi in x_raw_s]

            # >>> MICRO-PATCH : PAS de découpe pour les overlays (PB/Rival/laps) <<<
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
            grp = f"overlay{i}"

            speed_fig.add_trace(ScatterClass(
                x=x_plot, y=speed_plot, mode="lines",
                name=label, line=dict(width=1.8, color=col), legendgroup=grp))
            rpm_fig.add_trace(ScatterClass(
                x=x_plot, y=rpm_plot, mode="lines",
                name=label, line=dict(width=1.8, color=col), legendgroup=grp))
            gear_fig.add_trace(ScatterClass(
                x=x_plot, y=gear_plot, mode="lines+markers",
                name=label, line=dict(width=1.8, color=col),
                marker=dict(size=3, color=col), legendgroup=grp))
            tb_fig.add_trace(ScatterClass(
                x=x_plot, y=thr_plot, mode="lines",
                name=f"Throttle ({label})", line=dict(width=1.8, color=col, dash="solid"),
                legendgroup=grp))
            tb_fig.add_trace(ScatterClass(
                x=x_plot, y=brk_plot, mode="lines",
                name=f"Brake ({label})", line=dict(width=1.8, color=col, dash="dot"),
                legendgroup=grp))

        # Layouts + repère x=0 + annotation conditionnelle
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
            # >>> MICRO-PATCH : annotation uniquement si aucun trace <<<
            add_empty_note(fig)

        # Statut + instrumentation temps
        t_end = time.perf_counter()
        duration_ms = (t_end - t_start) * 1000.0
        shown_labels = [f"Lap {latest_lap}"] if latest_lap is not None else []
        shown_labels += [lbl for (lbl, _) in overlays]
        status = (
            f"Buffer: {len(buf)} points\n"
            f"Séries affichées: {', '.join(shown_labels) if shown_labels else '—'}\n"
            f"Restart détectés: {restart_cnt}\n"
            f"Points total (affichés): {total_points}\n"
            f"callback={duration_ms:.1f} ms\n"
            f"Dernière mise à jour: {time.strftime('%H:%M:%S', time.localtime(last_ts))}{stall_msg}"
        )

        if duration_ms > 400.0:
            _logger.warning("Dash callback slow: %.1f ms (buf=%d, overlays=%s, points=%d)",
                            duration_ms, len(buf), shown_labels, total_points)

        _prev_figs = (status, speed_fig, rpm_fig, gear_fig, tb_fig)
        _last_render_ts = last_ts
        _last_overlay_key = overlay_key
        return status, speed_fig, rpm_fig, gear_fig, tb_fig

    except Exception as e:
        _logger.error("update_graphs ERROR: %s", e, exc_info=True)
        status = f"Erreur callback — {type(e).__name__}: {e}"
        for fig in (speed_fig, rpm_fig, gear_fig, tb_fig):
            add_empty_note(fig)
        _prev_figs = (status, speed_fig, rpm_fig, gear_fig, tb_fig)
        return status, speed_fig, rpm_fig, gear_fig, tb_fig


# --- Export CSV (tout / PB / Rival) ---
@app.callback(
    Output("download_csv", "data"),
    Input("btn_export", "n_clicks"),
    Input("btn_export_pb", "n_clicks"),
    Input("btn_export_rival", "n_clicks"),
    prevent_initial_call=True
)
def export_csv(n_all, n_pb, n_rival):
    # déterminer quel bouton a déclenché via dash.callback_context
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(
        ".")[0] if ctx and ctx.triggered else None

    buf, _ = snapshot()
    if not buf:
        return None

    df = pd.DataFrame(buf)
    cols = ["t", "t_game_ms", "speed", "rpm", "gear",
            "throttle", "brake", "lap", "invalid", "lapDist", "who"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]

    if triggered_id == "btn_export_pb":
        dff = df[df["who"] == "pb"].copy()
        if dff.empty:
            return None
        filename = time.strftime("telemetry_PB_%Y%m%d_%H%M%S.csv")
        return dcc.send_data_frame(dff.to_csv, filename, index=False)

    if triggered_id == "btn_export_rival":
        dff = df[df["who"] == "rival"].copy()
        if dff.empty:
            return None
        filename = time.strftime("telemetry_Rival_%Y%m%d_%H%M%S.csv")
        return dcc.send_data_frame(dff.to_csv, filename, index=False)

    # sinon "tout"
    filename = time.strftime("telemetry_%Y%m%d_%H%M%S.csv")
    return dcc.send_data_frame(df.to_csv, filename, index=False)


def start_capture_in_background():
    th = threading.Thread(target=run_capture, daemon=True)
    th.start()
    return th


if __name__ == "__main__":
    start_capture_in_background()
    app.run(host="127.0.0.1", port=8050, debug=True, use_reloader=False)
