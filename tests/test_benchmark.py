import tempfile
import unittest
from pathlib import Path

from benchmark import run_parallel_benchmark


class TestBenchmark(unittest.TestCase):
    def test_benchmark_outputs_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = run_parallel_benchmark(
                num_games=4,
                num_players=4,
                attack_all=False,
                seed=321,
                workers=1,
                keep_per_game=False,
                output_prefix="unit_benchmark",
                results_dir=temp_dir,
            )
            second = run_parallel_benchmark(
                num_games=4,
                num_players=4,
                attack_all=False,
                seed=321,
                workers=1,
                keep_per_game=False,
                output_prefix="unit_benchmark",
                results_dir=temp_dir,
            )

            self.assertTrue(Path(first["json_path"]).exists())
            self.assertTrue(Path(first["csv_path"]).exists())
            self.assertGreater(len(first.get("leaderboard", [])), 0)

            winners_first = [row.get("winner") for row in first.get("games", [])]
            winners_second = [row.get("winner") for row in second.get("games", [])]
            self.assertEqual(winners_first, winners_second)

            top = first["leaderboard"][0]
            self.assertIn("strength_index", top)
            self.assertIn("elo", top)


if __name__ == "__main__":
    unittest.main()
