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
ANTENNA_ZONE = 6.0    # PCB past the display glass at +X: the whole antenna sits clear of the glass (less detuning, more room under it)
ANT_UNDER_GLASS = 0.0 # keep-out starts at the glass edge
PCB_T = 0.8           # JLC Economic PCBA minimum
PCB_W = 16.5          # 15.5 was too dense to place + route at JLC 4-layer rules (2026-10-03)
PART_H = 1.45         # tallest top-side part: EVQ-P7M01P 3D model is 1.45 (datasheet 1.35); everything else <= 1.06
GAP = 0.05

# --- battery (placeholder envelope until a real cell is picked) + haptics ---
BAT_W, BAT_T = 16.0, 2.5   # length is whatever is left between the motor and the antenna zone (below)
BAT_SWELL = 0.25
MOTOR_D, MOTOR_T = 8.0, 2.0   # coin ERM (8 x 2.0 "0820" class; Precision Microdrives C0720 is 7 x 2.1) in the battery layer
POGO_STRIP = 4.0              # pogo + battery-wire pads at the -X end
MOTOR_PAD_DX = 1.6            # motor pads (1.5 mm, PCB bottom) at MOTOR_X +- this, y = 0: spring-contact coin motor presses up on them

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

# battery layer, -X to +X: pogo strip | motor | battery | 0.5 | antenna zone (plastic only)
POGO_X = -CAV_L / 2 + POGO_STRIP / 2
MOTOR_X = -CAV_L / 2 + POGO_STRIP + 0.3 + MOTOR_D / 2
BAT_X1 = ANT_X0 - 0.5
BAT_X0 = MOTOR_X + MOTOR_D / 2 + 0.3
BAT_L = BAT_X1 - BAT_X0
POGO_PITCH = 2.3          # 1.0 mm pads; leaves room for the 2x2 mm battery pads at the edges
POGO_NETS = ["VBUS", "USB_DM", "USB_DP", "GND"]   # order along +Y

# buttons: side-push on the long edges, avoiding the antenna end
BUTTON_X = [-5.2, 5.5]          # clear of the FFC connector mounting pads (-X) and the ESP32 (+X)

# case ledges under the glass ends rest on the PCB top (GAP above it): no top-side parts there.
# Both glass ends: |y| >= LEDGE_Y and within LEDGE inside the glass end (x <= DISP_X0 + LEDGE, x >= DISP_X1 - LEDGE);
# the case also rests full-width on the antenna strip past the glass (x >= DISP_X1 + 0.15, copper only there).
LEDGE = 1.0
LEDGE_Y = FPC_W / 2 + 0.5

if __name__ == "__main__":
    assert BAT_W <= CAV_W - 0.6 and MOTOR_T <= BAT_T + BAT_SWELL, "battery layer does not fit"
    print(f"case {CASE_L:.1f} x {CASE_W:.1f} x {CASE_T:.2f} mm, pcb {PCB_L:.1f} x {PCB_W}")
    print(f"pogo strip {POGO_STRIP} mm at x={POGO_X:.2f}; motor at x={MOTOR_X:.2f}; battery {BAT_L:.1f} x {BAT_W} x {BAT_T}")

# board details the case depends on (set by hardware/gen_pcb.py)
BUTTON_INSET = 0.4    # switch body sits this far in from the PCB edge (nub tip at |y| = PCB_W/2 + 0.65 - BUTTON_INSET)
FFC_X = DISP_X0 + 6.9 # FH34SRJ centre; ribbon enters from -X
PCB_CORNER_R = 2.0    # must stay below the case inner corner radius (CORNER_R - WALL)
BATPAD_Y = 6.05       # 2x2 mm battery wire pads on the PCB bottom at x = POGO_X, y = +-BATPAD_Y
