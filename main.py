import json
import os
import random
from dataclasses import dataclass

import pygame
from pygame import mixer


# ============================================================
# INITIALISIERUNG
# ============================================================
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

try:
    mixer.init()
    AUDIO_ENABLED = True
except pygame.error:
    AUDIO_ENABLED = False


# ============================================================
# KONSTANTEN
# ============================================================
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 900
FPS = 60
TITLE = "Space Invaders"
HIGHSCORE_FILE = "highscore.json"
SAVE_FILE = "save.json"
ASSET_DIR = "img"

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (220, 60, 60)
GREEN = (60, 220, 100)
GOLD = (255, 215, 0)
CYAN = (0, 255, 255)
GRAY = (180, 180, 180)
DARK_BG = (8, 10, 25)
SOFT_BLUE = (25, 35, 70)

STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_NAME_ENTRY = "name_entry"

POWERUP_NONE = 0
POWERUP_HEALTH = 1
POWERUP_SPREAD = 2
POWERUP_LASER = 3


# ============================================================
# HILFSFUNKTIONEN
# ============================================================
def asset_path(filename: str) -> str:
    return os.path.join(ASSET_DIR, filename)


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


class SilentSound:
    def play(self):
        pass

    def set_volume(self, _volume):
        pass


@dataclass
class GameAssets:
    bg: pygame.Surface
    ship: pygame.Surface
    bullet: pygame.Surface
    alien_bullet: pygame.Surface
    boss: pygame.Surface
    explosion_frames: list
    alien_frames: list
    sound_explosion: object
    sound_hit: object
    sound_laser: object


class HighscoreManager:
    def __init__(self, filename: str):
        self.filename = filename

    def load(self):
        if not os.path.exists(self.filename):
            return []
        try:
            with open(self.filename, "r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, list):
                return []
            cleaned = []
            for entry in data:
                if isinstance(entry, dict):
                    name = str(entry.get("name", "---"))[:10]
                    score = int(entry.get("score", 0))
                    cleaned.append({"name": name, "score": score})
            return sorted(cleaned, key=lambda x: x["score"], reverse=True)[:10]
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return []

    def save_score(self, name: str, score: int):
        scores = self.load()
        scores.append({"name": name[:10], "score": int(score)})
        scores = sorted(scores, key=lambda x: x["score"], reverse=True)[:10]
        with open(self.filename, "w", encoding="utf-8") as file:
            json.dump(scores, file, indent=4, ensure_ascii=False)


def load_save():
    default_upgrades = {"max_health": 0, "speed": 0, "magnet": 0, "shield": 0}
    if not os.path.exists(SAVE_FILE):
        return {"coins": 0, "upgrades": default_upgrades.copy()}
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "upgrades" not in data:
                data["upgrades"] = default_upgrades.copy()
            else:
                for k, v in default_upgrades.items():
                    if k not in data["upgrades"]:
                        data["upgrades"][k] = v
            if "coins" not in data:
                data["coins"] = 0
            return data
    except Exception:
        return {"coins": 0, "upgrades": default_upgrades.copy()}


def save_game(coins, upgrades):
    data = {"coins": coins, "upgrades": upgrades}
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ============================================================
# ASSET-LOADER
# ============================================================
def create_fallback_surface(size, fill_color, alpha=True):
    flags = pygame.SRCALPHA if alpha else 0
    surface = pygame.Surface(size, flags)
    surface.fill(fill_color)
    return surface


class AssetLoader:
    @staticmethod
    def load_image(filename: str, fallback_size=(40, 40), fallback_color=(255, 255, 255, 255)):
        path = asset_path(filename)
        if os.path.exists(path):
            try:
                return pygame.image.load(path).convert_alpha()
            except pygame.error:
                pass
        return create_fallback_surface(fallback_size, fallback_color)

    @staticmethod
    def load_sound(filename: str, volume: float = 0.25):
        if not AUDIO_ENABLED:
            return SilentSound()
        path = asset_path(filename)
        if os.path.exists(path):
            try:
                sound = pygame.mixer.Sound(path)
                sound.set_volume(volume)
                return sound
            except pygame.error:
                pass
        return SilentSound()

    @classmethod
    def load_assets(cls) -> GameAssets:
        bg = cls.load_image("bg.png", (SCREEN_WIDTH, SCREEN_HEIGHT), (10, 10, 20, 255))
        if bg.get_size() != (SCREEN_WIDTH, SCREEN_HEIGHT):
            bg = pygame.transform.scale(bg, (SCREEN_WIDTH, SCREEN_HEIGHT))

        ship = cls.load_image("spaceship.png", (72, 72), (220, 220, 255, 255))
        ship = pygame.transform.scale(ship, (72, 72))

        bullet = cls.load_image("bullet.png", (12, 24), (255, 255, 255, 255))
        bullet = pygame.transform.scale(bullet, (12, 24))

        alien_bullet = cls.load_image("alien_bullet.png", (12, 24), (255, 80, 80, 255))
        alien_bullet = pygame.transform.scale(alien_bullet, (12, 24))

        boss = cls.load_image("boss.png", (180, 110), (255, 120, 120, 255))
        boss = pygame.transform.scale(boss, (180, 110))

        explosion_frames = []
        for i in range(1, 6):
            frame = cls.load_image(f"exp{i}.png", (40, 40), (255, 180, 0, 255))
            explosion_frames.append(frame)

        alien_frames = []
        for i in range(1, 6):
            alien = cls.load_image(f"alien{i}.png", (54, 42), (120, 255, 120, 255))
            alien = pygame.transform.scale(alien, (54, 42))
            alien_frames.append(alien)

        return GameAssets(
            bg=bg,
            ship=ship,
            bullet=bullet,
            alien_bullet=alien_bullet,
            boss=boss,
            explosion_frames=explosion_frames,
            alien_frames=alien_frames,
            sound_explosion=cls.load_sound("explosion.wav", 0.25),
            sound_hit=cls.load_sound("explosion2.wav", 0.25),
            sound_laser=cls.load_sound("laser.wav", 0.25),
        )


# ============================================================
# SPRITES
# ============================================================
class Explosion(pygame.sprite.Sprite):
    def __init__(self, x, y, size, frames):
        super().__init__()
        self.images = []
        scale_map = {1: (24, 24), 2: (50, 50), 3: (180, 180)}
        target_size = scale_map.get(size, (50, 50))

        for frame in frames:
            self.images.append(pygame.transform.scale(frame, target_size))

        self.index = 0
        self.counter = 0
        self.animation_speed = 3
        self.image = self.images[self.index]
        self.rect = self.image.get_rect(center=(x, y))

    def update(self):
        self.counter += 1
        if self.counter >= self.animation_speed:
            self.counter = 0
            self.index += 1
            if self.index >= len(self.images):
                self.kill()
            else:
                self.image = self.images[self.index]


class Particle(pygame.sprite.Sprite):
    def __init__(self, x, y, color):
        super().__init__()
        self.image = pygame.Surface((4, 4), pygame.SRCALPHA)
        self.image.fill(color)
        self.rect = self.image.get_rect(center=(x, y))
        self.vx = random.uniform(-4, 4)
        self.vy = random.uniform(-4, 4)
        self.lifetime = random.randint(18, 40)

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()


class PowerUp(pygame.sprite.Sprite):
    def __init__(self, x, y, powerup_type, font):
        super().__init__()
        self.powerup_type = powerup_type
        self.image = pygame.Surface((28, 28), pygame.SRCALPHA)

        if powerup_type == POWERUP_HEALTH:
            fill = (0, 255, 0)
            text = "H"
        elif powerup_type == POWERUP_SPREAD:
            fill = (0, 100, 255)
            text = "S"
        else:
            fill = (255, 255, 0)
            text = "L"

        pygame.draw.circle(self.image, fill, (14, 14), 14)
        text_image = font.render(text, True, BLACK)
        text_rect = text_image.get_rect(center=(14, 14))
        self.image.blit(text_image, text_rect)
        self.rect = self.image.get_rect(center=(x, y))

    def update(self):
        self.rect.y += 3
        if self.rect.top > SCREEN_HEIGHT:
            self.kill()


class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, image):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect(center=(x, y))

    def update(self):
        self.rect.y -= 10
        if self.rect.bottom < 0:
            self.kill()


class LaserBeam(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((24, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (0, 255, 255, 150), (8, 0, 8, SCREEN_HEIGHT))
        pygame.draw.rect(self.image, WHITE, (10, 0, 4, SCREEN_HEIGHT))
        self.rect = self.image.get_rect()
        self.rect.midbottom = (x, y)
        self.mask = pygame.mask.from_surface(self.image)
        self.lifetime = 1

    def update(self):
        self.lifetime -= 1
        if self.lifetime < 0:
            self.kill()


class Alien(pygame.sprite.Sprite):
    def __init__(self, x, y, alien_images):
        super().__init__()
        self.image = random.choice(alien_images)
        self.rect = self.image.get_rect(center=(x, y))
        self.mask = pygame.mask.from_surface(self.image)


class AlienBullet(pygame.sprite.Sprite):
    def __init__(self, x, y, image, speed=4, damage=1):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = speed
        self.damage = damage

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > SCREEN_HEIGHT:
            self.kill()


class Boss(pygame.sprite.Sprite):
    def __init__(self, x, y, image, health=20, move_speed=3):
        super().__init__()
        self.base_image = image
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect(center=(x, y))
        self.health_start = float(health)
        self.health = float(health)
        self.base_move_speed = move_speed
        self.move_speed = move_speed
        self.direction = 1
        self.last_shot_time = 0
        self.shot_cooldown = 700
        self.flash_timer = 0
        self.mask = pygame.mask.from_surface(self.image)

    def update(self):
        enraged = self.health < (self.health_start / 2)
        self.move_speed = self.base_move_speed * 1.25 if enraged else self.base_move_speed

        self.rect.x += self.direction * self.move_speed
        if self.rect.left <= 30:
            self.direction = 1
        elif self.rect.right >= SCREEN_WIDTH - 30:
            self.direction = -1

        if self.flash_timer > 0:
            self.flash_timer -= 1
            temp = self.base_image.copy()
            temp.fill((255, 255, 255, 100), special_flags=pygame.BLEND_RGBA_ADD)
            self.image = temp
        else:
            self.image = self.base_image.copy()

        self.mask = pygame.mask.from_surface(self.image)


class Asteroid(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.size = random.randint(36, 70)
        self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (110, 110, 110), (self.size // 2, self.size // 2), self.size // 2)
        for _ in range(4):
            crater_x = random.randint(8, self.size - 8)
            crater_y = random.randint(8, self.size - 8)
            crater_r = random.randint(4, 10)
            pygame.draw.circle(self.image, (80, 80, 80), (crater_x, crater_y), crater_r)
        self.rect = self.image.get_rect(center=(x, y))
        self.vx = random.uniform(-2.2, 2.2)
        self.vy = random.uniform(3.0, 5.0)
        self.damage = 1
        self.mask = pygame.mask.from_surface(self.image)

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        if self.rect.top > SCREEN_HEIGHT or self.rect.right < 0 or self.rect.left > SCREEN_WIDTH:
            self.kill()


class Spaceship(pygame.sprite.Sprite):
    def __init__(self, x, y, image, health=3):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect(center=(x, y))
        self.health_start = health
        self.health_remaining = health
        self.last_shot_time = 0
        self.powerup_type = POWERUP_NONE
        self.powerup_start_time = 0
        self.mask = pygame.mask.from_surface(self.image)

    def update(self, keys, now, play_top_limit):
        speed = 8

        if keys[pygame.K_LEFT]:
            self.rect.x -= speed
        if keys[pygame.K_RIGHT]:
            self.rect.x += speed
        if keys[pygame.K_UP]:
            self.rect.y -= speed
        if keys[pygame.K_DOWN]:
            self.rect.y += speed

        self.rect.left = clamp(self.rect.left, 0, SCREEN_WIDTH - self.rect.width)
        self.rect.top = clamp(self.rect.top, play_top_limit, SCREEN_HEIGHT - 30 - self.rect.height)

        if self.powerup_type != POWERUP_NONE and now - self.powerup_start_time > 5000:
            self.powerup_type = POWERUP_NONE
            self.powerup_start_time = 0

    def can_shoot(self, now, cooldown):
        return now - self.last_shot_time >= cooldown

    def mark_shot(self, now):
        self.last_shot_time = now

    def is_dead(self):
        return self.health_remaining <= 0


# ============================================================
# SPIELKLASSE
# ============================================================
class SpaceInvadersGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.assets = AssetLoader.load_assets()
        self.highscore_manager = HighscoreManager(HIGHSCORE_FILE)
        self.highscores = self.highscore_manager.load()

        self.font24 = pygame.font.SysFont("Constantia", 24)
        self.font30 = pygame.font.SysFont("Constantia", 30)
        self.font40 = pygame.font.SysFont("Constantia", 40)
        self.font56 = pygame.font.SysFont("Constantia", 56)

        self.state = STATE_MENU
        self.running = True
        self.player_name = ""

        self.hits = 0
        self.level = 1
        self.game_over = 0

        self.countdown = 3
        self.last_count_time = 0

        self.alien_cooldown = 1000
        self.last_alien_shot_time = 0
        self.screen_shake = 0

        self.combo_timer = 0
        self.combo_kills = 0
        self.combo_multiplier = 1

        self.stars = self._create_stars(120)

        self.alien_direction = 1
        self.alien_base_speed = 1
        self.alien_drop_distance = 12
        self.alien_left_bound = 35
        self.alien_right_bound = SCREEN_WIDTH - 35
        self.player_top_limit = SCREEN_HEIGHT - 280
        self.alien_game_over_line = SCREEN_HEIGHT - 220
        self.starting_alien_count = 1

        self.spaceship = None
        self.spaceship_group = pygame.sprite.GroupSingle()
        self.bullet_group = pygame.sprite.Group()
        self.alien_group = pygame.sprite.Group()
        self.alien_bullet_group = pygame.sprite.Group()
        self.explosion_group = pygame.sprite.Group()
        self.boss_group = pygame.sprite.GroupSingle()
        self.powerup_group = pygame.sprite.Group()
        self.particle_group = pygame.sprite.Group()
        self.asteroid_group = pygame.sprite.Group()

    # -----------------------------
    # BASIS
    # -----------------------------
    def _create_stars(self, count):
        stars = []
        for _ in range(count):
            stars.append([
                random.randint(0, SCREEN_WIDTH),
                random.randint(0, SCREEN_HEIGHT),
                random.uniform(0.7, 2.0),
                random.randint(1, 3),
            ])
        return stars

    def draw_text(self, text, font, color, x, y):
        image = font.render(text, True, color)
        self.screen.blit(image, (x, y))

    def draw_center_text(self, text, font, color, center_x, y):
        image = font.render(text, True, color)
        rect = image.get_rect(center=(center_x, y))
        self.screen.blit(image, rect)

    def draw_background(self):
        self.screen.fill(DARK_BG)

        for star in self.stars:
            star[1] += star[2]
            if star[1] > SCREEN_HEIGHT:
                star[1] = 0
                star[0] = random.randint(0, SCREEN_WIDTH)
            pygame.draw.rect(self.screen, (200, 200, 220), (star[0], star[1], star[3], star[3]))

       # pygame.draw.rect(self.screen, SOFT_BLUE, (0, SCREEN_HEIGHT - 160, SCREEN_WIDTH, 160)) - Zeichnet eine Hellere Oberfläche für das Spaceship!

    def clear_level_objects(self):
        self.bullet_group.empty()
        self.alien_group.empty()
        self.alien_bullet_group.empty()
        self.explosion_group.empty()
        self.boss_group.empty()
        self.powerup_group.empty()
        self.particle_group.empty()
        self.asteroid_group.empty()

    def reset_game(self):
        self.hits = 0
        self.level = 1
        self.game_over = 0
        self.player_name = ""
        self.combo_timer = 0
        self.combo_kills = 0
        self.combo_multiplier = 1
        self.screen_shake = 0
        self.alien_direction = 1
        self.alien_base_speed = 1
        self.alien_drop_distance = 12

        self.clear_level_objects()
        self.spaceship_group.empty()

        self.spaceship = Spaceship(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 120, self.assets.ship, health=3)
        self.spaceship_group.add(self.spaceship)
        self.start_level(1)

    # -----------------------------
    # LEVELSYSTEM
    # -----------------------------
    def create_aliens(self, rows, cols, speed):
        start_x = 120
        start_y = 120
        x_gap = 82
        y_gap = 60

        self.alien_base_speed = speed
        self.alien_direction = 1
        self.starting_alien_count = rows * cols

        for row in range(rows):
            for col in range(cols):
                alien = Alien(start_x + col * x_gap, start_y + row * y_gap, self.assets.alien_frames)
                self.alien_group.add(alien)

    def start_level(self, new_level):
        self.level = new_level
        self.game_over = 0
        self.countdown = 3
        self.last_count_time = pygame.time.get_ticks()
        self.clear_level_objects()

        if self.level < 5:
            rows = min(7, 4 + (self.level - 1))
            cols = min(8, 5 + (self.level - 1))
            alien_speed = 1 + (self.level - 1) * 0.25
            self.alien_drop_distance = 10
            self.create_aliens(rows, cols, alien_speed)
            self.alien_cooldown = max(320, 1000 - (self.level - 1) * 120)
            self.last_alien_shot_time = pygame.time.get_ticks()
        else:
            boss_health = 22 + (self.level - 5) * 10
            boss_speed = 3 + (self.level - 5) // 2
            boss = Boss(SCREEN_WIDTH // 2, 140, self.assets.boss, health=boss_health, move_speed=boss_speed)
            boss.shot_cooldown = max(260, 700 - (self.level - 5) * 60)
            self.boss_group.add(boss)
            self.alien_cooldown = 999999

    # -----------------------------
    # SPIELLOGIK
    # -----------------------------
    def add_explosion(self, x, y, size):
        self.explosion_group.add(Explosion(x, y, size, self.assets.explosion_frames))

    def add_particles(self, x, y, color, amount):
        for _ in range(amount):
            self.particle_group.add(Particle(x, y, color))

    def trigger_alien_death(self, alien):
        self.assets.sound_explosion.play()
        self.add_explosion(alien.rect.centerx, alien.rect.centery, 2)
        self.add_particles(alien.rect.centerx, alien.rect.centery, (255, random.randint(120, 255), 0), 15)
        self.screen_shake = max(self.screen_shake, 3)

        if random.random() < 0.1:
            powerup_type = random.randint(1, 3)
            self.powerup_group.add(PowerUp(alien.rect.centerx, alien.rect.centery, powerup_type, self.font24))

        self.combo_timer = 120
        self.combo_kills += 1
        if self.combo_kills >= 3:
            if self.combo_multiplier < 5:
                self.combo_multiplier += 1
            self.combo_kills = 0

        self.hits += 1 * self.combo_multiplier

    def handle_player_shooting(self, keys, now):
        if not self.spaceship or not keys[pygame.K_SPACE] or self.game_over != 0:
            return

        if self.spaceship.powerup_type == POWERUP_LASER:
            if self.spaceship.can_shoot(now, 180):
                self.bullet_group.add(LaserBeam(self.spaceship.rect.centerx, self.spaceship.rect.top))
                self.assets.sound_laser.play()
                self.spaceship.mark_shot(now)
            return

        shoot_cooldown = 300
        if not self.spaceship.can_shoot(now, shoot_cooldown):
            return

        self.assets.sound_laser.play()
        if self.spaceship.powerup_type == POWERUP_SPREAD:
            self.bullet_group.add(
                Bullet(self.spaceship.rect.centerx - 20, self.spaceship.rect.top, self.assets.bullet),
                Bullet(self.spaceship.rect.centerx, self.spaceship.rect.top, self.assets.bullet),
                Bullet(self.spaceship.rect.centerx + 20, self.spaceship.rect.top, self.assets.bullet),
            )
        else:
            self.bullet_group.add(Bullet(self.spaceship.rect.centerx, self.spaceship.rect.top, self.assets.bullet))
        self.spaceship.mark_shot(now)

    def handle_powerup_collection(self, now):
        if not self.spaceship:
            return

        collected = pygame.sprite.spritecollide(self.spaceship, self.powerup_group, dokill=True)
        for powerup in collected:
            if powerup.powerup_type == POWERUP_HEALTH:
                self.spaceship.health_remaining = min(self.spaceship.health_remaining + 1, self.spaceship.health_start)
            else:
                self.spaceship.powerup_type = powerup.powerup_type
                self.spaceship.powerup_start_time = now

    def handle_bullet_collisions(self):
        for bullet in list(self.bullet_group):
            if isinstance(bullet, LaserBeam):
                self._handle_laser_collisions(bullet)
            else:
                self._handle_normal_bullet_collisions(bullet)

    def _handle_normal_bullet_collisions(self, bullet):
        hit_aliens = pygame.sprite.spritecollide(bullet, self.alien_group, dokill=True)
        if hit_aliens:
            bullet.kill()
            for alien in hit_aliens:
                self.trigger_alien_death(alien)
            return

        boss = self.boss_group.sprite
        if boss and pygame.sprite.collide_mask(bullet, boss):
            bullet.kill()
            boss.health -= 1
            boss.flash_timer = 6
            self.assets.sound_explosion.play()
            self.screen_shake = max(self.screen_shake, 3)
            self.add_particles(bullet.rect.centerx, bullet.rect.top, (255, 100, 0), 6)

    def _handle_laser_collisions(self, laser):
        boss = self.boss_group.sprite
        if boss and pygame.sprite.collide_mask(laser, boss):
            boss.health -= 0.18
            boss.flash_timer = 2
            self.screen_shake = max(self.screen_shake, 2)
            self.add_particles(laser.rect.centerx + random.randint(-15, 15), boss.rect.bottom, CYAN, 2)

        hit_aliens = pygame.sprite.spritecollide(laser, self.alien_group, dokill=True)
        for alien in hit_aliens:
            self.trigger_alien_death(alien)

    def update_aliens_group_movement(self):
        if len(self.alien_group) == 0:
            return

        current_speed = self.alien_base_speed
        if self.level < 5 and self.starting_alien_count > 0:
            missing = self.starting_alien_count - len(self.alien_group)
            current_speed += missing * 0.03
            current_speed = min(current_speed, 4.0)

        move_down = False

        for alien in self.alien_group:
            alien.rect.x += self.alien_direction * current_speed

        for alien in self.alien_group:
            if alien.rect.right >= self.alien_right_bound and self.alien_direction > 0:
                move_down = True
                break
            if alien.rect.left <= self.alien_left_bound and self.alien_direction < 0:
                move_down = True
                break

        if move_down:
            self.alien_direction *= -1
            for alien in self.alien_group:
                alien.rect.y += self.alien_drop_distance

    def handle_enemy_fire(self, now):
        if self.level >= 5:
            boss = self.boss_group.sprite
            if not boss:
                return
            enraged = boss.health < (boss.health_start / 2)
            active_limit = 10 if enraged else 7
            actual_cooldown = boss.shot_cooldown // 2 if enraged else boss.shot_cooldown
            if now - boss.last_shot_time > actual_cooldown and len(self.alien_bullet_group) < active_limit:
                bullet = AlienBullet(boss.rect.centerx, boss.rect.bottom, self.assets.alien_bullet, speed=6, damage=2)
                self.alien_bullet_group.add(bullet)
                boss.last_shot_time = now
            return

        if now - self.last_alien_shot_time > self.alien_cooldown and len(self.alien_bullet_group) < 5 and len(self.alien_group) > 0:
            columns = {}
            for alien in self.alien_group:
                key = round(alien.rect.centerx / 20)
                if key not in columns or alien.rect.centery > columns[key].rect.centery:
                    columns[key] = alien

            shooters = list(columns.values())
            if shooters:
                attacker = random.choice(shooters)
                bullet = AlienBullet(attacker.rect.centerx, attacker.rect.bottom, self.assets.alien_bullet, speed=4, damage=1)
                self.alien_bullet_group.add(bullet)
                self.last_alien_shot_time = now

    def handle_enemy_collisions_with_player(self):
        if not self.spaceship:
            return

        for bullet in list(self.alien_bullet_group):
            if pygame.sprite.collide_mask(bullet, self.spaceship):
                bullet.kill()
                self.assets.sound_hit.play()
                self.spaceship.health_remaining -= bullet.damage
                self.screen_shake = 15
                self.add_explosion(bullet.rect.centerx, bullet.rect.centery, 1)

        for asteroid in list(self.asteroid_group):
            if pygame.sprite.collide_mask(asteroid, self.spaceship):
                asteroid.kill()
                self.assets.sound_hit.play()
                self.spaceship.health_remaining -= asteroid.damage
                self.screen_shake = 15
                self.add_explosion(asteroid.rect.centerx, asteroid.rect.centery, 2)

        for alien in list(self.alien_group):
            if self.spaceship.rect.colliderect(alien.rect):
                self.spaceship.health_remaining = 0
                self.game_over = -1
                return

        boss = self.boss_group.sprite
        if boss and self.spaceship.rect.colliderect(boss.rect):
            self.spaceship.health_remaining = 0
            self.game_over = -1

    def check_aliens_reached_bottom(self):
        if self.level >= 5:
            return

        for alien in self.alien_group:
            if alien.rect.bottom >= self.alien_game_over_line:
                self.game_over = -1
                return

    def handle_player_death(self):
        if self.spaceship and self.spaceship.is_dead():
            self.screen_shake = 30
            self.add_explosion(self.spaceship.rect.centerx, self.spaceship.rect.centery, 3)
            self.add_particles(self.spaceship.rect.centerx, self.spaceship.rect.centery, (255, 100, 0), 40)
            self.spaceship.kill()
            self.spaceship = None
            self.game_over = -1

    def handle_boss_death(self):
        boss = self.boss_group.sprite
        if boss and boss.health <= 0:
            self.screen_shake = 50
            self.add_explosion(boss.rect.centerx, boss.rect.centery, 3)
            self.add_particles(boss.rect.centerx, boss.rect.centery, (255, 50, 0), 50)
            boss.kill()
            self.game_over = 1

    def maybe_spawn_asteroid(self):
        if self.level > 2 and random.random() < 0.006:
            asteroid = Asteroid(random.randint(0, SCREEN_WIDTH), -50)
            self.asteroid_group.add(asteroid)

    def update_combo(self):
        if self.combo_timer > 0:
            self.combo_timer -= 1
            if self.combo_timer <= 0:
                self.combo_multiplier = 1
                self.combo_kills = 0

    def update_gameplay(self):
        now = pygame.time.get_ticks()
        keys = pygame.key.get_pressed()

        self.update_combo()

        if self.countdown > 0:
            if now - self.last_count_time > 1000:
                self.countdown -= 1
                self.last_count_time = now
            return

        if self.spaceship:
            self.spaceship.update(keys, now, self.player_top_limit)
            self.handle_powerup_collection(now)
            self.handle_player_shooting(keys, now)

        self.bullet_group.update()
        self.update_aliens_group_movement()
        self.alien_bullet_group.update()
        self.boss_group.update()
        self.explosion_group.update()
        self.powerup_group.update()
        self.particle_group.update()
        self.asteroid_group.update()

        self.handle_enemy_fire(now)
        self.maybe_spawn_asteroid()
        self.handle_bullet_collisions()
        self.handle_enemy_collisions_with_player()
        self.check_aliens_reached_bottom()
        self.handle_player_death()
        self.handle_boss_death()

        if self.level < 5 and len(self.alien_group) == 0 and self.game_over == 0:
            self.start_level(self.level + 1)

    # -----------------------------
    # DRAWING
    # -----------------------------
    def draw_hits_and_level(self):
        self.draw_text(f"Treffer: {self.hits}", self.font30, WHITE, SCREEN_WIDTH - 170, SCREEN_HEIGHT - 50)
        self.draw_text(f"Level: {self.level}", self.font30, WHITE, 20, SCREEN_HEIGHT - 50)

        if self.combo_multiplier > 1:
            combo_text = f"COMBO x{self.combo_multiplier}!"
            combo_color = (255, random.randint(150, 255), 0)
            self.draw_text(combo_text, self.font40, combo_color, SCREEN_WIDTH - 250, SCREEN_HEIGHT - 95)

    def draw_health_bar(self):
        if not self.spaceship:
            return
        bar_x = self.spaceship.rect.x
        bar_y = self.spaceship.rect.bottom + 12
        bar_w = self.spaceship.rect.width
        bar_h = 16
        pygame.draw.rect(self.screen, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h), border_radius=6)
        pygame.draw.rect(self.screen, RED, (bar_x, bar_y, bar_w, bar_h), border_radius=6)
        current_w = int(bar_w * (self.spaceship.health_remaining / self.spaceship.health_start))
        if current_w > 0:
            pygame.draw.rect(self.screen, GREEN, (bar_x, bar_y, current_w, bar_h), border_radius=6)

    def draw_boss_health_bar(self):
        boss = self.boss_group.sprite
        if not boss:
            return
        bar_w = 360
        bar_h = 20
        bar_x = SCREEN_WIDTH // 2 - bar_w // 2
        bar_y = 20
        pygame.draw.rect(self.screen, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h), border_radius=8)
        pygame.draw.rect(self.screen, RED, (bar_x, bar_y, bar_w, bar_h), border_radius=8)
        current_w = int(bar_w * max(0, boss.health) / boss.health_start)
        if current_w > 0:
            pygame.draw.rect(self.screen, GREEN, (bar_x, bar_y, current_w, bar_h), border_radius=8)

    def draw_menu(self):
        self.draw_center_text("SPACE INVADERS", self.font56, WHITE, SCREEN_WIDTH // 2, 130)
        self.draw_center_text("SPACE = Start", self.font30, GREEN, SCREEN_WIDTH // 2, 250)
        self.draw_center_text("ESC = Quit", self.font30, WHITE, SCREEN_WIDTH // 2, 300)

        self.draw_center_text("LEADERBOARD", self.font40, GOLD, SCREEN_WIDTH // 2, 390)

        y = 460
        for index, entry in enumerate(self.highscores[:10], start=1):
            self.draw_text(f"{index}.", self.font30, WHITE, SCREEN_WIDTH // 2 - 180, y)
            self.draw_text(entry.get("name", "---"), self.font30, WHITE, SCREEN_WIDTH // 2 - 80, y)
            self.draw_text(str(entry.get("score", 0)), self.font30, WHITE, SCREEN_WIDTH // 2 + 100, y)
            y += 38

    def draw_name_entry(self):
        if self.game_over == 1:
            self.draw_center_text("YOU WIN!", self.font56, GREEN, SCREEN_WIDTH // 2, 180)
        else:
            self.draw_center_text("GAME OVER", self.font56, RED, SCREEN_WIDTH // 2, 180)

        self.draw_center_text(f"Your Score: {self.hits}", self.font30, WHITE, SCREEN_WIDTH // 2, 290)
        self.draw_center_text("Enter Name:", self.font30, WHITE, SCREEN_WIDTH // 2, 380)
        self.draw_center_text(self.player_name + "_", self.font40, GOLD, SCREEN_WIDTH // 2, 450)
        self.draw_center_text("ENTER = Save", self.font30, GREEN, SCREEN_WIDTH // 2, 560)
        self.draw_center_text("ESC = Quit", self.font30, WHITE, SCREEN_WIDTH // 2, 600)

    def draw_playing(self):
        self.draw_hits_and_level()

        self.spaceship_group.draw(self.screen)
        self.bullet_group.draw(self.screen)
        self.alien_group.draw(self.screen)
        self.boss_group.draw(self.screen)
        self.alien_bullet_group.draw(self.screen)
        self.explosion_group.draw(self.screen)
        self.powerup_group.draw(self.screen)
        self.particle_group.draw(self.screen)
        self.asteroid_group.draw(self.screen)

        self.draw_health_bar()
        self.draw_boss_health_bar()

        if self.countdown > 0:
            self.draw_center_text("GET READY!", self.font56, WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30)
            self.draw_center_text(str(self.countdown), self.font56, GOLD, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40)

        if self.game_over == -1:
            self.draw_center_text("GAME OVER!", self.font56, WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 10)
            self.draw_center_text("Drück LEERTASTE zum Fortfahren", self.font30, WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60)

        if self.game_over == 1:
            self.draw_center_text("YOU WIN!", self.font56, WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 10)
            self.draw_center_text("Drück LEERTASTE zum Fortfahren", self.font30, WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60)

    def apply_screen_shake(self):
        if self.screen_shake <= 0:
            return
        shake_x = random.randint(-self.screen_shake, self.screen_shake)
        shake_y = random.randint(-self.screen_shake, self.screen_shake)
        screen_copy = self.screen.copy()
        self.screen.fill(BLACK)
        self.screen.blit(screen_copy, (shake_x, shake_y))
        self.screen_shake -= 1

    # -----------------------------
    # EVENTS
    # -----------------------------
    def handle_menu_events(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.reset_game()
                self.state = STATE_PLAYING
            elif event.key == pygame.K_ESCAPE:
                self.running = False

    def handle_name_entry_events(self, event):
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_RETURN:
            name_to_save = self.player_name.strip() or "AAA"
            self.highscore_manager.save_score(name_to_save, self.hits)
            self.highscores = self.highscore_manager.load()
            self.player_name = ""
            self.state = STATE_MENU
        elif event.key == pygame.K_BACKSPACE:
            self.player_name = self.player_name[:-1]
        elif event.key == pygame.K_ESCAPE:
            self.running = False
        else:
            if len(self.player_name) < 10 and event.unicode.isprintable() and event.unicode.strip() != "":
                self.player_name += event.unicode

    def handle_playing_events(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.running = False
        elif self.game_over != 0 and event.key == pygame.K_SPACE:
            self.state = STATE_NAME_ENTRY

    # -----------------------------
    # HAUPTSCHLEIFE
    # -----------------------------
    def process_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue

            if self.state == STATE_MENU:
                self.handle_menu_events(event)
            elif self.state == STATE_NAME_ENTRY:
                self.handle_name_entry_events(event)
            elif self.state == STATE_PLAYING:
                self.handle_playing_events(event)

    def update(self):
        if self.state == STATE_PLAYING and self.game_over == 0:
            self.update_gameplay()
        else:
            self.explosion_group.update()
            self.powerup_group.update()
            self.particle_group.update()

    def draw(self):
        self.draw_background()

        if self.state == STATE_MENU:
            self.draw_menu()
        elif self.state == STATE_NAME_ENTRY:
            self.draw_name_entry()
        elif self.state == STATE_PLAYING:
            self.draw_playing()

        self.apply_screen_shake()
        pygame.display.update()

    def run(self):
        while self.running:
            self.clock.tick(FPS)
            self.process_events()
            self.update()
            self.draw()

        pygame.quit()


# ============================================================
# PROGRAMMSTART
# ============================================================
if __name__ == "__main__":
    SpaceInvadersGame().run()
