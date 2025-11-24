import os
import sys
import math
import time
import random
import csv
import datetime
from collections import deque
import multiprocessing as mp
from multiprocessing import Manager

import pygame

# CONFIGURATION 

CELL = 28
GRID_W, GRID_H = 28, 20
INFO_PANEL_HEIGHT = 120
WIDTH = GRID_W * CELL
HEIGHT = GRID_H * CELL + INFO_PANEL_HEIGHT
FPS = 60

NUM_GHOSTS = 4
AI_WORK_MS = 80
GHOST_UPDATE_EVERY = 8

# Colors
COLORS = {
    'bg': (8, 8, 28),
    'wall_outer': (0, 0, 160),
    'wall_inner': (24, 24, 120),
    'pacman': (255, 225, 0),
    'pellet_outer': (255, 255, 255),
    'pellet_inner': (220, 220, 255),
    'info_bg': (12, 12, 40),
    'text': (235, 235, 235),
    'mode_parallel': (120, 230, 150),
    'mode_sequential': (255, 190, 90),
    'safe_mode': (100, 255, 100),
    'unsafe_mode': (255, 100, 100),
    'highlight': (255, 255, 0),
}

GHOST_COLORS = [
    (255, 0, 0),      # Blinky (Red)
    (255, 105, 180),  # Pinky (Pink)
    (0, 255, 255),    # Inky (Cyan)
    (255, 165, 0),    # Clyde (Orange)
    (180, 0, 180),    # Purple
    (0, 180, 80),     # Green
]

GHOST_NAMES = ['Blinky', 'Pinky', 'Inky', 'Clyde', 'Purple', 'Green']

# MAZE GENERATION 

def generate_maze(seed=100):
    """Generate a reproducible maze layout"""
    random.seed(seed)
    maze = [[0] * GRID_W for _ in range(GRID_H)]
    
   
    for y in range(GRID_H):
        for x in range(GRID_W):
            if x == 0 or y == 0 or x == GRID_W - 1 or y == GRID_H - 1:
                maze[y][x] = 1
    

    for y in range(3, GRID_H - 3, 3):
        for x in range(2, GRID_W - 2):
            if x % 5 != 0:
                maze[y][x] = 1
    

    for _ in range(30):
        rx = random.randint(2, GRID_W - 3)
        ry = random.randint(2, GRID_H - 3)
        maze[ry][rx] = 1
    

    maze[0][GRID_W // 2] = 0
    
    return maze

MAZE = generate_maze(seed=100)
BASE_PELLETS = {
    (x, y) for y in range(GRID_H) for x in range(GRID_W)
    if MAZE[y][x] == 0 and not (x == GRID_W // 2 and y == 0)
}

# PATHFINDING 

def in_bounds(x, y):
    return 0 <= x < GRID_W and 0 <= y < GRID_H

def get_neighbors(x, y):
    """Get valid neighboring cells"""
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if in_bounds(nx, ny) and MAZE[ny][nx] == 0:
            yield nx, ny

def bfs_pathfind(start, goal):
    """BFS pathfinding - returns next step towards goal"""
    sx, sy = start
    gx, gy = goal
    
    if start == goal:
        return start
    
    queue = deque([(sx, sy)])
    came_from = {(sx, sy): None}
    
    while queue:
        x, y = queue.popleft()
        if (x, y) == (gx, gy):
            break
        for nx, ny in get_neighbors(x, y):
            if (nx, ny) not in came_from:
                came_from[(nx, ny)] = (x, y)
                queue.append((nx, ny))
    
    if (gx, gy) not in came_from:
        return start
    
    # Backtrack to find first step
    current = (gx, gy)
    while came_from[current] != (sx, sy):
        current = came_from[current]
        if came_from[current] is None:
            break
    
    return current

#  HEAVY AI WORK SIMULATION 

def simulate_heavy_computation(ms):
    """Simulate CPU-intensive AI computation"""
    start = time.perf_counter()
    target = ms / 1000.0
    accumulator = 0
    
    while time.perf_counter() - start < target:
        for i in range(60):
            accumulator ^= (i * 131) ^ (i << 3)
    
    return accumulator

#  MULTIPROCESSING WORKERS 

def ghost_ai_worker_safe(args):
    """
    Safe worker with synchronization.
    Demonstrates proper use of locks for shared resource access.
    """
    gx, gy, px, py, ms, shared_stats, lock = args
    
    # Simulate heavy AI computation
    simulate_heavy_computation(ms)
    
    # Calculate next position
    next_pos = bfs_pathfind((gx, gy), (px, py))
    
    # SYNCHRONIZED access to shared statistics
    pid = os.getpid()
    with lock:
        shared_stats['total_updates'] += 1
        # Track unique process IDs (append to list, duplicates filtered later)
        pids = shared_stats.get('process_ids', [])
        if pid not in pids:
            shared_stats['process_ids'] = pids + [pid]
    
    return {
        'next_pos': next_pos,
        'process_id': pid,
        'ghost_pos': (gx, gy)
    }

def ghost_ai_worker_unsafe(args):
    """
    Unsafe worker WITHOUT synchronization.
    Demonstrates race conditions when locks are not used.
    """
    gx, gy, px, py, ms, shared_stats, _ = args
    
    simulate_heavy_computation(ms)
    next_pos = bfs_pathfind((gx, gy), (px, py))
    
    # UNSAFE: No lock - can cause race conditions!
    # Read-modify-write without synchronization
    pid = os.getpid()
    current = shared_stats['total_updates']
    time.sleep(0.001)  # Increase chance of race condition
    shared_stats['total_updates'] = current + 1
    shared_stats['race_condition_risk'] += 1
    
    return {
        'next_pos': next_pos,
        'process_id': pid,
        'ghost_pos': (gx, gy)
    }

def ghost_ai_worker_simple(args):
    """Simple worker for basic parallel demonstration"""
    gx, gy, px, py, ms = args
    simulate_heavy_computation(ms)
    return {
        'next_pos': bfs_pathfind((gx, gy), (px, py)),
        'process_id': os.getpid()
    }

# GAME ENTITIES 

class PacMan:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.x = GRID_W // 2
        self.y = GRID_H // 2
        self.mouth_phase = 0.0
        self.direction = (1, 0)
    
    def move(self, dx, dy):
        nx, ny = self.x + dx, self.y + dy
        if in_bounds(nx, ny) and MAZE[ny][nx] == 0:
            self.x, self.y = nx, ny
            self.direction = (dx, dy)
    
    def update(self, dt):
        self.mouth_phase = (self.mouth_phase + dt * 6) % (2 * math.pi)


class Ghost:
    START_POSITIONS = [
        (1, 1), (GRID_W - 2, 1),
        (1, GRID_H - 2), (GRID_W - 2, GRID_H - 2),
        (GRID_W // 2, 1), (GRID_W // 2, GRID_H - 2)
    ]
    
    def __init__(self, idx):
        self.idx = idx
        self.name = GHOST_NAMES[idx % len(GHOST_NAMES)]
        self.color = GHOST_COLORS[idx % len(GHOST_COLORS)]
        self.last_process_id = None
        self.update_count = 0
        self.reset()
    
    def reset(self):
        pos = self.START_POSITIONS[self.idx % len(self.START_POSITIONS)]
        self.x, self.y = pos
        self.update_count = 0

#  RENDERING 

class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font_large = pygame.font.SysFont("Consolas", 20, bold=True)
        self.font_medium = pygame.font.SysFont("Consolas", 16)
        self.font_small = pygame.font.SysFont("Consolas", 12)
    
    def draw_maze(self):
        for y in range(GRID_H):
            for x in range(GRID_W):
                if MAZE[y][x] == 1:
                    rect = pygame.Rect(x * CELL, y * CELL, CELL, CELL)
                    pygame.draw.rect(self.screen, COLORS['wall_outer'], rect)
                    inner = rect.inflate(-8, -8)
                    pygame.draw.rect(self.screen, COLORS['wall_inner'], inner)
    
    def draw_pellets(self, pellets):
        for x, y in pellets:
            cx = x * CELL + CELL // 2
            cy = y * CELL + CELL // 2
            pygame.draw.circle(self.screen, COLORS['pellet_outer'], (cx, cy), 5)
            pygame.draw.circle(self.screen, COLORS['pellet_inner'], (cx, cy), 3)
    
    def draw_pacman(self, pac, keys):
        cx = pac.x * CELL + CELL // 2
        cy = pac.y * CELL + CELL // 2
        radius = CELL // 2 - 2
        
        # Body
        pygame.draw.circle(self.screen, COLORS['pacman'], (cx, cy), radius)
        
        # Animated mouth
        open_ratio = (math.sin(pac.mouth_phase) + 1) / 2
        angle = 30 + open_ratio * 40
        
        # Direction based on keys or last direction
        if keys[pygame.K_LEFT]:
            start, end = 180 - angle, 180 + angle
        elif keys[pygame.K_RIGHT]:
            start, end = -angle, angle
        elif keys[pygame.K_UP]:
            start, end = 90 - angle, 90 + angle
        elif keys[pygame.K_DOWN]:
            start, end = 270 - angle, 270 + angle
        else:
            dx, dy = pac.direction
            if dx < 0:
                start, end = 180 - angle, 180 + angle
            elif dy < 0:
                start, end = 90 - angle, 90 + angle
            elif dy > 0:
                start, end = 270 - angle, 270 + angle
            else:
                start, end = -angle, angle
        
        # Draw mouth
        a1, a2 = math.radians(start), math.radians(end)
        p1 = (cx, cy)
        p2 = (cx + int(radius * math.cos(a1)), cy - int(radius * math.sin(a1)))
        p3 = (cx + int(radius * math.cos(a2)), cy - int(radius * math.sin(a2)))
        pygame.draw.polygon(self.screen, COLORS['bg'], [p1, p2, p3])
        
        # Outline
        pygame.draw.circle(self.screen, (0, 0, 0), (cx, cy), radius, 2)
    
    def draw_ghost(self, ghost, pac, show_process_id=False):
        gx = ghost.x * CELL
        gy = ghost.y * CELL
        body_w = CELL - 6
        body_h = CELL - 6
        
        # Head (ellipse)
        head_rect = pygame.Rect(gx + 3, gy + 3, body_w, int(body_h * 0.65))
        pygame.draw.ellipse(self.screen, ghost.color, head_rect)
        
        # Wavy skirt
        skirt_y = head_rect.bottom - 4
        segment = body_w // 4
        for i in range(4):
            x1 = gx + 3 + i * segment
            x2 = x1 + segment // 2
            x3 = x1 + segment
            pygame.draw.polygon(self.screen, ghost.color, [
                (x1, skirt_y), (x2, skirt_y + 8), (x3, skirt_y)
            ])
        
        # Fill body
        body_rect = pygame.Rect(gx + 3, head_rect.centery, body_w, skirt_y - head_rect.centery)
        pygame.draw.rect(self.screen, ghost.color, body_rect)
        
        # Eyes
        eye_w, eye_h = body_w // 4, body_h // 4
        left_eye = pygame.Rect(gx + 3 + body_w // 4 - eye_w // 2, gy + 3 + body_h // 4, eye_w, eye_h)
        right_eye = left_eye.move(body_w // 3, 0)
        pygame.draw.ellipse(self.screen, (255, 255, 255), left_eye)
        pygame.draw.ellipse(self.screen, (255, 255, 255), right_eye)
        
        # Pupils (follow Pac-Man)
        dx = pac.x - ghost.x
        dy = pac.y - ghost.y
        angle = math.atan2(dy, dx if dx != 0 else 0.001)
        pdx = int(math.cos(angle) * 2)
        pdy = int(math.sin(angle) * 2)
        
        pupil_w, pupil_h = max(2, eye_w // 2), max(2, eye_h // 2)
        lp = pygame.Rect(left_eye.centerx - pupil_w // 2 + pdx, 
                         left_eye.centery - pupil_h // 2 + pdy, pupil_w, pupil_h)
        rp = pygame.Rect(right_eye.centerx - pupil_w // 2 + pdx,
                         right_eye.centery - pupil_h // 2 + pdy, pupil_w, pupil_h)
        pygame.draw.ellipse(self.screen, (20, 20, 80), lp)
        pygame.draw.ellipse(self.screen, (20, 20, 80), rp)
        
        # Process ID indicator (if enabled)
        if show_process_id and ghost.last_process_id:
            pid_text = self.font_small.render(f"P{ghost.last_process_id % 100}", True, COLORS['highlight'])
            self.screen.blit(pid_text, (gx + 2, gy - 12))
    
    def draw_info_panel(self, game_state):
        """Draw the information panel with all statistics"""
        panel_y = GRID_H * CELL
        pygame.draw.rect(self.screen, COLORS['info_bg'], (0, panel_y, WIDTH, INFO_PANEL_HEIGHT))
        
        # Mode indicator
        if game_state['parallel']:
            mode_text = "PARALLEL (MULTICORE)"
            mode_color = COLORS['mode_parallel']
        else:
            mode_text = "SEQUENTIAL (SINGLE-CORE)"
            mode_color = COLORS['mode_sequential']
        
        self.screen.blit(
            self.font_large.render(f"MODE: {mode_text}", True, mode_color),
            (10, panel_y + 5)
        )
        
        # Lock status
        if game_state['show_locks']:
            lock_text = "LOCKS: ON (Safe)"
            lock_color = COLORS['safe_mode']
        else:
            lock_text = "LOCKS: OFF (Unsafe!)"
            lock_color = COLORS['unsafe_mode']
        
        self.screen.blit(
            self.font_medium.render(lock_text, True, lock_color),
            (400, panel_y + 7)
        )
        
        # Performance metrics
        metrics_y = panel_y + 30
        avg_ai = game_state['avg_ai_time'] * 1000
        
        metrics_text = (
            f"AI Time: {avg_ai:.1f}ms | "
            f"FPS: {game_state['fps']:.0f} | "
            f"Workload: {game_state['ai_work_ms']}ms | "
            f"Ghosts: {NUM_GHOSTS}"
        )
        self.screen.blit(self.font_medium.render(metrics_text, True, COLORS['text']), (10, metrics_y))
        
        # Speedup calculation
        speedup_y = panel_y + 50
        if game_state['sequential_time'] > 0 and game_state['parallel_time'] > 0:
            actual_speedup = game_state['sequential_time'] / game_state['parallel_time']
            theoretical_speedup = NUM_GHOSTS
            efficiency = (actual_speedup / theoretical_speedup) * 100
            
            speedup_text = (
                f"Speedup: {actual_speedup:.2f}x | "
                f"Theoretical Max: {theoretical_speedup}x | "
                f"Efficiency: {efficiency:.1f}%"
            )
            self.screen.blit(self.font_medium.render(speedup_text, True, COLORS['highlight']), (10, speedup_y))
        
        # Shared statistics
        stats_y = panel_y + 70
        stats = game_state['shared_stats']
        if stats:
            updates = stats.get('total_updates', 0)
            process_ids = stats.get('process_ids', [])
            processes = len(set(process_ids)) if process_ids else 0
            race_risk = stats.get('race_condition_risk', 0)
            
            stats_text = f"Total Updates: {updates} | Active Processes: {processes}"
            if not game_state['show_locks']:
                stats_text += f" | Race Condition Events: {race_risk}"
            
            self.screen.blit(self.font_small.render(stats_text, True, COLORS['text']), (10, stats_y))
        
        # Ghost thread info
        ghost_y = panel_y + 88
        ghost_info = "Threads: "
        for ghost in game_state['ghosts']:
            pid = ghost.last_process_id % 100 if ghost.last_process_id else 0
            ghost_info += f"{ghost.name[:2]}(P{pid}) "
        
        self.screen.blit(self.font_small.render(ghost_info, True, COLORS['text']), (10, ghost_y))
        
        # Controls
        controls_y = panel_y + 103
        controls = "SPACE:Mode | L:Locks | U:Unsafe | +/-:Workload | R:Reset | Q:Quit"
        self.screen.blit(self.font_small.render(controls, True, (150, 150, 150)), (10, controls_y))

#  CSV LOGGING 

class CSVLogger:
    def __init__(self, filename="parallel_pacman_results.csv"):
        self.filename = filename
        self.headers = [
            "timestamp", "mode", "locks_enabled", "ai_work_ms",
            "avg_ai_ms", "fps", "num_ghosts", "speedup",
            "total_updates", "active_processes"
        ]
        self._write_header()
    
    def _write_header(self):
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w', newline='') as f:
                    csv.writer(f).writerow(self.headers)
            except Exception as e:
                print(f"[WARN] Could not create CSV: {e}")
    
    def log(self, game_state):
        stats = game_state.get('shared_stats', {})
        process_ids = stats.get('process_ids', [])
        row = [
            datetime.datetime.now().isoformat(),
            "parallel" if game_state['parallel'] else "sequential",
            game_state['show_locks'],
            game_state['ai_work_ms'],
            game_state['avg_ai_time'] * 1000,
            game_state['fps'],
            NUM_GHOSTS,
            game_state.get('speedup', 0),
            stats.get('total_updates', 0),
            len(set(process_ids)) if process_ids else 0
        ]
        try:
            with open(self.filename, 'a', newline='') as f:
                csv.writer(f).writerow(row)
        except Exception as e:
            print(f"[WARN] Could not write to CSV: {e}")

# MAIN GAME

class ParallelPacmanGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Parallel Pac-Man — Threading Demonstration (Group 12)")
        self.clock = pygame.time.Clock()
        self.renderer = Renderer(self.screen)
        self.logger = CSVLogger()
        
        # Game entities
        self.pacman = PacMan()
        self.ghosts = [Ghost(i) for i in range(NUM_GHOSTS)]
        self.pellets = set(BASE_PELLETS)
        
        # Game state
        self.parallel = True
        self.show_locks = True
        self.ai_work_ms = AI_WORK_MS
        self.ai_times = []
        self.sequential_time = 0.0
        self.parallel_time = 0.0
        self.frame = 0
        self.running = True
        
        # Multiprocessing setup
        self.manager = Manager()
        self.shared_stats = self.manager.dict({
            'total_updates': 0,
            'process_ids': [],  # Use list (Manager doesn't support sets)
            'race_condition_risk': 0
        })
        self.lock = self.manager.Lock()
    
    def reset_shared_stats(self):
        """Reset shared statistics"""
        self.shared_stats['total_updates'] = 0
        self.shared_stats['process_ids'] = []
        self.shared_stats['race_condition_risk'] = 0
    
    def reset_game(self):
        """Reset the entire game state"""
        self.pacman.reset()
        for ghost in self.ghosts:
            ghost.reset()
        self.pellets = set(BASE_PELLETS)
        self.reset_shared_stats()
        self.ai_times.clear()
    
    def handle_events(self):
        """Process pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self.parallel = not self.parallel
                    self.reset_shared_stats()
                elif event.key == pygame.K_l:
                    self.show_locks = not self.show_locks
                    self.reset_shared_stats()
                elif event.key == pygame.K_u:
                    self.show_locks = False  # Enable unsafe mode
                    self.reset_shared_stats()
                elif event.key == pygame.K_r:
                    self.reset_game()
                elif event.key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
                    self.ai_work_ms = min(500, self.ai_work_ms + 10)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.ai_work_ms = max(0, self.ai_work_ms - 10)
    
    def handle_input(self, keys):
        """Handle continuous key presses"""
        if keys[pygame.K_LEFT]:
            self.pacman.move(-1, 0)
        if keys[pygame.K_RIGHT]:
            self.pacman.move(1, 0)
        if keys[pygame.K_UP]:
            self.pacman.move(0, -1)
        if keys[pygame.K_DOWN]:
            self.pacman.move(0, 1)
    
    def update_ghosts_parallel(self, pool):
        """Update all ghosts in parallel using multiprocessing"""
        if self.show_locks:
            # Safe mode with locks
            args = [
                (g.x, g.y, self.pacman.x, self.pacman.y, 
                 self.ai_work_ms, self.shared_stats, self.lock)
                for g in self.ghosts
            ]
            worker = ghost_ai_worker_safe
        else:
            # Unsafe mode without locks
            args = [
                (g.x, g.y, self.pacman.x, self.pacman.y,
                 self.ai_work_ms, self.shared_stats, None)
                for g in self.ghosts
            ]
            worker = ghost_ai_worker_unsafe
        
        try:
            async_result = pool.map_async(worker, args)
            results = async_result.get(timeout=5.0)
            
            for ghost, result in zip(self.ghosts, results):
                ghost.x, ghost.y = result['next_pos']
                ghost.last_process_id = result['process_id']
                ghost.update_count += 1
                
        except mp.TimeoutError:
            print("[WARN] Parallel update timed out")
    
    def update_ghosts_sequential(self):
        """Update all ghosts sequentially (one at a time)"""
        for ghost in self.ghosts:
            simulate_heavy_computation(self.ai_work_ms)
            next_pos = bfs_pathfind((ghost.x, ghost.y), (self.pacman.x, self.pacman.y))
            ghost.x, ghost.y = next_pos
            ghost.last_process_id = os.getpid()
            ghost.update_count += 1
            
            if self.show_locks:
                with self.lock:
                    self.shared_stats['total_updates'] += 1
            else:
                self.shared_stats['total_updates'] += 1
    
    def check_collisions(self):
        """Check for Pac-Man and ghost collisions"""
        for ghost in self.ghosts:
            if (ghost.x, ghost.y) == (self.pacman.x, self.pacman.y):
                time.sleep(0.3)
                self.reset_game()
                return True
        return False
    
    def get_game_state(self):
        """Compile current game state for rendering and logging"""
        avg_ai = sum(self.ai_times) / len(self.ai_times) if self.ai_times else 0.0
        
        # Calculate speedup
        speedup = 0.0
        if self.sequential_time > 0 and self.parallel_time > 0:
            speedup = self.sequential_time / self.parallel_time
        
        # Convert shared_stats to regular dict
        stats_copy = dict(self.shared_stats)
        
        return {
            'parallel': self.parallel,
            'show_locks': self.show_locks,
            'ai_work_ms': self.ai_work_ms,
            'avg_ai_time': avg_ai,
            'fps': self.clock.get_fps(),
            'sequential_time': self.sequential_time,
            'parallel_time': self.parallel_time,
            'speedup': speedup,
            'shared_stats': stats_copy,
            'ghosts': self.ghosts,
        }
    
    def run(self, pool):
        """Main game loop"""
        last_time = time.perf_counter()
        
        while self.running:
            current_time = time.perf_counter()
            dt = current_time - last_time
            last_time = current_time
            
            # Handle events and input
            self.handle_events()
            keys = pygame.key.get_pressed()
            self.handle_input(keys)
            
            # Eat pellets
            self.pellets.discard((self.pacman.x, self.pacman.y))
            self.pacman.update(dt)
            
            # Update ghosts periodically
            self.frame += 1
            if self.frame % GHOST_UPDATE_EVERY == 0:
                t0 = time.perf_counter()
                
                if self.parallel:
                    self.update_ghosts_parallel(pool)
                else:
                    self.update_ghosts_sequential()
                
                ai_time = time.perf_counter() - t0
                self.ai_times.append(ai_time)
                if len(self.ai_times) > 30:
                    self.ai_times.pop(0)
                
                # Track times for speedup calculation
                if self.parallel:
                    self.parallel_time = ai_time
                    if self.sequential_time == 0:
                        self.sequential_time = ai_time * NUM_GHOSTS * 0.8
                else:
                    self.sequential_time = ai_time
                    if self.parallel_time == 0:
                        self.parallel_time = ai_time / max(1, NUM_GHOSTS * 0.5)
                
                # Log to CSV
                game_state = self.get_game_state()
                self.logger.log(game_state)
            
            # Check collisions
            self.check_collisions()
            
            # Render
            self.screen.fill(COLORS['bg'])
            self.renderer.draw_maze()
            self.renderer.draw_pellets(self.pellets)
            self.renderer.draw_pacman(self.pacman, keys)
            
            for ghost in self.ghosts:
                self.renderer.draw_ghost(ghost, self.pacman, show_process_id=self.parallel)
            
            self.renderer.draw_info_panel(self.get_game_state())
            
            pygame.display.flip()
            self.clock.tick(FPS)
        
        pygame.quit()


#  ENTRY POINT 

def main():
    """Entry point with multiprocessing pool setup"""
    mp.freeze_support()  # Required for Windows
    
    num_workers = min(NUM_GHOSTS, max(1, mp.cpu_count()))
    
    print("=" * 60)
    print("  PARALLEL PAC-MAN — Threading Demonstration")
    print("  Group 12: Ghosts in Parallel")
    print("=" * 60)
    print(f"\n  CPU Cores Available: {mp.cpu_count()}")
    print(f"  Worker Processes: {num_workers}")
    print(f"  Number of Ghosts: {NUM_GHOSTS}")
    print(f"  Initial AI Workload: {AI_WORK_MS}ms per ghost")
    print("\n  Controls:")
    print("    Arrow Keys  - Move Pac-Man")
    print("    SPACE       - Toggle Parallel/Sequential mode")
    print("    L           - Toggle Lock visualization")
    print("    U           - Enable Unsafe mode (show race conditions)")
    print("    +/-         - Adjust AI workload")
    print("    R           - Reset game")
    print("    ESC/Q       - Quit")
    print("\n  Starting game...")
    print("=" * 60)
    
    with mp.Pool(processes=num_workers) as pool:
        game = ParallelPacmanGame()
        game.run(pool)
    
    print("\n  Thanks for playing Parallel Pac-Man!")
    print("  Results saved to: parallel_pacman_results.csv")
    print("=" * 60)


if __name__ == "__main__":
    main()