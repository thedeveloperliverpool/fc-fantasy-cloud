import math
import random
import sys

import pygame


WIDTH, HEIGHT = 1280, 760
CENTER = (390, HEIGHT // 2 - 30)
FPS = 60
SIM_AREA_RIGHT = 780


STAGES = [
    {
        "name": "1) Giant Molecular Cloud",
        "duration": 8.0,
        "radius_scale": 1.0,
        "core_radius": 6,
        "core_intensity": 25,
        "rotation": 0.15,
        "turbulence": 12,
        "particle_color": (170, 190, 230),
    },
    {
        "name": "2) Gravitational Collapse",
        "duration": 8.0,
        "radius_scale": 0.72,
        "core_radius": 14,
        "core_intensity": 60,
        "rotation": 0.35,
        "turbulence": 8,
        "particle_color": (190, 210, 255),
    },
    {
        "name": "3) Protostar",
        "duration": 8.0,
        "radius_scale": 0.48,
        "core_radius": 26,
        "core_intensity": 120,
        "rotation": 0.65,
        "turbulence": 4,
        "particle_color": (245, 220, 170),
    },
    {
        "name": "4) Fusion Ignition",
        "duration": 8.0,
        "radius_scale": 0.3,
        "core_radius": 34,
        "core_intensity": 220,
        "rotation": 0.95,
        "turbulence": 2,
        "particle_color": (255, 210, 130),
    },
    {
        "name": "5) Main Sequence Star",
        "duration": 8.0,
        "radius_scale": 0.2,
        "core_radius": 38,
        "core_intensity": 255,
        "rotation": 1.1,
        "turbulence": 1,
        "particle_color": (255, 235, 170),
    },
]

NEBULA_DEFINITION = (
    "A nebula is a giant cloud of gas and dust in space. "
    "Some nebulae are the remains of dying stars, while others are places where new stars are born."
)

NEBULA_TYPES = [
    "Emission: glows from ionized gas (often red/pink).",
    "Reflection: dust scatters nearby starlight (often blue).",
    "Dark: dense dust blocks light behind it.",
    "Planetary/Supernova remnant: shells from dying stars.",
]

STELLAR_NURSERY = (
    "A stellar nursery is a cold, dense molecular cloud where gravity "
    "pulls clumps together until protostars form."
)

STAR_FORMATION_STEPS = [
    "1) Gas and dust collect in a molecular cloud.",
    "2) Gravity causes collapse into dense cores.",
    "3) A protostar forms and heats up.",
    "4) Fusion ignites in the core.",
    "5) A stable main-sequence star is born.",
]

SUMMARY = (
    "Nebulae are the raw material of stars. In stellar nurseries, gravity "
    "compresses gas and dust until fusion starts, creating a new star."
)

SECTION_CONTENT = [
    {
        "title": "1) What Is a Nebula?",
        "lines": [NEBULA_DEFINITION],
    },
    {
        "title": "2) Types of Nebulae",
        "lines": NEBULA_TYPES,
    },
    {
        "title": "3) What Are Stellar Nurseries?",
        "lines": [STELLAR_NURSERY],
    },
    {
        "title": "4) How Stars Form",
        "lines": STAR_FORMATION_STEPS,
    },
    {
        "title": "5) Simple Diagrams/Images",
        "lines": ["The diagram simulation below animates cloud -> collapse -> protostar -> star flow."],
    },
    {
        "title": "6) Short Summary",
        "lines": [SUMMARY],
    },
]


class Particle:
    def __init__(self):
        self.base_angle = random.uniform(0, math.tau)
        self.base_radius = random.uniform(20, 240)
        self.speed = random.uniform(0.05, 0.35)
        self.offset = random.uniform(0, math.tau)

    def position(self, sim_time, radius_scale, rotation, turbulence):
        r = max(8, self.base_radius * radius_scale)
        wobble = math.sin(sim_time * 2.3 + self.offset) * turbulence
        angle = self.base_angle + sim_time * self.speed * (1 + rotation) / max(0.2, r / 120)
        x = CENTER[0] + (r + wobble) * math.cos(angle)
        y = CENTER[1] + (r + wobble) * math.sin(angle)
        return int(x), int(y)


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


def get_stage(sim_time):
    elapsed = 0.0
    for i, stage in enumerate(STAGES):
        end = elapsed + stage["duration"]
        if sim_time <= end:
            local_t = (sim_time - elapsed) / stage["duration"]
            return i, local_t
        elapsed = end
    return len(STAGES) - 1, 1.0


def draw_glow(surface, radius, intensity):
    glow = pygame.Surface((radius * 8, radius * 8), pygame.SRCALPHA)
    cx, cy = glow.get_width() // 2, glow.get_height() // 2
    for i in range(5, 0, -1):
        rr = int(radius * (i * 0.9))
        alpha = min(255, int(intensity / i))
        pygame.draw.circle(glow, (255, 210, 120, alpha), (cx, cy), rr)
    surface.blit(glow, (CENTER[0] - cx, CENTER[1] - cy))
    pygame.draw.circle(surface, (255, 240, 190), CENTER, radius)


def draw_wrapped_text(surface, text, font, color, x, y, max_width, line_gap=4):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        test = word if not line else f"{line} {word}"
        if font.size(test)[0] <= max_width:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)

    yy = y
    for entry in lines:
        rendered = font.render(entry, True, color)
        surface.blit(rendered, (x, yy))
        yy += rendered.get_height() + line_gap
    return yy


def draw_section(surface, title, body_lines, x, y, w, fonts):
    head_font, body_font = fonts
    panel_h = 28 + max(40, len(body_lines) * 20 + 20)
    pygame.draw.rect(surface, (21, 25, 46), (x, y, w, panel_h), border_radius=10)
    pygame.draw.rect(surface, (70, 85, 140), (x, y, w, panel_h), 1, border_radius=10)
    surface.blit(head_font.render(title, True, (255, 228, 165)), (x + 12, y + 8))
    yy = y + 36
    for line in body_lines:
        yy = draw_wrapped_text(surface, line, body_font, (225, 232, 255), x + 12, yy, w - 24, 2) + 2
    return y + panel_h + 10


def draw_nebula_type_diagram(surface, x, y, w, h):
    pygame.draw.rect(surface, (19, 23, 40), (x, y, w, h), border_radius=10)
    pygame.draw.rect(surface, (70, 85, 140), (x, y, w, h), 1, border_radius=10)
    cx = x + 62
    cy = y + h // 2
    pygame.draw.circle(surface, (255, 235, 190), (cx, cy), 12)
    pygame.draw.circle(surface, (180, 120, 210), (cx + 80, cy - 6), 30, 2)   # emission cloud
    pygame.draw.circle(surface, (120, 170, 255), (cx + 160, cy - 6), 30, 2)  # reflection cloud
    pygame.draw.circle(surface, (40, 40, 50), (cx + 240, cy - 6), 30)        # dark cloud
    pygame.draw.line(surface, (255, 210, 120), (cx + 8, cy), (cx + 50, cy - 2), 1)
    pygame.draw.line(surface, (255, 210, 120), (cx + 8, cy), (cx + 130, cy - 2), 1)


def draw_star_formation_diagram(surface, x, y, w, h):
    pygame.draw.rect(surface, (19, 23, 40), (x, y, w, h), border_radius=10)
    pygame.draw.rect(surface, (70, 85, 140), (x, y, w, h), 1, border_radius=10)
    points = [
        (x + 60, y + h // 2),
        (x + 140, y + h // 2),
        (x + 220, y + h // 2),
        (x + 300, y + h // 2),
    ]
    sizes = [24, 18, 12, 14]
    colors = [(120, 150, 230), (170, 200, 255), (245, 205, 150), (255, 240, 185)]
    for i in range(len(points) - 1):
        pygame.draw.line(surface, (160, 170, 210), (points[i][0] + 28, points[i][1]), (points[i + 1][0] - 28, points[i + 1][1]), 2)
    for pt, size, color in zip(points, sizes, colors):
        pygame.draw.circle(surface, color, pt, size, 0 if color == colors[-1] else 2)


def draw_background(screen, stars):
    screen.fill((5, 7, 18))
    for sx, sy, sr in stars:
        pygame.draw.circle(screen, (120, 130, 170), (sx, sy), sr)
    pygame.draw.line(screen, (45, 52, 90), (SIM_AREA_RIGHT, 0), (SIM_AREA_RIGHT, HEIGHT), 2)


def star_params(sim_time):
    total_duration = sum(stage["duration"] for stage in STAGES)
    local_time = sim_time % total_duration
    stage_idx, local_t = get_stage(local_time)
    stage = STAGES[stage_idx]
    next_stage = STAGES[min(stage_idx + 1, len(STAGES) - 1)]
    t = smoothstep(local_t)
    return {
        "stage_idx": stage_idx,
        "stage": stage,
        "radius_scale": lerp(stage["radius_scale"], next_stage["radius_scale"], t),
        "core_radius": int(lerp(stage["core_radius"], next_stage["core_radius"], t)),
        "core_intensity": int(lerp(stage["core_intensity"], next_stage["core_intensity"], t)),
        "rotation": lerp(stage["rotation"], next_stage["rotation"], t),
        "turbulence": lerp(stage["turbulence"], next_stage["turbulence"], t),
        "particle_color": lerp_color(stage["particle_color"], next_stage["particle_color"], t),
    }


def draw_mode_nebula(screen, particles, sim_time):
    pulse = 0.7 + 0.3 * math.sin(sim_time * 1.2)
    for p in particles:
        r = 0.85 + 0.18 * math.sin(sim_time * 0.8 + p.offset)
        x, y = p.position(sim_time * 0.5, r, 0.25, 14)
        col = (int(120 + 60 * pulse), int(140 + 50 * pulse), int(205 + 40 * pulse))
        pygame.draw.circle(screen, col, (x, y), 2)
    draw_glow(screen, 14, 50)


def draw_mode_types(screen, sim_time):
    y = HEIGHT // 2 - 10
    x0 = 95
    gap = 200

    emission_pulse = 35 + int(7 * math.sin(sim_time * 4))
    pygame.draw.circle(screen, (255, 120, 130), (x0, y), emission_pulse, 2)
    pygame.draw.circle(screen, (255, 160, 160), (x0, y), 8)

    rx = x0 + gap
    pygame.draw.circle(screen, (130, 180, 255), (rx, y), 34, 2)
    beam_y = y + int(8 * math.sin(sim_time * 2))
    pygame.draw.line(screen, (240, 240, 255), (rx - 70, beam_y), (rx - 24, y), 2)
    pygame.draw.circle(screen, (255, 240, 200), (rx - 80, beam_y), 6)

    dx = x0 + gap * 2
    for i in range(16):
        sx = dx - 50 + i * 7
        sy = y - 42 + (i * 11) % 84
        pygame.draw.circle(screen, (180, 190, 230), (sx, sy), 1)
    shift = int(6 * math.sin(sim_time))
    pygame.draw.circle(screen, (30, 30, 40), (dx + shift, y), 34)

    labels = [("Emission", x0 - 34), ("Reflection", rx - 44), ("Dark", dx - 12)]
    for text, lx in labels:
        font = pygame.font.SysFont("consolas", 17)
        screen.blit(font.render(text, True, (220, 228, 250)), (lx, y + 52))


def draw_mode_nursery(screen, particles, sim_time):
    cores = [(260, 320), (430, 270), (525, 420)]
    collapse = 0.65 - 0.33 * (0.5 + 0.5 * math.sin(sim_time * 0.45))
    for p in particles[:280]:
        core = cores[int(p.base_angle * 10) % len(cores)]
        angle = p.base_angle + sim_time * p.speed * 0.65
        r = max(14, p.base_radius * collapse)
        x = int(core[0] + r * math.cos(angle))
        y = int(core[1] + r * math.sin(angle))
        pygame.draw.circle(screen, (160, 185, 240), (x, y), 2)
    for cx, cy in cores:
        pygame.draw.circle(screen, (255, 225, 175), (cx, cy), 10)
        pygame.draw.circle(screen, (255, 180, 120), (cx, cy), 24, 1)


def draw_mode_star_formation(screen, particles, sim_time):
    params = star_params(sim_time)
    for p in particles:
        x, y = p.position(sim_time, params["radius_scale"], params["rotation"], params["turbulence"])
        pygame.draw.circle(screen, params["particle_color"], (x, y), 2)
    draw_glow(screen, params["core_radius"], params["core_intensity"])
    return params["stage_idx"], params["stage"]["name"]


def draw_mode_diagrams(screen, sim_time):
    box_x, box_y = 90, 190
    box_w, box_h = 580, 260
    draw_star_formation_diagram(screen, box_x, box_y, box_w, box_h)
    marker_x = box_x + 64 + int((sim_time * 55) % 250)
    pygame.draw.circle(screen, (255, 220, 120), (marker_x, box_y + box_h // 2), 6)
    font = pygame.font.SysFont("consolas", 17)
    text = "Animated flow: cloud -> collapse -> protostar -> star"
    screen.blit(font.render(text, True, (220, 228, 250)), (box_x + 35, box_y + box_h + 16))


def draw_mode_summary(screen, sim_time):
    timeline_y = HEIGHT // 2 - 10
    xs = [110, 230, 350, 470, 590]
    labels = ["Cloud", "Core", "Proto", "Fusion", "Star"]
    active = int((sim_time * 0.75) % len(xs))
    for i, x in enumerate(xs):
        color = (255, 220, 125) if i == active else (150, 170, 220)
        pygame.draw.circle(screen, color, (x, timeline_y), 18 if i == active else 14)
        if i < len(xs) - 1:
            pygame.draw.line(screen, (140, 150, 200), (x + 20, timeline_y), (xs[i + 1] - 20, timeline_y), 2)
        font = pygame.font.SysFont("consolas", 15)
        screen.blit(font.render(labels[i], True, (220, 228, 250)), (x - 24, timeline_y + 30))


def draw_right_panel(screen, active_section, panel_fonts):
    panel_head_font, panel_body_font, stage_font = panel_fonts
    panel_x = SIM_AREA_RIGHT + 16
    panel_w = WIDTH - panel_x - 16
    y = 20
    title = "Section Simulations"
    y = draw_section(
        screen,
        title,
        ["Press 1-6 to switch between separate simulations for each nebula topic."],
        panel_x,
        y,
        panel_w,
        (panel_head_font, panel_body_font),
    )
    tabs = " ".join([f"[{i + 1}]" for i in range(len(SECTION_CONTENT))])
    screen.blit(stage_font.render(tabs, True, (180, 195, 235)), (panel_x + 12, y + 4))
    y += 26

    content = SECTION_CONTENT[active_section]
    y = draw_section(
        screen,
        content["title"],
        content["lines"],
        panel_x,
        y,
        panel_w,
        (panel_head_font, panel_body_font),
    )

    if active_section == 1:
        draw_nebula_type_diagram(screen, panel_x, y, panel_w, 82)
    elif active_section in (3, 4):
        draw_star_formation_diagram(screen, panel_x, y, panel_w, 82)
    elif active_section == 5:
        draw_section(
            screen,
            "Summary",
            ["Nebulae are cosmic gas/dust clouds. Dense regions collapse into protostars and become stars."],
            panel_x,
            y,
            panel_w,
            (panel_head_font, panel_body_font),
        )


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Nebula and Star Formation Simulation")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("georgia", 30, bold=True)
    info_font = pygame.font.SysFont("georgia", 20)
    stage_font = pygame.font.SysFont("consolas", 16)
    panel_head_font = pygame.font.SysFont("georgia", 18, bold=True)
    panel_body_font = pygame.font.SysFont("georgia", 15)

    particles = [Particle() for _ in range(360)]
    stars = [(random.randint(0, WIDTH), random.randint(0, HEIGHT), random.randint(1, 2)) for _ in range(180)]
    sim_time = 0.0
    active_section = 0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        sim_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and pygame.K_1 <= event.key <= pygame.K_6:
                active_section = event.key - pygame.K_1

        draw_background(screen, stars)

        mode_name = SECTION_CONTENT[active_section]["title"]
        if active_section == 0:
            draw_mode_nebula(screen, particles, sim_time)
        elif active_section == 1:
            draw_mode_types(screen, sim_time)
        elif active_section == 2:
            draw_mode_nursery(screen, particles, sim_time)
        elif active_section == 3:
            _, mode_name = draw_mode_star_formation(screen, particles, sim_time)
            mode_name = f"4) How Stars Form - {mode_name}"
        elif active_section == 4:
            draw_mode_diagrams(screen, sim_time)
        else:
            draw_mode_summary(screen, sim_time)

        title = title_font.render("Nebula to Star Simulation", True, (240, 240, 255))
        stage_text = info_font.render(f"Active Simulation: {mode_name}", True, (255, 230, 170))
        hint = stage_font.render("Press 1-6 to change section | ESC to quit", True, (175, 185, 210))
        screen.blit(title, (26, 20))
        screen.blit(stage_text, (26, 62))
        screen.blit(hint, (26, 92))

        bar_x, bar_y = 26, HEIGHT - 120
        bar_w, bar_h = SIM_AREA_RIGHT - 52, 70
        pygame.draw.rect(screen, (20, 24, 46), (bar_x, bar_y, bar_w, bar_h), border_radius=10)
        pygame.draw.rect(screen, (60, 75, 130), (bar_x, bar_y, bar_w, bar_h), 2, border_radius=10)

        segment_w = bar_w / len(SECTION_CONTENT)
        for i, section in enumerate(SECTION_CONTENT):
            x = int(bar_x + i * segment_w)
            active = i == active_section
            color = (250, 210, 120) if active else (140, 150, 190)
            label = stage_font.render(section["title"].split(") ")[0], True, color)
            screen.blit(label, (x + 30, bar_y + 26))
            if i > 0:
                pygame.draw.line(screen, (55, 60, 100), (x, bar_y + 8), (x, bar_y + bar_h - 8), 1)

        draw_right_panel(screen, active_section, (panel_head_font, panel_body_font, stage_font))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
