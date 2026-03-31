import unittest

from multi_ai import MultiAIGame
from config import GRID_SIZE


class TestMultiAIHeadless(unittest.TestCase):
    def _run_game(self, seed: int):
        game = MultiAIGame(num_ais=2, attack_all=False, seed=seed, render=False)
        max_turns = 5000

        while not game.game_over and max_turns > 0:
            game.perform_ai_turn()
            max_turns -= 1

        self.assertTrue(game.game_over)
        self.assertGreater(max_turns, 0)

        if game.analytics:
            payload = game.analytics.to_dict()
            self.assertEqual(len(payload.get("run_metadata", {}).get("ai_roster", [])), 2)
            self.assertEqual(len(payload.get("run_metadata", {}).get("placement_roster", [])), 2)
            self.assertEqual(payload.get("run_metadata", {}).get("grid_size"), GRID_SIZE)

        return game.winner, game.analytics.turns if game.analytics else None

    def test_seeded_headless_run_is_reproducible(self):
        first = self._run_game(42)
        second = self._run_game(42)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
