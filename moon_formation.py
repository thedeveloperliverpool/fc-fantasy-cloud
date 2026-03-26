import math
import random
import pygame

# Giant impact simulation (2D, stylized)
# Simplified N-body gravity + debris disk + accretion into a proto-Moon

WIDTH, HEIGHT = 1200, 720
FPS = 60
G = 0.42  # tuned for stable orbits in this scale
TIME_SCALE = 40.0  # simulation seconds per real second

# Body and debris parameters
EARTH_MASS = 1200
THEIA_MASS = 600
EARTH_RADIUS = 36
THEIA_RADIUS = 16
DEBRIS_COUNT = 220
DEBRIS_MASS = 1.2
DEBRIS_SPEED_JITTER = 1.6
DEBRIS_SPAWN_RADIUS = 10
DISK_DAMP = 0.015  # circularization strength per step
DISK_INFLOW = 0.004  # inward drift toward Earth per step
DISK_TARGET_RADIUS = 140

# Accretion thresholds
ACCRETE_RADIUS = 22
MOON_SEED_MASS = 20
MOON_SEED_RADIUS = 12
MOON_ORBIT_RADIUS = 170
MOON_MAX_ORBIT = 260
MOON_GRAVITY_BOOST = 1.4

BG = (10, 12, 24)
WHITE = (235, 235, 240)
EARTH_BLUE = (90, 140, 230)
THEIA_RED = (220, 110, 90)
DEBRIS_GRAY = (170, 175, 190)
MOON_COLOR = (200, 200, 210)


class Body:
    def __init__(self, x, y, vx, vy, mass, radius, color, name=""):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.mass = mass
        self.radius = radius
        self.color = color
        self.name = name

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), int(self.radius))


class Debris:
    def __init__(self, x, y, vx, vy, mass):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.mass = mass

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, screen):
        pygame.draw.circle(screen, DEBRIS_GRAY, (int(self.x), int(self.y)), 2)


def distance(a, b):
    dx = a.x - b.x
    dy = a.y - b.y
    return math.hypot(dx, dy)


def apply_gravity(a, b, dt):
    dx = b.x - a.x
    dy = b.y - a.y
    r2 = dx * dx + dy * dy + 1e-6
    r = math.sqrt(r2)
    force = G * a.mass * b.mass / r2
    ax = force * dx / (r * a.mass)
    ay = force * dy / (r * a.mass)
    bx = -force * dx / (r * b.mass)
    by = -force * dy / (r * b.mass)
    a.vx += ax * dt
    a.vy += ay * dt
    b.vx += bx * dt
    b.vy += by * dt


def spawn_debris(impact_x, impact_y, base_vx, base_vy):
    debris = []
    for _ in range(DEBRIS_COUNT):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.5, 1.5) * DEBRIS_SPEED_JITTER
        vx = base_vx + math.cos(angle) * speed
        vy = base_vy + math.sin(angle) * speed
        x = impact_x + math.cos(angle) * random.uniform(0, DEBRIS_SPAWN_RADIUS)
        y = impact_y + math.sin(angle) * random.uniform(0, DEBRIS_SPAWN_RADIUS)
        debris.append(Debris(x, y, vx, vy, DEBRIS_MASS))
    return debris


def accrete(debris_list, moon):
    remaining = []
    for d in debris_list:
        dx = d.x - moon.x
        dy = d.y - moon.y
        if math.hypot(dx, dy) < ACCRETE_RADIUS:
            moon.mass += d.mass
            moon.radius = max(MOON_SEED_RADIUS, math.sqrt(moon.mass) * 0.7)
        else:
            remaining.append(d)
    return remaining


def clamp_world(body):
    # Keep objects within a padded box to reduce runaway drift
    pad = 200
    if body.x < -pad:
        body.x = WIDTH + pad
    if body.x > WIDTH + pad:
        body.x = -pad
    if body.y < -pad:
        body.y = HEIGHT + pad
    if body.y > HEIGHT + pad:
        body.y = -pad


def circularize_velocity(d, earth, dt):
    dx = d.x - earth.x
    dy = d.y - earth.y
    r = math.hypot(dx, dy) + 1e-6
    tx = -dy / r
    ty = dx / r
    v_circ = math.sqrt(G * earth.mass / r)
    target_vx = tx * v_circ
    target_vy = ty * v_circ
    d.vx += (target_vx - d.vx) * DISK_DAMP * dt
    d.vy += (target_vy - d.vy) * DISK_DAMP * dt

    # Mild inward drift so debris gradually settles toward an Earth-centered disk
    dx = d.x - earth.x
    dy = d.y - earth.y
    r = math.hypot(dx, dy) + 1e-6
    if r > DISK_TARGET_RADIUS:
        d.vx += (-dx / r) * DISK_INFLOW * dt
        d.vy += (-dy / r) * DISK_INFLOW * dt


def angular_momentum_z(earth, moon, debris_list):
    total = 0.0
    if moon:
        rx = moon.x - earth.x
        ry = moon.y - earth.y
        total += moon.mass * (rx * moon.vy - ry * moon.vx)
    for d in debris_list:
        rx = d.x - earth.x
        ry = d.y - earth.y
        total += d.mass * (rx * d.vy - ry * d.vx)
    return total


def set_circular_orbit(body, center, radius):
    body.x = center.x + radius
    body.y = center.y
    v = math.sqrt(G * center.mass / radius)
    body.vx = 0.0
    body.vy = -v


def keep_in_orbit(body, center):
    dx = body.x - center.x
    dy = body.y - center.y
    r = math.hypot(dx, dy) + 1e-6
    if r > MOON_MAX_ORBIT:
        scale = MOON_MAX_ORBIT / r
        body.x = center.x + dx * scale
        body.y = center.y + dy * scale
        # remove radial velocity to keep near-circular orbit
        rx = dx / r
        ry = dy / r
        vr = body.vx * rx + body.vy * ry
        body.vx -= vr * rx
        body.vy -= vr * ry


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Giant Impact: Moon Formation (Stylized)")
    clock = pygame.time.Clock()

    earth = Body(WIDTH * 0.5, HEIGHT * 0.5, 0, 0, EARTH_MASS, EARTH_RADIUS, EARTH_BLUE, "Earth")
    theia = Body(WIDTH * 0.15, HEIGHT * 0.35, 1.6, 0.8, THEIA_MASS, THEIA_RADIUS, THEIA_RED, "Theia")

    debris = []
    moon = None
    impacted = False

    font = pygame.font.SysFont("Helvetica", 18)

    sim_time = 0.0
    t_log = []
    Lz_log = []
    moon_mass_log = []

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        sim_dt = dt * TIME_SCALE
        sim_time += sim_dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return main()
                if event.key == pygame.K_p:
                    try:
                        import matplotlib.pyplot as plt
                    except Exception:
                        print("matplotlib is required for plots. Install with: pip install matplotlib")
                    else:
                        if t_log:
                            plt.figure()
                            plt.plot(t_log, Lz_log, label="Total Lz (moon + debris)")
                            plt.xlabel("Time (simulation seconds)")
                            plt.ylabel("Angular momentum (scaled)")
                            plt.title("Angular Momentum Conservation")
                            plt.legend()
                            plt.grid(True, alpha=0.3)

                            plt.figure()
                            plt.plot(t_log, moon_mass_log, label="Moon mass")
                            plt.xlabel("Time (simulation seconds)")
                            plt.ylabel("Mass (scaled)")
                            plt.title("Moon Accretion")
                            plt.legend()
                            plt.grid(True, alpha=0.3)
                            plt.show()

        # Gravity between main bodies (before impact) -- Earth is fixed at center
        if not impacted:
            dx = earth.x - theia.x
            dy = earth.y - theia.y
            r2 = dx * dx + dy * dy + 1e-6
            r = math.sqrt(r2)
            force = G * earth.mass * theia.mass / r2
            theia.vx += (force * dx / (r * theia.mass)) * sim_dt
            theia.vy += (force * dy / (r * theia.mass)) * sim_dt

        theia.update(sim_dt)
        clamp_world(theia)

        if not impacted and distance(earth, theia) <= earth.radius + theia.radius:
            impacted = True
            impact_x = (earth.x + theia.x) / 2
            impact_y = (earth.y + theia.y) / 2
            base_vx = (earth.vx + theia.vx) / 2
            base_vy = (earth.vy + theia.vy) / 2
            debris = spawn_debris(impact_x, impact_y, base_vx, base_vy)

            # Merge into a slightly more massive Earth remnant (Earth remains fixed)
            earth.mass += theia.mass * 0.6
            earth.radius = math.sqrt(earth.mass) * 0.9

            # Seed a proto-moon in a circular orbit
            moon = Body(
                earth.x + MOON_ORBIT_RADIUS,
                earth.y,
                0.0,
                0.0,
                MOON_SEED_MASS,
                MOON_SEED_RADIUS,
                MOON_COLOR,
                "Moon",
            )
            set_circular_orbit(moon, earth, MOON_ORBIT_RADIUS)

        # Debris and moon dynamics
        if impacted:
            if moon:
                # Gravity between Earth and Moon
                dx = earth.x - moon.x
                dy = earth.y - moon.y
                r2 = dx * dx + dy * dy + 1e-6
                r = math.sqrt(r2)
                force = G * earth.mass * moon.mass / r2
                moon.vx += (force * dx / (r * moon.mass)) * sim_dt
                moon.vy += (force * dy / (r * moon.mass)) * sim_dt
                moon.update(sim_dt)
                clamp_world(moon)
                keep_in_orbit(moon, earth)

            for d in debris:
                # Earth gravity (Earth fixed)
                dx = earth.x - d.x
                dy = earth.y - d.y
                r2 = dx * dx + dy * dy + 1e-6
                r = math.sqrt(r2)
                force = G * earth.mass * d.mass / r2
                d.vx += (force * dx / (r * d.mass)) * sim_dt
                d.vy += (force * dy / (r * d.mass)) * sim_dt

                if moon:
                    # Moon gravity
                    dxm = moon.x - d.x
                    dym = moon.y - d.y
                    rm2 = dxm * dxm + dym * dym + 1e-6
                    rm = math.sqrt(rm2)
                    force_m = G * moon.mass * d.mass / rm2 * MOON_GRAVITY_BOOST
                    d.vx += (force_m * dxm / (rm * d.mass)) * sim_dt
                    d.vy += (force_m * dym / (rm * d.mass)) * sim_dt

                circularize_velocity(d, earth, sim_dt)

                d.update(sim_dt)
                clamp_world(d)

            if moon:
                debris = accrete(debris, moon)

            t_log.append(sim_time)
            Lz_log.append(angular_momentum_z(earth, moon, debris))
            moon_mass_log.append(moon.mass if moon else 0.0)

        screen.fill(BG)
        earth.draw(screen)
        if not impacted:
            theia.draw(screen)
        if impacted and moon:
            moon.draw(screen)
        for d in debris:
            d.draw(screen)

        status = "Impact" if impacted else "Approach"
        info = f"Phase: {status} | Debris: {len(debris)} | R: reset | P: plot"
        text = font.render(info, True, WHITE)
        screen.blit(text, (20, 20))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
