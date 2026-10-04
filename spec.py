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
X0_EXTRA = 1.2               # extra length at -X so the battery keeps its full volume next to the motor

# --- board ---
ANTENNA_ZONE = 6.0    # PCB past the display glass at +X: the whole antenna sits clear of the glass (less detuning, more room under it)
ANT_UNDER_GLASS = 0.0 # keep-out starts at the glass edge
PCB_T = 0.8           # JLC Economic PCBA minimum
PCB_W = 16.5          # 15.5 was too dense to place + route at JLC 4-layer rules (2026-10-03)
PART_H = 1.20         # tallest top-side part: SWPA3012S 47 uH booster inductor (side switches replaced by capacitive touch)
GAP = 0.05

# --- battery (placeholder envelope until a real cell is picked) + haptics ---
BAT_W, BAT_T = 16.0, 2.5   # length is whatever is left between the motor and the antenna zone (below)
BAT_SWELL = 0.25
MOTOR_D, MOTOR_T = 6.0, 2.0   # coin ERM, 6 x 2.0 (C0620 class), spring-contact version: no soldering
MOTOR_ZONE = MOTOR_D + 0.6    # battery-layer zone at -X: motor in the middle, pogo pads + battery pads + magnets in its corners
MOTOR_PAD_DX = 1.4            # motor spring pads (1.5 mm, PCB bottom) at MOTOR_X +- this, y = 0

# derived plan-view sizes
CAV_L = X0_EXTRA + FPC_BEND + DISP_L + ANTENNA_ZONE   # inner cavity length
CAV_W = PCB_W + 0.2
CASE_L = CAV_L + 2 * WALL
CASE_W = CAV_W + 2 * WALL
PCB_L = CAV_L - 0.2

# X positions
DISP_X0 = -CAV_L / 2 + X0_EXTRA + FPC_BEND        # glass edge at the FPC end
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

# battery layer, -X to +X: motor zone (pogo/battery pads + magnets in its corners) | battery | 0.5 | antenna zone (plastic only)
MOTOR_X = -CAV_L / 2 + MOTOR_ZONE / 2
BAT_X0 = -CAV_L / 2 + MOTOR_ZONE + 0.3
BAT_X1 = ANT_X0 - 0.5
BAT_L = BAT_X1 - BAT_X0
POGO_DX, POGO_Y = 1.8, 4.4    # four 1.0 mm pogo pads at (MOTOR_X +- POGO_DX, +-POGO_Y), clear of the motor
POGO_PADS = [(MOTOR_X - POGO_DX, -POGO_Y, "VBUS"), (MOTOR_X + POGO_DX, -POGO_Y, "USB_DM"),
             (MOTOR_X - POGO_DX, POGO_Y, "USB_DP"), (MOTOR_X + POGO_DX, POGO_Y, "GND")]
BATPAD_X, BATPAD_Y = MOTOR_X, 6.9   # 2x2 mm battery wire pads (PCB bottom); the dock magnets sit under them in the floor

# capacitive touch electrodes on the PCB top at the long edges (case: solid TPU windows over them, no holes)
TOUCH_X = [-5.2, 5.5]
TOUCH_L, TOUCH_W = 4.0, 1.6     # electrode size; centred TOUCH_W/2 + 0.3 in from the PCB edge

# case ledges under the glass ends rest on the PCB top (GAP above it): no top-side parts there.
# Both glass ends: |y| >= LEDGE_Y and within LEDGE inside the glass end (x <= DISP_X0 + LEDGE, x >= DISP_X1 - LEDGE);
# the case also rests full-width on the antenna strip past the glass (x >= DISP_X1 + 0.15, copper only there).
LEDGE = 1.0
LEDGE_Y = FPC_W / 2 + 0.5

if __name__ == "__main__":
    assert BAT_W <= CAV_W - 0.6 and MOTOR_T <= BAT_T + BAT_SWELL, "battery layer does not fit"
    print(f"case {CASE_L:.1f} x {CASE_W:.1f} x {CASE_T:.2f} mm, pcb {PCB_L:.1f} x {PCB_W}")
    print(f"motor at x={MOTOR_X:.2f}; battery {BAT_L:.1f} x {BAT_W} x {BAT_T} = {BAT_L*BAT_W*BAT_T:.0f} mm3 (original 27x15x2.5 = 1012)")

# board details the case depends on (set by hardware/gen_pcb.py)
FFC_X = DISP_X0 + 6.9 # FH34SRJ centre; ribbon enters from -X
PCB_CORNER_R = 2.0    # must stay below the case inner corner radius (CORNER_R - WALL)
