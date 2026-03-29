import csv
import json
import tempfile
import unittest

from analytics import GameAnalytics


class TestAnalytics(unittest.TestCase):
    def test_seed_persisted_to_json_and_summary_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            analytics = GameAnalytics(mode="MultiAI", num_players=2, attack_all=True, seed=123)
            analytics.next_turn()
            analytics.record_shot(0, 1, 2, 3, True, False)
            analytics.finalize("AI 1")

            json_path, csv_path = analytics.save(folder=temp_dir)

            with open(json_path, "r", encoding="utf8") as f:
                data = json.load(f)
            self.assertEqual(data.get("seed"), 123)

            with open(csv_path, "r", encoding="utf8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("seed"), "123")

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
            self.assertEqual(rows[0].get("run_id"), "old_run")
            self.assertEqual(rows[0].get("seed"), "")
            self.assertEqual(rows[1].get("seed"), "7")


if __name__ == "__main__":
    unittest.main()
