#!/usr/bin/env python3
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]

fig, ax = plt.subplots(1, 1, figsize=(14, 10))
ax.set_xlim(0, 10)
ax.set_ylim(0, 8)
ax.axis("off")

bg_color = "#12121a"
fig.patch.set_facecolor(bg_color)
ax.set_facecolor(bg_color)

states = {
    "PENDING": (1.5, 5.5),
    "FIRING": (5, 5.5),
    "SILENCED": (8.5, 5.5),
    "ESCALATED": (5, 3),
    "RESOLVING": (5, 1),
    "RESOLVED": (1.5, 1),
}

state_color = "#282c34"
border_color = "#63708c"
text_color = "#c8ced6"


def draw_state(name, pos):
    x, y = pos
    box = FancyBboxPatch(
        (x - 0.6, y - 0.4),
        1.2,
        0.8,
        boxstyle="round,pad=0.05,rounding_size=0.15",
        facecolor=state_color,
        edgecolor=border_color,
        linewidth=2,
    )
    ax.add_patch(box)
    ax.text(
        x,
        y,
        name,
        ha="center",
        va="center",
        fontsize=14,
        color=text_color,
        fontweight="bold",
    )


transitions = [
    ("PENDING", "FIRING", "hits >= threshold"),
    ("FIRING", "SILENCED", "silence window"),
    ("FIRING", "ESCALATED", "escalation timer"),
    ("FIRING", "RESOLVING", "misses >= threshold"),
    ("RESOLVING", "RESOLVED", "confirmed normal"),
    ("SILENCED", "FIRING", "window expired"),
    ("ESCALATED", "RESOLVING", "misses >= threshold"),
]

arrow_style = dict(
    arrowstyle="->", color="#63708c", lw=1.5, connectionstyle="arc3,rad=0"
)


def draw_arrow(start, end, label):
    sx, sy = states[start]
    ex, ey = states[end]

    if start == "PENDING" and end == "FIRING":
        sx += 0.6
        ex -= 0.6
        ax.annotate("", xy=(ex, ey), xytext=(sx, sy), arrowprops=arrow_style)
        mx = (sx + ex) / 2
        ax.text(mx, sy + 0.3, label, ha="center", fontsize=9, color="#8b94a0")

    elif start == "FIRING" and end == "SILENCED":
        sx += 0.6
        ex -= 0.6
        ax.annotate("", xy=(ex, ey), xytext=(sx, sy), arrowprops=arrow_style)
        mx = (sx + ex) / 2
        ax.text(mx, sy + 0.3, label, ha="center", fontsize=9, color="#8b94a0")

    elif start == "FIRING" and end == "ESCALATED":
        ax.annotate(
            "",
            xy=(ex + 0.3, ey + 0.4),
            xytext=(sx, sy - 0.4),
            arrowprops=dict(
                arrowstyle="->",
                color="#63708c",
                lw=1.5,
                connectionstyle="arc3,rad=-0.3",
            ),
        )
        ax.text(5.5, 4.2, label, fontsize=9, color="#8b94a0")

    elif start == "FIRING" and end == "RESOLVING":
        ax.annotate(
            "",
            xy=(ex, ey + 0.4),
            xytext=(sx, sy - 0.4),
            arrowprops=dict(
                arrowstyle="->", color="#63708c", lw=1.5, connectionstyle="arc3,rad=0.2"
            ),
        )
        ax.text(5.7, 3.2, label, fontsize=9, color="#8b94a0")

    elif start == "RESOLVING" and end == "RESOLVED":
        ex += 0.6
        sx -= 0.6
        ax.annotate("", xy=(ex, ey), xytext=(sx, sy), arrowprops=arrow_style)
        mx = (sx + ex) / 2
        ax.text(mx, sy - 0.3, label, ha="center", fontsize=9, color="#8b94a0")

    elif start == "SILENCED" and end == "FIRING":
        ex += 0.6
        sx -= 0.6
        ax.annotate("", xy=(ex, ey), xytext=(sx, sy), arrowprops=arrow_style)
        mx = (sx + ex) / 2
        ax.text(mx, sy - 0.3, label, ha="center", fontsize=9, color="#8b94a0")

    elif start == "ESCALATED" and end == "RESOLVING":
        ax.annotate(
            "",
            xy=(ex, ey + 0.4),
            xytext=(sx + 0.3, sy - 0.4),
            arrowprops=dict(
                arrowstyle="->", color="#63708c", lw=1.5, connectionstyle="arc3,rad=0.3"
            ),
        )
        ax.text(4.2, 2.0, label, fontsize=9, color="#8b94a0")


for start, end, label in transitions:
    draw_arrow(start, end, label)

for name, pos in states.items():
    draw_state(name, pos)

ax.set_title(
    "Marmot Alert State Machine",
    fontsize=18,
    color=text_color,
    pad=20,
    fontweight="bold",
)

plt.tight_layout()
plt.savefig(
    "state_machine_diagram.png",
    dpi=150,
    facecolor=bg_color,
    bbox_inches="tight",
    pad_inches=0.5,
)
print("Saved: state_machine_diagram.png")
