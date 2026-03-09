"""
Generate Assets/entelgia_correlation_map.png

Produces a styled parameter-correlation diagram for the Entelgia cognitive
architecture.  Run from the repository root:

    python scripts/generate_correlation_map.py

Requires: matplotlib
"""

import os
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

# ---------------------------------------------------------------------------
# Layout & theme
# ---------------------------------------------------------------------------

BG = "#0d1117"
CARD_COLORS = {
    "id":          "#2d1a00",
    "ego":         "#0a1e1a",
    "superego":    "#1a0a30",
    "sa":          "#0a201a",
    "conflict":    "#2d0a0a",
    "emotion":     "#1a0a30",
    "energy":      "#0a2010",
    "stagnation":  "#1a1500",
    "temperature": "#1a1000",
    "unresolved":  "#2d1a00",
    "pressure":    "#1a0a0a",
    "hijack":      "#2d0a1e",
    "ltm":         "#0a1a30",
    "circularity": "#0a2818",
}

BORDER_COLORS = {
    "id":          "#ef4444",
    "ego":         "#0d9488",
    "superego":    "#7c3aed",
    "sa":          "#059669",
    "conflict":    "#ef4444",
    "emotion":     "#7c3aed",
    "energy":      "#14b8a6",
    "stagnation":  "#f59e0b",
    "temperature": "#f59e0b",
    "unresolved":  "#ef4444",
    "pressure":    "#ef4444",
    "hijack":      "#ef4444",
    "ltm":         "#14b8a6",
    "circularity": "#14b8a6",
}

TITLE_COLOR = "#e2e8f0"
SUBTITLE_COLOR = "#94a3b8"
BODY_COLOR = "#cbd5e1"
LABEL_COLOR = "#64748b"
FORMULA_BG = "#0f172a"
FORMULA_TEXT = "#e2e8f0"
FORMULA_ACCENT = "#14b8a6"

# ---------------------------------------------------------------------------
# Parameter card data
# ---------------------------------------------------------------------------

PARAMS = [
    ("id",          "Id",              "Raw impulse & desire.\nPushes toward novelty\nand aggression."),
    ("ego",         "Ego",             "The mediator. Tries to balance\nId and SuperEgo.\nGets eroded when conflict is high."),
    ("superego",    "SuperEgo",        "Moral constraint & rules.\nPushes toward caution\nand guilt."),
    ("sa",          "Self-Awareness",  "Grows slowly each turn.\nHigher SA = deeper\nmemory retrieval."),
    ("conflict",    "Conflict Index",  "How much internal tension exists\nright now. Calculated as the\ndistance between drives."),
    ("emotion",     "Emotion",         "Label + intensity per turn.\nAnger boosts Id.\nFear boosts SuperEgo."),
    ("energy",      "Energy",          "Depletes every turn.\nHigh conflict = faster drain.\nHits 0 — Dream cycle triggers."),
    ("stagnation",  "Stagnation",      "How repetitive is the dialogue?\nFeeds Drive Pressure (20%)."),
    ("temperature", "Temperature",     "LLM creativity level.\nDriven directly by the\ndominant drive."),
    ("unresolved",  "Unresolved",      "Open questions not answered.\nFeeds Drive Pressure (25%)."),
    ("pressure",    "Drive Pressure",  "The overall urgency level of the agent.\nCombines all stress signals\ninto one score."),
    ("hijack",      "Limbic Hijack",   "When pressure ≥ 8.0, emotion\noverrides rational control.\nSuperEgo suppressed. Id takes over."),
    ("ltm",         "LTM Promotion",   "High emotion intensity + affect gate\n→ memory enters conscious LTM.\nThis is the main finding of the paper."),
    ("circularity", "Circularity",     "How much the dialogue is looping.\nHybrid: Jaccard keywords\n+ semantic embeddings."),
]

FORMULAS = [
    (
        "Conflict",
        "Conflict = |Id − Ego| + |SuperEgo − Ego|",
        "The further Id and SuperEgo pull away from Ego, the higher the conflict.",
    ),
    (
        "Energy drain",
        "Energy drain / turn = random(8–15) + 0.4 × conflict",
        "High conflict makes the agent mentally exhausted faster — earlier sleep.",
    ),
    (
        "Drive Pressure",
        "Drive Pressure = 0.45×conflict + 0.25×unresolved + 0.20×stagnation + 0.10×energy",
        'The single number that tells you how "stressed" the agent is right now.',
    ),
    (
        "LTM Promotion",
        "LTM Promotion gate = emotion intensity  (not scalar importance)",
        "Conscious memories have significantly higher emotion intensity than subconscious ones.\n"
        "p = 8×10⁻⁵,  d = 0.84.",
    ),
    (
        "Circularity",
        "Circularity = 0.5 × Jaccard(keywords) + 0.5 × cosine(embeddings)",
        "If ≥ 3 turn-pairs score above 0.5, Fixy flags circular reasoning and intervenes.",
    ),
]

LEGEND = [
    ("#ef4444", "Strong positive correlation"),
    ("#14b8a6", "Medium correlation"),
    ("#f59e0b", "Weak correlation"),
    ("#7c3aed", "Negative / inhibiting"),
]

# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

COLS = 4
ROWS_PARAMS = (len(PARAMS) + COLS - 1) // COLS   # ceil

# Figure dimensions — large so cells and text are clearly readable
CELL_W = 4.2    # inches per column
CELL_H = 3.2    # inches per row (bigger squares)
H_PAD  = 0.18  # horizontal gap between cells (fraction of CELL_W)
V_PAD  = 0.18  # vertical gap between cells (fraction of CELL_H)
MARGIN_TOP    = 1.8   # inches
MARGIN_BOTTOM = 0.6
MARGIN_LR     = 0.5

FIG_W = COLS * CELL_W + (COLS - 1) * CELL_W * H_PAD + 2 * MARGIN_LR
# formula section height
FORMULA_H = len(FORMULAS) * 1.35 + 1.0
FIG_H = (MARGIN_TOP
         + ROWS_PARAMS * CELL_H + (ROWS_PARAMS - 1) * CELL_H * V_PAD
         + 0.6            # legend strip
         + FORMULA_H
         + MARGIN_BOTTOM)


def _card(ax, x, y, w, h, key):
    """Draw one parameter card at data-coordinates (x, y)."""
    key_id, label, desc = next(p for p in PARAMS if p[0] == key)
    bg   = CARD_COLORS[key]
    edge = BORDER_COLORS[key]

    # Card background
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02",
        facecolor=bg,
        edgecolor=edge,
        linewidth=2.5,
        zorder=2,
    )
    ax.add_patch(rect)

    # Colour indicator bar on the left edge
    bar = mpatches.Rectangle(
        (x, y), w * 0.025, h,
        facecolor=edge,
        zorder=3,
    )
    ax.add_patch(bar)

    # Label
    ax.text(
        x + w * 0.06, y + h * 0.82,
        label,
        color=TITLE_COLOR,
        fontsize=14,
        fontweight="bold",
        va="top",
        ha="left",
        zorder=4,
    )

    # Description
    ax.text(
        x + w * 0.06, y + h * 0.60,
        desc,
        color=BODY_COLOR,
        fontsize=10.5,
        va="top",
        ha="left",
        linespacing=1.55,
        zorder=4,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate(output_path: str) -> None:
    fig = plt.figure(figsize=(FIG_W, FIG_H), facecolor=BG)
    ax  = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.set_xlim(0, FIG_W)
    ax.set_ylim(0, FIG_H)
    ax.axis("off")

    # ── Header ────────────────────────────────────────────────────────────
    header_y = FIG_H - MARGIN_TOP * 0.35
    ax.text(
        FIG_W / 2, header_y,
        "ENTELGIA — HOW THE MIND WORKS",
        color=TITLE_COLOR,
        fontsize=26,
        fontweight="bold",
        ha="center",
        va="top",
    )
    ax.text(
        FIG_W / 2, header_y - 0.7,
        "Parameter correlations — from Freudian drives to memory consolidation",
        color=SUBTITLE_COLOR,
        fontsize=14,
        ha="center",
        va="top",
        style="italic",
    )

    # ── Parameter cards ───────────────────────────────────────────────────
    cw = CELL_W
    ch = CELL_H
    gx = cw * H_PAD
    gy = ch * V_PAD

    grid_top = FIG_H - MARGIN_TOP
    for i, (key, _label, _desc) in enumerate(PARAMS):
        col = i % COLS
        row = i // COLS
        x = MARGIN_LR + col * (cw + gx)
        y = grid_top - (row + 1) * ch - row * gy
        _card(ax, x, y, cw, ch, key)

    # ── Legend strip ──────────────────────────────────────────────────────
    legend_y = (grid_top
                - ROWS_PARAMS * ch
                - (ROWS_PARAMS - 1) * gy
                - 0.55)
    lx = MARGIN_LR
    ax.text(lx, legend_y, "Correlation strength:", color=LABEL_COLOR,
            fontsize=11, va="center")
    lx += 2.0
    for color, text in LEGEND:
        circ = plt.Circle((lx, legend_y), 0.12, color=color, zorder=5)
        ax.add_patch(circ)
        ax.text(lx + 0.22, legend_y, text, color=SUBTITLE_COLOR,
                fontsize=10.5, va="center")
        lx += len(text) * 0.135 + 0.7

    # ── Formulas section ──────────────────────────────────────────────────
    formula_top = legend_y - 0.45
    # Section divider line
    ax.plot([MARGIN_LR, FIG_W - MARGIN_LR], [formula_top, formula_top],
            color="#1e293b", linewidth=1.5, zorder=2)
    ax.text(
        MARGIN_LR, formula_top - 0.10,
        "// KEY FORMULAS FROM THE CODE",
        color=LABEL_COLOR,
        fontsize=12,
        va="top",
        fontfamily="monospace",
    )

    fy = formula_top - 0.55
    for _title, formula, note in FORMULAS:
        # Formula box
        fw = FIG_W - 2 * MARGIN_LR
        fh = 1.1
        rect = FancyBboxPatch(
            (MARGIN_LR, fy - fh), fw, fh,
            boxstyle="round,pad=0.02",
            facecolor=FORMULA_BG,
            edgecolor="#1e293b",
            linewidth=1.2,
            zorder=2,
        )
        ax.add_patch(rect)

        # Accent bar
        bar = mpatches.Rectangle(
            (MARGIN_LR, fy - fh), 0.06, fh,
            facecolor=FORMULA_ACCENT,
            zorder=3,
        )
        ax.add_patch(bar)

        # Formula text
        ax.text(
            MARGIN_LR + 0.16, fy - 0.12,
            "⊕  " + formula,
            color=FORMULA_ACCENT,
            fontsize=11,
            fontfamily="monospace",
            fontweight="bold",
            va="top",
            zorder=4,
        )
        ax.text(
            MARGIN_LR + 0.16, fy - 0.52,
            note,
            color=BODY_COLOR,
            fontsize=9.5,
            va="top",
            linespacing=1.45,
            zorder=4,
        )
        fy -= fh + 0.22

    # ── Save ──────────────────────────────────────────────────────────────
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    plt.close(fig)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(repo_root, "Assets", "entelgia_correlation_map.png")
    generate(out)
