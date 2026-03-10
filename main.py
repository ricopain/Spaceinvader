import pygame
from pygame import mixer
from pygame.locals import *
import random
import os
import json

pygame.mixer.pre_init(44100, -16, 2, 512)
mixer.init()
pygame.init()

# -----------------------------
# HIGHSCORE
# -----------------------------
HIGHSCORE_FILE = "highscore.json"

def load_highscores():
    if not os.path.exists(HIGHSCORE_FILE):
        return []
    try:
        with open(HIGHSCORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_highscore(name, score):
    scores = load_highscores()
    scores.append({"name": name, "score": score})
    scores = sorted(scores, key=lambda x: x["score"], reverse=True)[:10]
    with open(HIGHSCORE_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=4)

highscores = load_highscores()

# -----------------------------
# CONFIG
# -----------------------------
clock = pygame.time.Clock()
fps = 60

screen_width = 600
screen_height = 800
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Space Invanders")

font30 = pygame.font.SysFont("Constantia", 30)
font40 = pygame.font.SysFont("Constantia", 40)

# colours
red = (255, 0, 0)
green = (0, 255, 0)
white = (255, 255, 255)

# load sounds
explosion_fx = pygame.mixer.Sound("img/explosion.wav")
explosion_fx.set_volume(0.25)

explosion2_fx = pygame.mixer.Sound("img/explosion2.wav")
explosion2_fx.set_volume(0.25)

laser_fx = pygame.mixer.Sound("img/laser.wav")
laser_fx.set_volume(0.25)

# load bg
bg = pygame.image.load("img/bg.png")

# Create stars for scrolling background
stars = []
for _ in range(100):
    # x, y, speed, size
    stars.append([random.randint(0, screen_width), random.randint(0, screen_height), random.uniform(1, 3), random.randint(1, 3)])

def draw_bg():
    screen.blit(bg, (0, 0))
    # Draw and move stars
    for star in stars:
        star[1] += star[2] # move y
        if star[1] > screen_height:
            star[1] = 0
            star[0] = random.randint(0, screen_width)
        pygame.draw.rect(screen, (200, 200, 200), (star[0], star[1], star[3], star[3]))

def draw_text(text, font, text_col, x, y):
    img = font.render(text, True, text_col)
    screen.blit(img, (x, y))

def safe_load_image(path, fallback_size=(40, 40)):
    """Falls ein Bild fehlt: erstellt eine einfache Fläche als Ersatz."""
    if os.path.exists(path):
        return pygame.image.load(path).convert_alpha()
    surf = pygame.Surface(fallback_size, pygame.SRCALPHA)
    surf.fill((255, 255, 255, 255))
    return surf

# -----------------------------
# GAME STATE
# -----------------------------
hits = 0
level = 1

# countdown
countdown = 3
last_count = pygame.time.get_ticks()

# game_over: 0 = läuft, 1 = gewonnen, -1 = verloren
game_over = 0

game_state = "menu"  # menu, playing, name_entry
player_name = ""

# difficulty base
alien_cooldown = 1000  # ms (wird pro level schneller)
last_alien_shot = pygame.time.get_ticks()

screen_shake = 0
combo_timer = 0
combo_kills = 0
combo_multiplier = 1

def trigger_alien_death(al, is_laser=False):
    global hits, combo_timer, combo_kills, combo_multiplier, screen_shake
    
    explosion_fx.play()
    explosion = Explosion(al.rect.centerx, al.rect.centery, 2)
    explosion_group.add(explosion)
    screen_shake = max(screen_shake, 3)
    
    for _ in range(15):
        particle_group.add(Particle(al.rect.centerx, al.rect.centery, (255, random.randint(100, 255), 0)))
        
    if random.random() < 0.1:
        p_type = random.randint(1, 3)
        powerup_group.add(PowerUp(al.rect.centerx, al.rect.centery, p_type))
        
    combo_timer = 120
    combo_kills += 1
    if combo_kills >= 3:
        if combo_multiplier < 5:
            combo_multiplier += 1
        combo_kills = 0
        
    hits += (1 * combo_multiplier)

# -----------------------------
# SPRITES
# -----------------------------
class Spaceship(pygame.sprite.Sprite):
    def __init__(self, x, y, health):
        pygame.sprite.Sprite.__init__(self)
        self.image = safe_load_image("img/spaceship.png", (60, 60))
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        self.health_start = health
        self.health_remaining = health
        self.last_shot = pygame.time.get_ticks()
        
        self.power_up_type = 0  # 0=none, 1=health (instant), 2=spread, 3=rapid
        self.power_up_time = 0

    def update(self):
        speed = 8
        local_game_over = 0

        key = pygame.key.get_pressed()
        if key[pygame.K_LEFT] and self.rect.left > 0:
            self.rect.x -= speed
        if key[pygame.K_RIGHT] and self.rect.right < screen_width:
            self.rect.x += speed
            
        now = pygame.time.get_ticks()
        
        # Handle active power-up duration (5 seconds)
        if self.power_up_time > 0 and now - self.power_up_time > 5000:
            self.power_up_type = 0
            
        # Check power-up collision
        hit_pwrup = pygame.sprite.spritecollide(self, powerup_group, True)
        for pw in hit_pwrup:
            if pw.p_type == 1: # Health
                self.health_remaining = min(self.health_remaining + 1, self.health_start)
            else:
                self.power_up_type = pw.p_type
                self.power_up_time = now

        # Adjust shooting cooldown based on power-up
        cooldown = 500

        if key[pygame.K_SPACE] and local_game_over == 0:
            if self.power_up_type == 3:
                # LaserBeam!
                laser = LaserBeam(self.rect.centerx, self.rect.top)
                bullet_group.add(laser)
                if now - self.last_shot > 150:
                    laser_fx.play()
                    self.last_shot = now
            elif now - self.last_shot > cooldown:
                laser_fx.play()
                if self.power_up_type == 2: # Spread
                    b1 = Bullets(self.rect.centerx - 20, self.rect.top)
                    b2 = Bullets(self.rect.centerx, self.rect.top)
                    b3 = Bullets(self.rect.centerx + 20, self.rect.top)
                    bullet_group.add(b1, b2, b3)
                else:
                    bullet = Bullets(self.rect.centerx, self.rect.top)
                    bullet_group.add(bullet)
                self.last_shot = now

        self.mask = pygame.mask.from_surface(self.image)

        # health bar
        pygame.draw.rect(screen, red, (self.rect.x, self.rect.bottom + 10, self.rect.width, 15))
        if self.health_remaining > 0:
            pygame.draw.rect(
                screen,
                green,
                (self.rect.x, self.rect.bottom + 10, int(self.rect.width * (self.health_remaining / self.health_start)), 15),
            )
        else:
            global screen_shake
            screen_shake = 30
            explosion = Explosion(self.rect.centerx, self.rect.centery, 3)
            explosion_group.add(explosion)
            for _ in range(40):
                particle_group.add(Particle(self.rect.centerx, self.rect.centery, (255, 100, 0)))
            self.kill()
            local_game_over = -1

        return local_game_over

class Bullets(pygame.sprite.Sprite):
    def __init__(self, x, y):
        pygame.sprite.Sprite.__init__(self)
        self.image = safe_load_image("img/bullet.png", (10, 20))
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]

    def update(self):
        global hits
        self.rect.y -= 7
        if self.rect.bottom < 0:
            self.kill()
            return

        # Treffer auf normale Aliens
        hit_list = pygame.sprite.spritecollide(self, alien_group, True)
        if hit_list:
            self.kill()
            for al in hit_list:
                trigger_alien_death(al)
            return

        # Treffer auf Boss
        boss_hit = pygame.sprite.spritecollide(self, boss_group, False, pygame.sprite.collide_mask)
        if boss_hit:
            self.kill()
            explosion_fx.play()
            global screen_shake
            screen_shake = max(screen_shake, 3)
            for b in boss_hit:
                b.health -= 1
                b.flash_timer = 6
                # particles for boss hit
                for _ in range(5):
                    particle_group.add(Particle(self.rect.centerx, self.rect.top, (255, 100, 0)))

class Aliens(pygame.sprite.Sprite):
    def __init__(self, x, y, speed=1):
        pygame.sprite.Sprite.__init__(self)
        self.image = safe_load_image(f"img/alien{random.randint(1, 5)}.png", (50, 40))
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        self.move_counter = 0
        self.move_direction = 1
        self.speed = speed

    def update(self):
        self.rect.x += self.move_direction * self.speed
        self.move_counter += 1 * self.speed
        if abs(self.move_counter) > 75:
            self.move_direction *= -1
            self.move_counter *= self.move_direction

class Alien_Bullets(pygame.sprite.Sprite):
    def __init__(self, x, y, speed=3, damage=1, img_path="img/alien_bullet.png"):
        pygame.sprite.Sprite.__init__(self)
        self.image = safe_load_image(img_path, (10, 20))
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        self.speed = speed
        self.damage = damage

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > screen_height:
            self.kill()
            return

        hits = pygame.sprite.spritecollide(self, spaceship_group, False, pygame.sprite.collide_mask)
        if hits:
            self.kill()
            explosion2_fx.play()
            global screen_shake
            screen_shake = 15
            for sp in hits:
                sp.health_remaining -= self.damage
            explosion = Explosion(self.rect.centerx, self.rect.centery, 1)
            explosion_group.add(explosion)

class Boss(pygame.sprite.Sprite):
    def __init__(self, x, y, health, move_speed=3):
        pygame.sprite.Sprite.__init__(self)
        self.base_image = safe_load_image("img/boss.png", (140, 90))
        self.image = self.base_image
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        self.health_start = health
        self.health = health

        self.base_move_speed = move_speed
        self.move_speed = move_speed
        self.direction = 1

        self.last_shot = pygame.time.get_ticks()
        self.shot_cooldown = 700  # ms, wird später pro level etwas schneller

        self.flash_timer = 0
        self.mask = pygame.mask.from_surface(self.image)

    def update(self):
        # Enrage
        in_enrage = self.health < (self.health_start / 2)
        if in_enrage:
            self.move_speed = self.base_move_speed * 1.5
            actual_cooldown = self.shot_cooldown // 2
        else:
            self.move_speed = self.base_move_speed
            actual_cooldown = self.shot_cooldown

        # bewegen
        self.rect.x += self.direction * self.move_speed
        if self.rect.left <= 20:
            self.direction = 1
        if self.rect.right >= screen_width - 20:
            self.direction = -1

        # schießen
        now = pygame.time.get_ticks()
        if now - self.last_shot > actual_cooldown and len(alien_bullet_group) < (10 if in_enrage else 7):
            # Boss-Bullet (falls boss_bullet.png nicht existiert, nimmt safe_load_image Ersatz)
            bullet = Alien_Bullets(self.rect.centerx, self.rect.bottom, speed=5, damage=2, img_path="img/boss_bullet.png")
            alien_bullet_group.add(bullet)
            self.last_shot = now

        # Treffer-Flash (optional) oder Rot wenn Enrage
        if self.flash_timer > 0:
            self.flash_timer -= 1
            tmp = self.base_image.copy()
            tmp.fill((255, 255, 255, 120), special_flags=pygame.BLEND_RGBA_ADD)
            self.image = tmp
        else:
            if in_enrage:
                tmp = self.base_image.copy()
                tmp.fill((255, 100, 100, 100), special_flags=pygame.BLEND_RGBA_MULT)
                self.image = tmp
            else:
                self.image = self.base_image

        self.mask = pygame.mask.from_surface(self.image)

        # Boss Healthbar oben
        bar_w = 300
        bar_h = 16
        x = screen_width // 2 - bar_w // 2
        y = 20
        pygame.draw.rect(screen, red, (x, y, bar_w, bar_h))
        if self.health > 0:
            pygame.draw.rect(screen, green, (x, y, int(bar_w * (self.health / self.health_start)), bar_h))
        else:
            # Boss tot
            global screen_shake
            screen_shake = 50
            explosion = Explosion(self.rect.centerx, self.rect.centery, 3)
            explosion_group.add(explosion)
            for _ in range(50):
                particle_group.add(Particle(self.rect.centerx, self.rect.centery, (255, 50, 0)))
            self.kill()

class Explosion(pygame.sprite.Sprite):
    def __init__(self, x, y, size):
        pygame.sprite.Sprite.__init__(self)
        self.images = []
        for num in range(1, 6):
            img = safe_load_image(f"img/exp{num}.png", (40, 40))
            if size == 1:
                img = pygame.transform.scale(img, (20, 20))
            if size == 2:
                img = pygame.transform.scale(img, (40, 40))
            if size == 3:
                img = pygame.transform.scale(img, (160, 160))
            self.images.append(img)
        self.index = 0
        self.image = self.images[self.index]
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        self.counter = 0

    def update(self):
        explosion_speed = 3
        self.counter += 1
        if self.counter >= explosion_speed and self.index < len(self.images) - 1:
            self.counter = 0
            self.index += 1
            self.image = self.images[self.index]
        if self.index >= len(self.images) - 1 and self.counter >= explosion_speed:
            self.kill()

# -----------------------------
# NEW CLASSES: PARTICLES & POWERUPS
# -----------------------------
class Particle(pygame.sprite.Sprite):
    def __init__(self, x, y, color):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface((4, 4))
        self.image.fill(color)
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        self.vx = random.uniform(-4, 4)
        self.vy = random.uniform(-4, 4)
        self.lifetime = random.randint(20, 40)
        
    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()

class PowerUp(pygame.sprite.Sprite):
    def __init__(self, x, y, p_type):
        pygame.sprite.Sprite.__init__(self)
        self.p_type = p_type # 1=Health(Green), 2=Spread(Blue), 3=Rapid(Yellow)
        self.image = pygame.Surface((20, 20))
        if p_type == 1:
            self.image.fill((0, 255, 0))
            self.text = "H"
        elif p_type == 2:
            self.image.fill((0, 100, 255))
            self.text = "S"
        else:
            self.image.fill((255, 255, 0))
            self.text = "L"
            
        t_img = font30.render(self.text, True, (0, 0, 0))
        t_rect = t_img.get_rect(center=(10, 10))
        self.image.blit(t_img, t_rect)
        
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        
    def update(self):
        self.rect.y += 3
        if self.rect.top > screen_height:
            self.kill()

class LaserBeam(pygame.sprite.Sprite):
    def __init__(self, x, y):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface((30, screen_height), pygame.SRCALPHA)
        self.image.fill((0, 255, 255, 200))
        pygame.draw.rect(self.image, (255, 255, 255), (10, 0, 10, screen_height))
        self.rect = self.image.get_rect()
        self.rect.midbottom = [x, y]
        self.mask = pygame.mask.from_surface(self.image)
        
    def update(self):
        global screen_shake
        # Boss collision
        boss_hit = pygame.sprite.spritecollide(self, boss_group, False, pygame.sprite.collide_mask)
        if boss_hit:
            for b in boss_hit:
                b.health -= 0.15
                b.flash_timer = 2
                screen_shake = max(screen_shake, 2)
                for _ in range(2):
                    particle_group.add(Particle(self.rect.centerx + random.randint(-15, 15), b.rect.bottom, (0, 255, 255)))
                    
        # Alien collision
        alien_hit = pygame.sprite.spritecollide(self, alien_group, True)
        if alien_hit:
            for al in alien_hit:
                trigger_alien_death(al, is_laser=True)
                
        # Lived 1 frame
        self.kill()

class Asteroid(pygame.sprite.Sprite):
    def __init__(self, x, y):
        pygame.sprite.Sprite.__init__(self)
        self.size = random.randint(30, 60)
        self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (100, 100, 100), (self.size//2, self.size//2), self.size//2)
        for _ in range(4):
            pygame.draw.circle(self.image, (80, 80, 80), (random.randint(5, self.size-5), random.randint(5, self.size-5)), random.randint(3, 8))
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(3, 6)
        self.mask = pygame.mask.from_surface(self.image)
        self.damage = 1

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        if self.rect.top > screen_height or self.rect.right < 0 or self.rect.left > screen_width:
            self.kill()
            return
            
        if game_over == 0 and spaceship:
            if pygame.sprite.collide_mask(self, spaceship):
                global screen_shake
                self.kill()
                explosion2_fx.play()
                spaceship.health_remaining -= self.damage
                screen_shake = 15
                explosion = Explosion(self.rect.centerx, self.rect.centery, 2)
                explosion_group.add(explosion)

# -----------------------------
# GROUPS
# -----------------------------
spaceship_group = pygame.sprite.Group()
bullet_group = pygame.sprite.Group()
alien_group = pygame.sprite.Group()
alien_bullet_group = pygame.sprite.Group()
explosion_group = pygame.sprite.Group()
boss_group = pygame.sprite.Group()
powerup_group = pygame.sprite.Group()
particle_group = pygame.sprite.Group()

# -----------------------------
# LEVEL SYSTEM
# -----------------------------
def draw_hits_and_level():
    # unten rechts: Treffer
    t1 = f"Treffer: {hits}"
    img1 = font30.render(t1, True, white)
    screen.blit(img1, (screen_width - img1.get_width() - 10, screen_height - img1.get_height() - 10))

    if combo_multiplier > 1:
        c_text = f"COMBO x{combo_multiplier}!"
        # pulsieren
        c_color = (255, random.randint(150, 255), 0)
        img_c = font40.render(c_text, True, c_color)
        screen.blit(img_c, (screen_width - img_c.get_width() - 10, screen_height - img_c.get_height() - 50))

    # unten links: Level
    t2 = f"Level: {level}"
    img2 = font30.render(t2, True, white)
    screen.blit(img2, (10, screen_height - img2.get_height() - 10))

def clear_level_objects():
    bullet_group.empty()
    alien_group.empty()
    alien_bullet_group.empty()
    boss_group.empty()
    explosion_group.empty()
    powerup_group.empty()
    particle_group.empty()
    # Also reuse alien_bullet_group for asteroids for simplicity


def create_aliens(rows, cols, speed):
    # grid
    start_x = 100
    start_y = 120
    x_gap = 90
    y_gap = 65

    for r in range(rows):
        for c in range(cols):
            alien = Aliens(start_x + c * x_gap, start_y + r * y_gap, speed=speed)
            alien_group.add(alien)

def start_level(new_level):
    global level, countdown, last_count, game_over, alien_cooldown, last_alien_shot
    level = new_level
    game_over = 0

    # countdown reset
    countdown = 3
    last_count = pygame.time.get_ticks()

    # clear bullets/aliens/boss from old level
    clear_level_objects()

    # difficulty scaling
    # Level 1..4: mehr Aliens, schneller, schnelleres Schießen
    if level < 4:
        base_rows = 4
        base_cols = 5
        rows = min(7, base_rows + (level - 1))     # max 7
        cols = min(8, base_cols + (level - 1))     # max 8
        alien_speed = 1 + (level - 1) // 2         # 1,1,2,2...
        create_aliens(rows, cols, speed=alien_speed)

        alien_cooldown = max(250, 1000 - (level - 1) * 150)  # schneller pro level
        last_alien_shot = pygame.time.get_ticks()

    # ab Level 5: Boss
    else:
        # Boss wird pro Level stärker
        boss_health = 20 + (level - 5) * 10
        boss_speed = 3 + (level - 5) // 2

        boss = Boss(screen_width // 2, 140, health=boss_health, move_speed=boss_speed)
        # Boss schießt pro Level etwas schneller
        boss.shot_cooldown = max(250, 700 - (level - 5) * 60)

        boss_group.add(boss)

        # auch alien_cooldown egal, aber lassen wir sinnvoll:
        alien_cooldown = 999999

# -----------------------------
# PLAYER CREATE & SCREENS
# -----------------------------
spaceship = None

def reset_game():
    global hits, level, game_over, spaceship
    hits = 0
    spaceship_group.empty()
    bullet_group.empty()
    alien_group.empty()
    alien_bullet_group.empty()
    boss_group.empty()
    explosion_group.empty()
    
    spaceship = Spaceship(screen_width // 2, screen_height - 100, 3)
    spaceship_group.add(spaceship)
    powerup_group.empty()
    particle_group.empty()
    start_level(1)

def draw_menu():
    draw_text("SPACE INVADERS", font40, white, screen_width // 2 - 150, 100)
    draw_text("Press SPACE to Start", font30, green, screen_width // 2 - 140, 200)
    
    draw_text("LEADERBOARD", font40, (255, 215, 0), screen_width // 2 - 120, 300)
    y = 360
    for i, entry in enumerate(highscores[:10]):
        rank_text = f"{i+1}."
        name_text = entry.get("name", "---")
        score_text = str(entry.get("score", 0))
        
        draw_text(rank_text, font30, white, screen_width // 2 - 150, y)
        draw_text(name_text, font30, white, screen_width // 2 - 70, y)
        draw_text(score_text, font30, white, screen_width // 2 + 80, y)
        y += 40

def draw_name_entry():
    if game_over == 1:
        draw_text("YOU WIN!", font40, green, screen_width // 2 - 90, 150)
    else:
        draw_text("GAME OVER", font40, red, screen_width // 2 - 110, 150)
        
    draw_text(f"Your Score: {hits}", font30, white, screen_width // 2 - 90, 250)
    draw_text("Enter Name:", font30, white, screen_width // 2 - 80, 350)
    draw_text(player_name + "_", font40, (255, 215, 0), screen_width // 2 - 50, 420)
    draw_text("Press ENTER to Save", font30, green, screen_width // 2 - 130, 520)

# -----------------------------
# MAIN LOOP
# -----------------------------
run = True
while run:
    clock.tick(fps)
    draw_bg()

    if game_state == "menu":
        draw_menu()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    reset_game()
                    game_state = "playing"
                if event.key == pygame.K_ESCAPE:
                    run = False

    elif game_state == "name_entry":
        draw_name_entry()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    name_to_save = player_name.strip()
                    if name_to_save == "":
                        name_to_save = "AAA"
                    save_highscore(name_to_save, hits)
                    highscores = load_highscores()
                    player_name = ""
                    game_state = "menu"
                elif event.key == pygame.K_BACKSPACE:
                    player_name = player_name[:-1]
                elif event.key == pygame.K_ESCAPE:
                    run = False
                else:
                    if len(player_name) < 10 and event.unicode.isprintable():
                        player_name += event.unicode

    elif game_state == "playing":
        draw_hits_and_level()

        # Wenn Player tot oder Boss tot, nichts weiter updaten
        if game_over == 0:
            # Tick combo timer
            if combo_timer > 0:
                combo_timer -= 1
                if combo_timer <= 0:
                    combo_multiplier = 1
                    combo_kills = 0

            # Countdown Phase
            if countdown > 0:
                draw_text("GET READY!", font40, white, screen_width // 2 - 110, screen_height // 2 + 50)
                draw_text(str(countdown), font40, white, screen_width // 2 - 10, screen_height // 2 + 100)

                count_timer = pygame.time.get_ticks()
                if count_timer - last_count > 1000:
                    countdown -= 1
                    last_count = count_timer

            # Gameplay Phase
            else:
                if level < 5:
                    time_now = pygame.time.get_ticks()
                    if (
                        time_now - last_alien_shot > alien_cooldown
                        and len(alien_bullet_group) < 5
                        and len(alien_group) > 0
                    ):
                        attacking_alien = random.choice(alien_group.sprites())
                        alien_bullet = Alien_Bullets(attacking_alien.rect.centerx, attacking_alien.rect.bottom, speed=3, damage=1)
                        alien_bullet_group.add(alien_bullet)
                        last_alien_shot = time_now

                    if len(alien_group) == 0:
                        start_level(level + 1)
                        
                    # Spawn Asteroids randomly
                    if level > 2 and random.random() < 0.01:
                        asteroid = Asteroid(random.randint(0, screen_width), -50)
                        alien_bullet_group.add(asteroid)
                else:
                    if len(boss_group) == 0:
                        game_over = 1

                if game_over == 0 and spaceship:
                    game_over = spaceship.update()

                    bullet_group.update()
                    alien_group.update()
                    boss_group.update()
                    alien_bullet_group.update()

        explosion_group.update()
        powerup_group.update()
        particle_group.update()

        # draw all sprites
        spaceship_group.draw(screen)
        bullet_group.draw(screen)
        alien_group.draw(screen)
        boss_group.draw(screen)
        alien_bullet_group.draw(screen)
        explosion_group.draw(screen)
        powerup_group.draw(screen)
        particle_group.draw(screen)

        # end screens (inside playing state)
        if game_over == -1:
            draw_text("GAME OVER!", font40, white, screen_width // 2 - 120, screen_height // 2 + 50)
            draw_text("Drueck LEERTASTE zum Fortfahren", font30, white, screen_width // 2 - 220, screen_height // 2 + 100)

        if game_over == 1:
            draw_text("YOU WIN!", font40, white, screen_width // 2 - 90, screen_height // 2 + 50)
            draw_text("Drueck LEERTASTE zum Fortfahren", font30, white, screen_width // 2 - 220, screen_height // 2 + 100)

        # events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    run = False
                # If game is over, Space takes us to name entry
                if game_over != 0 and event.key == pygame.K_SPACE:
                    game_state = "name_entry"

    # Screen Shake application
    if screen_shake > 0:
        shake_x = random.randint(-screen_shake, screen_shake)
        shake_y = random.randint(-screen_shake, screen_shake)
        # To avoid black borders, we don't scale up, we just get artifacts at edges, or we draw to a surface and blit.
        # Quick and dirty: Just offset everything already drawn!
        screen_copy = screen.copy()
        screen.fill((0, 0, 0))
        screen.blit(screen_copy, (shake_x, shake_y))
        screen_shake -= 1

    pygame.display.update()

pygame.quit()
