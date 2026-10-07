"""Project Horae rev A netlist: the single source of truth for gen_sch.py and gen_pcb.py.

Each part: (ref, symbol lib_id, value, footprint, LCSC, {pin: net}, block).
Unlisted pins are left unconnected. Reference designs: Espressif ESP32-S3 schematic checklist,
Good Display GDEM0097T61 datasheet p.20, Watchy v3 (sqfmi/watchy-hardware).
"""

R0402, C0402, C0603 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0603_1608Metric"
L0402, L0603 = "Inductor_SMD:L_0402_1005Metric", "Inductor_SMD:L_0603_1608Metric"
R0201, C0201, L0201 = "Resistor_SMD:R_0201_0603Metric", "Capacitor_SMD:C_0201_0603Metric", "Inductor_SMD:L_0201_0603Metric"
PAD15, PAD20, PAD20R = "TestPoint:TestPoint_Pad_D1.5mm", "TestPoint:TestPoint_Pad_2.0x2.0mm", "TestPoint:TestPoint_Pad_D2.0mm"
PAD10 = "TestPoint:TestPoint_Pad_D1.0mm"

# LCSC parts (basic where possible). 0201s and the 0.4 mm WCSPs need JLC Standard PCBA (Economic stops at 0402).
C100N, C1U25, C10U = "C66938", "C52923", "C15525"   # C100N is 0201 (space); others basic 0402
C1U = "C76935"   # 1uF 10V 0201 (space)
C18P = "C62164"  # 18pF C0G 0201 (FH 0201CG180J500NT): all four crystal load caps on one line
R10K, R1M, R10M, R20K, R22, R2R2 = "C473048", "C295786", "C3036920", "C295787", "C155743", "C327251"   # 0201 (space; no basic 0201 exists) except R2R2
# R10M: LIZ CR0201FH1005G +-1% (C3036920). Yageo's RC0201FR-0710ML (C469663) carries a 6445-piece minimum buy (~$9 per
# order) with only ~1.2k in stock; C320452 is +-5%. R510 (touch series R): FH RC-01W5100FT +-1% (C304550), not Yageo
# RC0201FR-07510RL (C57784, same 6016-piece / ~$9 minimum buy).
R510 = "C304550"


def R(ref, val, lcsc, a, b, block, fp=R0201):
    return (ref, "Device:R", val, fp, lcsc, {"1": a, "2": b}, block)


def C(ref, val, lcsc, a, b, block, fp=C0201):
    return (ref, "Device:C", val, fp, lcsc, {"1": a, "2": b}, block)


def TP(ref, net, fp, block):
    return (ref, "Connector:TestPoint", net, fp, "", {"1": net}, block)


ESP_PINS = {
    "1": "RF_CHIP", "2": "VDD3P3", "3": "VDD3P3", "4": "EN",
    "5": "BOOT",          # GPIO0 strap: test pad only
    # side facing the antenna (pins 6-14, GPIO1-9): touch, interrupts, haptics, ADC - all RTC GPIOs (deep-sleep wake)
    "6": "TOUCH_DOWN",    # GPIO1  T1
    "7": "TOUCH_BACK",    # GPIO2  T2
    "8": "TOUCH_MENU",    # GPIO3  T3
    "9": "TOUCH_UP",      # GPIO4  T4
    "10": "VIB",          # GPIO5   haptic motor
    "11": "CHG_STAT",     # GPIO6   charger CHG (open drain, low = charging): wake on dock
    "12": "BAT_ADC",      # GPIO7   ADC1_CH6
    "13": "I2C_SDA",      # GPIO8   the accelerometer sits right above these two: I2C runs straight up to its south pads ...
    "14": "I2C_SCL",      # GPIO9   (ULP bit-bangs I2C on any RTC GPIO)
    # side facing the display connector (pins 15-27): SPI + I2C on RTC GPIOs so the ULP core can refresh the time alone
    "15": "ACC_INT1",     # GPIO10  ... and the interrupts straight east to its west pads; step/tap wake
    "16": "ACC_INT2",     # GPIO11
    "17": "EPD_BUSY",     # GPIO12
    "18": "EPD_RES",      # GPIO13
    "19": "EPD_DC",       # GPIO14
    "20": "+3V3",         # VDD3P3_RTC
    "21": "XTAL32_P",     # GPIO15  32.768 kHz crystal: the ESP32 RTC keeps time (no RTC IC; phone sync corrects drift)
    "22": "XTAL32_N",     # GPIO16
    "23": "EPD_CS",       # GPIO17
    "24": "EPD_SCK",      # GPIO18
    "25": "USB_DM", "26": "USB_DP",
    "27": "EPD_MOSI",     # GPIO21
    "43": "MIC_DATA",     # GPIO38  PDM data in (the ROM drives GPIO38 LOW in USB-OTG download mode: harmless on an input)
    "44": "MIC_CLK",      # GPIO39  PDM clock (I2S0 PDM RX); low in download mode = mic asleep
    "45": "MIC_VDD",      # GPIO40  powers the mic directly: 0 uA when off. MTDO is driven HIGH by the ROM in USB-OTG download
                          #         mode (TRM v1.8 Table 33.4-2), so it may only be the mic's VDD, never its DATA output
    "29": "VDD_SPI", "46": "+3V3", "49": "TXD0", "50": "RXD0",
    "53": "XTAL_N", "54": "XTAL_P_L", "55": "+3V3", "56": "+3V3", "57": "GND",
}

PARTS = [
    # --- MCU ---
    ("U1", "MCU_Espressif:ESP32-S3", "ESP32-S3FN8", "horae:QFN-56-1EP_7x7mm_P0.4mm_EP4x4mm_Espressif", "C2913196", ESP_PINS, "mcu"),   # EP: Espressif 3x3 windows + 12 tented vias
    ("Y1", "Device:Crystal_GND24", "40MHz 12pF", "Crystal:Crystal_SMD_2520-4Pin_2.5x2.0mm", "C19076867",
     {"1": "XTAL_P", "2": "GND", "3": "XTAL_N", "4": "GND"}, "mcu"),   # KYX K2C400001210: +-10 ppm, +-20 ppm -40..85 C, ESR <= 40R
    C("C1", "18pF", C18P, "XTAL_P", "GND", "mcu"),     # 2 x (12 - ~3 stray); trim for +-10 ppm in TX-tone mode
    C("C2", "18pF", C18P, "XTAL_N", "GND", "mcu"),
    ("Y2", "Device:Crystal", "32.768kHz 12.5pF", "horae:CRYSTAL-SMD_L2.1-W1.2-P1.50", "C403709",
     {"1": "XTAL32_P", "2": "XTAL32_N"}, "mcu"),                     # 2012, ESR 70k (Espressif: <= 70k)
    C("C32", "18pF", C18P, "XTAL32_P", "GND", "mcu"),  # ~12 pF vs CL 12.5: ~+4 ppm, trimmed in firmware against the 40 MHz
    C("C33", "18pF", C18P, "XTAL32_N", "GND", "mcu"),
    ("L1", "Device:L", "24nH", L0201, "C2991767", {"1": "XTAL_P_L", "2": "XTAL_P"}, "mcu"),  # Espressif: series L on XTAL_P
    ("L2", "Device:L", "2nH", L0201, "C86125", {"1": "+3V3", "2": "VDD3P3"}, "mcu"),       # LC filter on VDD3P3
    C("C3", "1uF", C1U, "VDD3P3", "GND", "mcu"),
    C("C5", "10uF", C10U, "+3V3", "GND", "mcu", C0402),   # bulk at the ESP32 (the buck sits at the far end)
    C("C6", "1uF", C1U, "+3V3", "GND", "mcu"),            # VDDA pins 55/56 (Espressif reference schematic: C3 1 uF + C2 10 nF), at the pins on F.Cu
    C("C36", "10nF", "C326875", "+3V3", "GND", "mcu"),    # VDDA HF bypass, next to C6 (same 10 nF line as C19)
    C("C7", "100nF", C100N, "+3V3", "GND", "mcu"),        # ends up at U6 Vdd/Vdd_IO (C20 is the one at pin 20)
    C("C34", "100nF", C100N, "+3V3", "GND", "mcu"),       # VDD3P3_CPU pin 46 (Espressif ref C10): place at the pin
    C("C8", "1uF", C1U, "VDD_SPI", "GND", "mcu"),
    C("C9", "100nF", C100N, "VDD_SPI", "GND", "mcu"),
    R("R1", "10k", R10K, "+3V3", "EN", "mcu"),
    C("C10", "1uF", C1U, "EN", "GND", "mcu"),
    # RF: match from the openEMS sim of the trimmed antenna in the two-shell case with spring bars (hardware/rf, report_v3); C12 is a tuning spot
    C("C11", "0.5pF", "C85920", "RF_CHIP", "GND", "rf"),        # Murata GRM0335C1HR50BA01D +-0.1 pF
    ("L3", "Device:L", "0.8nH", L0201, "C156227", {"1": "RF_CHIP", "2": "RF_ANT"}, "rf"),   # Murata LQP03TN0N8B02D +-0.1 nH: match from RF v4, 2026-10-06 (LQP03HQ0N8B02D C2043648 is the higher-Q alternative)
    C("C12", "DNP", "", "RF_ANT", "GND", "rf"),
    ("AE1", "Device:Antenna_Chip", "PCB IFA", "horae:SWRA117D", "", {"1": "RF_ANT", "2": "GND"}, "rf"),

    # --- power: pogo USB in -> BQ25101 linear charger (IN rated 30 V, but U4 clamps VBUS from ~6 V; <= 75 nA battery drain) -> TPS62840 buck ---
    ("U2", "horae:BQ25101YFPR", "BQ25101", "horae:DSBGA-6_L0.9-W1.6-R2-C3-P0.40-BL", "C478468",
     {"A1": "VBAT", "A2": "VBUS", "B1": "CHG_TS", "B2": "CHG_ISET", "C1": "CHG_STAT", "C2": "GND"}, "power"),
    R("R2", "6.8k", "C274877", "CHG_ISET", "GND", "power"),     # 135 A*ohm / 6.8k = 19.9 mA = 0.5C of a 40 mAh cell (5.6k only if >= 48 mAh)
    R("R7", "2.7k", "C273271", "CHG_ISET", "CHG_ISET_RC", "power"),   # SLUSBV8C 8.3.6/9.2.2: ISET RC for ICHG < 50 mA, at U2.B2
    C("C19", "10nF", "C326875", "CHG_ISET_RC", "GND", "power"),
    R("R5", "10k", R10K, "CHG_TS", "GND", "power"),              # no NTC: 10k on TS per datasheet
    C("C13", "4.7uF/25V", "C2858031", "VBUS", "GND", "power", C0402),   # IN 1-10 uF: the 1uF/10V 0201 kept ~0.24 uF at 5 V; at U2.A2
    C("C14", "1uF", C1U, "VBAT", "GND", "power"),              # charger OUT cap at U2.A1, TI typ. app. (C15 is 13 mm away at the buck)
    C("C15", "10uF", C10U, "VBAT", "GND", "power", C0402),     # buck VIN
    ("U3", "horae:TPS62840YBGR", "TPS62840", "horae:DSBGA-6_L1.4-W1.0-R2-C3-P0.40-BL", "C2071139",
     {"A1": "GND", "A2": "+3V3", "B1": "VBAT", "B2": "BUCK_SW", "C1": "VBAT", "C2": "BUCK_VSET"}, "power"),
    ("L5", "Device:L", "2.2uH", "horae:IND-SMD_L1.6-W0.8", "C31123918", {"1": "BUCK_SW", "2": "+3V3"}, "power"),   # LSCND1608HKT2R2MF: 0.8 mm, Isat 1.3 A, 0.20 ohm
    R("R6", "267k", "C423627", "BUCK_VSET", "GND", "power"),    # VSET table: 267k -> 3.3 V
    C("C17", "10uF", C10U, "+3V3", "GND", "power", C0402),     # buck output
    R("R3", "10M", R10M, "VBAT", "BAT_ADC", "power"),     # 0.2 uA divider; calibrate per board at the 4.20 V end of charge
    R("R4", "10M", R10M, "BAT_ADC", "GND", "power"),
    C("C18", "100nF", C100N, "BAT_ADC", "GND", "power"),
    ("U4", "Power_Protection:USBLC6-2P6", "USBLC6-2P6", "Package_TO_SOT_SMD:SOT-666", "C15999",   # genuine ST (C2827693 is TECH PUBLIC)
     {"1": "USB_DP_POGO", "2": "GND", "3": "USB_DM_POGO", "4": "USB_DM", "5": "VBUS", "6": "USB_DP"}, "power"),
    # Flow-through ESD (ST DS4260 fig. 17): the pogo pads enter U4 on pins 1/3 (I/O1/I/O2) and leave from pins 6/4 to the ESP32,
    # so the clamp sits on the path, not on a stub. Pins 1-6 and 3-4 are joined inside the USBLC6.

    # --- sensors ---
    ("U6", "horae:LIS2DUX12TR", "LIS2DUX12", "horae:LGA-12_L2.0-W2.0-P0.50-TL_LIS2DUX12TR", "C17548754",
     {"1": "I2C_SCL", "2": "+3V3", "3": "+3V3", "4": "I2C_SDA", "6": "GND", "7": "GND", "8": "GND", "9": "+3V3",
      "10": "+3V3", "11": "ACC_INT2", "12": "ACC_INT1"}, "sensors"),   # CS=VDDIO -> I2C, SA0=VDDIO -> 0x19 (ties to the CS pin next to it); DS14071 Table 1: pin 5 NC, pin 7 RES/EXT_CLK to GND
    C("C20", "100nF", C100N, "+3V3", "GND", "sensors"),
    # I2C (accelerometer only) uses the ESP32 internal pull-ups (~45k): ~0.6 us rise at 100 kHz on this short bus

    # --- display: GDEM0097T61 via FH34SRJ, booster per GD typical application circuit ---
    # FH34SRJ: the FPC slot is on the fitting-nail side and the tails sit under the back-flip actuator (Hirose catalog p.2/6/8),
    # so J1 turns 180 deg (gen_pcb.py) to face the U-bend at -X. Display pin 1 (GDR) stays at -Y and meets contact 18: pad = 19 - pin.
    ("J1", "horae:FH34SRJ-18S-0.5SH", "FH34SRJ-18S-0.5SH(50)", "horae:FFC-SMD_18P-P0.50_FH34SRJ-18S-0.5SH", "C3169386",
     {"18": "EPD_GDR", "17": "EPD_RESE", "16": "EPD_VSHR", "15": "EPD_BUSY", "14": "EPD_RES", "13": "EPD_DC",
      "12": "EPD_CS", "11": "EPD_SCK", "10": "EPD_MOSI", "9": "+3V3", "8": "GND", "7": "EPD_VDD",
      "5": "EPD_VSH1", "4": "PREVGH", "3": "EPD_VSL", "2": "PREVGL", "1": "EPD_VCOM",
      "19": "GND", "20": "GND"}, "display"),          # pad 6 = display pin 13 (VPP, "keep open")
    ("Q1", "horae:PMZ390UN,315", "PMZ390UN", "horae:SOT-883-3_L1.0-W0.6-BR", "C458236",
     {"1": "EPD_GDR", "2": "EPD_RESE", "3": "EPD_SW"}, "display"),
    ("L4", "Device:L", "47uH", "horae:IND-SMD_L3.0-W3.0_SWPA3010S", "C96826", {"1": "+3V3", "2": "EPD_SW"}, "display"),   # Sunlord SWPA3010S470MT, catalog land 0.8 x 2.7: 3x3x1.0, Isat 0.22 A rated / 0.35 typ, DCR 1.95 ohm
    C("C35", "10uF", C10U, "+3V3", "GND", "display", C0402),   # booster/VCI input bulk at L4 pin 1 (GD p.20 C4 4.7 uF)
    R("R11", "1M", R1M, "EPD_GDR", "GND", "display"),
    R("R12", "2.2", R2R2, "EPD_RESE", "GND", "display", R0402),   # booster current sense (>= 0.05 W): 0402
    ("D1", "Device:D_Schottky", "PMEG3002AEL", "horae:SOD-882_L1.0-W0.6-RD", "C478015", {"1": "EPD_PUMP", "2": "PREVGL"}, "display"),
    ("D2", "Device:D_Schottky", "PMEG3002AEL", "horae:SOD-882_L1.0-W0.6-RD", "C478015", {"1": "GND", "2": "EPD_PUMP"}, "display"),
    ("D3", "Device:D_Schottky", "PMEG3002AEL", "horae:SOD-882_L1.0-W0.6-RD", "C478015", {"1": "PREVGH", "2": "EPD_SW"}, "display"),
    C("C22", "4.7uF/25V", "C2858031", "EPD_SW", "EPD_PUMP", "display", C0402),
    C("C24", "2.2uF/25V", "C307418", "PREVGL", "GND", "display", C0402),   # +-15..20 V rail: 0.17-0.24 uF left vs 0.07-0.10
    C("C25", "2.2uF/25V", "C307418", "PREVGH", "GND", "display", C0402),   # +-15..20 V rail: 0.17-0.24 uF left vs 0.07-0.10
    C("C26", "1uF/25V", C1U25, "EPD_VSHR", "GND", "display", C0402),
    C("C27", "1uF/25V", C1U25, "EPD_VDD", "GND", "display", C0402),
    C("C28", "2.2uF/25V", "C307418", "EPD_VSH1", "GND", "display", C0402),   # +-15..20 V rail: 0.17-0.24 uF left vs 0.07-0.10
    C("C29", "2.2uF/25V", "C307418", "EPD_VSL", "GND", "display", C0402),   # +-15..20 V rail: 0.17-0.24 uF left vs 0.07-0.10
    C("C30", "1uF/25V", C1U25, "EPD_VCOM", "GND", "display", C0402),

    # --- UI: capacitive touch + haptics + mic ---
    ("MIC1", "horae:LMD2718T261-OA1", "LMD2718T261", "horae:MIC-SMD_6P-L2.8-W1.9-P0.98-TL", "C5373237",
     {"1": "GND", "2": "GND", "3": "GND", "4": "MIC_VDD", "5": "MIC_DATA", "6": "MIC_CLK"}, "ui"),   # top-port PDM, L/R=GND (left)
    C("C31", "100nF", C100N, "MIC_VDD", "GND", "ui"),
    TP("TCH1", "TOUCH_UP_E", "horae:TouchPad_4.0x1.6mm", "ui"), TP("TCH2", "TOUCH_DOWN_E", "horae:TouchPad_4.0x1.6mm", "ui"),
    TP("TCH3", "TOUCH_MENU_E", "horae:TouchPad_4.0x1.6mm", "ui"), TP("TCH4", "TOUCH_BACK_E", "horae:TouchPad_4.0x1.6mm", "ui"),
    *[R(r, "510", R510, n, n + "_E", "ui") for r, n in (("R14", "TOUCH_UP"), ("R15", "TOUCH_DOWN"),
                                                             ("R16", "TOUCH_MENU"), ("R17", "TOUCH_BACK"))],   # HDG 1.3.14: 510R within 1 mm of the pin
    ("Q2", "horae:PMZ390UN,315", "PMZ390UN", "horae:SOT-883-3_L1.0-W0.6-BR", "C458236",
     {"1": "VIB", "2": "GND", "3": "MOT_N"}, "ui"),            # coin ERM low-side switch (~80 mA)
    R("R13", "1M", R1M, "VIB", "GND", "ui"),                     # gate pull-down: motor off while the ESP32 boots
    ("D4", "Device:D_Schottky", "PMEG3002AEL", "horae:SOD-882_L1.0-W0.6-RD", "C478015", {"1": "VBAT", "2": "MOT_N"}, "ui"),   # flyback (0.2 A cont., 1 A rep. peak)

    # --- pads (bottom side; no parts) ---
    TP("TP1", "VBUS", PAD10, "pads"), TP("TP2", "USB_DM_POGO", PAD10, "pads"),
    TP("TP3", "USB_DP_POGO", PAD10, "pads"), TP("TP4", "GND", PAD10, "pads"),
    TP("TP5", "VBAT", PAD20, "pads"), TP("TP6", "GND", PAD20R, "pads"),         # battery wires: + square, - round
    TP("TP7", "VBAT", PAD15, "pads"), TP("TP8", "MOT_N", PAD15, "pads"),        # coin motor leads (soldered)
    TP("TP9", "TXD0", PAD10, "pads"), TP("TP10", "RXD0", PAD10, "pads"),
    TP("TP11", "EN", PAD10, "pads"), TP("TP12", "BOOT", PAD10, "pads"), TP("TP13", "+3V3", PAD10, "pads"),
]

POWER_NETS = ["GND", "+3V3", "VBAT", "VBUS", "VDD3P3", "VDD_SPI"]   # get PWR_FLAGs (VDD_SPI is driven inside the ESP32)

if __name__ == "__main__":
    refs = [p[0] for p in PARTS]
    assert len(refs) == len(set(refs)), "duplicate refs"
    nets = {}
    for p in PARTS:
        for pin, net in p[5].items():
            nets.setdefault(net, []).append(f"{p[0]}.{pin}")
    lonely = {n: v for n, v in nets.items() if len(v) < 2}
    assert not lonely, f"single-pin nets: {lonely}"
    placed = [p for p in PARTS if p[4]]
    print(f"{len(PARTS)} parts ({len(placed)} JLC-placed), {len(nets)} nets, {len({p[4] for p in placed})} unique LCSC lines")
