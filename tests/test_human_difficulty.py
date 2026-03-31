import tempfile
import unittest

from engine import Board
from human_difficulty import (
    DifficultyGenome,
    DifficultyLab,
    KnowledgeGraph,
    KnowledgeGraphAI,
    build_difficulty_profiles,
    create_human_opponent_ai,
    save_profiles,
)


class TestHumanDifficulty(unittest.TestCase):
    def test_knowledge_graph_update(self):
        graph = KnowledgeGraph()
        self.assertEqual(graph.score("search", "edge"), 0.0)
        graph.update("search", "edge", reward=1.0, lr=1.0)
        self.assertEqual(graph.score("search", "edge"), 1.0)

    def test_knowledge_graph_ai_unique_shots(self):
        board = Board(5, 5)
        ai = KnowledgeGraphAI(board, genome=DifficultyGenome(name="test"))
        seen = set()
        for _ in range(15):
            shot = ai.get_shot_coordinates()
            self.assertNotIn(shot, seen)
            self.assertTrue(0 <= shot[0] < board.width)
            self.assertTrue(0 <= shot[1] < board.height)
            seen.add(shot)

    def test_difficulty_lab_evolve_small(self):
        lab = DifficultyLab(seed=7)
        result = lab.evolve(generations=2, population=4, games_per_eval=1, elite_size=2)
        self.assertIn("best", result)
        self.assertIn("leaderboard", result)
        self.assertGreater(len(result.get("leaderboard", [])), 0)
        self.assertIn("profiles", result)
        self.assertIn("humanhard", result["profiles"])

    def test_profile_save_and_factory_load(self):
        profiles = build_difficulty_profiles(DifficultyGenome(name="base"))
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = f"{temp_dir}/profiles.json"
            save_profiles(profile_path, profiles)
            board = Board(10, 10)
            ai = create_human_opponent_ai("human-hard", board, profile_file=profile_path)
            self.assertIsNotNone(ai)


if __name__ == "__main__":
    unittest.main()
