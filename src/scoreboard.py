import os
import json
import csv
import glob
from typing import List, Dict, Any
from collections import defaultdict

class Scoreboard:
    """
    Analyzes historical experiment data to provide a cross-experiment scoreboard.
    """
    def __init__(self, results_dir: str = "results"):
        self.results_dir = results_dir
        self.summary_file = os.path.join(results_dir, "summary.csv")

    def get_aggregate_stats(self) -> List[Dict[str, Any]]:
        """
        Aggregates win counts and performance metrics across all experiments.
        Groups performance by AI logic type if available.
        """
        files = glob.glob(os.path.join(self.results_dir, "*.json"))
        ai_stats = defaultdict(lambda: {
            "wins": 0, 
            "total_games": 0, 
            "total_shots": 0, 
            "total_hits": 0,
            "accuracy": 0.0,
            "total_survival_turns": 0,
            "victories": [] # List of victory details
        })

        for file_path in files:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    winner_name = data.get("winner")
                    winner_idx = None
                    player_ai_types = data.get("player_ai_types", {})
                    players = data.get("players", {})

                    if winner_name == "Player":
                        winner_type = "HumanPlayer"
                    elif winner_name and winner_name.startswith("AI "):
                        try: 
                            idx_str = winner_name.split(" ")[1]
                            winner_idx = str(int(idx_str) - 1)
                            winner_type = player_ai_types.get(winner_idx, winner_name)
                        except: 
                            winner_type = winner_name
                    else:
                        winner_type = winner_name

                    if winner_type:
                        ai_stats[winner_type]["wins"] += 1
                        ai_stats[winner_type]["victories"].append({
                            "mode": data.get("mode"),
                            "run_id": data.get("run_id"),
                            "turns": data.get("turns")
                        })
                    
                    for p_id, stats in players.items():
                        ai_type = player_ai_types.get(str(p_id), f"AI {int(p_id)+1}")
                        ai_stats[ai_type]["total_games"] += 1
                        ai_stats[ai_type]["total_shots"] += stats.get("shots", 0)
                        ai_stats[ai_type]["total_hits"] += stats.get("hits", 0)
                        ai_stats[ai_type]["total_survival_turns"] += stats.get("turns_alive", data.get("turns", 0))
                        
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

        leaderboard = []
        for ai_type, stats in ai_stats.items():
            if stats["total_shots"] > 0:
                stats["accuracy"] = (stats["total_hits"] / stats["total_shots"]) * 100
            stats["win_rate"] = (stats["wins"] / stats["total_games"]) * 100 if stats["total_games"] > 0 else 0
            stats["avg_survival"] = stats["total_survival_turns"] / stats["total_games"] if stats["total_games"] > 0 else 0
            leaderboard.append({"type": ai_type, **stats})

        # Sort by wins, then accuracy
        leaderboard.sort(key=lambda x: (x["wins"], x["accuracy"]), reverse=True)
        return leaderboard

    def get_recent_runs(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns the most recent experiment summaries."""
        runs = []
        if not os.path.exists(self.summary_file):
            return runs
            
        with open(self.summary_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                runs.append(row)
        
        return runs[-limit:][::-1] # Last N runs, reversed

if __name__ == "__main__":
    sb = Scoreboard()
    print("--- GLOBAL AI STRATEGY LEADERBOARD ---")
    stats = sb.get_aggregate_stats()
    for i, entry in enumerate(stats[:10]):
        print(f"{i+1}. {entry['type']}: {entry['wins']} Wins | {entry['accuracy']:.2f}% Accuracy | {entry['total_games']} Games Playable")
    
    print("\n--- RECENT RUNS ---")
    recent = sb.get_recent_runs(5)
    for run in recent:
        print(f"[{run['run_id']}] {run['mode']} - Winner: {run['winner']} ({run['turns']} turns)")
