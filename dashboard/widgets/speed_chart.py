"""
speed_chart.py - Widget graphique des vitesses pour telemetrie F1.

Ce module fournit la classe `SpeedChart`, un widget PyQt6 qui affiche
les vitesses en km/h sur le temps d'un tour. Le widget peut afficher :
- le tour en cours (ligne principale, mise a jour en temps reel),
- des tours "overlay" (historique ou rivaux) pour comparaison,
- un "ghost" PB (meilleur personnel) et des rivaux eventuels.

Les commentaires dans ce fichier sont en francais et cherchent a
expliquer les structures de donnees, la logique de dessin, et les
decisions pour la mise a jour efficace du graphe.
"""
from ..constants import BG_DARK, GRID_COLOR, TEXT_COLOR
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib
matplotlib.use("QtAgg")


# Durée (en secondes) de la fenetre lorsque le mode n'est pas "full_lap".
WINDOW_S = 30

# Palette de couleurs pour les overlays de tours du joueur (selectionnes).
_OVERLAY_COLORS = [
    "#ff8a65", "#ce93d8", "#a5d6a7", "#ffd54f",
    "#ef9a9a", "#80cbc4", "#ffab40", "#b39ddb",
]

# Couleurs utilises pour les differents roles sur le graphe.
COLOR_CURRENT = "#4fc3f7"  # tour en cours (bleu clair)
COLOR_BEST = "#ffd54f"     # couleur pour le meilleur tour
COLOR_RIVAL = "#ff8a65"    # couleur par defaut pour un rival
_RIVAL_COLORS = ["#ff8a65", "#ef9a9a", "#ffab40", "#ffcc80"]


def ms_to_str(ms: float) -> str:
    """Convertit une duree en millisecondes en string lisible.

    Format renvoyé : M:SS.mmm (minutes:secondes.millisecondes). Si la
    valeur est <= 0, renvoie une representation vide/placeholder.
    """
    if ms <= 0:
        return "--:--.---"
    total_s, ms_part = divmod(int(ms), 1000)
    m, s = divmod(total_s, 60)
    return f"{m}:{s:02d}.{ms_part:03d}"


class SpeedChart(QWidget):
    """Widget PyQt qui affiche l'evolution de la vitesse au cours d'un tour.

    Attributs internes principaux :
    - _cur_times / _cur_speeds : donnees temporelles du tour en cours (listes)
    - _laps : dictionnaire {lap_num: {times, speeds, lap_time_ms, label?}}
    - _visible : ensemble de lap_num a afficher en overlay
    - _overlay_lines : mapping lap_num -> objet Line2D de matplotlib pour suppression

    On maintient en parallele des structures pour un "rival" et un "pb ghost"
    afin de permettre comparaison cote-a-cote tout en gardant une logique de
    mise a jour independante (pour redraw plus efficiente).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Mode d'affichage : 'full_lap' montre tout le tour, autre valeur montre
        # une fenetre glissante de taille WINDOW_S.
        self._mode = "full_lap"

        # Donnees du tour en cours
        self._cur_times:  list = []  # temps en secondes depuis debut de tour
        self._cur_speeds: list = []  # vitesses correspondantes en km/h

        # Laps historiques du JOUEUR : {lap_num: {times, speeds, lap_time_ms}}
        self._laps: dict = {}

        # Ensemble de tours visibles (overlay) et references vers leurs lignes
        self._visible: set = set()
        self._overlay_lines: dict = {}

        # Afficher ou non la ligne du tour en cours
        self._show_cur: bool = True

        # ----- Structures pour le RIVAL (ghost/rival playback) -----
        self._rival_cur_times:  list = []
        self._rival_cur_speeds: list = []
        self._rival_laps: dict = {}
        self._rival_visible: set = set()
        self._rival_overlay_lines: dict = {}
        self._show_rival_cur: bool = False

        # ----- PB ghost (meilleur perso) -----
        self._pb_cur_times:  list = []
        self._pb_cur_speeds: list = []
        self._legend = None

        # Setup matplotlib figure / axes avec theme sombre
        fig = Figure(figsize=(8, 4), facecolor=BG_DARK)
        self._ax = fig.add_subplot(111, facecolor=BG_DARK)
        self._ax.set_ylim(0, 380)
        self._ax.set_xlabel("Temps du tour (s)", color=TEXT_COLOR)
        self._ax.set_ylabel("km/h", color=TEXT_COLOR)
        self._ax.tick_params(colors=TEXT_COLOR)
        self._ax.grid(True, color=GRID_COLOR, linewidth=0.5)
        for spine in self._ax.spines.values():
            spine.set_edgecolor(GRID_COLOR)

        # Ligne principale pour le tour courant
        (self._cur_line,) = self._ax.plot(
            [], [], color=COLOR_CURRENT, linewidth=2, zorder=10, label="Tour en cours"
        )

        # Ligne pour le rival (par defaut invisible jusqu'a ce qu'on active)
        (self._rival_cur_line,) = self._ax.plot(
            [], [], color=COLOR_RIVAL, linewidth=2, linestyle="--", alpha=0.85, zorder=9, visible=False, label="Rival (en cours)"
        )

        # Legende initiale (sera reconstruite dynamiquement)
        self._legend = self._ax.legend(
            loc="upper left", framealpha=0.25, facecolor=BG_DARK,
            edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9
        )

        # Canvas PyQt pour l'affichage
        self._canvas = FigureCanvas(fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def set_cur_visible(self, show: bool):
        self._show_cur = show
        self._cur_line.set_visible(show)
        self._canvas.draw_idle()

    def set_mode(self, mode: str):
        """Change le mode d'affichage et force le redraw du tour courant.

        `mode` attendu: 'full_lap' | autre -> fenetre glissante.
        """
        self._mode = mode
        self._redraw_current()

    def append(self, speed: float, lap_ms: float):
        if lap_ms <= 0:
            return  # pas encore franchi la ligne de depart
        t = lap_ms / 1000.0
        # Ignorer les points non monotones (paquets en desordre ou transitoires)
        if self._cur_times and t < self._cur_times[-1]:
            return
        self._cur_speeds.append(speed)
        self._cur_times.append(t)
        self._redraw_current()

    def commit_lap(self, lap_num: int, lap_time_ms: float):
        """Verrouille le tour en cours dans `_laps` sous cle `lap_num`.

        On exige au moins 5 points pour eviter d'enregistrer des tours
        incomplets (par ex. reset immediat). Retourne True si sauvegarde.
        """
        if len(self._cur_times) < 5:
            return False
        self._laps[lap_num] = {
            "times":       list(self._cur_times),
            "speeds":      list(self._cur_speeds),
            "lap_time_ms": lap_time_ms,
        }
        return True

    def set_visible_laps(self, lap_nums: set):
        # Defini l'ensemble des tours du JOUEUR a afficher en overlay.
        self._visible = set(lap_nums)
        self._rebuild_overlays()

    def reset(self):
        """Reinitialise les donnees du tour en cours (ne touche pas aux overlays)."""
        self._cur_times.clear()
        self._cur_speeds.clear()
        self._cur_line.set_xdata([])
        self._cur_line.set_ydata([])
        # On recentre l'axe X sur une plage minimale
        self._ax.set_xlim(0, 1)
        self._canvas.draw_idle()

    def best_lap_num(self):
        if not self._laps:
            return None
        return min(
            (n for n, d in self._laps.items() if d["lap_time_ms"] > 0),
            key=lambda n: self._laps[n]["lap_time_ms"],
            default=None,
        )

    def lap_info(self):
        return sorted(
            [(n, d["lap_time_ms"]) for n, d in self._laps.items()],
            key=lambda x: x[0],
        )

    # ── Rival ───────────────────────────────────────────────────────────

    def append_rival(self, speed: float, lap_ms: float):
        if lap_ms <= 0 or speed <= 0:
            return  # ghost hors piste ou à l'arrêt
        t = lap_ms / 1000.0
        # Ignorer les points non monotones
        if self._rival_cur_times and t < self._rival_cur_times[-1]:
            return
        self._rival_cur_speeds.append(speed)
        self._rival_cur_times.append(t)
        self._redraw_rival_cur()

    def reset_rival(self):
        self._rival_cur_times.clear()
        self._rival_cur_speeds.clear()
        self._rival_cur_line.set_xdata([])
        self._rival_cur_line.set_ydata([])
        self._canvas.draw_idle()

    def append_pb(self, speed: float, lap_ms: float):
        t = lap_ms / 1000.0
        if self._pb_cur_times and t < self._pb_cur_times[-1]:
            return
        self._pb_cur_speeds.append(speed)
        self._pb_cur_times.append(t)

    def reset_pb(self):
        self._pb_cur_times.clear()
        self._pb_cur_speeds.clear()

    def commit_pb_lap(self, lap_time_ms: float) -> bool:
        """Enregistre le PB courant comme un "ghost" rival sous la cle 0.

        Cela permet de reutiliser la logique d'affichage des rivaux pour
        montrer le meilleur tour personnel cote-a-cote.
        """
        if len(self._pb_cur_times) < 5:
            return False
        self._rival_laps[0] = {
            "times":       list(self._pb_cur_times),
            "speeds":      list(self._pb_cur_speeds),
            "lap_time_ms": lap_time_ms,
            "label":       "Meilleur perso",
        }
        return True

    def commit_pb_from_player_lap(self, lap_time_ms: float) -> bool:
        """Enregistre le tour courant du JOUEUR comme PB si meilleur.

        Verifie si la valeur est meilleure que l'existant (cle 0) avant
        d'ecraser. Retourne True si sauvegarde effectuee.
        """
        if len(self._cur_times) < 5:
            return False
        existing = self._rival_laps.get(0)
        if existing is not None and lap_time_ms >= existing["lap_time_ms"]:
            return False  # pas un nouveau PB
        self._rival_laps[0] = {
            "times":       list(self._cur_times),
            "speeds":      list(self._cur_speeds),
            "lap_time_ms": lap_time_ms,
            "label":       "Meilleur perso",
        }
        return True

    def commit_rival_lap(self, lap_num: int, lap_time_ms: float, label: str = ""):
        if len(self._rival_cur_times) < 5:
            return None
        self._rival_laps[lap_num] = {
            "times":       list(self._rival_cur_times),
            "speeds":      list(self._rival_cur_speeds),
            "lap_time_ms": lap_time_ms,
            "label":       label,
        }
        return lap_num

    def set_rival_cur_visible(self, show: bool):
        self._show_rival_cur = show
        self._redraw_rival_cur()
        self._redraw_current()  # met à jour l'axe X si le rival s'étend plus loin

    def set_visible_rival_laps(self, lap_nums: set):
        self._rival_visible = set(lap_nums)
        self._rebuild_rival_overlays()

    def best_rival_lap_num(self):
        if not self._rival_laps:
            return None
        return min(
            (n for n, d in self._rival_laps.items() if d["lap_time_ms"] > 0),
            key=lambda n: self._rival_laps[n]["lap_time_ms"],
            default=None,
        )

    def rival_lap_info(self):
        """Retourne [(lap_num, lap_time_ms, label), ...] triés par lap_num."""
        return sorted(
            [(n, d["lap_time_ms"], d.get("label", ""))
             for n, d in self._rival_laps.items()],
            key=lambda x: x[0],
        )

    def _rebuild_rival_overlays(self):
        # Supprime les lignes de overlay qui ne sont plus selectionnees
        for lap_num in list(self._rival_overlay_lines):
            if lap_num not in self._rival_visible:
                self._rival_overlay_lines[lap_num].remove()
                del self._rival_overlay_lines[lap_num]

        # Reconstruit les nouvelles lignes de overlay pour les rivaux visibles
        best = self.best_rival_lap_num()
        color_idx = 0
        for lap_num in sorted(self._rival_visible):
            if lap_num not in self._rival_laps:
                continue
            if lap_num in self._rival_overlay_lines:
                continue
            rec = self._rival_laps[lap_num]
            color = COLOR_BEST if lap_num == best else _RIVAL_COLORS[color_idx % len(
                _RIVAL_COLORS)]
            color_idx += 1
            lbl = rec.get("label") or f"Rival {lap_num}"
            (line,) = self._ax.plot(
                rec["times"], rec["speeds"],
                color=color, linewidth=1.5, alpha=0.75, zorder=5, linestyle="--",
                label=lbl,
            )
            self._rival_overlay_lines[lap_num] = line

        # Rafraichir l'affichage et legende
        self._canvas.draw_idle()
        self._update_legend()
        self._redraw_current()

    def _redraw_rival_cur(self):
        self._rival_cur_line.set_visible(self._show_rival_cur)
        if self._show_rival_cur and self._rival_cur_times:
            self._rival_cur_line.set_xdata(self._rival_cur_times)
            self._rival_cur_line.set_ydata(self._rival_cur_speeds)
        self._update_legend()
        self._canvas.draw_idle()

    def _rebuild_overlays(self):
        # Meme logique que pour les rivaux, appliquee aux tours du JOUEUR
        for lap_num in list(self._overlay_lines):
            if lap_num not in self._visible:
                self._overlay_lines[lap_num].remove()
                del self._overlay_lines[lap_num]

        best = self.best_lap_num()
        color_idx = 0
        for lap_num in sorted(self._visible):
            if lap_num not in self._laps:
                continue
            if lap_num in self._overlay_lines:
                continue
            rec = self._laps[lap_num]
            color = COLOR_BEST if lap_num == best else _OVERLAY_COLORS[color_idx % len(
                _OVERLAY_COLORS)]
            color_idx += 1
            star = "\u2605 " if lap_num == best else ""
            (line,) = self._ax.plot(
                rec["times"], rec["speeds"],
                color=color, linewidth=1.5, alpha=0.75, zorder=5,
                label=f"{star}Tour {lap_num}  {ms_to_str(rec['lap_time_ms'])}",
            )
            self._overlay_lines[lap_num] = line

        self._canvas.draw_idle()
        self._update_legend()
        # Mettre a jour l'axe X apres changement des overlays
        self._redraw_current()

    def _update_legend(self):
        """Reconstruit dynamiquement la legende selon les courbes visibles.

        On reconstruit plutot que de simplement afficher/masquer la legende
        pour garder l'ordre d'affichage et les labels coherents avec les
        lignes actuellement tracees.
        """
        lines, labels = [], []
        if self._show_cur and self._cur_times:
            lines.append(self._cur_line)
            labels.append("Tour en cours")
        if self._show_rival_cur and self._rival_cur_times:
            lines.append(self._rival_cur_line)
            labels.append("Rival (en cours)")
        for line in self._overlay_lines.values():
            lines.append(line)
            labels.append(line.get_label())
        for line in self._rival_overlay_lines.values():
            lines.append(line)
            labels.append(line.get_label())
        if lines:
            self._legend = self._ax.legend(
                lines, labels,
                loc="upper left", framealpha=0.25, facecolor=BG_DARK,
                edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9
            )
        else:
            if self._legend:
                self._legend.remove()
                self._legend = None

    def _max_reference_duration(self) -> float:
        # Calcule la duree maximale parmi les tours de reference et le rival en
        # cours; utilisee pour dimensionner l'axe X quand on montre le tour
        # en entier pour comparaison cote-a-cote.
        all_laps = list(self._laps.values()) + list(self._rival_laps.values())
        durations = [d["times"][-1] for d in all_laps if d["times"]]
        if self._show_rival_cur and self._rival_cur_times:
            durations.append(self._rival_cur_times[-1])
        return max(durations, default=0.0)

    def _redraw_current(self):
        # Redessine la ligne du tour courant selon le mode choisi.
        if not self._cur_times:
            # Meme sans data en cours, on maintient l'axe sur la duree de reference
            ref = self._max_reference_duration()
            if ref > 0:
                self._ax.set_xlim(0.0, ref)
                self._canvas.draw_idle()
            return

        if self._mode == "full_lap":
            # Affiche tout le tour depuis 0 jusqu'a la progression actuelle
            xs, ys = self._cur_times, self._cur_speeds
            # Axe X = max entre la progression actuelle et le tour de reference le plus long
            x_max = max(self._cur_times[-1],
                        self._max_reference_duration(), 1.0)
            x_min = 0.0
        else:
            # Mode fenetre glissante: ne garde que les points dans la fenetre
            t_end = self._cur_times[-1]
            t_start = max(0.0, t_end - WINDOW_S)
            pairs = [(t, s) for t, s in zip(self._cur_times, self._cur_speeds)
                     if t >= t_start]
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            x_min, x_max = t_start, max(t_end, t_start + 1.0)

        # Met a jour les donnees de la courbe et force un redraw asynchrone
        self._cur_line.set_xdata(xs)
        self._cur_line.set_ydata(ys)
        self._cur_line.set_visible(self._show_cur)
        self._ax.set_xlim(x_min, x_max)
        self._update_legend()
        self._canvas.draw_idle()
