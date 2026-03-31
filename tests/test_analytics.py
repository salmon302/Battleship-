import csv
import json
import os
import tempfile
import unittest

from analytics import GameAnalytics


class TestAnalytics(unittest.TestCase):
    def test_seed_persisted_to_json_and_summary_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            analytics = GameAnalytics(
                mode="MultiAI",
                num_players=2,
                attack_all=True,
                seed=123,
                run_metadata={
                    "ai_type": "Statistical",
                    "ai_roster": ["HuntAndTargetAI", "ParityAI"],
                    "placement_roster": ["RandomPlacementAI", "EdgePlacementAI"],
                    "grid_size": 8,
                },
            )
            analytics.next_turn()
            analytics.record_shot(0, 1, 2, 3, True, False)
            analytics.finalize("AI 1")

            json_path, csv_path = analytics.save(folder=temp_dir)

            with open(json_path, "r", encoding="utf8") as f:
                data = json.load(f)
            self.assertEqual(data.get("seed"), 123)
            self.assertEqual(data.get("run_metadata", {}).get("ai_type"), "Statistical")
            self.assertEqual(data.get("run_metadata", {}).get("ai_roster"), ["HuntAndTargetAI", "ParityAI"])
            self.assertEqual(data.get("run_metadata", {}).get("grid_size"), 8)

            with open(csv_path, "r", encoding="utf8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("seed"), "123")
            self.assertEqual(rows[0].get("ai_type"), "Statistical")
            self.assertEqual(rows[0].get("ai_roster"), "HuntAndTargetAI|ParityAI")
            self.assertEqual(rows[0].get("placement_roster"), "RandomPlacementAI|EdgePlacementAI")

    def test_summary_csv_header_migrates_to_include_seed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = f"{temp_dir}/summary.csv"

            old_header = [
                "run_id",
                "mode",
                "num_players",
                "attack_all",
                "start_time",
                "end_time",
                "duration_s",
                "turns",
                "winner",
                "total_shots",
                "total_hits",
                "accuracy_percent",
            ]
            old_row = [
                "old_run",
                "MultiAI",
                "4",
                "1",
                "2026-01-01T00:00:00",
                "2026-01-01T00:00:10",
                "10.0",
                "50",
                "AI 1",
                "100",
                "40",
                "40.0",
            ]

            with open(csv_path, "w", encoding="utf8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(old_header)
                writer.writerow(old_row)

            analytics = GameAnalytics(mode="MultiAI", num_players=2, attack_all=False, seed=7)
            analytics.finalize("AI 1")
            analytics.append_summary_csv(folder=temp_dir)

            with open(csv_path, "r", encoding="utf8", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            self.assertIn("seed", reader.fieldnames or [])
            self.assertIn("ai_type", reader.fieldnames or [])
            self.assertIn("ai_roster", reader.fieldnames or [])
            self.assertIn("placement_roster", reader.fieldnames or [])
            self.assertIn("grid_size", reader.fieldnames or [])
            self.assertIn("batch_index", reader.fieldnames or [])
            self.assertIn("batch_games", reader.fieldnames or [])
            self.assertEqual(rows[0].get("run_id"), "old_run")
            self.assertEqual(rows[0].get("seed"), "")
            self.assertEqual(rows[0].get("ai_roster"), "")
            self.assertEqual(rows[1].get("seed"), "7")

    def test_human_performance_exports_include_grid_and_rosters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            analytics = GameAnalytics(
                mode="PvE",
                num_players=2,
                attack_all=False,
                seed=9,
                run_metadata={
                    "ai_type": "Parity",
                    "ai_roster": ["ParityAI"],
                    "placement_roster": ["EdgePlacementAI"],
                    "grid_size": 10,
                },
            )

            analytics.next_turn()
            analytics.record_shot(0, 1, 2, 3, True, False, turn=1)
            analytics.next_turn()
            analytics.record_shot(1, 0, 0, 0, False, False, turn=2)
            analytics.next_turn()
            analytics.record_shot(0, 1, 4, 5, False, False, turn=3)
            analytics.finalize("Player")

            analytics.save(folder=temp_dir)

            turns_path = os.path.join(temp_dir, "human_turns_ml.csv")
            sessions_path = os.path.join(temp_dir, "human_sessions.csv")

            with open(turns_path, "r", encoding="utf8", newline="") as f:
                turn_rows = list(csv.DictReader(f))

            self.assertEqual(len(turn_rows), 2)
            self.assertEqual(turn_rows[0].get("grid_size"), "10")
            self.assertEqual(turn_rows[0].get("ai_roster"), "ParityAI")
            self.assertEqual(turn_rows[0].get("placement_roster"), "EdgePlacementAI")
            self.assertEqual(len(turn_rows[0].get("state_hits_bitmap", "")), 100)
            self.assertEqual(len(turn_rows[0].get("state_misses_bitmap", "")), 100)

            with open(sessions_path, "r", encoding="utf8", newline="") as f:
                session_rows = list(csv.DictReader(f))

            self.assertEqual(len(session_rows), 1)
            self.assertEqual(session_rows[0].get("grid_size"), "10")
            self.assertEqual(session_rows[0].get("ai_roster"), "ParityAI")
            self.assertEqual(session_rows[0].get("placement_roster"), "EdgePlacementAI")
            self.assertEqual(session_rows[0].get("total_player_shots"), "2")


if __name__ == "__main__":
    unittest.main()
