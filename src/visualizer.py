import json
import os
import glob
import pygame
from typing import List, Dict

def generate_heatmap(results_dir: str = "results") -> List[List[int]]:
    """
    Scans all JSON result files to create a global heatmap of shots.
    """
    heatmap = [[0 for _ in range(10)] for _ in range(10)]
    files = glob.glob(os.path.join(results_dir, "*.json"))
    
    for file_path in files:
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                shots = data.get("shots", [])
                for shot in shots:
                    x, y = shot.get("x"), shot.get("y")
                    if 0 <= x < 10 and 0 <= y < 10:
                        heatmap[y][x] += 1
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
    return heatmap

def print_text_heatmap(heatmap: List[List[int]]):
    """Prints a text-based heatmap representation."""
    if not heatmap: return
    max_val = max(max(row) for row in heatmap) or 1
    
    print("\nGlobal Shot Heatmap (Shots per Cell):")
    print("   " + " ".join(f"{i:2}" for i in range(10)))
    for y, row in enumerate(heatmap):
        line = f"{y:2} "
        for x in row:
            # Scale representation
            intensity = int((x / max_val) * 10)
            char = str(intensity) if intensity > 0 else "."
            line += f" {char} "
        print(line)

def draw_interactive_heatmap(surf, x, y, size, results_dir="results"):
    """
    Draws a heatmap directly on a Pygame surface.
    """
    heatmap = generate_heatmap(results_dir)
    max_val = 0
    for row in heatmap:
        for val in row:
            if val > max_val: max_val = val
    
    cs = size // 10
    font = pygame.font.SysFont("Arial", 12)
    
    # Background
    pygame.draw.rect(surf, (255, 255, 255), (x, y, size, size))
    
    for row_idx, row in enumerate(heatmap):
        for col_idx, val in enumerate(row):
            intensity = (val / max_val) * 255 if max_val > 0 else 0
            # Color gradient: Blue (low) to Red (high)
            color = (int(intensity), 100, 255 - int(intensity))
            rect = pygame.Rect(x + col_idx * cs, y + row_idx * cs, cs, cs)
            pygame.draw.rect(surf, color, rect)
            pygame.draw.rect(surf, (200, 200, 200), rect, 1) # Grid lines
            
            if val > 0:
                txt = font.render(str(val), True, (255, 255, 255) if intensity > 150 else (0, 0, 0))
                surf.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))

if __name__ == "__main__":
    results_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results"))
    h = generate_heatmap(results_path)
    print_text_heatmap(h)
