import os
import argparse
import time

def run_batch(num_games: int, num_players: int, attack_all: bool, seed: int | None = None):
    """Runs a batch of games without a GUI/Pygame window."""
    print(f"--- STARTING BATCH SIMULATION: {num_games} games, {num_players} AIs ---")
    if seed is not None:
        print(f"Deterministic seed mode enabled (base seed={seed}).")
    start_time = time.time()
    
    # Disable Pygame rendering for headless performance
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'

    # Imported lazily so environment variables are set before pygame init.
    from multi_ai import MultiAIGame
    
    for i in range(num_games):
        game_seed = (seed + i) if seed is not None else None
        game = MultiAIGame(num_ais=num_players, attack_all=attack_all, seed=game_seed, render=False)
        
        # Run until game is over
        while not game.game_over:
            game.perform_ai_turn()
            
        print(f"Game {i+1}/{num_games} complete. Winner: {game.winner}")

    duration = time.time() - start_time
    print(f"\n--- BATCH COMPLETE: {num_games} games in {duration:.2f}s ({duration/max(1,num_games):.3f}s/game) ---")
    print("Results saved to results/ folder.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless Battleship++ Batch Simulator")
    parser.add_argument("--games", type=int, default=10, help="Number of games to run")
    parser.add_argument("--players", type=int, default=10, help="Number of AIs per game")
    parser.add_argument("--attack-all", action="store_true", help="Enable 'Attack All' mode")
    parser.add_argument("--seed", type=int, default=None, help="Base random seed for deterministic runs")
    
    args = parser.parse_args()
    
    run_batch(args.games, args.players, args.attack_all, seed=args.seed)
