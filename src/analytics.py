import os
import json
import csv
import time
import datetime
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class GameAnalytics:
    """Collects simple per-run analytics and persists results.

    - Records each shot with shooter, target, coords, hit/sunk flags and timestamp.
    - Tracks per-player shot/hit/miss/ships_sunk counters.
    - Saves a detailed JSON and appends a summary CSV row in `results/`.
    """

    def __init__(
        self,
        mode: str,
        num_players: int = 2,
        attack_all: bool = False,
        seed: int | None = None,
        run_metadata: Dict[str, Any] | None = None,
    ):
        self.mode = mode
        self.num_players = num_players
        self.attack_all = bool(attack_all)
        self.seed = seed
        self.run_metadata = dict(run_metadata or {})
        self.run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start_time = time.time()
        self.end_time = None
        self.turns = 0
        self.shots: list[Dict[str, Any]] = []

        # initialize player stats (indices 0..num_players-1)
        self.players: Dict[int, Dict[str, int]] = {
            i: {"shots": 0, "hits": 0, "misses": 0, "ships_sunk": 0}
            for i in range(num_players)
        }

        self.winner: str | None = None

    def next_turn(self) -> None:
        self.turns += 1

    def record_shot(self, shooter_id: int, target_id: int, x: int, y: int, hit: bool, is_sunk: bool, turn: int | None = None) -> None:
        if shooter_id not in self.players:
            self.players[shooter_id] = {"shots": 0, "hits": 0, "misses": 0, "ships_sunk": 0}

        rec = {
            "shooter": int(shooter_id),
            "target": int(target_id),
            "x": int(x),
            "y": int(y),
            "hit": bool(hit),
            "is_sunk": bool(is_sunk),
            "turn": int(turn) if turn is not None else self.turns,
            "ts": time.time(),
        }

        self.shots.append(rec)
        p = self.players[shooter_id]
        p["shots"] += 1
        if hit:
            p["hits"] += 1
        else:
            p["misses"] += 1
        if is_sunk:
            p["ships_sunk"] += 1

    def finalize(self, winner: str) -> None:
        self.end_time = time.time()
        self.winner = winner
        # Record final survival state for all players
        for p_id in list(self.players.keys()):
            if "turns_alive" not in self.players[p_id]:
                self.players[p_id]["turns_alive"] = self.turns
                self.players[p_id]["survived"] = (winner == f"AI {p_id+1}" or (winner == "Player" and p_id == 0))

    def record_defeat(self, player_id: int):
        """Specifically records when a player is eliminated."""
        if player_id in self.players:
            self.players[player_id]["turns_alive"] = self.turns
            self.players[player_id]["survived"] = False

    def get_player_ai_types(self) -> Dict[int, str]:
        """Optionally stores AI logic class names for better reporting."""
        return getattr(self, "player_ai_types", {})

    @staticmethod
    def _summary_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            return "|".join(str(v) for v in value)
        if isinstance(value, dict):
            return "|".join(f"{k}:{value[k]}" for k in sorted(value))
        return str(value)

    @staticmethod
    def _append_csv_row(path: Path, header: list[str], row: list[Any]) -> None:
        existing_rows: list[dict[str, str]] = []
        needs_rewrite = False
        if path.exists():
            with open(path, "r", newline="", encoding="utf8") as f:
                reader = csv.DictReader(f)
                existing_header = reader.fieldnames or []
                if existing_header != header:
                    needs_rewrite = True
                    existing_rows = list(reader)

        if not path.exists() or needs_rewrite:
            with open(path, "w", newline="", encoding="utf8") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                for prev in existing_rows:
                    writer.writerow([prev.get(col, "") for col in header])

        with open(path, "a", newline="", encoding="utf8") as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def to_dict(self) -> Dict[str, Any]:
        duration = None
        if self.end_time:
            duration = round(self.end_time - self.start_time, 3)

        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "num_players": self.num_players,
            "attack_all": int(self.attack_all),
            "seed": self.seed,
            "run_metadata": self.run_metadata,
            "start_time": datetime.datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_s": duration,
            "turns": self.turns,
            "winner": self.winner,
            "player_ai_types": self.get_player_ai_types(),
            "players": self.players,
            "shots": self.shots,
        }

    def save_json(self, folder: str = "results") -> str:
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
            path = Path(folder) / f"{self.run_id}_{self.mode}.json"
            with open(path, "w", encoding="utf8") as f:
                json.dump(self.to_dict(), f, indent=2)
            return str(path)
        except Exception:
            logger.exception("Failed to write analytics JSON to %s", folder)
            raise

    def append_summary_csv(self, folder: str = "results", csv_name: str = "summary.csv") -> str:
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
            path = Path(folder) / csv_name
            header = [
                "run_id",
                "mode",
                "num_players",
                "attack_all",
                "seed",
                "ai_type",
                "ai_roster",
                "placement_roster",
                "grid_size",
                "batch_index",
                "batch_games",
                "start_time",
                "end_time",
                "duration_s",
                "turns",
                "winner",
                "total_shots",
                "total_hits",
                "accuracy_percent",
            ]

            total_shots = sum(p["shots"] for p in self.players.values())
            total_hits = sum(p["hits"] for p in self.players.values())
            accuracy = round((total_hits / total_shots) * 100, 2) if total_shots else 0.0

            row = [
                self.run_id,
                self.mode,
                self.num_players,
                int(self.attack_all),
                self.seed if self.seed is not None else "",
                self._summary_text(self.run_metadata.get("ai_type")),
                self._summary_text(self.run_metadata.get("ai_roster")),
                self._summary_text(self.run_metadata.get("placement_roster")),
                self._summary_text(self.run_metadata.get("grid_size")),
                self._summary_text(self.run_metadata.get("batch_index")),
                self._summary_text(self.run_metadata.get("batch_games")),
                datetime.datetime.fromtimestamp(self.start_time).isoformat(),
                datetime.datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else "",
                round((self.end_time - self.start_time), 3) if self.end_time else "",
                self.turns,
                self.winner,
                total_shots,
                total_hits,
                accuracy,
            ]

            self._append_csv_row(path, header, row)

            return str(path)
        except Exception:
            logger.exception("Failed to append analytics summary CSV to %s", folder)
            raise

    def export_human_performance(self, folder: str = "results") -> tuple[str, str] | None:
        """Writes PvE human-centric outputs for downstream ML and skill analysis.

        Produces:
        - `human_turns_ml.csv`: one row per human shot with pre-shot board state bitmaps.
        - `human_sessions.csv`: one row per PvE session with aggregate human metrics.
        """
        if self.mode != "PvE":
            return None

        human_shots = [s for s in self.shots if int(s.get("shooter", -1)) == 0]
        if not human_shots:
            return None

        Path(folder).mkdir(parents=True, exist_ok=True)

        grid_size = int(self.run_metadata.get("grid_size", 10))
        max_coord = max(max(int(s["x"]), int(s["y"])) for s in human_shots)
        grid_size = max(grid_size, max_coord + 1)

        turns_path = Path(folder) / "human_turns_ml.csv"
        sessions_path = Path(folder) / "human_sessions.csv"

        turns_header = [
            "run_id",
            "ai_type",
            "ai_roster",
            "placement_roster",
            "seed",
            "grid_size",
            "winner",
            "shot_index",
            "turn",
            "x",
            "y",
            "hit",
            "is_sunk",
            "hits_before_count",
            "misses_before_count",
            "hit_streak_before",
            "state_hits_bitmap",
            "state_misses_bitmap",
        ]

        known_hits = [[False for _ in range(grid_size)] for _ in range(grid_size)]
        known_misses = [[False for _ in range(grid_size)] for _ in range(grid_size)]

        player_hits = 0
        player_misses = 0
        player_ships_sunk = 0
        hit_streak = 0
        max_hit_streak = 0
        first_hit_turn = ""
        last_turn = None
        turn_deltas: list[int] = []

        ai_type = self._summary_text(self.run_metadata.get("ai_type"))
        ai_roster = self._summary_text(self.run_metadata.get("ai_roster"))
        placement_roster = self._summary_text(self.run_metadata.get("placement_roster"))
        winner = self.winner or ""

        for shot_index, shot in enumerate(human_shots, start=1):
            turn = int(shot.get("turn", shot_index))
            x = int(shot["x"])
            y = int(shot["y"])
            hit = bool(shot["hit"])
            is_sunk = bool(shot["is_sunk"])

            if last_turn is not None:
                turn_deltas.append(turn - last_turn)
            last_turn = turn

            state_hits_bitmap = "".join("1" if c else "0" for row in known_hits for c in row)
            state_misses_bitmap = "".join("1" if c else "0" for row in known_misses for c in row)

            turn_row = [
                self.run_id,
                ai_type,
                ai_roster,
                placement_roster,
                self.seed if self.seed is not None else "",
                grid_size,
                winner,
                shot_index,
                turn,
                x,
                y,
                int(hit),
                int(is_sunk),
                player_hits,
                player_misses,
                hit_streak,
                state_hits_bitmap,
                state_misses_bitmap,
            ]
            self._append_csv_row(turns_path, turns_header, turn_row)

            if hit:
                known_hits[y][x] = True
                player_hits += 1
                hit_streak += 1
                max_hit_streak = max(max_hit_streak, hit_streak)
                if first_hit_turn == "":
                    first_hit_turn = turn
            else:
                known_misses[y][x] = True
                player_misses += 1
                hit_streak = 0

            if is_sunk:
                player_ships_sunk += 1

        total_player_shots = len(human_shots)
        player_accuracy = round((player_hits / total_player_shots) * 100, 2) if total_player_shots else 0.0
        avg_turn_delta = round(sum(turn_deltas) / len(turn_deltas), 3) if turn_deltas else 0.0

        session_header = [
            "run_id",
            "ai_type",
            "ai_roster",
            "placement_roster",
            "seed",
            "grid_size",
            "winner",
            "player_won",
            "total_player_shots",
            "total_player_hits",
            "total_player_misses",
            "player_accuracy_percent",
            "player_ships_sunk",
            "first_hit_turn",
            "max_hit_streak",
            "avg_turn_delta_between_player_shots",
            "duration_s",
            "turns",
        ]
        session_row = [
            self.run_id,
            ai_type,
            ai_roster,
            placement_roster,
            self.seed if self.seed is not None else "",
            grid_size,
            winner,
            int(winner == "Player"),
            total_player_shots,
            player_hits,
            player_misses,
            player_accuracy,
            player_ships_sunk,
            first_hit_turn,
            max_hit_streak,
            avg_turn_delta,
            round((self.end_time - self.start_time), 3) if self.end_time else "",
            self.turns,
        ]
        self._append_csv_row(sessions_path, session_header, session_row)

        return str(turns_path), str(sessions_path)

    def save(self, folder: str = "results") -> tuple[str, str]:
        json_path = self.save_json(folder)
        csv_path = self.append_summary_csv(folder)
        try:
            self.export_human_performance(folder)
        except Exception:
            logger.exception("Failed to export human performance outputs")
        return json_path, csv_path
