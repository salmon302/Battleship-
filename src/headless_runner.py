import os
import argparse
import time
from typing import Any

def _run_legacy_batch(
    num_games: int,
    num_players: int,
    attack_all: bool,
    seed: int | None = None,
    keep_per_game: bool = True,
) -> None:
    """Runs a batch of games without a GUI/Pygame window."""
    print(f"--- STARTING BATCH SIMULATION: {num_games} games, {num_players} AIs ---")
    if seed is not None:
        print(f"Deterministic seed mode enabled (base seed={seed}).")
    if not keep_per_game:
        print("Per-game result files disabled for faster execution.")
    start_time = time.time()
    
    # Disable Pygame rendering for headless performance
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    if not keep_per_game:
        os.environ['BATTLESHIP_DISABLE_LEARNING_PERSIST'] = '1'

    # Imported lazily so environment variables are set before pygame init.
    from multi_ai import MultiAIGame
    
    for i in range(num_games):
        game_seed = (seed + i) if seed is not None else None
        game = MultiAIGame(
            num_ais=num_players,
            attack_all=attack_all,
            seed=game_seed,
            render=False,
            run_metadata={
                "batch_index": i + 1,
                "batch_games": num_games,
            },
            auto_save_results=keep_per_game,
        )
        
        # Run until game is over
        while not game.game_over:
            game.perform_ai_turn()
            
        print(f"Game {i+1}/{num_games} complete. Winner: {game.winner}")

    duration = time.time() - start_time
    print(f"\n--- BATCH COMPLETE: {num_games} games in {duration:.2f}s ({duration/max(1,num_games):.3f}s/game) ---")
    if keep_per_game:
        print("Results saved to results/ folder.")
    else:
        print("Per-game JSON output skipped.")


def run_batch(
    num_games: int,
    num_players: int,
    attack_all: bool,
    seed: int | None = None,
    workers: int = 1,
    benchmark: bool = False,
    keep_per_game: bool = True,
    output_prefix: str = "benchmark",
) -> dict[str, Any] | None:
    """Runs either legacy sequential mode or benchmark mode with richer metrics."""
    use_benchmark = bool(benchmark) or int(workers) > 1 or not keep_per_game
    if not use_benchmark:
        _run_legacy_batch(
            num_games=num_games,
            num_players=num_players,
            attack_all=attack_all,
            seed=seed,
            keep_per_game=True,
        )
        return None

    from benchmark import run_parallel_benchmark

    print(
        f"--- STARTING BENCHMARK MODE: {num_games} games, {num_players} AIs, "
        f"workers={max(1, int(workers))} ---"
    )
    if seed is not None:
        print(f"Deterministic seed mode enabled (base seed={seed}).")
    if not keep_per_game:
        print("Per-game result files disabled for faster benchmarking.")

    report = run_parallel_benchmark(
        num_games=num_games,
        num_players=num_players,
        attack_all=attack_all,
        seed=seed,
        workers=max(1, int(workers)),
        keep_per_game=keep_per_game,
        output_prefix=output_prefix,
    )

    print(
        f"\n--- BENCHMARK COMPLETE: {num_games} games in {report['wall_time_s']:.2f}s "
        f"({report['games_per_second']:.2f} games/s) ---"
    )
    print(f"Benchmark JSON: {report['json_path']}")
    print(f"Leaderboard CSV: {report['csv_path']}")

    leaderboard = report.get("leaderboard") or []
    if leaderboard:
        top = leaderboard[0]
        print(
            "Top algorithm: "
            f"{top['algorithm']} | strength={top['strength_index']:.2f} | "
            f"win_rate={top['win_rate']:.2f}% | elo={top['elo']:.1f}"
        )
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless Battleship++ Batch Simulator")
    parser.add_argument("--games", type=int, default=10, help="Number of games to run")
    parser.add_argument("--players", type=int, default=10, help="Number of AIs per game")
    parser.add_argument("--attack-all", action="store_true", help="Enable 'Attack All' mode")
    parser.add_argument("--seed", type=int, default=None, help="Base random seed for deterministic runs")
    parser.add_argument("--workers", type=int, default=1, help="Worker processes for benchmark mode")
    parser.add_argument("--benchmark", action="store_true", help="Use robust benchmark pipeline")
    parser.add_argument(
        "--no-per-game",
        action="store_true",
        help="Disable per-game JSON output for higher throughput",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="benchmark",
        help="Filename prefix for benchmark aggregate outputs",
    )
    
    args = parser.parse_args()
    
    run_batch(
        args.games,
        args.players,
        args.attack_all,
        seed=args.seed,
        workers=args.workers,
        benchmark=args.benchmark,
        keep_per_game=not args.no_per_game,
        output_prefix=args.output_prefix,
    )
