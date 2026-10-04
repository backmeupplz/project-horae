"""Shared dimensions for Project Horae rev A (mm). Used by cad/ and hardware/.

Axes: X = watch length (strap direction), -X = display FPC end, +X = antenna end.
Y = width. Z = up, z=0 at the bottom of the case floor. Origin XY = case centre.
"""

# --- case shell ---
WALL = 0.9            # side wall (0.2 mm nozzle -> 0.6 possible; 0.9 for first prints)
FLOOR = 0.6
LIP = 0.5             # top bezel thickness over the display glass
LIP_OVERLAP = 1.0     # how far the bezel covers the glass edge (glass border is 1.75)
BEZEL_GASKET = 0.2    # TPU seal under the bezel, on the glass border + frame top (compressed); splash resistance
CORNER_R = 3.0        # outer plan-view corner radius

# --- display: Good Display GDEM0097T61 (datasheet p.7) ---
DISP_L, DISP_W, DISP_T = 30.0, 14.15, 1.0
DISP_AA_L, DISP_AA_W = 22.26, 10.65
DISP_AA_MARGIN_FAR = 1.75    # active area to the glass end away from the FPC
FPC_W = 9.5                  # tail width at the connector
FPC_LEN = 11.38              # tail length beyond the glass edge
FPC_BEND = 1.5               # room beyond the glass for the U-bend

# --- board ---
ANTENNA_ZONE = 5.0    # PCB past the display glass at +X; Watchy meander IFA (14.35 x 5.4) sits 0.8 mm in from the end
ANT_UNDER_GLASS = 1.0 # antenna keep-out also runs 1.0 mm under the glass end margin (no active area there)
PCB_T = 0.8           # JLC Economic PCBA minimum
PCB_W = 16.5          # 15.5 was too dense to place + route at JLC 4-layer rules (2026-10-03)
PART_H = 1.35         # tallest top-side part (EVQ-P7M01P side switch); everything else <= 1.06
GAP = 0.05

# --- battery (placeholder envelope until a real cell is picked) ---
BAT_L, BAT_W, BAT_T = 27.0, 15.0, 2.5
BAT_SWELL = 0.25

# derived plan-view sizes
CAV_L = FPC_BEND + DISP_L + ANTENNA_ZONE          # inner cavity length
CAV_W = PCB_W + 0.2
CASE_L = CAV_L + 2 * WALL
CASE_W = CAV_W + 2 * WALL
PCB_L = CAV_L - 0.2

# X positions
DISP_X0 = -CAV_L / 2 + FPC_BEND                   # glass edge at the FPC end
DISP_X1 = DISP_X0 + DISP_L
DISP_CX = (DISP_X0 + DISP_X1) / 2
ANT_X0 = DISP_X1 - ANT_UNDER_GLASS                # antenna keep-out (copper-free all layers, no battery below)

# Z stack (bottom up)
Z_BAT0 = FLOOR
Z_BAT1 = Z_BAT0 + BAT_T + BAT_SWELL
Z_PCB0 = Z_BAT1 + GAP
Z_PCB1 = Z_PCB0 + PCB_T
Z_DISP0 = Z_PCB1 + PART_H + GAP
Z_DISP1 = Z_DISP0 + DISP_T
CASE_T = Z_DISP1 + BEZEL_GASKET + LIP

# battery sits toward the FPC end, clear of the antenna zone; pogo pads go in the free strip
BAT_X1 = ANT_X0 - 0.5
BAT_X0 = BAT_X1 - BAT_L
POGO_X = (-CAV_L / 2 + BAT_X0) / 2                # centre of the free strip at -X
POGO_PITCH = 2.3          # 1.0 mm pads; leaves room for the 2x2 mm battery pads at the edges
POGO_NETS = ["VBUS", "USB_DM", "USB_DP", "GND"]   # order along +Y

# buttons: side-push on the long edges, avoiding the antenna end
BUTTON_X = [-5.2, 5.5]          # clear of the FFC connector mounting pads (-X) and the ESP32 (+X)

# case ledges under the glass ends rest on the PCB top (GAP above it): no top-side parts there.
# -X: x <= DISP_X0 + LEDGE and |y| >= LEDGE_Y (the FPC passes between). +X: x >= DISP_X1 - LEDGE, full width
# (inside the antenna keep-out as long as LEDGE <= ANT_UNDER_GLASS).
LEDGE = 1.0
LEDGE_Y = FPC_W / 2 + 0.5

if __name__ == "__main__":
    assert BAT_X0 - (-CAV_L / 2) >= 3.0, "no room for pogo pads"
    print(f"case {CASE_L:.1f} x {CASE_W:.1f} x {CASE_T:.2f} mm, pcb {PCB_L:.1f} x {PCB_W}")
    print(f"free strip for pogo: {BAT_X0 + CAV_L/2:.1f} mm at x={POGO_X:.2f}")

# board details the case depends on (set by hardware/gen_pcb.py)
BUTTON_INSET = 0.4    # switch body sits this far in from the PCB edge (nub tip at |y| = PCB_W/2 + 0.65 - BUTTON_INSET)
FFC_X = DISP_X0 + 6.9 # FH34SRJ centre; ribbon enters from -X
PCB_CORNER_R = 2.0    # must stay below the case inner corner radius (CORNER_R - WALL)
BATPAD_Y = 6.05       # 2x2 mm battery wire pads on the PCB bottom at x = POGO_X, y = +-BATPAD_Y
