import csv
import datetime
import json
import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BenchmarkConfig:
    games: int
    players: int
    attack_all: bool
    workers: int
    seed: int | None
    keep_per_game: bool


def _winner_to_index(winner: str | None) -> int | None:
    if not winner or not winner.startswith("AI "):
        return None
    try:
        return int(winner.split(" ")[1]) - 1
    except (IndexError, ValueError):
        return None


def _player_type(player_ai_types: dict[Any, Any], player_id: int) -> str:
    if player_id in player_ai_types:
        return str(player_ai_types[player_id])
    key = str(player_id)
    if key in player_ai_types:
        return str(player_ai_types[key])
    return f"AI {player_id + 1}"


def _rank_key(player_stats: dict[str, Any], turns_total: int) -> tuple[int, float, float, float]:
    survived = 1 if bool(player_stats.get("survived", False)) else 0
    turns_alive = float(player_stats.get("turns_alive", turns_total))
    ships_sunk = float(player_stats.get("ships_sunk", 0))
    hits = float(player_stats.get("hits", 0))
    return (survived, turns_alive, ships_sunk, hits)


def _elo_expected(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def _run_single_game(task: tuple[int, dict[str, Any]]) -> dict[str, Any]:
    game_index, cfg = task

    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["BATTLESHIP_DISABLE_LEARNING_PERSIST"] = "1"

    from multi_ai import MultiAIGame

    base_seed = cfg.get("seed")
    game_seed = (int(base_seed) + game_index) if base_seed is not None else None

    game = MultiAIGame(
        num_ais=int(cfg["players"]),
        attack_all=bool(cfg["attack_all"]),
        seed=game_seed,
        render=False,
        run_metadata={
            "batch_index": game_index + 1,
            "batch_games": int(cfg["games"]),
        },
        auto_save_results=bool(cfg.get("keep_per_game", False)),
    )

    while not game.game_over:
        game.perform_ai_turn()

    if game.analytics and game.analytics.end_time is None:
        game.analytics.finalize(game.winner or "No one")

    payload = game.analytics.to_dict() if game.analytics else None
    return {
        "game_index": game_index,
        "seed": game_seed,
        "winner": game.winner,
        "analytics": payload,
    }


def _aggregate(results: list[dict[str, Any]], cfg: BenchmarkConfig) -> dict[str, Any]:
    stats = defaultdict(
        lambda: {
            "games": 0,
            "wins": 0,
            "shots": 0,
            "hits": 0,
            "ships_sunk": 0,
            "survival_turns": 0.0,
            "survived_games": 0,
            "elo": 1000.0,
        }
    )

    game_summaries: list[dict[str, Any]] = []
    elo_k = 16.0

    for result in results:
        analytics = result.get("analytics") or {}
        players = analytics.get("players") or {}
        player_ai_types = analytics.get("player_ai_types") or {}
        turns_total = int(analytics.get("turns", 0) or 0)

        per_player_rank: list[tuple[str, tuple[int, float, float, float]]] = []

        for raw_player_id, player_stats in players.items():
            try:
                player_id = int(raw_player_id)
            except (TypeError, ValueError):
                continue

            algo_name = _player_type(player_ai_types, player_id)
            entry = stats[algo_name]
            entry["games"] += 1
            entry["shots"] += int(player_stats.get("shots", 0) or 0)
            entry["hits"] += int(player_stats.get("hits", 0) or 0)
            entry["ships_sunk"] += int(player_stats.get("ships_sunk", 0) or 0)
            entry["survival_turns"] += float(player_stats.get("turns_alive", turns_total) or 0)
            if bool(player_stats.get("survived", False)):
                entry["survived_games"] += 1

            per_player_rank.append((algo_name, _rank_key(player_stats, turns_total)))

        winner = result.get("winner")
        winner_idx = _winner_to_index(winner if isinstance(winner, str) else None)
        if winner_idx is not None:
            winner_name = _player_type(player_ai_types, winner_idx)
            stats[winner_name]["wins"] += 1

        for i in range(len(per_player_rank)):
            for j in range(i + 1, len(per_player_rank)):
                left_name, left_rank = per_player_rank[i]
                right_name, right_rank = per_player_rank[j]
                if left_name == right_name:
                    continue

                if left_rank > right_rank:
                    left_score, right_score = 1.0, 0.0
                elif left_rank < right_rank:
                    left_score, right_score = 0.0, 1.0
                else:
                    left_score, right_score = 0.5, 0.5

                left_elo = stats[left_name]["elo"]
                right_elo = stats[right_name]["elo"]
                left_expected = _elo_expected(left_elo, right_elo)
                right_expected = _elo_expected(right_elo, left_elo)
                stats[left_name]["elo"] = left_elo + elo_k * (left_score - left_expected)
                stats[right_name]["elo"] = right_elo + elo_k * (right_score - right_expected)

        game_summaries.append(
            {
                "game_index": int(result.get("game_index", 0)),
                "seed": result.get("seed"),
                "winner": winner,
                "turns": turns_total,
                "duration_s": analytics.get("duration_s"),
            }
        )

    leaderboard: list[dict[str, Any]] = []
    for algo_name, values in stats.items():
        games = max(1, int(values["games"]))
        shots = int(values["shots"])
        hits = int(values["hits"])
        wins = int(values["wins"])
        survived_games = int(values["survived_games"])

        accuracy = (100.0 * hits / shots) if shots else 0.0
        win_rate = 100.0 * wins / games
        survival_rate = 100.0 * survived_games / games
        avg_survival_turns = values["survival_turns"] / games

        elo_value = float(values["elo"])
        elo_scaled = max(0.0, min(100.0, (elo_value - 800.0) / 8.0))
        strength_index = 0.45 * win_rate + 0.20 * accuracy + 0.20 * survival_rate + 0.15 * elo_scaled

        leaderboard.append(
            {
                "algorithm": algo_name,
                "games": games,
                "wins": wins,
                "win_rate": round(win_rate, 3),
                "shots": shots,
                "hits": hits,
                "accuracy": round(accuracy, 3),
                "ships_sunk": int(values["ships_sunk"]),
                "avg_survival_turns": round(avg_survival_turns, 3),
                "survival_rate": round(survival_rate, 3),
                "elo": round(elo_value, 3),
                "strength_index": round(strength_index, 3),
            }
        )

    leaderboard.sort(
        key=lambda row: (
            row["strength_index"],
            row["win_rate"],
            row["survival_rate"],
            row["accuracy"],
        ),
        reverse=True,
    )

    return {
        "config": asdict(cfg),
        "games": sorted(game_summaries, key=lambda row: row["game_index"]),
        "leaderboard": leaderboard,
        "winner_distribution": {
            row["algorithm"]: row["wins"] for row in leaderboard if int(row["wins"]) > 0
        },
    }


def _write_outputs(report: dict[str, Any], output_prefix: str, results_dir: str) -> tuple[str, str]:
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_prefix = output_prefix.strip() or "benchmark"
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"{safe_prefix}_{run_id}.json"
    csv_path = out_dir / f"{safe_prefix}_{run_id}.csv"

    with json_path.open("w", encoding="utf8") as f:
        json.dump(report, f, indent=2)

    leaderboard = report.get("leaderboard") or []
    header = [
        "algorithm",
        "games",
        "wins",
        "win_rate",
        "shots",
        "hits",
        "accuracy",
        "ships_sunk",
        "avg_survival_turns",
        "survival_rate",
        "elo",
        "strength_index",
    ]
    with csv_path.open("w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for row in leaderboard:
            writer.writerow({k: row.get(k, "") for k in header})

    return str(json_path), str(csv_path)


def run_parallel_benchmark(
    num_games: int,
    num_players: int,
    attack_all: bool,
    seed: int | None = None,
    workers: int = 1,
    keep_per_game: bool = False,
    output_prefix: str = "benchmark",
    results_dir: str = "results",
) -> dict[str, Any]:
    if num_games < 1:
        raise ValueError("num_games must be >= 1")
    if num_players < 2:
        raise ValueError("num_players must be >= 2")

    max_workers = max(1, min(int(workers), int(num_games)))
    cfg = BenchmarkConfig(
        games=int(num_games),
        players=int(num_players),
        attack_all=bool(attack_all),
        workers=max_workers,
        seed=seed,
        keep_per_game=bool(keep_per_game),
    )

    task_cfg = {
        "games": cfg.games,
        "players": cfg.players,
        "attack_all": cfg.attack_all,
        "seed": cfg.seed,
        "keep_per_game": cfg.keep_per_game,
    }

    started = time.time()
    raw_results: list[dict[str, Any]] = []

    if max_workers == 1:
        for game_index in range(cfg.games):
            raw_results.append(_run_single_game((game_index, task_cfg)))
    else:
        completed = 0
        progress_stride = max(1, cfg.games // 10)
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_run_single_game, (game_index, task_cfg)) for game_index in range(cfg.games)]
            for future in as_completed(futures):
                raw_results.append(future.result())
                completed += 1
                if completed % progress_stride == 0 or completed == cfg.games:
                    print(f"Benchmark progress: {completed}/{cfg.games} games complete")

    raw_results.sort(key=lambda row: int(row.get("game_index", 0)))
    report = _aggregate(raw_results, cfg)

    elapsed = time.time() - started
    report["wall_time_s"] = round(elapsed, 3)
    report["games_per_second"] = round(cfg.games / max(elapsed, 1e-9), 3)

    json_path, csv_path = _write_outputs(report, output_prefix=output_prefix, results_dir=results_dir)
    report["json_path"] = json_path
    report["csv_path"] = csv_path
    return report
