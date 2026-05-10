

import pygame
import random
import math
import sys
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

WIDTH, HEIGHT = 1200, 700
FPS = 60
GRAVITY = 0.15
TILE_SIZE = 40

COL = {
    "sky_top":    (10,  5,  20),
    "sky_bot":    (60, 20, 10),
    "mars_red":   (180, 70, 30),
    "mars_dark":  (120, 40, 15),
    "sand":       (210,130, 60),
    "rock":       (140, 80, 50),
    "hud_bg":     ( 10, 10, 20, 200),
    "hud_green":  ( 60,255,100),
    "hud_yellow": (255,220, 50),
    "hud_red":    (255, 60, 60),
    "white":      (255,255,255),
    "cyan":       ( 80,240,255),
    "orange":     (255,160, 30),
    "blue":       ( 40,120,255),
    "purple":     (180, 80,255),
    "dark":       ( 15, 10, 25),
    "panel":      ( 20, 15, 35),
}

pygame.font.init()
try:
    FONT_BIG   = pygame.font.SysFont("consolas", 64, bold=True)
    FONT_MED   = pygame.font.SysFont("consolas", 28, bold=True)
    FONT_SMALL = pygame.font.SysFont("consolas", 18)
    FONT_TINY  = pygame.font.SysFont("consolas", 14)
except:
    FONT_BIG   = pygame.font.Font(None, 64)
    FONT_MED   = pygame.font.Font(None, 28)
    FONT_SMALL = pygame.font.Font(None, 18)
    FONT_TINY  = pygame.font.Font(None, 14)

def lerp(a, b, t): return a + (b - a) * t
def clamp(v, lo, hi): return max(lo, min(hi, v))
def dist(a, b): return math.hypot(a[0]-b[0], a[1]-b[1])

def draw_rounded_rect(surf, color, rect, r=8, alpha=255):
    s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    pygame.draw.rect(s, (*color[:3], alpha), (0,0,rect[2],rect[3]), border_radius=r)
    surf.blit(s, (rect[0], rect[1]))

def draw_bar(surf, x, y, w, h, val, mx, color, bg=(30,30,50)):
    draw_rounded_rect(surf, bg, (x,y,w,h), 4)
    fw = int(w * clamp(val/mx, 0, 1))
    if fw > 4:
        draw_rounded_rect(surf, color, (x,y,fw,h), 4)

def text_shadow(surf, text, font, color, x, y, shadow=(0,0,0)):
    s = font.render(text, True, shadow)
    surf.blit(s, (x+2, y+2))
    s = font.render(text, True, color)
    surf.blit(s, (x, y))

class Particle:
    def __init__(self, x, y, vx, vy, color, life, size=3, gravity=0):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = vx, vy
        self.color = color
        self.life = self.max_life = life
        self.size = size
        self.gravity = gravity

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.vx *= 0.97
        self.life -= 1

    def draw(self, surf, cam_x=0):
        alpha = int(255 * self.life / self.max_life)
        s = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (self.size, self.size), self.size)
        surf.blit(s, (int(self.x - cam_x - self.size), int(self.y - self.size)))

    @property
    def alive(self): return self.life > 0

class ParticleSystem:
    def __init__(self):
        self.particles: List[Particle] = []

    def emit(self, x, y, color, count=6, speed=2, life=30, size=3, gravity=0.05):
        for _ in range(count):
            a = random.uniform(0, math.pi*2)
            sp = random.uniform(0.3, speed)
            self.particles.append(Particle(
                x, y, math.cos(a)*sp, math.sin(a)*sp,
                color, random.randint(life//2, life), size, gravity
            ))

    def emit_dir(self, x, y, color, dx, dy, spread=0.5, count=4, speed=2, life=20, size=2):
        for _ in range(count):
            a = math.atan2(dy, dx) + random.uniform(-spread, spread)
            sp = random.uniform(0.5, speed)
            self.particles.append(Particle(
                x, y, math.cos(a)*sp, math.sin(a)*sp,
                color, random.randint(life//2, life), size, 0.02
            ))

    def update(self):
        self.particles = [p for p in self.particles if p.alive]
        for p in self.particles:
            p.update()

    def draw(self, surf, cam_x=0):
        for p in self.particles:
            p.draw(surf, cam_x)

@dataclass
class Resources:
    oxygen: float = 100.0
    energy: float = 100.0
    minerals: int = 0
    water: int = 0
    score: int = 0
    o2_drain: float = 0.139

    max_oxygen: float = 100.0
    max_energy: float = 100.0

    def consume(self, oxygen=0.0, energy=0.0):
        self.oxygen = clamp(self.oxygen - oxygen, 0, self.max_oxygen)
        self.energy = clamp(self.energy - energy, 0, self.max_energy)

    def restore(self, oxygen=0.0, energy=0.0):
        self.oxygen = clamp(self.oxygen + oxygen, 0, self.max_oxygen)
        self.energy = clamp(self.energy + energy, 0, self.max_energy)

    @property
    def critical(self): return self.oxygen < 20 or self.energy < 15

    @property
    def dead(self): return self.oxygen <= 0 or self.energy <= 0

@dataclass
class Upgrade:
    name: str
    desc: str
    cost_minerals: int
    cost_water: int
    level: int = 0
    max_level: int = 3

    def can_buy(self, res: Resources) -> bool:
        return (self.level < self.max_level and
                res.minerals >= self.cost_minerals and
                res.water >= self.cost_water)

    def buy(self, res: Resources):
        if self.can_buy(res):
            res.minerals -= self.cost_minerals
            res.water    -= self.cost_water
            self.level   += 1
            return True
        return False

class Rover:
    W, H = 52, 32

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.facing = 1
        self.drill_active = False
        self.drill_timer = 0
        self.boost_timer = 0
        self.invincible = 0
        self.anim_timer = 0
        self.wheel_rot = 0.0
        self.shield_hp = 0
        self.engine_level = 0
        self.tank_level = 0

        self.speed = 3.5
        self.base_speed = 3.5
        self.in_sand = False
        self.jump_power = -6.0
        self.max_vy = 12.0

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.W//2), int(self.y - self.H//2), self.W, self.H)

    @property
    def cx(self): return self.x
    @property
    def cy(self): return self.y

    def apply_upgrade(self, upgrade: Upgrade):
        name = upgrade.name
        lv   = upgrade.level
        if name == "ENGINE":
            self.base_speed   = 3.5 + lv * 1.0
            self.speed        = self.base_speed
            self.jump_power   = -6.0 - lv * 0.8
            self.engine_level = lv
        elif name == "TANK":
            self.tank_level = lv
        elif name == "SHIELD":
            self.shield_hp  = lv * 40
            self.invincible = 0

    def update(self, keys, terrain_rects, cam_x, res: Resources):
        self.anim_timer += 1

        if not self.in_sand:
            self.speed = self.base_speed
        self.in_sand = False

        move = 0
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: move = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: move =  1
        if move:
            self.facing = move
            self.vx = move * self.speed
            if self.on_ground:
                res.consume(energy=0.02)
                self.wheel_rot += self.speed * move * 3
        else:
            self.vx *= 0.75

        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground:
            self.vy = self.jump_power
            self.on_ground = False
            res.consume(energy=0.5)

        self.vy += GRAVITY
        self.vy = clamp(self.vy, -20, self.max_vy)

        self._move_and_collide(terrain_rects)

        if self.drill_timer > 0: self.drill_timer -= 1
        if self.boost_timer > 0: self.boost_timer -= 1
        if self.invincible  > 0: self.invincible  -= 1

        res.consume(oxygen=res.o2_drain)

        self.x = clamp(self.x, self.W//2, WORLD_WIDTH - self.W//2)
        if self.y > HEIGHT + 100:
            self.y = HEIGHT - 80
            self.vy = 0
            res.consume(oxygen=10)

    def _move_and_collide(self, rects):
        self.x += self.vx
        r = self.rect
        for tr in rects:
            if r.colliderect(tr):
                if self.vx > 0: self.x = tr.left  - self.W//2
                elif self.vx < 0: self.x = tr.right + self.W//2
                self.vx = 0
        self.y += self.vy
        self.on_ground = False
        r = self.rect
        for tr in rects:
            if r.colliderect(tr):
                if self.vy > 0:
                    self.y = tr.top - self.H//2
                    self.on_ground = True
                elif self.vy < 0:
                    self.y = tr.bottom + self.H//2
                self.vy = 0

    def draw(self, surf, cam_x, ps: ParticleSystem, res: Resources):
        sx = int(self.x - cam_x)
        sy = int(self.y)
        hw, hh = self.W//2, self.H//2

        if self.invincible > 0 and (self.invincible % 6 < 3):
            return
        if self.shield_hp > 0:
            r2 = int(max(self.W, self.H)//2 + 6)
            s = pygame.Surface((r2*2+2, r2*2+2), pygame.SRCALPHA)
            pygame.draw.circle(s, (80, 180, 255, 60), (r2+1, r2+1), r2)
            pygame.draw.circle(s, (80, 180, 255, 120), (r2+1, r2+1), r2, 2)
            surf.blit(s, (sx - r2 - 1, sy - r2 - 1))

        body_col = (70, 130, 180) if self.engine_level == 0 else (
                   (100,180, 80) if self.engine_level == 1 else
                   (200,150, 30) if self.engine_level == 2 else (220, 80, 80))
        pygame.draw.rect(surf, body_col,
                         (sx - hw + 4, sy - hh + 2, self.W - 8, self.H - 8), border_radius=6)
        pygame.draw.rect(surf, (200,220,255),
                         (sx - hw + 4, sy - hh + 2, self.W - 8, self.H - 8), 2, border_radius=6)

        cab_x = sx + self.facing * 4
        pygame.draw.ellipse(surf, (60,200,240),
                            (cab_x - 10, sy - hh - 8, 20, 14))
        pygame.draw.ellipse(surf, (200,240,255),
                            (cab_x - 10, sy - hh - 8, 20, 14), 2)

        pygame.draw.line(surf, (255,200,0),
                         (sx + self.facing * 8, sy - hh + 2),
                         (sx + self.facing * 16, sy - hh - 12), 2)
        pygame.draw.circle(surf, (255,100,0),
                           (sx + self.facing * 16, sy - hh - 12), 3)

        if self.drill_active or self.drill_timer > 0:
            d_len = 18
            dx = sx + self.facing * hw
            pygame.draw.polygon(surf, (200,200,50), [
                (dx, sy - 4),
                (dx, sy + 4),
                (dx + self.facing * d_len, sy)
            ])
            pygame.draw.line(surf, (255,220,0),
                             (dx, sy), (dx + self.facing * d_len, sy), 1)

        wheel_y = sy + hh - 4
        for wx in [sx - hw + 8, sx, sx + hw - 8]:
            pygame.draw.circle(surf, (50, 50, 60), (wx, wheel_y), 9)
            pygame.draw.circle(surf, (90, 90,100), (wx, wheel_y), 9, 2)
            angle = math.radians(self.wheel_rot % 360)
            for i in range(4):
                a = angle + i * math.pi/2
                ex = int(wx + math.cos(a) * 7)
                ey = int(wheel_y + math.sin(a) * 7)
                pygame.draw.line(surf, (130,130,140), (wx, wheel_y), (ex, ey), 2)

        if abs(self.vx) > 0.5:
            ex = sx - self.facing * hw
            for _ in range(2):
                ps.particles.append(Particle(
                    self.x - self.facing * hw, self.y + 8,
                    -self.facing * random.uniform(0.5,2.0),
                    random.uniform(-0.5, 0.5),
                    random.choice([(255,150,30),(255,80,0),(200,200,200)]),
                    random.randint(8,18), random.randint(2,4), 0
                ))

class Collectible:
    def __init__(self, x, y, kind="mineral"):
        self.x, self.y = float(x), float(y)
        self.kind = kind
        self.alive = True
        self.bob = random.uniform(0, math.pi*2)
        self.size = 10 if kind == "mineral" else 8

    @property
    def rect(self): return pygame.Rect(int(self.x)-self.size, int(self.y)-self.size,
                                       self.size*2, self.size*2)

    def update(self): self.bob += 0.05

    def draw(self, surf, cam_x, rover_x=None, rover_y=None):
        sx = int(self.x - cam_x)
        sy = int(self.y + math.sin(self.bob) * 4)
        if rover_x is not None:
            d = dist((self.x, self.y), (rover_x, rover_y))
            if d < 120:
                glow_r = int(self.size + 10 + 4 * math.sin(self.bob * 3))
                s = pygame.Surface((glow_r*2, glow_r*2), pygame.SRCALPHA)
                a = int(120 * (1 - d/120))
                gc = (80,240,255,a) if self.kind=="water" else (220,140,255,a)
                pygame.draw.circle(s, gc, (glow_r, glow_r), glow_r)
                surf.blit(s, (sx - glow_r, sy - glow_r))
        if self.kind == "mineral":
            pts = []
            for i in range(6):
                a = math.radians(i*60 - 30)
                pts.append((int(sx + math.cos(a)*self.size),
                            int(sy + math.sin(a)*self.size)))
            pygame.draw.polygon(surf, (180, 80, 255), pts)
            pygame.draw.polygon(surf, (220,140,255), pts, 2)
            pygame.draw.circle(surf, (255,220,255), (sx-3, sy-3), 2)
        else:
            pygame.draw.circle(surf, (40,140,255), (sx, sy), self.size)
            pygame.draw.circle(surf, (100,200,255), (sx, sy), self.size, 2)
            pygame.draw.circle(surf, (200,230,255), (sx-3, sy-3), 3)
        col = (220,140,255) if self.kind=="mineral" else (100,200,255)
        lbl = FONT_TINY.render("+" + ("MIN" if self.kind=="mineral" else "H₂O"), True, col)
        surf.blit(lbl, (sx - lbl.get_width()//2, sy - self.size - 16))

class Hazard:
    """Базовий клас загрози"""
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.alive = True

    def update(self, rover: Rover, res: Resources, ps: ParticleSystem): pass
    def draw(self, surf, cam_x): pass

class DustStorm(Hazard):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.vx = random.uniform(-4, -1.5)
        self.w = random.randint(160, 320)
        self.h = random.randint(60, 120)
        self.alpha = random.randint(80, 160)
        self.lifetime = random.randint(300, 600)
        self.timer = 0

    def update(self, rover, res, ps):
        self.x += self.vx
        self.timer += 1
        if self.timer > self.lifetime or self.x + self.w < 0:
            self.alive = False
        r = pygame.Rect(int(self.x), int(self.y), self.w, self.h)
        if r.colliderect(rover.rect):
            res.consume(oxygen=0.08, energy=0.05)
            rover.vx += self.vx * 0.15
        if random.random() < 0.3:
            ps.particles.append(Particle(
                self.x + random.randint(0, self.w),
                self.y + random.randint(0, self.h),
                self.vx * 0.8, random.uniform(-0.3, 0.3),
                (200, 120, 50), random.randint(20,50),
                random.randint(3,8), 0
            ))

    def draw(self, surf, cam_x):
        sx = int(self.x - cam_x)
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for i in range(6):
            a = int(self.alpha * (1 - i/6))
            pygame.draw.rect(s, (200, 120, 50, a//2),
                             (i*4, i*4, self.w-i*8, self.h-i*8), border_radius=20)
        surf.blit(s, (sx, int(self.y)))
        lbl = FONT_TINY.render(" DUST STORM", True, (255,200,80))
        surf.blit(lbl, (sx + self.w//2 - lbl.get_width()//2, int(self.y) - 16))

class Meteor(Hazard):
    def __init__(self, x):
        super().__init__(x, -20)
        self.vx = random.uniform(-1.5, 0.5)
        self.vy = random.uniform(4, 7)
        self.size = random.randint(8, 22)
        self.trail: List[Tuple] = []

    def update(self, rover, res, ps):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 12: self.trail.pop(0)
        self.x += self.vx
        self.y += self.vy
        if self.y > HEIGHT + 50: self.alive = False
        if dist((self.x, self.y), (rover.cx, rover.cy)) < self.size + 20:
            if rover.invincible == 0:
                if rover.shield_hp > 0:
                    rover.shield_hp -= 30
                    rover.invincible = 60
                else:
                    res.consume(oxygen=15, energy=20)
                    rover.invincible = 90
                ps.emit(self.x, self.y, (255,180,0), count=20, speed=5, life=40, size=5, gravity=0.1)
                self.alive = False

    def draw(self, surf, cam_x):
        for i, (tx, ty) in enumerate(self.trail):
            alpha = int(200 * i / len(self.trail))
            r = max(1, self.size - (len(self.trail)-i)//2)
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 140, 30, alpha), (r,r), r)
            surf.blit(s, (int(tx - cam_x - r), int(ty - r)))
        sx = int(self.x - cam_x)
        pygame.draw.circle(surf, (220, 80, 20), (sx, int(self.y)), self.size)
        pygame.draw.circle(surf, (255,200,100), (sx, int(self.y)), self.size//2)
        pygame.draw.circle(surf, (255,255,200), (sx - self.size//3, int(self.y) - self.size//3), 3)

class OxygenDepo(Hazard):
    """Станція поповнення кисню"""
    def __init__(self, x, y):
        super().__init__(x, y)
        self.charge = 100
        self.pulse = 0
        self.used = False

    def update(self, rover, res, ps):
        self.pulse += 0.07
        r = pygame.Rect(int(self.x) - 20, int(self.y) - 30, 40, 60)
        if r.colliderect(rover.rect) and self.charge > 0:
            amount = min(2.0, self.charge)
            res.restore(oxygen=amount)
            self.charge -= amount
            if self.charge <= 0:
                self.charge = 0
            ps.emit_dir(self.x, self.y - 20, (100,230,255),
                        0, -1, spread=0.8, count=2, speed=1.5, life=25)

    def draw(self, surf, cam_x):
        sx = int(self.x - cam_x)
        sy = int(self.y)
        pygame.draw.rect(surf, (60, 80, 100), (sx - 6, sy - 30, 12, 30))
        c = (0, 200, 200) if self.charge > 0 else (80, 80, 80)
        pygame.draw.ellipse(surf, c, (sx - 14, sy - 44, 28, 18))
        pygame.draw.ellipse(surf, (200, 255, 255), (sx - 14, sy - 44, 28, 18), 2)
        if self.charge > 0:
            pr = int(20 + math.sin(self.pulse) * 6)
            s = pygame.Surface((pr*2, pr*2), pygame.SRCALPHA)
            a = int(60 + math.sin(self.pulse)*40)
            pygame.draw.circle(s, (0,200,200,a), (pr,pr), pr, 3)
            surf.blit(s, (sx - pr, sy - 35 - pr))
        lbl = FONT_TINY.render(f"O₂ {int(self.charge)}%", True, (0,220,220))
        surf.blit(lbl, (sx - lbl.get_width()//2, sy - 58))

class Battery:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.alive = True
        self.bob = random.uniform(0, math.pi * 2)

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - 10, int(self.y) - 12, 20, 24)

    def update(self):
        self.bob += 0.06

    def draw(self, surf, cam_x):
        sx = int(self.x - cam_x)
        sy = int(self.y + math.sin(self.bob) * 4)
        pygame.draw.rect(surf, (50, 200, 80), (sx - 9, sy - 10, 18, 20), border_radius=3)
        pygame.draw.rect(surf, (100, 255, 130), (sx - 9, sy - 10, 18, 20), 2, border_radius=3)
        pygame.draw.rect(surf, (180, 255, 180), (sx - 4, sy - 14, 8, 5), border_radius=2)
        pts = [(sx, sy - 6), (sx - 4, sy + 1), (sx, sy + 1), (sx, sy + 7), (sx + 4, sy), (sx, sy)]
        pygame.draw.polygon(surf, (255, 255, 100), pts)
        lbl = FONT_TINY.render("+", True, (100, 255, 130))
        surf.blit(lbl, (sx - lbl.get_width() // 2, sy - 26))

class PishanaPastyaka(Hazard):
    def __init__(self, x, y, width=200):
        super().__init__(x, y)
        self.width = width
        self.height = 22
        self.is_active = False
        self.sand_drain = 0.04
        self.hidden = False

    def update(self, rover, res, ps):
        trap_rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)
        if trap_rect.colliderect(rover.rect):
            self.is_active = True
            rover.in_sand = True
            rover.speed = rover.base_speed * 0.35
            res.consume(energy=self.sand_drain)
            if random.random() < 0.35:
                ps.emit(rover.cx, rover.cy + 14,
                        (210, 130, 60), count=2, speed=1, life=18, size=3)
        else:
            self.is_active = False

    def draw(self, surf, cam_x):
        sx = int(self.x - cam_x)
        if sx > WIDTH + self.width or sx + self.width < 0:
            return
        if self.hidden and not self.is_active:
            return
        col = (255, 200, 0) if self.is_active else (210, 150, 40)
        pygame.draw.rect(surf, col,
                         (sx, int(self.y), self.width, self.height), border_radius=4)
        for i in range(0, self.width, 18):
            pygame.draw.line(surf, (160, 100, 20),
                             (sx + i, int(self.y)),
                             (sx + i + 9, int(self.y) + self.height), 2)
        if not self.hidden:
            lbl = FONT_TINY.render("~ ПІСОК ~", True, (120, 70, 10))
            surf.blit(lbl, (sx + self.width // 2 - lbl.get_width() // 2, int(self.y) - 16))


class GiantAsteroid(Hazard):
    def __init__(self, x):
        super().__init__(x, -60)
        self.vx = random.uniform(-0.5, 0.5)
        self.vy = random.uniform(2.5, 4.0)
        self.size = random.randint(38, 55)
        self.trail = []
        self.exploded = False
        self.shards = []

    def update(self, rover, res, ps, terrain_rects=None):
        if terrain_rects is None: terrain_rects = []
        if self.exploded:
            for s in self.shards:
                s[0] += s[2]
                s[1] += s[3]
                s[3] += 0.2
                s[4] -= 1
                if s[4] > 0 and dist((s[0], s[1]), (rover.cx, rover.cy)) < 28:
                    if rover.invincible == 0:
                        res.consume(energy=5.0)
                        rover.invincible = 30
            self.shards = [s for s in self.shards if s[4] > 0]
            if not self.shards:
                self.alive = False
            return
        self.trail.append((self.x, self.y))
        if len(self.trail) > 18: self.trail.pop(0)
        self.x += self.vx
        self.y += self.vy
        for tr in terrain_rects:
            if tr.colliderect(pygame.Rect(int(self.x)-self.size, int(self.y)-self.size,
                                          self.size*2, self.size*2)):
                self._explode(rover, res, ps)
                return
        if self.y > HEIGHT + 200:
            self.alive = False
        if dist((self.x, self.y), (rover.cx, rover.cy)) < self.size + 20:
            if rover.invincible == 0:
                res.consume(oxygen=25, energy=30)
                rover.invincible = 120
            self._explode(rover, res, ps)

    def _explode(self, rover, res, ps):
        self.exploded = True
        ps.emit(self.x, self.y, (255, 160, 30), count=35, speed=8, life=60, size=6, gravity=0.15)
        ps.emit(self.x, self.y, (255, 80, 0),   count=20, speed=5, life=45, size=4, gravity=0.1)
        for _ in range(12):
            angle = random.uniform(0, math.pi * 2)
            spd   = random.uniform(3, 9)
            life  = random.randint(60, 120)
            self.shards.append([
                self.x, self.y,
                math.cos(angle) * spd, math.sin(angle) * spd - 2,
                life, random.randint(6, 14)
            ])

    def draw(self, surf, cam_x):
        if self.exploded:
            for s in self.shards:
                sx2 = int(s[0] - cam_x)
                sy2 = int(s[1])
                a = int(255 * s[4] / 120)
                pygame.draw.circle(surf, (180, 90, 40), (sx2, sy2), s[5])
            return
        for i, (tx, ty) in enumerate(self.trail):
            r = max(1, self.size - (len(self.trail)-i)//2)
            alpha = int(180 * i / max(len(self.trail),1))
            sv = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(sv, (255, 120, 30, alpha), (r, r), r)
            surf.blit(sv, (int(tx - cam_x - r), int(ty - r)))
        sx = int(self.x - cam_x)
        pygame.draw.circle(surf, (160, 70, 20), (sx, int(self.y)), self.size)
        pygame.draw.circle(surf, (220, 120, 50), (sx, int(self.y)), self.size // 2)
        pygame.draw.circle(surf, (255, 200, 100), (sx - self.size//3, int(self.y) - self.size//3), 5)
        wt = FONT_SMALL.render("АСТЕРОЇД!", True, (255, 80, 0))
        surf.blit(wt, (sx - wt.get_width()//2, int(self.y) - self.size - 22))


WORLD_WIDTH = 15000

def generate_terrain():
    """Генерує поверхню Марса та повертає (rects, height_map, surface_points)"""
    seg = 40
    heights = []
    h = 440
    for i in range(WORLD_WIDTH // seg + 1):
        h += random.uniform(-18, 18)
        h = clamp(h, 340, 560)
        heights.append(h)

    rects = []
    pts = []
    for i, hy in enumerate(heights):
        x = i * seg
        pts.append((x, hy))
        rect = pygame.Rect(x, int(hy), seg, HEIGHT - int(hy) + 10)
        rects.append(rect)
    return rects, heights, pts

def draw_terrain(surf, cam_x, heights, pts):
    seg = 40
    sky = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(lerp(10, 60, t))
        g = int(lerp( 5, 20, t))
        b = int(lerp(20, 10, t))
        pygame.draw.line(sky, (r,g,b), (0,y), (WIDTH,y))
    surf.blit(sky, (0,0))

    random.seed(42)
    for _ in range(120):
        sx = random.randint(0, WIDTH)
        sy = random.randint(0, 200)
        br = random.randint(100,255)
        pygame.draw.circle(surf, (br,br,br), (sx, sy), 1)
    random.seed()

    visible_i0 = max(0, int(cam_x / seg) - 1)
    visible_i1 = min(len(heights)-1, int((cam_x + WIDTH) / seg) + 2)

    poly = [(0, HEIGHT)]
    for i in range(visible_i0, visible_i1 + 1):
        x = i * seg - int(cam_x)
        y = heights[i]
        poly.append((x, y))
    poly.append((WIDTH, HEIGHT))

    if len(poly) > 3:
        pygame.draw.polygon(surf, COL["mars_red"], poly)
        for i in range(visible_i0, visible_i1):
            x0 = i * seg - int(cam_x)
            x1 = (i+1) * seg - int(cam_x)
            pygame.draw.line(surf, COL["sand"],
                             (x0, int(heights[i])), (x1, int(heights[i+1])), 3)

    random.seed(12345)
    for _ in range(60):
        rx = random.randint(0, WORLD_WIDTH - 80)
        ri = clamp(rx // seg, 0, len(heights)-1)
        ry = int(heights[ri]) - random.randint(4, 14)
        rw = random.randint(10, 30)
        rh = random.randint(6, 16)
        sx = rx - int(cam_x)
        if -rw < sx < WIDTH + rw:
            col = random.choice([COL["rock"], COL["mars_dark"], (160, 90, 60)])
            pygame.draw.ellipse(surf, col, (sx, ry, rw, rh))
    random.seed()

class HUD:
    def __init__(self):
        self.warn_alpha = 0
        self.warn_msg = ""
        self.warn_timer = 0
        self.msg_queue: List[Tuple] = []

    def warn(self, msg, color=(255, 80, 80)):
        self.warn_msg = msg
        self.warn_timer = 120

    def add_msg(self, text, color=(255,255,255)):
        self.msg_queue.append([text, color, 90])

    def update(self):
        if self.warn_timer > 0: self.warn_timer -= 1
        self.msg_queue = [[t, c, ti-1] for t,c,ti in self.msg_queue if ti > 0]

    def draw(self, surf, res: Resources, rover: Rover, hazards, level, dist,
             goal, infinite=False, roguelike=False, next_card=5000, chosen_cards=None):
        draw_rounded_rect(surf, (15,10,30), (10,10,210,120), 10, 200)
        oc = COL["hud_green"] if res.oxygen > 40 else COL["hud_yellow"] if res.oxygen > 20 else COL["hud_red"]
        text_shadow(surf, f"O₂  {res.oxygen:5.1f}%", FONT_SMALL, oc, 18, 18)
        draw_bar(surf, 18, 42, 190, 12, res.oxygen, res.max_oxygen, oc)
        ec = COL["hud_green"] if res.energy > 40 else COL["hud_yellow"] if res.energy > 20 else COL["hud_red"]
        text_shadow(surf, f"  {res.energy:5.1f}%", FONT_SMALL, ec, 18, 62)
        draw_bar(surf, 18, 84, 190, 12, res.energy, res.max_energy, ec)
        text_shadow(surf, f"{res.minerals:3d}  {res.water:3d}", FONT_SMALL, (200,180,255), 18, 104)

        draw_rounded_rect(surf, (15,10,30), (WIDTH//2-165, 10, 330, 40), 8, 200)
        if roguelike:
            left_c = max(0, next_card - dist)
            text_shadow(surf, f" ROGUELIKE  {dist}м   за {left_c}м картка",
                        FONT_SMALL, (255,200,80), WIDTH//2-155, 20)
        elif infinite:
            text_shadow(surf, f" БЕЗКІНЕЧНИЙ  {dist}м", FONT_SMALL, (100,220,255), WIDTH//2-155, 20)
        else:
            left = max(0, goal - dist)
            text_shadow(surf, f" ДЕНЬ {level}/3   {left}м до фінішу", FONT_SMALL, (220,220,255), WIDTH//2-155, 20)

        if roguelike and chosen_cards:
            cx2 = WIDTH - 10
            for card in reversed(chosen_cards[-8:]):
                rc = RARITY_COLOR[card.rarity]
                ic = FONT_TINY.render(card.name[:8], True, rc)
                cx2 -= ic.get_width() + 6
                draw_rounded_rect(surf, (20,15,40), (cx2-2, 56, ic.get_width()+4, 18), 3, 200)
                pygame.draw.rect(surf, rc, (cx2-2, 56, ic.get_width()+4, 18), 1, border_radius=3)
                surf.blit(ic, (cx2, 58))

        if rover.shield_hp > 0:
            draw_rounded_rect(surf, (15,10,50), (WIDTH-160, 10, 150, 40), 8, 200)
            text_shadow(surf, f" {rover.shield_hp}", FONT_SMALL, (80,180,255), WIDTH-150, 20)

        if self.warn_timer > 0:
            a = min(255, self.warn_timer * 4)
            s = pygame.Surface((WIDTH, 40), pygame.SRCALPHA)
            s.fill((255,30,30, int(a*0.4)))
            surf.blit(s, (0, HEIGHT//2 - 20))
            wt = FONT_MED.render(f"  {self.warn_msg}  ", True, (255, 80, 80))
            surf.blit(wt, (WIDTH//2 - wt.get_width()//2, HEIGHT//2 - 14))

        for i, (text, color, timer) in enumerate(reversed(self.msg_queue[-4:])):
            a = min(255, timer * 4)
            s = FONT_SMALL.render(text, True, color)
            sa = pygame.Surface(s.get_size(), pygame.SRCALPHA)
            sa.fill((0,0,0,0))
            sa.blit(s, (0,0))
            sa.set_alpha(a)
            surf.blit(sa, (WIDTH - s.get_width() - 20, HEIGHT - 60 - i*26))

        hints = [("←→/AD", "рух"), ("SPC/W", "стрибок"), ("E", "бур"), ("TAB", "апгрейди"), ("Z", "ачівки")]
        x = 10
        for key, act in hints:
            draw_rounded_rect(surf, (40,40,70), (x, HEIGHT-34, 80, 24), 4, 180)
            t = FONT_TINY.render(f"{key}: {act}", True, (200,200,255))
            surf.blit(t, (x+4, HEIGHT-30))
            x += 88

    def draw_achievement_strip(self, surf, achievements):
        """Постійна смужка іконок розблокованих ачівок під ресурсами"""
        unlocked = [a for a in achievements if a.unlocked]
        if not unlocked:
            return
        draw_rounded_rect(surf, (15,10,30), (10, 136, len(unlocked)*28 + 8, 28), 6, 180)
        for i, a in enumerate(unlocked):
            ic = FONT_SMALL.render(a.icon, True, a.color)
            surf.blit(ic, (14 + i*28, 140))

class UpgradeScreen:
    def __init__(self):
        self.visible = False
        self.selected = 0
        self.upgrades = [
            Upgrade("ENGINE", "Двигун: +швидкість +стрибок",  cost_minerals=10, cost_water=5),
            Upgrade("TANK",   "Бак кисню: +ємність",          cost_minerals=5,  cost_water=10),
            Upgrade("SHIELD", "Щит: захист від метеоритів",   cost_minerals=15, cost_water=8),
            Upgrade("DRILL",  "Бур: більше мінералів",        cost_minerals=8,  cost_water=3),
        ]
        self.last_key_time = 0

    def toggle(self): self.visible = not self.visible

    def handle_key(self, event, res: Resources, rover: Rover, hud: HUD):
        if not self.visible: return
        if event.key == pygame.K_UP or event.key == pygame.K_w:
            self.selected = (self.selected - 1) % len(self.upgrades)
        elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
            self.selected = (self.selected + 1) % len(self.upgrades)
        elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
            up = self.upgrades[self.selected]
            if up.buy(res):
                rover.apply_upgrade(up)
                hud.add_msg(f" {up.name} Lv{up.level} встановлено!", (100,255,150))
            else:
                hud.add_msg(" Недостатньо ресурсів!", (255,80,80))

    def draw(self, surf, res: Resources):
        if not self.visible: return
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        s.fill((5, 5, 20, 200))
        surf.blit(s, (0,0))
        wx, wy, ww, wh = WIDTH//2-280, HEIGHT//2-180, 560, 380
        draw_rounded_rect(surf, (20,15,40), (wx,wy,ww,wh), 16, 240)
        pygame.draw.rect(surf, (80,60,160), (wx,wy,ww,wh), 2, border_radius=16)
        text_shadow(surf, " ЦЕНТР АПГРЕЙДІВ ", FONT_MED, (180,140,255), wx+140, wy+16)
        text_shadow(surf, f" {res.minerals}   {res.water}", FONT_SMALL, (220,200,255), wx+20, wy+52)
        for i, up in enumerate(self.upgrades):
            iy = wy + 90 + i * 66
            sel = i == self.selected
            bg = (50,40,100) if sel else (25,20,50)
            draw_rounded_rect(surf, bg, (wx+10, iy, ww-20, 58), 10, 220)
            if sel:
                pygame.draw.rect(surf, (130,90,255),
                                 (wx+10, iy, ww-20, 58), 2, border_radius=10)
            col = (255,220,80) if sel else (200,180,255)
            text_shadow(surf, f"{up.name}  Lv{up.level}/{up.max_level}", FONT_SMALL, col, wx+22, iy+8)
            text_shadow(surf, up.desc, FONT_TINY, (160,160,200), wx+22, iy+32)
            can = up.can_buy(res)
            cc = (100,255,150) if can else (200,80,80)
            pc = f"{up.cost_minerals}  {up.cost_water}"
            if up.level >= up.max_level:
                pc = " MAX"
                cc = (80,255,80)
            ct = FONT_SMALL.render(pc, True, cc)
            surf.blit(ct, (wx + ww - ct.get_width() - 20, iy + 18))
        text_shadow(surf, "↑↓ вибір   ENTER/SPC купити   TAB закрити", FONT_TINY,
                    (120,120,180), wx + 30, wy + wh - 28)

class Achievement:
    def __init__(self, key, name, desc, icon, color=(255,220,80)):
        self.key   = key
        self.name  = name
        self.desc  = desc
        self.icon  = icon
        self.color = color
        self.unlocked = False
        self.popup_timer = 0

    def unlock(self):
        if not self.unlocked:
            self.unlocked = True
            self.popup_timer = 220

class AchievementSystem:
    def __init__(self):
        self.all = [
            Achievement("first_mineral",  "Перший кристал",    "Зібрати перший мінерал",         "", (180, 80,255)),
            Achievement("first_water",    "Водопостачання",    "Знайти першу воду",               "", ( 40,160,255)),
            Achievement("half_way",       "Півдорогою",        "Подолати 50% маршруту",           "", (100,255,150)),
            Achievement("minerals_20",    "Гірничий майстер",  "Назбирати 20 мінералів",          "", (220,140,255)),
            Achievement("sand_trap",      "В'язкий Марс",      "Потрапити в пісчану пастку",      "", (210,150, 40)),
            Achievement("full_upgrades",  "Повністю прокачаний","Купити будь-який апгрейд Lv3",   "", (255,100, 80)),
            Achievement("campaign_done",  "Герой Марса",       "Пройти всю кампанію (3 дні)",     "", (255,200,  0)),
            Achievement("inf_6000",       "Марафонець",        "Проїхати 6000м в безкінечному",   "",  ( 80,220,255)),
            Achievement("inf_20000",      "Довгий Шлях",       "Проїхати 20000м в безкінечному",  "", (120,180,255)),
            Achievement("inf_30000",      "Тридцять кiлометрiв","Проїхати 30000м в безкiнечному",  "", (160,200,255)),
            Achievement("inf_50000",      "Залізна Воля",      "Проїхати 50000м в безкінечному",  "", (255,220,100)),
            Achievement("inf_100000",     "Легенда Марса",     "Проїхати 100000м в безкін.",      "", (255,180,  0)),
            Achievement("cards_6",        "Колекціонер",       "Побачити 6 різних карт",          "", (180, 80,255)),
            Achievement("cards_15",       "Знавець",           "Побачити 15 різних карт",         "", (100,180,255)),
            Achievement("cards_24",       "Архіваріус",        "Побачити 24 різні карти",         "", (255,150, 50)),
            Achievement("cards_all",      "Повний Архів",      "Побачити всі карти в roguelike",  "", (255,220,  0)),
            Achievement("speed_day1",     "Спринтер (День 1)", "День 1 менше нiж за 1хв 10с",   "", (255,100,100)),
            Achievement("speed_day2",     "Спринтер (День 2)", "День 2 менше нiж за 1 хвилину", "", (255,120, 80)),
            Achievement("speed_day3",     "Спринтер (День 3)", "День 3 менше нiж за 55 секунд", "", (255,160, 40)),
        ]
        self._map = {a.key: a for a in self.all}
        self.seen_cards: set = set()

    def unlock(self, key: str, hud: HUD):
        a = self._map.get(key)
        if a and not a.unlocked:
            a.unlock()
            hud.add_msg(f" АЧІВКА: {a.name}!", a.color)

    def check_all(self, res: Resources, rover: Rover, game, hud: HUD):
        if res.minerals >= 1:
            self.unlock("first_mineral", hud)
        if res.minerals >= 20:
            self.unlock("minerals_20", hud)
        if res.water >= 1:
            self.unlock("first_water", hud)
        if game.dist_traveled >= game.goal_dist * 0.5:
            self.unlock("half_way", hud)
        for h in game.hazards:
            if isinstance(h, PishanaPastyaka) and h.is_active:
                self.unlock("sand_trap", hud)
        for up in game.upgrade_screen.upgrades:
            if up.level >= 3:
                self.unlock("full_upgrades", hud)
        if game.infinite_mode:
            if game.dist_traveled >= 6000:   self.unlock("inf_6000",   hud)
            if game.dist_traveled >= 20000:  self.unlock("inf_20000",  hud)
            if game.dist_traveled >= 30000:  self.unlock("inf_30000",  hud)
            if game.dist_traveled >= 50000:  self.unlock("inf_50000",  hud)
            if game.dist_traveled >= 100000: self.unlock("inf_100000", hud)
        sc = len(self.seen_cards)
        if sc >= 6:              self.unlock("cards_6",    hud)
        if sc >= 15:             self.unlock("cards_15",   hud)
        if sc >= 24:             self.unlock("cards_24",   hud)
        if sc >= len(ALL_CARDS): self.unlock("cards_all",  hud)

    def draw_popups(self, surf):
        active = [a for a in self.all if a.popup_timer > 0]
        for i, a in enumerate(active[:2]):
            a.popup_timer -= 1
            alpha = min(255, a.popup_timer * 3)
            py = HEIGHT - 90 - i * 64
            draw_rounded_rect(surf, (20,15,40), (WIDTH-310, py, 300, 54), 10, min(220, alpha))
            pygame.draw.rect(surf, a.color,
                             (WIDTH-310, py, 300, 54), 2, border_radius=10)
            icon_t = FONT_MED.render(a.icon, True, a.color)
            surf.blit(icon_t, (WIDTH-300, py + 12))
            name_t = FONT_SMALL.render(" " + a.name, True, a.color)
            surf.blit(name_t, (WIDTH-270, py + 6))
            desc_t = FONT_TINY.render(a.desc, True, (180,180,220))
            surf.blit(desc_t, (WIDTH-270, py + 30))

    def draw_screen(self, surf, from_menu=False, show_book=False,
                    book_sel=0, book_detail=False, scroll_y=0):
        surf.fill((5, 3, 15))
        random.seed(55)
        for _ in range(100):
            pygame.draw.circle(surf, (random.randint(40,120),)*3,
                               (random.randint(0,WIDTH), random.randint(0,HEIGHT)), 1)
        random.seed()

        wx, wy, ww = WIDTH//2 - 360, 20, 720
        inner_h = HEIGHT - 100
        draw_rounded_rect(surf, (18,13,35), (wx, wy, ww, inner_h), 14, 250)
        pygame.draw.rect(surf, (100,80,200), (wx, wy, ww, inner_h), 2, border_radius=14)

        if show_book:
            if book_detail and 0 <= book_sel < len(ALL_CARDS):
                card = ALL_CARDS[book_sel]
                seen = card.key in self.seen_cards
                rc = RARITY_COLOR[card.rarity] if seen else (80,70,100)

                text_shadow(surf, "ДЕТАЛІ КАРТКИ", FONT_MED, rc, wx + ww//2 - 100, wy + 14)

                cw3, ch3 = 340, 420
                cx3 = wx + ww//2 - cw3//2
                cy3 = wy + 70
                draw_rounded_rect(surf, (28,20,50), (cx3, cy3, cw3, ch3), 16, 245)
                pygame.draw.rect(surf, rc, (cx3, cy3, cw3, ch3), 2, border_radius=16)

                rl = FONT_MED.render(RARITY_LABEL[card.rarity], True, rc)
                surf.blit(rl, (cx3 + cw3//2 - rl.get_width()//2, cy3 + 16))

                stars = {"common":1,"rare":2,"epic":3,"legendary":4}[card.rarity]
                st = FONT_MED.render("* " * stars, True, rc)
                surf.blit(st, (cx3 + cw3//2 - st.get_width()//2, cy3 + 48))

                if seen:
                    nm = FONT_MED.render(card.name, True, (255,240,200))
                    surf.blit(nm, (cx3 + cw3//2 - nm.get_width()//2, cy3 + 82))

                    pygame.draw.line(surf, (*rc, 160),
                                     (cx3+20, cy3+120), (cx3+cw3-20, cy3+120), 1)

                    buff_l = FONT_SMALL.render("БАФИ", True, (80,220,120))
                    surf.blit(buff_l, (cx3+20, cy3+132))
                    for j, b in enumerate(card.buffs):
                        bt = FONT_SMALL.render("+ " + b, True, (60,200,100))
                        surf.blit(bt, (cx3+20, cy3+158 + j*26))

                    deb_y = cy3 + 158 + len(card.buffs)*26 + 16
                    pygame.draw.line(surf, (*rc, 100),
                                     (cx3+20, deb_y-8), (cx3+cw3-20, deb_y-8), 1)
                    deb_l = FONT_SMALL.render("ДЕБАФИ", True, (220,80,80))
                    surf.blit(deb_l, (cx3+20, deb_y))
                    for j, d in enumerate(card.debuffs):
                        dt2 = FONT_SMALL.render("- " + d, True, (200,70,70))
                        surf.blit(dt2, (cx3+20, deb_y+26 + j*26))
                else:
                    q = FONT_BIG.render("???", True, (70,65,90))
                    surf.blit(q, (cx3 + cw3//2 - q.get_width()//2, cy3 + ch3//2 - 30))
                    ht = FONT_SMALL.render("Картку ще не побачено в грі", True, (90,85,110))
                    surf.blit(ht, (cx3 + cw3//2 - ht.get_width()//2, cy3 + ch3//2 + 20))

                hint_text = "ESC — назад до книги"
            else:
                text_shadow(surf, "КНИГА КАРТОК", FONT_MED, (255,180,50), wx + ww//2 - 100, wy + 14)
                seen_count = len(self.seen_cards)
                total_cards = len(ALL_CARDS)
                ct = FONT_SMALL.render(f"{seen_count} / {total_cards} карток побачено", True, (160,160,220))
                surf.blit(ct, (wx + 20, wy + 50))
                draw_bar(surf, wx+20, wy+78, ww-40, 8, seen_count, total_cards, (255,160,50))

                cols = 4
                cw2 = (ww - 40 - (cols-1)*8) // cols
                ch2 = 82
                clip_top = wy + 92
                clip_h   = inner_h - 92 - 46
                surf.set_clip(pygame.Rect(wx, clip_top, ww, clip_h))
                for i, card in enumerate(ALL_CARDS):
                    col = i % cols
                    row = i // cols
                    ax = wx + 20 + col * (cw2 + 8)
                    ay = wy + 98 + row * (ch2 + 6) - scroll_y
                    if ay + ch2 < clip_top: continue
                    if ay > clip_top + clip_h: break
                    seen = card.key in self.seen_cards
                    rc = RARITY_COLOR[card.rarity] if seen else (50,45,65)
                    sel = (i == book_sel)
                    bg = (55,35,90) if sel else (35,26,58) if seen else (16,13,28)
                    draw_rounded_rect(surf, bg, (ax, ay, cw2, ch2), 7, 230)
                    border_col = (255,255,150) if sel else rc
                    bw2 = 2 if sel else 1
                    pygame.draw.rect(surf, border_col, (ax, ay, cw2, ch2), bw2, border_radius=7)
                    if seen:
                        ic = FONT_SMALL.render(card.rarity[0].upper(), True, rc)
                        surf.blit(ic, (ax+6, ay+4))
                        nm = FONT_TINY.render(card.name, True, (220,210,240))
                        surf.blit(nm, (ax+6, ay+26))
                        rl = FONT_TINY.render(RARITY_LABEL[card.rarity], True, rc)
                        surf.blit(rl, (ax+6, ay+44))
                        if card.buffs:
                            bt2 = FONT_TINY.render("+" + card.buffs[0][:18], True, (80,210,110))
                            surf.blit(bt2, (ax+6, ay+62))
                    else:
                        q = FONT_MED.render("?", True, (60,55,80))
                        surf.blit(q, (ax + cw2//2 - q.get_width()//2,
                                     ay + ch2//2 - q.get_height()//2))
                surf.set_clip(None)

                hint_text = "Стрілки — вибір   ENTER — деталі   Scroll — прокрутка   B/ESC — назад"

        else:
            text_shadow(surf, "ДОСЯГНЕННЯ", FONT_MED, (255,220,80), wx + ww//2 - 100, wy + 14)
            unlocked_count = sum(1 for a in self.all if a.unlocked)
            ct = FONT_SMALL.render(f"{unlocked_count} / {len(self.all)} розблоковано", True, (160,160,220))
            surf.blit(ct, (wx + 20, wy + 50))
            draw_bar(surf, wx+20, wy+78, ww-40, 8, unlocked_count, len(self.all), (100,255,150))

            col_w = (ww - 40) // 2
            clip_top = wy + 94
            clip_h   = inner_h - 94 - 46
            surf.set_clip(pygame.Rect(wx, clip_top, ww, clip_h))
            for i, a in enumerate(self.all):
                col = i % 2
                row = i // 2
                ax = wx + 20 + col * (col_w + 4)
                ay = wy + 100 + row * 56 - scroll_y
                if ay + 56 < clip_top: continue
                if ay > clip_top + clip_h: break
                col_bg = (40,28,72) if a.unlocked else (20,15,35)
                draw_rounded_rect(surf, col_bg, (ax, ay, col_w - 4, 48), 8, 230)
                if a.unlocked:
                    pygame.draw.rect(surf, a.color, (ax, ay, col_w-4, 48), 1, border_radius=8)
                ic = FONT_MED.render(a.icon if a.unlocked else "?", True,
                                     a.color if a.unlocked else (70,70,90))
                surf.blit(ic, (ax + 8, ay + 10))
                name_col = a.color if a.unlocked else (90,90,115)
                nt = FONT_SMALL.render(a.name if a.unlocked else "???", True, name_col)
                surf.blit(nt, (ax + 44, ay + 6))
                dt = FONT_TINY.render(a.desc, True, (130,130,170) if a.unlocked else (55,55,75))
                surf.blit(dt, (ax + 44, ay + 28))
                if a.unlocked:
                    chk = FONT_SMALL.render("v", True, (80,255,80))
                    surf.blit(chk, (ax + col_w - 22, ay + 14))
            surf.set_clip(None)

            bx, by2 = wx + ww//2 - 100, wy + inner_h - 38
            draw_rounded_rect(surf, (40,28,70), (bx, by2, 200, 30), 8, 220)
            pygame.draw.rect(surf, (200,140,60), (bx, by2, 200, 30), 1, border_radius=8)
            bt3 = FONT_SMALL.render("B — Книга карток", True, (255,180,60))
            surf.blit(bt3, (bx + 100 - bt3.get_width()//2, by2 + 6))

            hint_text = "ESC — назад до меню" if from_menu else "Z — закрити"

        hint = FONT_SMALL.render(hint_text, True, (120,100,180))
        surf.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 46))

class RocketLaunch:
    def __init__(self):
        self.timer = 0
        self.rocket_y = 0.0
        self.rocket_vy = 0.0
        self.rover_x = 0.0
        self.rover_y = 0.0
        self.rover_in_rocket = False
        self.done = False
        self.score = 0
        self.ps = ParticleSystem()

    def setup(self, score):
        self.timer = 0
        self.rocket_x = WIDTH // 2
        self.rocket_y = float(HEIGHT - 160)
        self.rocket_vy = 0.0
        self.rover_x = float(WIDTH // 2 - 200)
        self.rover_y = float(HEIGHT - 100)
        self.rover_in_rocket = False
        self.launched = False
        self.done = False
        self.score = score
        self.earth_alpha = 0

    def update(self):
        self.timer += 1
        self.ps.update()

        if self.timer < 80:
            self.rover_x += 3.5
            if self.timer % 4 == 0:
                self.ps.particles.append(Particle(
                    self.rover_x - 20, self.rover_y + 16,
                    random.uniform(-2, 0), random.uniform(-1, 0.5),
                    (200, 120, 50), 20, 4, 0.05
                ))

        elif self.timer < 110:
            if not self.rover_in_rocket:
                jump_t = self.timer - 80
                self.rover_x = self.rocket_x - 5
                self.rover_y = (HEIGHT - 100) - math.sin(jump_t / 30 * math.pi) * 80
                if jump_t > 28:
                    self.rover_in_rocket = True
                    self.rover_y = self.rocket_y + 30

        elif self.timer < 160:
            for _ in range(4):
                self.ps.particles.append(Particle(
                    self.rocket_x + random.randint(-12, 12),
                    self.rocket_y + 80,
                    random.uniform(-1, 1),
                    random.uniform(2, 5),
                    random.choice([(255,200,0),(255,120,0),(255,60,0),(200,200,200)]),
                    random.randint(15, 35), random.randint(3, 7), 0.1
                ))
            self.rocket_x = WIDTH // 2 + random.randint(-3, 3)

        elif not self.done:
            self.launched = True
            self.rocket_vy -= 0.4
            self.rocket_y += self.rocket_vy
            self.rocket_x = WIDTH // 2 + math.sin(self.timer * 0.05) * 4

            for _ in range(6):
                self.ps.particles.append(Particle(
                    self.rocket_x + random.randint(-10, 10),
                    self.rocket_y + 85,
                    random.uniform(-1.5, 1.5),
                    random.uniform(3, 7),
                    random.choice([(255,220,50),(255,140,0),(255,80,0),(180,180,255)]),
                    random.randint(20, 50), random.randint(4, 9), 0.05
                ))
            self.earth_alpha = min(255, (self.timer - 160) * 3)

            if self.rocket_y < -200:
                self.done = True

    def draw(self, surf):
        surf.fill((3, 2, 12))
        random.seed(999)
        for _ in range(180):
            sx = random.randint(0, WIDTH)
            sy = random.randint(0, HEIGHT)
            br = random.randint(80, 255)
            r = random.randint(1, 2)
            pygame.draw.circle(surf, (br, br, min(255, br+30)), (sx, sy), r)
        random.seed()

        if self.earth_alpha > 0:
            er = 90
            es = pygame.Surface((er*2, er*2), pygame.SRCALPHA)
            pygame.draw.circle(es, (30, 80, 200, self.earth_alpha), (er, er), er)
            pygame.draw.circle(es, (40, 160, 60, self.earth_alpha), (er+20, er-20), 30)
            pygame.draw.circle(es, (40, 160, 60, self.earth_alpha), (er-25, er+15), 20)
            pygame.draw.circle(es, (200, 230, 255, self.earth_alpha//2), (er, er), er, 4)
            surf.blit(es, (WIDTH//2 - er, 30))
            if self.earth_alpha > 100:
                lt = FONT_MED.render("ЗЕМЛЯ!", True, (150, 220, 255))
                lt.set_alpha(self.earth_alpha)
                surf.blit(lt, (WIDTH//2 - lt.get_width()//2, 200))

        pygame.draw.ellipse(surf, (160, 55, 20),
                            (-100, HEIGHT - 60, WIDTH + 200, 160))

        rx, ry = int(self.rocket_x), int(self.rocket_y)
        pygame.draw.rect(surf, (200, 200, 220), (rx - 18, ry, 36, 80), border_radius=4)
        pygame.draw.rect(surf, (240, 240, 255), (rx - 18, ry, 36, 80), 2, border_radius=4)
        pygame.draw.polygon(surf, (255, 80, 80), [
            (rx, ry - 40), (rx - 18, ry), (rx + 18, ry)
        ])
        pygame.draw.circle(surf, (100, 220, 255), (rx, ry + 20), 12)
        pygame.draw.circle(surf, (200, 240, 255), (rx, ry + 20), 12, 2)
        pygame.draw.polygon(surf, (180, 60, 60), [
            (rx - 18, ry + 55), (rx - 35, ry + 85), (rx - 18, ry + 80)
        ])
        pygame.draw.polygon(surf, (180, 60, 60), [
            (rx + 18, ry + 55), (rx + 35, ry + 85), (rx + 18, ry + 80)
        ])
        nt = FONT_TINY.render("MARS-1", True, (60, 60, 80))
        surf.blit(nt, (rx - nt.get_width()//2, ry + 45))

        if self.rover_in_rocket:
            pygame.draw.rect(surf, (70, 130, 180),
                             (rx - 8, ry + 12, 16, 10), border_radius=3)

        if not self.rover_in_rocket:
            rvx, rvy = int(self.rover_x), int(self.rover_y)
            pygame.draw.rect(surf, (70, 130, 180),
                             (rvx - 22, rvy - 14, 44, 28), border_radius=5)
            pygame.draw.ellipse(surf, (60, 200, 240),
                                (rvx - 8, rvy - 22, 18, 12))
            for wx in [rvx - 14, rvx, rvx + 14]:
                pygame.draw.circle(surf, (50, 50, 60), (wx, rvy + 12), 8)
                pygame.draw.circle(surf, (90, 90, 100), (wx, rvy + 12), 8, 2)

        self.ps.draw(surf)

        if self.timer < 80:
            t = FONT_MED.render("Ровер прямує до ракети...", True, (200, 200, 255))
            surf.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT - 40))
        elif self.timer < 110:
            t = FONT_MED.render("Ровер завантажується!", True, (255, 220, 100))
            surf.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT - 40))
        elif self.timer < 160:
            t = FONT_MED.render("Запуск двигунів...", True, (255, 160, 60))
            surf.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT - 40))
            countdown = 5 - (self.timer - 110) // 10
            if countdown > 0:
                ct = FONT_BIG.render(str(countdown), True, (255, 80, 80))
                surf.blit(ct, (WIDTH//2 - ct.get_width()//2, HEIGHT//2 - 40))
        else:
            t = FONT_MED.render(" СТАРТ!", True, (255, 255, 100))
            surf.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT - 40))

RARITY_COLOR = {
    "common":    (160, 160, 180),
    "rare":      (60,  140, 255),
    "epic":      (180,  60, 255),
    "legendary": (255, 180,   0),
}
RARITY_LABEL = {
    "common": "ЗВИЧАЙНА", "rare": "РІДКІСНА",
    "epic": "ЕПІЧНА",     "legendary": "ЛЕГЕНДАРНА",
}

@dataclass
class Card:
    key: str
    name: str
    rarity: str
    buffs: List[str]
    debuffs: List[str]
    effect: dict

ALL_CARDS = [
    Card("l_god",    "Марсіанський Бог",   "legendary",
         ["+80% швидкість", "-40% витрата O₂"],
         ["+80% частота метеоритів"],
         {"speed_mul": 1.8, "o2_drain_mul": 0.6, "meteor_min_mul": 0.2, "meteor_max_mul": 0.2}),

    Card("l_turtle", "Залізна Черепаха",   "legendary",
         ["-70% шкода від усього", "Щит відновлюється"],
         ["-45% швидкість"],
         {"speed_mul": 0.55, "shield_regen": True, "damage_mul": 0.3}),

    Card("l_solar",  "Сонячний Вибух",     "legendary",
         ["Батарейки +120% енергії", "Депо O₂ повністю заряджені"],
         ["+100% частота бурів"],
         {"battery_energy_mul": 2.2, "o2_depot_bonus": True,
          "storm_min_mul": 0.35, "storm_max_mul": 0.35}),

    Card("e_rocket", "Реактивний Двигун",  "epic",
         ["+60% швидкість", "+40% висота стрибка"],
         ["-25% макс кисень"],
         {"speed_mul": 1.6, "jump_mul": 1.4, "max_o2_mul": 0.75}),

    Card("e_bunker", "Бункер",             "epic",
         ["-65% шкода від метеоритів", "Пісок -50% ефект"],
         ["-25% швидкість"],
         {"speed_mul": 0.75, "damage_mul": 0.35, "sand_slow_mul": 0.5}),

    Card("e_water",  "Водяний Запас",      "epic",
         ["Вода дає +80% більше O₂", "Бур знаходить більше води"],
         ["Батарейки -35% енергії"],
         {"water_o2_mul": 1.8, "battery_energy_mul": 0.65}),

    Card("e_radar",  "Мінний Детектор",    "epic",
         ["Пісок видно здалеку", "Пісок -60% уповільнення"],
         ["+40% частота метеоритів"],
         {"sand_slow_mul": 0.4, "sand_visible": True,
          "meteor_min_mul": 0.6, "meteor_max_mul": 0.6}),

    Card("e_nuclear","Ядерний Реактор",    "epic",
         ["Рух не витрачає енергію", "+30% макс енергія"],
         ["-20% витрата O₂ швидша"],
         {"no_move_energy": True, "max_energy_mul": 1.3, "o2_drain_mul": 1.2}),

    Card("r_turbo",  "Турбо",              "rare",
         ["+30% швидкість"],
         ["-12% макс кисень"],
         {"speed_mul": 1.3, "max_o2_mul": 0.88}),

    Card("r_tough",  "Стійкість",          "rare",
         ["-35% шкода від бурь"],
         ["+25% частота метеоритів"],
         {"storm_damage_mul": 0.65, "meteor_min_mul": 0.75, "meteor_max_mul": 0.75}),

    Card("r_drill",  "Ефективний Бур",     "rare",
         ["Бур +60% ресурсів", "Вода +30% O₂"],
         ["+10% витрата O₂"],
         {"drill_bonus_mul": 1.6, "water_o2_mul": 1.3, "o2_drain_mul": 1.1}),

    Card("r_filter", "Кисневий Фільтр",    "rare",
         ["-18% витрата O₂"],
         ["Батарейки -20% енергії"],
         {"o2_drain_mul": 0.82, "battery_energy_mul": 0.8}),

    Card("r_light",  "Легкий Корпус",      "rare",
         ["+22% швидкість", "+18% висота стрибка"],
         ["+20% шкода від метеоритів"],
         {"speed_mul": 1.22, "jump_mul": 1.18, "damage_mul": 1.2}),

    Card("r_miner",  "Гірничий Майстер",   "rare",
         ["+2 мінерали за збір", "Вода дає +20% O₂"],
         ["+8% витрата O₂"],
         {"mineral_bonus": 2, "water_o2_mul": 1.2, "o2_drain_mul": 1.08}),

    Card("r_emerg",  "Аварійний Запас",    "rare",
         ["При O₂<15% — авто +25% O₂ (раз)"],
         ["+5% витрата O₂"],
         {"emergency_o2": True, "o2_drain_mul": 1.05}),

    Card("r_surfer", "Пісочний Серфер",    "rare",
         ["В піску не витрачається енергія"],
         ["-10% загальна швидкість"],
         {"no_sand_energy": True, "speed_mul": 0.9}),

    Card("r_shield2","Метеоритний Щит",    "rare",
         ["Кожні 20с перший метеорит — без шкоди"],
         ["+5% витрата O₂"],
         {"periodic_shield": True, "o2_drain_mul": 1.05}),

    Card("r_scout",  "Скаут",              "rare",
         ["Ресурси видно далі", "+15% бур радіус"],
         ["+6% витрата O₂"],
         {"scout_vision": True, "drill_range_bonus": 0.15, "o2_drain_mul": 1.06}),

    Card("c_fuel",   "Паливна Клітина",    "common",
         ["Батарейки +12% енергії"],
         ["Буря -5% O₂ більше"],
         {"battery_energy_mul": 1.12, "storm_o2_mul": 1.05}),

    Card("c_tank",   "Кисневий Балон",     "common",
         ["+18% макс кисень"],
         ["-5% швидкість"],
         {"max_o2_mul": 1.18, "speed_mul": 0.95}),

    Card("c_rubber", "Гумові Колеса",      "common",
         ["Пісок -25% уповільнення"],
         ["Метеорити +8% шкоди"],
         {"sand_slow_mul": 0.75, "damage_mul": 1.08}),

    Card("c_antenna","Антена",             "common",
         ["Бур радіус +30м"],
         ["+4% витрата O₂"],
         {"drill_range_bonus": 30, "o2_drain_mul": 1.04}),

    Card("c_speed",  "Легка Підвіска",     "common",
         ["+8% швидкість"],
         ["Пісок -5% ефективніший"],
         {"speed_mul": 1.08, "sand_slow_mul": 0.95}),

    Card("c_dust",   "Пиловий Фільтр",     "common",
         ["Бурі -22% шкоди"],
         ["Метеорити +10% частота"],
         {"storm_damage_mul": 0.78, "meteor_min_mul": 0.9, "meteor_max_mul": 0.9}),

    Card("c_armor",  "Кераміка",           "common",
         ["Метеорити -15% шкоди"],
         ["Бурі +10% шкоди"],
         {"damage_mul": 0.85, "storm_damage_mul": 1.1}),

    Card("c_nav",    "Навігатор",          "common",
         ["+12% очок за відстань"],
         ["Нічого"],
         {"score_mul": 1.12}),

    Card("c_tech",   "Технік",             "common",
         ["Апгрейди -15% дешевші"],
         ["+6% витрата O₂"],
         {"upgrade_discount": 0.85, "o2_drain_mul": 1.06}),

    Card("c_xtank",  "Запасний Бак",       "common",
         ["+15% макс енергія"],
         ["-5% швидкість"],
         {"max_energy_mul": 1.15, "speed_mul": 0.95}),

    Card("c_lucky",  "Удача",              "common",
         ["Рідкісніші карти частіше"],
         ["Нічого"],
         {"luck": True}),

    Card("c_cooler", "Холодильник",        "common",
         ["-8% витрата O₂", "Метеорити -8% шкоди"],
         ["Батарейки -8% енергії"],
         {"o2_drain_mul": 0.92, "damage_mul": 0.92, "battery_energy_mul": 0.92}),
]

RARITY_WEIGHTS = {"common": 50, "rare": 30, "epic": 15, "legendary": 5}

class CardScreen:
    """Екран вибору карток кожні 5000м"""

    def __init__(self):
        self.visible   = False
        self.cards: List[Card] = []
        self.selected  = 0
        self.timer     = 0
        self.luck_mul  = 1.0

    def show(self, luck_mul=1.0):
        self.luck_mul = luck_mul
        self.cards    = self._pick_three()
        self.selected = 0
        self.visible  = True
        self.timer    = 0
        return {c.key for c in self.cards}

    def _pick_three(self):
        weights = {r: w * (self.luck_mul if r != "common" else 1.0)
                   for r, w in RARITY_WEIGHTS.items()}
        by_rarity = {}
        for c in ALL_CARDS:
            by_rarity.setdefault(c.rarity, []).append(c)

        chosen = []
        seen   = set()
        attempts = 0
        while len(chosen) < 3 and attempts < 200:
            attempts += 1
            rarities = list(weights.keys())
            ws       = [weights[r] for r in rarities]
            total    = sum(ws)
            r_val    = random.uniform(0, total)
            cumul    = 0
            rarity   = rarities[-1]
            for r, w in zip(rarities, ws):
                cumul += w
                if r_val <= cumul:
                    rarity = r
                    break
            pool = [c for c in by_rarity.get(rarity, []) if c.key not in seen]
            if pool:
                card = random.choice(pool)
                seen.add(card.key)
                chosen.append(card)
        return chosen

    def handle_key(self, event):
        if not self.visible: return None
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self.selected = (self.selected - 1) % len(self.cards)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.selected = (self.selected + 1) % len(self.cards)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.visible = False
            return self.cards[self.selected]
        return None

    def draw(self, surf):
        if not self.visible: return
        self.timer += 1

        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((5, 3, 20, 210))
        surf.blit(ov, (0, 0))

        text_shadow(surf, " ВИБІР КАРТКИ ", FONT_BIG, (255, 200, 80), WIDTH//2 - 220, 40)
        st = FONT_SMALL.render("← → вибір   ENTER — взяти", True, (160, 160, 220))
        surf.blit(st, (WIDTH//2 - st.get_width()//2, 110))

        cw, ch = 310, 380
        gap    = 24
        total  = len(self.cards) * cw + (len(self.cards)-1) * gap
        x0     = WIDTH//2 - total//2

        for i, card in enumerate(self.cards):
            cx = x0 + i * (cw + gap)
            cy = 145
            sel = (i == self.selected)
            rc  = RARITY_COLOR[card.rarity]

            if sel:
                bounce = int(math.sin(self.timer * 0.08) * 8)
                cy -= bounce + 10
                glow = pygame.Surface((cw+20, ch+20), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*rc, 60), (0,0,cw+20,ch+20), border_radius=16)
                surf.blit(glow, (cx-10, cy-10))

            bg_col = (30, 22, 55) if sel else (18, 14, 35)
            draw_rounded_rect(surf, bg_col, (cx, cy, cw, ch), 14, 240)
            pygame.draw.rect(surf, rc, (cx, cy, cw, ch), 2, border_radius=14)

            rl = FONT_SMALL.render(RARITY_LABEL[card.rarity], True, rc)
            surf.blit(rl, (cx + cw//2 - rl.get_width()//2, cy + 12))

            nl = FONT_MED.render(card.name, True, (255, 240, 200) if sel else (200, 200, 220))
            surf.blit(nl, (cx + cw//2 - nl.get_width()//2, cy + 44))

            pygame.draw.line(surf, (*rc, 120), (cx+16, cy+80), (cx+cw-16, cy+80), 1)

            by = cy + 92
            buff_lbl = FONT_TINY.render("БАФИ:", True, (100, 255, 140))
            surf.blit(buff_lbl, (cx+16, by)); by += 18
            for b in card.buffs:
                bt = FONT_TINY.render(f"+ {b}", True, (80, 230, 120))
                surf.blit(bt, (cx+16, by)); by += 16

            by += 8
            deb_lbl = FONT_TINY.render("ДЕБАФИ:", True, (255, 100, 100))
            surf.blit(deb_lbl, (cx+16, by)); by += 18
            for d in card.debuffs:
                dt2 = FONT_TINY.render(f"- {d}", True, (220, 80, 80))
                surf.blit(dt2, (cx+16, by)); by += 16

            stars = {"common":1,"rare":2,"epic":3,"legendary":4}[card.rarity]
            st2 = FONT_SMALL.render("" * stars, True, rc)
            surf.blit(st2, (cx + cw//2 - st2.get_width()//2, cy + ch - 30))


class ApocCutscene:
    def __init__(self):
        self.timer = 0
        self.ps = ParticleSystem()
        self.done = False
        self.rocket_x = WIDTH // 2
        self.rocket_y = -80.0
        self.rocket_vy = 3.0
        self.exploded = False
        self.rover_x = float(WIDTH // 2)
        self.rover_y = -40.0
        self.rover_vy = 0.0
        self.rover_landed = False
        self.shake = 0

    def reset(self):
        self.__init__()

    def update(self):
        self.timer += 1
        self.ps.update()
        if self.shake > 0: self.shake -= 1

        if not self.exploded:
            self.rocket_y += self.rocket_vy
            self.rocket_vy += 0.04
            if self.timer % 3 == 0:
                self.ps.particles.append(Particle(
                    self.rocket_x + random.randint(-8,8),
                    self.rocket_y + 70,
                    random.uniform(-1,1), random.uniform(2,5),
                    random.choice([(255,200,50),(255,120,0),(180,180,180)]),
                    random.randint(15,35), random.randint(3,7), 0.1
                ))
            if self.rocket_y > HEIGHT * 0.35 and not self.exploded:
                self.exploded = True
                self.shake = 40
                for _ in range(60):
                    a = random.uniform(0, math.pi*2)
                    sp = random.uniform(3, 14)
                    self.ps.particles.append(Particle(
                        self.rocket_x, self.rocket_y,
                        math.cos(a)*sp, math.sin(a)*sp - 2,
                        random.choice([(255,200,0),(255,80,0),(255,255,255),(200,50,0)]),
                        random.randint(40,90), random.randint(4,10), 0.08
                    ))
        else:
            if not self.rover_landed:
                self.rover_vy += 0.25
                self.rover_y += self.rover_vy
                if self.rover_y >= HEIGHT - 120:
                    self.rover_y = HEIGHT - 120
                    self.rover_landed = True
                    self.shake = 20
                    self.ps.emit(self.rover_x, self.rover_y+16,
                                 (200,120,50), count=20, speed=4, life=30, size=5, gravity=0.1)
            elif self.timer > 280:
                self.done = True

    def draw(self, surf):
        sx_off = random.randint(-self.shake, self.shake) if self.shake > 0 else 0
        sy_off = random.randint(-self.shake//2, self.shake//2) if self.shake > 0 else 0

        for y in range(HEIGHT):
            t = y / HEIGHT
            r = int(lerp(5, 50, t)); g = int(lerp(2, 15, t)); b = int(lerp(12, 8, t))
            pygame.draw.line(surf, (r,g,b), (0,y), (WIDTH,y))

        random.seed(77)
        for _ in range(150):
            pygame.draw.circle(surf, (random.randint(80,200),)*3,
                               (random.randint(0,WIDTH), random.randint(0,HEIGHT//2)), 1)
        random.seed()

        pygame.draw.ellipse(surf, (140, 45, 15), (-80, HEIGHT-80, WIDTH+160, 180))
        pygame.draw.ellipse(surf, (180, 75, 30), (-80, HEIGHT-65, WIDTH+160, 150))

        ox = sx_off; oy = sy_off

        if not self.exploded:
            rx = int(self.rocket_x + ox)
            ry = int(self.rocket_y + oy)
            pygame.draw.rect(surf, (200,200,220), (rx-16, ry, 32, 72), border_radius=4)
            pygame.draw.polygon(surf, (255,80,80), [(rx,ry-35),(rx-16,ry),(rx+16,ry)])
            pygame.draw.circle(surf, (100,220,255), (rx, ry+18), 10)
            pygame.draw.circle(surf, (200,240,255), (rx, ry+18), 10, 2)
            pygame.draw.polygon(surf, (180,60,60),[(rx-16,ry+50),(rx-30,ry+75),(rx-16,ry+70)])
            pygame.draw.polygon(surf, (180,60,60),[(rx+16,ry+50),(rx+30,ry+75),(rx+16,ry+70)])

            if self.timer > 30:
                mt = FONT_MED.render("МЕТЕОРИТ!", True, (255,80,50))
                surf.blit(mt, (WIDTH//2 - mt.get_width()//2, 40))
                msize = 22
                mx = rx + 180 - min(self.timer - 30, 150)
                my = ry - 60 + (self.timer - 30) * 0.4
                pygame.draw.circle(surf, (180, 70, 20), (int(mx), int(my)), msize)
                pygame.draw.circle(surf, (255, 140, 50), (int(mx), int(my)), msize//2)

        self.ps.draw(surf)

        if self.exploded and not self.rover_landed:
            rvx = int(self.rover_x + ox)
            rvy = int(self.rover_y + oy)
            pygame.draw.rect(surf, (70,130,180),(rvx-22,rvy-14,44,28), border_radius=5)
            pygame.draw.ellipse(surf, (60,200,240),(rvx-8,rvy-22,18,12))
            for wx2 in [rvx-14,rvx,rvx+14]:
                pygame.draw.circle(surf,(50,50,60),(wx2,rvy+12),8)

        if self.rover_landed:
            rvx = int(self.rover_x + ox)
            rvy = int(self.rover_y + oy)
            pygame.draw.rect(surf,(70,130,180),(rvx-22,rvy-14,44,28),border_radius=5)
            pygame.draw.ellipse(surf,(60,200,240),(rvx-8,rvy-22,18,12))
            for wx2 in [rvx-14,rvx,rvx+14]:
                pygame.draw.circle(surf,(50,50,60),(wx2,rvy+12),8)

            msg1 = FONT_MED.render("Ракету збито. Марс в хаосі.", True, (255,120,80))
            msg2 = FONT_MED.render("Знайди 100 мінералів та 100 води щоб вижити.", True, (220,200,160))
            msg3 = FONT_SMALL.render("ENTER — почати", True, (160,160,220))
            surf.blit(msg1, (WIDTH//2-msg1.get_width()//2, HEIGHT//2-40))
            surf.blit(msg2, (WIDTH//2-msg2.get_width()//2, HEIGHT//2+10))
            surf.blit(msg3, (WIDTH//2-msg3.get_width()//2, HEIGHT//2+60))


class MainMenu:
    def __init__(self):
        self.selected = 0
        self.options = ["РОЗПОЧАТИ МІСІЮ", "БЕЗКІНЕЧНИЙ РЕЖИМ", "ROGUELIKE", "ДОСЯГНЕННЯ", "АПОКАЛІПСИС", "ВИХІД"]
        self.timer = 0
        self.stars = [(random.randint(0,WIDTH), random.randint(0,HEIGHT),
                       random.randint(1,3), random.random()) for _ in range(200)]

    def handle(self, event, apoc_unlocked=False):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected-1) % len(self.options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected+1) % len(self.options)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.selected == 4 and not apoc_unlocked:
                    return -2
                return self.selected
        return -1

    def draw(self, surf, apoc_unlocked=False):
        self.timer += 1
        for y in range(HEIGHT):
            t = y / HEIGHT
            r = int(lerp(5,40,t)); g = int(lerp(3,15,t)); b = int(lerp(15,8,t))
            pygame.draw.line(surf, (r,g,b), (0,y),(WIDTH,y))
        for sx,sy,sz,phase in self.stars:
            br = int(150 + 100*math.sin(self.timer*0.03 + phase*10))
            pygame.draw.circle(surf, (br,br,br), (sx,sy), sz)
        pygame.draw.ellipse(surf, (160,55,20), (-50, HEIGHT-80, WIDTH+100, 200))
        pygame.draw.ellipse(surf, (200,90,40), (-50, HEIGHT-70, WIDTH+100, 180))
        for dx in [-2,0,2]:
            t = FONT_BIG.render("MARS ODYSSEY", True, (80,20,0))
            surf.blit(t, (WIDTH//2 - t.get_width()//2 + dx, 100 + dx))
        t = FONT_BIG.render("MARS ODYSSEY", True, (255,130,30))
        surf.blit(t, (WIDTH//2 - t.get_width()//2, 100))
        sub = FONT_MED.render("Виживання на Червоній планеті", True, (200,140,80))
        surf.blit(sub, (WIDTH//2 - sub.get_width()//2, 175))
        descs = [
            "Кампанія: 3 дні, зростаюча складність",
            "Нескінченна карта, дебафи кожні 6 км",
            "Картки кожні 5 км — баф або дебаф",
            "Переглянути всі досягнення",
            "Пройди кампанію + 30000м у безкінечному" if not apoc_unlocked else "Апокаліпсис на Марсі. Знайди 100+100 ресурсів.",
            ""
        ]
        for i, opt in enumerate(self.options):
            sel = i == self.selected
            locked = (i == 4 and not apoc_unlocked)
            bw, bh = 400, 54
            bx = WIDTH//2 - bw//2
            by = 235 + i * 76
            pulse = int(8*math.sin(self.timer*0.06)) if sel else 0
            if locked:
                bg = (30,20,30)
            elif i == 4:
                bg = (80,15,15) if sel else (50,10,10)
            elif i == 1:
                bg = (30,80,160)
            else:
                bg = (60,30,100) if sel else (25,15,45)
            draw_rounded_rect(surf, bg, (bx-pulse, by-pulse//2, bw+pulse*2, bh+pulse), 12, 230)
            if locked:
                bc = (80,50,80)
            elif i == 4:
                bc = (255,60,60) if sel else (180,40,40)
            elif i == 1:
                bc = (80,180,255) if sel else (60,120,200)
            else:
                bc = (200,130,255) if sel else (100,70,160)
            pygame.draw.rect(surf, bc, (bx-pulse, by-pulse//2, bw+pulse*2, bh+pulse), 2, border_radius=12)
            label = ("[ЗАКРИТО] " + opt) if locked else opt
            tc = (100,80,100) if locked else (255,100,100) if i==4 else (180,220,255) if i==1 else (255,220,255) if sel else (160,130,200)
            lt = FONT_MED.render(label, True, tc)
            surf.blit(lt, (WIDTH//2 - lt.get_width()//2, by + 10))
            if sel and descs[i]:
                dc = (180,80,80) if i==4 and not apoc_unlocked else (160,160,200)
                dt = FONT_TINY.render(descs[i], True, dc)
                surf.blit(dt, (WIDTH//2 - dt.get_width()//2, by + 34))
        vt = FONT_TINY.render("WASD: рух  SPC: стрибок  E: бур  TAB: апгрейди", True, (100,80,140))
        surf.blit(vt, (WIDTH//2 - vt.get_width()//2, HEIGHT - 28))

class EndScreen:
    def __init__(self):
        self.timer  = 0
        self.result = ""
        self.score  = 0
        self.reason = ""
        self.level  = 1
        self.next_level = 2

    def setup(self, result, score, reason="", level=1, next_level=2):
        self.result     = result
        self.score      = score
        self.reason     = reason
        self.level      = level
        self.next_level = next_level
        self.timer      = 0

    def handle(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                return "next" if self.result == "level_win" else "restart"
            if event.key == pygame.K_ESCAPE:
                return "menu"
        return ""

    def draw(self, surf):
        self.timer += 1
        surf.fill((5, 3, 10))
        random.seed(77)
        for _ in range(120):
            sx = random.randint(0, WIDTH)
            sy = random.randint(0, HEIGHT)
            pygame.draw.circle(surf, (random.randint(60,150),)*3, (sx,sy), 1)
        random.seed()

        r = int(200 + 60 * math.sin(self.timer * 0.05))

        if self.result == "level_win":
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (80, 200, 255, 40), (r,r), r)
            surf.blit(s, (WIDTH//2-r, HEIGHT//2-r))
            text_shadow(surf, f" ДЕНЬ {self.level} ПРОЙДЕНО!", FONT_BIG,
                        (80, 220, 255), WIDTH//2 - 300, 150)
            diff_names = {1: "Нормальна", 2: "Важка", 3: "Екстремальна"}
            lines = [
                f"Рахунок: {self.score}",
                f"",
                f" ДЕНЬ {self.next_level}: {diff_names.get(self.next_level, '')} складність",
                f"",
                "ENTER / R — наступний день",
                "ESC — головне меню",
            ]
            for i, line in enumerate(lines):
                if not line: continue
                col = (150, 220, 255) if "" not in line else (255, 220, 80)
                if "ENTER" in line or "ESC" in line: col = (160, 160, 220)
                lt = FONT_MED.render(line, True, col)
                surf.blit(lt, (WIDTH//2 - lt.get_width()//2, 270 + i*46))

        elif self.result == "win":
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (30,255,100,40), (r,r), r)
            surf.blit(s, (WIDTH//2-r, HEIGHT//2-r))
            text_shadow(surf, " МІСІЯ ВИКОНАНА!", FONT_BIG, (0,255,120), WIDTH//2 - 280, 160)
            lines = [
                f"Всі 3 дні пройдено! Ровер повернувся на Землю.",
                f"Фінальний рахунок: {self.score}",
                "", "ENTER / R — нова гра", "ESC — головне меню",
            ]
            for i, line in enumerate(lines):
                if not line: continue
                col = (200,255,200)
                if "ENTER" in line or "ESC" in line: col = (160,160,220)
                lt = FONT_MED.render(line, True, col)
                surf.blit(lt, (WIDTH//2 - lt.get_width()//2, 280 + i*46))

        else:
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (255,50,20,40), (r,r), r)
            surf.blit(s, (WIDTH//2-r, HEIGHT//2-r))
            text_shadow(surf, " МІСІЯ ПРОВАЛЕНА", FONT_BIG, (255,60,30), WIDTH//2 - 270, 160)
            lines = [
                f"День {self.level} | Причина: {self.reason}",
                f"Рахунок: {self.score}",
                "", "ENTER / R — спробувати день знову", "ESC — головне меню",
            ]
            for i, line in enumerate(lines):
                if not line: continue
                col = (255,200,200)
                if "ENTER" in line or "ESC" in line: col = (160,160,220)
                lt = FONT_MED.render(line, True, col)
                surf.blit(lt, (WIDTH//2 - lt.get_width()//2, 280 + i*46))

class Game:
    STATE_MENU         = "menu"
    STATE_PLAY         = "play"
    STATE_END          = "end"
    STATE_PAUSE        = "pause"
    STATE_ROCKET       = "rocket"
    STATE_CARDS        = "cards"
    STATE_ACHIEVEMENTS = "achievements"
    STATE_CUTSCENE     = "cutscene"

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("MARS ODYSSEY")
        self.clock  = pygame.time.Clock()
        self.state  = self.STATE_MENU

        self.menu          = MainMenu()
        self.end_scr       = EndScreen()
        self.rocket_anim   = RocketLaunch()
        self.card_screen   = CardScreen()
        self.current_level  = 1
        self.infinite_mode  = False
        self.roguelike_mode = False
        self.apoc_mode      = False
        self.show_book      = False
        self.book_sel       = 0
        self.book_detail    = False
        self.ach_scroll     = 0
        self.book_scroll    = 0
        self.cutscene       = ApocCutscene()
        self.giant_ast_timer = 300
        self.achievements   = AchievementSystem()
        self.reset()

    LEVEL_GOALS = {1: 12000, 2: 10000, 3: 8000}

    @property
    def apoc_unlocked(self):
        a = self.achievements._map
        return (a.get("campaign_done") and a["campaign_done"].unlocked and
                a.get("inf_30000") and a["inf_30000"].unlocked)

    APOC_CONFIG = dict(o2_drain=0.139, storm_min=120, storm_max=265,
                       meteor_min=30, meteor_max=90, battery_energy=7,
                       o2_depot_gap=500, battery_gap=600, sand_o2=0.06)

    INFINITE_DEBUFFS = [
        (6000,  " Бурі частішають!",         {"storm_min": 80,  "storm_max": 200}),
        (12000, " Менше станцій O₂!",        {"o2_depot_gap": 700}),
        (18000, " Метеорити частішають!",    {"meteor_min": 30, "meteor_max": 90}),
        (24000, " Батареї слабші (-20%)!",   {"battery_energy": 20}),
        (30000, " Кисень швидше тане!",      {"o2_drain": 0.174}),
        (36000, " Бурі ще частіші!",         {"storm_min": 50,  "storm_max": 120}),
        (42000, " Станцій O₂ майже нема!",   {"o2_depot_gap": 1100}),
        (48000, " Метеоритний шторм!",       {"meteor_min": 18, "meteor_max": 55}),
        (54000, " Батареї майже пусті!",     {"battery_energy": 5}),
        (60000, " МАКСИМАЛЬНА НЕБЕЗПЕКА!",   {"o2_drain": 0.208, "storm_min": 40, "storm_max": 90}),
    ]

    LEVEL_CONFIG = {
        1: dict(o2_drain=0.139, storm_min=180, storm_max=400,
                meteor_min=60,  meteor_max=180, battery_energy=35,
                o2_depot_gap=500, battery_gap=600, sand_o2=0.04),
        2: dict(o2_drain=0.139, storm_min=80,  storm_max=200,
                meteor_min=60,  meteor_max=180, battery_energy=15,
                o2_depot_gap=500, battery_gap=600, sand_o2=0.04),
        3: dict(o2_drain=0.174, storm_min=80,  storm_max=200,
                meteor_min=30,  meteor_max=90,  battery_energy=5,
                o2_depot_gap=800, battery_gap=900, sand_o2=0.07),
    }

    def reset(self):
        lv = clamp(self.current_level, 1, 3)

        if self.apoc_mode:
            self.cfg = dict(**self.APOC_CONFIG)
            world_w = 500000
        elif self.infinite_mode:
            self.cfg = dict(o2_drain=0.139, storm_min=180, storm_max=400,
                            meteor_min=60, meteor_max=180, battery_energy=35,
                            o2_depot_gap=500, battery_gap=600, sand_o2=0.04)
            self.inf_stage = 0
            self.inf_next_debuff = 6000
            world_w = 500000
        elif self.roguelike_mode:
            self.cfg = dict(o2_drain=0.139, storm_min=180, storm_max=400,
                            meteor_min=60, meteor_max=180, battery_energy=35,
                            o2_depot_gap=500, battery_gap=600, sand_o2=0.04)
            self.card_muls = {
                "speed_mul":1.0,"jump_mul":1.0,"o2_drain_mul":1.0,
                "max_o2_mul":1.0,"max_energy_mul":1.0,"damage_mul":1.0,
                "storm_damage_mul":1.0,"battery_energy_mul":1.0,
                "sand_slow_mul":1.0,"drill_bonus_mul":1.0,"water_o2_mul":1.0,
                "score_mul":1.0,"upgrade_discount":1.0,
                "meteor_min_mul":1.0,"meteor_max_mul":1.0,
                "storm_min_mul":1.0,"storm_max_mul":1.0,
                "drill_range_bonus":0,"mineral_bonus":0,"luck":False,
                "no_move_energy":False,"no_sand_energy":False,
                "shield_regen":False,"emergency_o2":False,
                "periodic_shield":False,"o2_depot_bonus":False,
                "sand_visible":False,"scout_vision":False,
                "emergency_o2_used":False,"periodic_shield_timer":0,
            }
            self.rogue_next_card = 5000
            self.chosen_cards = []
            world_w = 500000
        else:
            self.cfg = self.LEVEL_CONFIG[lv]
            world_w = self.LEVEL_GOALS[lv] + 2000

        global WORLD_WIDTH
        WORLD_WIDTH = world_w

        self.terrain_rects, self.heights, self.surface_pts = generate_terrain()
        start_y = self.heights[2] - Rover.H
        self.rover = Rover(100, start_y)
        self.res = Resources()
        self.res.o2_drain = self.cfg["o2_drain"]
        self.ps  = ParticleSystem()
        self.hud = HUD()
        self.upgrade_screen = UpgradeScreen()
        self.show_achievements = False
        self.cam_x = 0.0
        self.day_timer = 0
        self.day_len   = 60 * 60
        self.dist_traveled = 0
        self.goal_dist = (self.LEVEL_GOALS.get(lv, 999999)
                         if not self.infinite_mode and not self.roguelike_mode
                         else 999999)
        self.prev_x    = self.rover.x
        self.hazards: List[Hazard] = []
        self.collectibles: List[Collectible] = []
        self.batteries: List[Battery] = []
        self.storm_timer  = 200
        self.meteor_timer = 90
        self.giant_ast_timer = 400
        self.spawn_frontier = 0
        initial = min(6000, WORLD_WIDTH)
        self._spawn_chunk(0, initial)
        self.spawn_frontier = initial
        self.paused = False

    def _spawn_chunk(self, x_from, x_to):
        """Спавн об'єктів у діапазоні x_from..x_to (прогресивно для великих карт)"""
        seg = 40
        cfg = self.cfg

        COLL_GAP = 320
        x = (max(x_from, 80) // COLL_GAP + 1) * COLL_GAP
        while x < x_to:
            i = clamp(x // seg, 0, len(self.heights)-2)
            y = self.heights[i] - 10
            kind = random.choice(["mineral","mineral","water"])
            self.collectibles.append(Collectible(x + random.randint(-20, 20), y, kind))
            x += 320

        gap = cfg["o2_depot_gap"]
        x = (x_from // gap + 1) * gap
        while x < x_to:
            i = clamp(x // seg, 0, len(self.heights)-1)
            depo = OxygenDepo(x, self.heights[i] - 10)
            if self.apoc_mode:
                depo.charge = 50
            self.hazards.append(depo)
            x += gap

        b_gap = cfg["battery_gap"]
        x = (x_from // b_gap + 1) * b_gap
        while x < x_to:
            i = clamp(x // seg, 0, len(self.heights)-1)
            self.batteries.append(Battery(x + random.randint(-40,40), self.heights[i] - 18))
            x += b_gap

        x = (x_from // 700 + 1) * 700
        while x < x_to:
            i = clamp(x // seg, 0, len(self.heights)-1)
            trap_y = int(self.heights[i]) - 20
            trap = PishanaPastyaka(x, trap_y, width=random.randint(150, 280))
            trap.sand_drain = cfg["sand_o2"]
            trap.hidden = self.apoc_mode
            self.hazards.append(trap)
            x += 700

    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            events = pygame.event.get()
            for ev in events:
                if ev.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                self._handle_event(ev)
            self._update()
            self._draw()
            pygame.display.flip()

    def _handle_event(self, ev):
        if self.state == self.STATE_MENU:
            r = self.menu.handle(ev, self.apoc_unlocked)
            if r == 0:
                self.infinite_mode = False; self.roguelike_mode = False; self.apoc_mode = False
                self.current_level = 1; self.reset(); self.state = self.STATE_PLAY
            elif r == 1:
                self.infinite_mode = True; self.roguelike_mode = False; self.apoc_mode = False
                self.reset(); self.state = self.STATE_PLAY
            elif r == 2:
                self.infinite_mode = False; self.roguelike_mode = True; self.apoc_mode = False
                self.reset(); self.state = self.STATE_PLAY
            elif r == 3:
                self.state = self.STATE_ACHIEVEMENTS
            elif r == 4:
                self.infinite_mode = False; self.roguelike_mode = False; self.apoc_mode = True
                self.reset()
                self.cutscene.reset()
                self.state = self.STATE_CUTSCENE
            elif r == 5:
                pygame.quit(); sys.exit()
            elif r == -2:
                self.hud.warn("Спочатку пройди кампанію та 30000м у безкінечному!")

        elif self.state == self.STATE_CUTSCENE:
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.cutscene.rover_landed:
                    self.state = self.STATE_PLAY

        elif self.state == self.STATE_ACHIEVEMENTS:
            if ev.type == pygame.MOUSEWHEEL:
                if self.show_book and not self.book_detail:
                    cols = 4
                    rows = math.ceil(len(ALL_CARDS) / cols)
                    max_scroll = max(0, rows * 88 - 400)
                    self.book_scroll = clamp(self.book_scroll - ev.y * 30, 0, max_scroll)
                elif not self.show_book:
                    rows = math.ceil(len(self.achievements.all) / 2)
                    max_scroll = max(0, rows * 56 - 400)
                    self.ach_scroll = clamp(self.ach_scroll - ev.y * 30, 0, max_scroll)
            if ev.type == pygame.KEYDOWN:
                if self.show_book:
                    cols = 4
                    total = len(ALL_CARDS)
                    if self.book_detail:
                        if ev.key == pygame.K_ESCAPE:
                            self.book_detail = False
                    else:
                        if ev.key in (pygame.K_RIGHT, pygame.K_d):
                            self.book_sel = (self.book_sel + 1) % total
                        elif ev.key in (pygame.K_LEFT, pygame.K_a):
                            self.book_sel = (self.book_sel - 1) % total
                        elif ev.key in (pygame.K_DOWN, pygame.K_s):
                            self.book_sel = min(self.book_sel + cols, total - 1)
                        elif ev.key in (pygame.K_UP, pygame.K_w):
                            self.book_sel = max(self.book_sel - cols, 0)
                        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self.book_detail = True
                        elif ev.key in (pygame.K_b, pygame.K_ESCAPE):
                            self.show_book = False
                            self.book_detail = False
                            self.book_scroll = 0
                else:
                    if ev.key == pygame.K_ESCAPE:
                        self.ach_scroll = 0
                        self.state = self.STATE_MENU
                    elif ev.key == pygame.K_b:
                        self.show_book = True
                        self.book_sel = 0
                        self.book_detail = False
                        self.book_scroll = 0

        elif self.state == self.STATE_CARDS:
            if ev.type == pygame.KEYDOWN:
                card = self.card_screen.handle_key(ev)
                if card:
                    self._apply_card(card)
                    self.state = self.STATE_PLAY

        elif self.state == self.STATE_PLAY:
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_TAB:
                    self.upgrade_screen.toggle()
                    self.show_achievements = False
                elif ev.key == pygame.K_z and not self.upgrade_screen.visible:
                    self.show_achievements = not self.show_achievements
                elif ev.key == pygame.K_ESCAPE:
                    self.state = self.STATE_MENU
                elif ev.key == pygame.K_e and not self.upgrade_screen.visible:
                    self._drill()
                else:
                    self.upgrade_screen.handle_key(ev, self.res, self.rover, self.hud)

        elif self.state == self.STATE_ROCKET:
            if ev.type == pygame.KEYDOWN and self.rocket_anim.done:
                if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.current_level = 1
                    self.end_scr.setup("win", self.rocket_anim.score)
                    self.state = self.STATE_END

        elif self.state == self.STATE_END:
            r = self.end_scr.handle(ev)
            if r == "next":
                self.current_level += 1
                self.reset()
                self.state = self.STATE_PLAY
            elif r == "restart":
                self.reset()
                self.state = self.STATE_PLAY
            elif r == "menu":
                self.current_level = 1
                self.state = self.STATE_MENU

    def _drill(self):
        if self.rover.drill_timer > 0: return
        self.rover.drill_active = True
        self.rover.drill_timer  = 40
        drill_lv = next((u.level for u in self.upgrade_screen.upgrades if u.name=="DRILL"), 0)
        drill_range = 120 + drill_lv * 30
        found = False
        for c in self.collectibles:
            if c.alive and dist((self.rover.cx, self.rover.cy), (c.x, c.y)) < drill_range:
                c.alive = False
                found = True
                if c.kind == "mineral":
                    gain = 3 + drill_lv * 2
                    self.res.minerals += gain
                    self.hud.add_msg(f"+{gain} мінералів ", (180,80,255))
                    self.res.score += 10
                else:
                    gain = 2 + drill_lv
                    self.res.water += gain
                    o2_gain = 8 + drill_lv * 4
                    self.res.restore(oxygen=o2_gain)
                    self.hud.add_msg(f"+{gain} води   +{o2_gain}% O₂", (80,160,255))
                    self.res.score += 15
                self.ps.emit(c.x, c.y, (220,150,255), count=12, speed=3, life=35, size=4, gravity=0.05)
        if not found:
            self.hud.add_msg("Немає ресурсів поряд! (радіус 120)", (180,100,60))
        self.ps.emit_dir(self.rover.cx, self.rover.cy, (220,200,80),
                         self.rover.facing, 0, spread=0.3, count=8, speed=3)

    def _apply_card(self, card: Card):
        """Застосовує ефект картки до гри"""
        m = card.effect
        cm = self.card_muls
        for key in ("speed_mul","jump_mul","o2_drain_mul","max_o2_mul","max_energy_mul",
                    "damage_mul","storm_damage_mul","battery_energy_mul","sand_slow_mul",
                    "drill_bonus_mul","water_o2_mul","score_mul","upgrade_discount",
                    "meteor_min_mul","meteor_max_mul","storm_min_mul","storm_max_mul"):
            if key in m:
                cm[key] *= m[key]
        for key in ("drill_range_bonus","mineral_bonus"):
            if key in m:
                cm[key] += m[key]
        for key in ("no_move_energy","no_sand_energy","shield_regen","emergency_o2",
                    "periodic_shield","o2_depot_bonus","sand_visible","scout_vision","luck"):
            if m.get(key):
                cm[key] = True

        base = dict(o2_drain=0.139, storm_min=180, storm_max=400,
                    meteor_min=60, meteor_max=180, battery_energy=35,
                    o2_depot_gap=500, battery_gap=600, sand_o2=0.04)
        self.cfg["o2_drain"]       = base["o2_drain"]       * cm["o2_drain_mul"]
        self.cfg["storm_min"]      = int(base["storm_min"]  * cm["storm_min_mul"])
        self.cfg["storm_max"]      = int(base["storm_max"]  * cm["storm_max_mul"])
        self.cfg["meteor_min"]     = int(base["meteor_min"] * cm["meteor_min_mul"])
        self.cfg["meteor_max"]     = int(base["meteor_max"] * cm["meteor_max_mul"])
        self.cfg["battery_energy"] = int(base["battery_energy"] * cm["battery_energy_mul"])
        self.res.o2_drain          = self.cfg["o2_drain"]
        self.res.max_oxygen        = 100 * cm["max_o2_mul"]
        self.res.max_energy        = 100 * cm["max_energy_mul"]
        self.rover.base_speed      = 3.5 * cm["speed_mul"]
        self.rover.speed           = self.rover.base_speed
        self.rover.jump_power      = -6.0 * cm["jump_mul"]

        self.chosen_cards.append(card)
        self.achievements.seen_cards.add(card.key)
        rc = RARITY_COLOR[card.rarity]
        self.hud.add_msg(f" {card.name} [{RARITY_LABEL[card.rarity]}]", rc)

    def _update(self):
        if self.state == self.STATE_ROCKET:
            self.rocket_anim.update()
            return
        if self.state == self.STATE_CUTSCENE:
            self.cutscene.update()
            return
        if self.state == self.STATE_CARDS:
            return
        if self.state != self.STATE_PLAY: return
        if self.upgrade_screen.visible: return

        keys = pygame.key.get_pressed()
        self.rover.update(keys, self.terrain_rects, self.cam_x, self.res)
        self.day_timer += 1

        dx = self.rover.x - self.prev_x
        if dx > 0:
            self.dist_traveled = max(self.dist_traveled, int(self.rover.x - 100))
        self.prev_x = self.rover.x

        target_cam = self.rover.x - WIDTH * 0.35
        target_cam = clamp(target_cam, 0, WORLD_WIDTH - WIDTH)
        self.cam_x = lerp(self.cam_x, target_cam, 0.1)

        if self.roguelike_mode and self.dist_traveled >= self.rogue_next_card:
            luck = 1.5 if self.card_muls.get("luck") else 1.0
            shown_keys = self.card_screen.show(luck_mul=luck)
            self.achievements.seen_cards.update(shown_keys)
            self.rogue_next_card += 5000
            self.state = self.STATE_CARDS
            return

        if self.roguelike_mode:
            cm = self.card_muls
            if cm["shield_regen"] and self.rover.shield_hp < 120:
                self.rover.shield_hp = min(120, self.rover.shield_hp + 0.05)
            if cm["emergency_o2"] and not cm["emergency_o2_used"] and self.res.oxygen < 15:
                self.res.restore(oxygen=25)
                cm["emergency_o2_used"] = True
                self.hud.add_msg(" Аварійний запас O₂ активовано!", (255,100,100))
            if cm["periodic_shield"]:
                cm["periodic_shield_timer"] += 1
                if cm["periodic_shield_timer"] >= 20 * 60:
                    cm["periodic_shield_timer"] = 0
                    self.rover.invincible = max(self.rover.invincible, 60)
        target_cam = self.rover.x - WIDTH * 0.35
        target_cam = clamp(target_cam, 0, WORLD_WIDTH - WIDTH)
        self.cam_x = lerp(self.cam_x, target_cam, 0.1)

        CHUNK_SIZE = 2000
        needed = int(self.rover.x) + 5000
        if needed > self.spawn_frontier:
            new_frontier = self.spawn_frontier + CHUNK_SIZE
            self._spawn_chunk(self.spawn_frontier, min(new_frontier, WORLD_WIDTH))
            self.spawn_frontier = new_frontier

        if not self.infinite_mode and not self.roguelike_mode and not self.apoc_mode:
            goal = self.LEVEL_GOALS[clamp(self.current_level, 1, 3)]
            if self.dist_traveled >= goal:
                elapsed_secs = self.day_timer // 60
                if self.current_level == 1 and elapsed_secs < 70:
                    self.achievements.unlock("speed_day1", self.hud)
                elif self.current_level == 2 and elapsed_secs < 60:
                    self.achievements.unlock("speed_day2", self.hud)
                elif self.current_level == 3 and elapsed_secs < 55:
                    self.achievements.unlock("speed_day3", self.hud)
                if self.current_level >= 3:
                    self.achievements.unlock("campaign_done", self.hud)
                    self.rocket_anim.setup(self.res.score + 500)
                    self.state = self.STATE_ROCKET
                    return
                else:
                    self.res.score += 300
                    self.end_scr.setup("level_win", self.res.score,
                                       level=self.current_level,
                                       next_level=self.current_level + 1)
                    self.state = self.STATE_END
                    return
            left = goal - self.dist_traveled
            if left <= 500 and left > 490:
                self.hud.warn(f"До фінішу {left}м!")

        if self.infinite_mode and self.dist_traveled >= self.inf_next_debuff:
            for milestone, msg, changes in self.INFINITE_DEBUFFS:
                if self.dist_traveled >= milestone and milestone == self.inf_next_debuff:
                    self.cfg.update(changes)
                    self.res.o2_drain = self.cfg["o2_drain"]
                    self.hud.warn(msg, (255, 80, 80))
                    self.inf_next_debuff += 6000
                    break

        self.storm_timer  -= 1
        self.meteor_timer -= 1
        if self.storm_timer <= 0:
            sy = random.choice(self.heights[len(self.heights)//2:])
            storm_y = sy - random.randint(60, 120)
            self.hazards.append(DustStorm(self.cam_x + WIDTH + 50, storm_y))
            self.storm_timer = random.randint(self.cfg["storm_min"], self.cfg["storm_max"])
        if self.meteor_timer <= 0:
            mx = self.cam_x + random.randint(50, WIDTH-50)
            self.hazards.append(Meteor(mx))
            self.meteor_timer = random.randint(self.cfg["meteor_min"], self.cfg["meteor_max"])
        if self.apoc_mode:
            self.giant_ast_timer -= 1
            if self.giant_ast_timer <= 0:
                mx = self.cam_x + random.randint(100, WIDTH-100)
                self.hazards.append(GiantAsteroid(mx))
                self.giant_ast_timer = random.randint(600, 1200)

        for h in self.hazards:
            if isinstance(h, GiantAsteroid):
                h.update(self.rover, self.res, self.ps, self.terrain_rects)
            else:
                h.update(self.rover, self.res, self.ps)
        self.hazards = [h for h in self.hazards if h.alive]

        for c in self.collectibles:
            c.update()
        self.collectibles = [c for c in self.collectibles if c.alive]

        tank_lv = next((u.level for u in self.upgrade_screen.upgrades if u.name=="TANK"), 0)
        self.res.max_oxygen = 100 + tank_lv * 40

        for b in self.batteries:
            b.update()
            if b.alive and b.rect.colliderect(self.rover.rect):
                b.alive = False
                energy_gain = self.cfg["battery_energy"]
                self.res.restore(energy=energy_gain)
                self.hud.add_msg(f"+{energy_gain}% енергії ", (255, 220, 50))
                self.ps.emit(b.x, b.y, (255, 220, 50), count=12, speed=3, life=30, size=4)
                self.res.score += 8
        self.batteries = [b for b in self.batteries if b.alive]

        self.achievements.check_all(self.res, self.rover, self, self.hud)

        self.ps.update()
        self.hud.update()

        if self.res.oxygen < 20:
            self.hud.warn("КРИТИЧНИЙ РІВЕНЬ КИСНЮ!")
        elif self.res.energy < 20:
            self.hud.warn("МАЛО ЕНЕРГІЇ!")

        if self.apoc_mode and self.res.minerals >= 100 and self.res.water >= 100:
            self.res.score += 1000
            self.end_scr.setup("win", self.res.score, "Ракету полагоджено! Ти повертаєшся додому!")
            self.state = self.STATE_END

        if self.res.dead:
            reason = "Вичерпався кисень!" if self.res.oxygen <= 0 else "Зникла енергія!"
            self.end_scr.setup("lose", self.res.score, reason, level=self.current_level)
            self.state = self.STATE_END

    def _draw(self):
        surf = self.screen
        if self.state == self.STATE_MENU:
            self.menu.draw(surf, self.apoc_unlocked)
        elif self.state == self.STATE_CUTSCENE:
            self.cutscene.draw(surf)
        elif self.state == self.STATE_ACHIEVEMENTS:
            scroll = self.book_scroll if self.show_book else self.ach_scroll
            self.achievements.draw_screen(surf, from_menu=True, show_book=self.show_book,
                                          book_sel=self.book_sel, book_detail=self.book_detail,
                                          scroll_y=scroll)
        elif self.state in (self.STATE_PLAY, self.STATE_CARDS):
            self._draw_game(surf)
            if self.state == self.STATE_CARDS:
                self.card_screen.draw(surf)
        elif self.state == self.STATE_ROCKET:
            self.rocket_anim.draw(surf)
            if self.rocket_anim.done:
                t = FONT_MED.render("ENTER — далі", True, (200, 255, 200))
                surf.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT - 50))
        elif self.state == self.STATE_END:
            self.end_scr.draw(surf)

    def _draw_game(self, surf):
        draw_terrain(surf, self.cam_x, self.heights, self.surface_pts)

        gx = int(self.goal_dist + 100 - self.cam_x)
        if 0 < gx < WIDTH:
            pygame.draw.line(surf, (0,255,100), (gx, 0), (gx, HEIGHT), 2)
            gt = FONT_SMALL.render(" ЦІЛЬ", True, (0,255,100))
            surf.blit(gt, (gx - gt.get_width()//2, 20))

        for b in self.batteries:
            bx_s = b.x - self.cam_x
            if -50 < bx_s < WIDTH + 50:
                b.draw(surf, self.cam_x)

        for c in self.collectibles:
            cx_s = c.x - self.cam_x
            if -50 < cx_s < WIDTH + 50:
                c.draw(surf, self.cam_x, self.rover.cx, self.rover.cy)

        for h in self.hazards:
            hx = h.x - self.cam_x
            if -400 < hx < WIDTH + 400:
                h.draw(surf, self.cam_x)

        self.rover.draw(surf, self.cam_x, self.ps, self.res)

        self.ps.draw(surf, self.cam_x)

        self.hud.draw(surf, self.res, self.rover, self.hazards,
                      self.current_level, self.dist_traveled,
                      self.LEVEL_GOALS.get(self.current_level, 999999),
                      infinite=self.infinite_mode,
                      roguelike=self.roguelike_mode,
                      next_card=getattr(self, 'rogue_next_card', 5000),
                      chosen_cards=getattr(self, 'chosen_cards', []))

        self.hud.draw_achievement_strip(surf, self.achievements.all)

        bw = WIDTH - 40
        draw_rounded_rect(surf, (20,15,40), (20, HEIGHT-18, bw, 10), 5, 180)
        if self.roguelike_mode:
            next_c = getattr(self, 'rogue_next_card', 5000)
            prev_c = next_c - 5000
            pct = clamp((self.dist_traveled - prev_c) / 5000, 0, 1)
            fw = int(bw * pct)
            col = (255, 180, 50)
            if fw > 4: draw_rounded_rect(surf, col, (20, HEIGHT-18, fw, 10), 5)
            tl = FONT_TINY.render(f" До наступної картки: {max(0, next_c - self.dist_traveled)}м", True, (200,160,80))
        elif self.infinite_mode:
            next_d = getattr(self, 'inf_next_debuff', 6000)
            prev_d = next_d - 6000
            pct = clamp((self.dist_traveled - prev_d) / 6000, 0, 1)
            fw = int(bw * pct)
            col = (80, 180, 255)
            if fw > 4: draw_rounded_rect(surf, col, (20, HEIGHT-18, fw, 10), 5)
            tl = FONT_TINY.render(f" До наступного дебафу: {max(0, next_d - self.dist_traveled)}м", True, (120,160,220))
        else:
            goal = self.LEVEL_GOALS.get(self.current_level, 1)
            fw = int(bw * clamp(self.dist_traveled / goal, 0, 1))
            col = (60,255,120) if self.dist_traveled < goal * 0.8 else (255,200,60)
            if fw > 4: draw_rounded_rect(surf, col, (20, HEIGHT-18, fw, 10), 5)
            tl = FONT_TINY.render(f"День {self.current_level} — проїхати {self.LEVEL_GOALS[self.current_level]}м", True, (120,120,180))
        surf.blit(tl, (WIDTH//2 - tl.get_width()//2, HEIGHT - 36))

        self.upgrade_screen.draw(surf, self.res)

        self.achievements.draw_popups(surf)

        if self.apoc_mode:
            draw_rounded_rect(surf, (40,10,10), (WIDTH-220, 56, 210, 52), 8, 210)
            pygame.draw.rect(surf, (200,60,60), (WIDTH-220, 56, 210, 52), 1, border_radius=8)
            mt = FONT_SMALL.render(f"МЕТА: Мiнерали {self.res.minerals}/100", True, (220,140,255))
            surf.blit(mt, (WIDTH-214, 62))
            wt2 = FONT_SMALL.render(f"      Вода     {self.res.water}/100", True, (80,180,255))
            surf.blit(wt2, (WIDTH-214, 84))

        if self.show_achievements:
            self.achievements.draw_screen(surf)

if __name__ == "__main__":
    g = Game()
    g.run()