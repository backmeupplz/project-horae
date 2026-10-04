"""Project Horae rev A netlist: the single source of truth for gen_sch.py and gen_pcb.py.

Each part: (ref, symbol lib_id, value, footprint, LCSC, {pin: net}, block).
Unlisted pins are left unconnected. Reference designs: Espressif ESP32-S3 schematic checklist,
Good Display GDEM0097T61 datasheet p.20, Watchy v3 (sqfmi/watchy-hardware).
"""

R0402, C0402, C0603 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0603_1608Metric"
L0402, L0603 = "Inductor_SMD:L_0402_1005Metric", "Inductor_SMD:L_0603_1608Metric"
R0201, C0201, L0201 = "Resistor_SMD:R_0201_0603Metric", "Capacitor_SMD:C_0201_0603Metric", "Inductor_SMD:L_0201_0603Metric"
PAD15, PAD20 = "TestPoint:TestPoint_Pad_D1.5mm", "TestPoint:TestPoint_Pad_2.0x2.0mm"
PAD10 = "TestPoint:TestPoint_Pad_D1.0mm"

# LCSC parts (basic where possible)
C100N, C1U25, C10U, C22U, C4U7_25 = "C66938", "C52923", "C15525", "C59461", "C69335"   # C100N is 0201 (space); others basic 0402 except C4U7_25
C1U = "C76935"   # 1uF 10V 0201 (space)
R10K, R1M, R10M, R20K, R22, R2R2 = "C473048", "C295786", "C320452", "C295787", "C155743", "C327251"   # 0201 (space; no basic 0201 exists) except R2R2


def R(ref, val, lcsc, a, b, block, fp=R0201):
    return (ref, "Device:R", val, fp, lcsc, {"1": a, "2": b}, block)


def C(ref, val, lcsc, a, b, block, fp=C0201):
    return (ref, "Device:C", val, fp, lcsc, {"1": a, "2": b}, block)


def TP(ref, net, fp, block):
    return (ref, "Connector:TestPoint", net, fp, "", {"1": net}, block)


ESP_PINS = {
    "1": "RF_CHIP", "2": "VDD3P3", "3": "VDD3P3", "4": "EN",
    "5": "BOOT",          # GPIO0 strap: test pad only
    "6": "EPD_BUSY",      # GPIO1   display on RTC GPIOs so a ULP/wake-stub can drive it later
    "7": "EPD_RES",       # GPIO2
    "8": "TOUCH_UP",      # GPIO3  T3
    "9": "EPD_SCK",       # GPIO4
    "10": "RTC_INT",      # GPIO5
    "11": "TOUCH_BACK",   # GPIO6  T6   capacitive touch (Watchy button GPIOs where possible)
    "12": "TOUCH_MENU",   # GPIO7  T7   deep-sleep touch wake
    "13": "TOUCH_DOWN",   # GPIO8  T8
    "14": "BAT_ADC",      # GPIO9   ADC1_CH8
    "15": "CHG_STAT",     # GPIO10
    "16": "I2C_SCL",      # GPIO11
    "17": "I2C_SDA",      # GPIO12
    "18": "EPD_MOSI",     # GPIO13
    
    "20": "+3V3",         # VDD3P3_RTC
    "21": "EPD_DC",       # GPIO15
    "22": "EPD_CS",       # GPIO16
    "23": "VIB",          # GPIO17  haptic motor
    "19": "PPG_INT",      # GPIO14  spare wake-capable pin, brought to a pad for a future heart-rate flex
    "24": "ACC_INT1",     # GPIO18
    "27": "ACC_INT2",     # GPIO21
    "25": "ESP_DM", "26": "ESP_DP",
        "29": "VDD_SPI", "46": "+3V3", "49": "TXD0", "50": "RXD0",
    "53": "XTAL_N", "54": "XTAL_P_L", "55": "+3V3", "56": "+3V3", "57": "GND",
}

PARTS = [
    # --- MCU ---
    ("U1", "MCU_Espressif:ESP32-S3", "ESP32-S3FN8", "Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP4x4mm_ThermalVias", "C2913196", ESP_PINS, "mcu"),
    ("Y1", "Device:Crystal_GND24", "40MHz 15pF", "Crystal:Crystal_SMD_2520-4Pin_2.5x2.0mm", "C284176",
     {"1": "XTAL_P", "2": "GND", "3": "XTAL_N", "4": "GND"}, "mcu"),
    C("C1", "24pF", "C285108", "XTAL_P", "GND", "mcu"),
    C("C2", "24pF", "C285108", "XTAL_N", "GND", "mcu"),
    ("L1", "Device:L", "24nH", L0201, "C2991767", {"1": "XTAL_P_L", "2": "XTAL_P"}, "mcu"),  # Espressif: series L on XTAL_P
    ("L2", "Device:L", "2nH", L0201, "C86125", {"1": "+3V3", "2": "VDD3P3"}, "mcu"),       # LC filter on VDD3P3
    C("C3", "1uF", C1U, "VDD3P3", "GND", "mcu"),
    C("C5", "10uF", C10U, "+3V3", "GND", "mcu", C0402),
    C("C6", "100nF", C100N, "+3V3", "GND", "mcu"),        # VDDA
    C("C7", "100nF", C100N, "+3V3", "GND", "mcu"),        # VDD3P3_RTC / CPU
    C("C8", "1uF", C1U, "VDD_SPI", "GND", "mcu"),
    C("C9", "100nF", C100N, "VDD_SPI", "GND", "mcu"),
    R("R1", "10k", R10K, "+3V3", "EN", "mcu"),
    C("C10", "1uF", C1U, "EN", "GND", "mcu"),
    # RF: match from the openEMS sim of the trimmed antenna in the case (hardware/rf); C12 is a tuning spot
    C("C11", "0.9pF", "C471401", "RF_CHIP", "GND", "rf"),
    ("L3", "Device:L", "0.6nH", L0201, "C77699", {"1": "RF_CHIP", "2": "RF_ANT"}, "rf"),
    C("C12", "DNP", "", "RF_ANT", "GND", "rf"),
    ("AE1", "Device:Antenna_Chip", "PCB IFA", "horae:SWRA117D", "", {"1": "RF_ANT", "2": "GND"}, "rf"),

    # --- power: pogo USB in, charger, LDO ---
    ("U2", "horae:TP4054", "TP4054", "horae:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BL", "C32574",
     {"1": "CHG_STAT", "2": "GND", "3": "VBAT", "4": "VBUS", "5": "PROG"}, "power"),
    R("R2", "20k", R20K, "PROG", "GND", "power"),        # 1000 V / 20k = 50 mA (0.5C for ~100 mAh)
    C("C13", "1uF", C1U, "VBUS", "GND", "power"),
    C("C15", "22uF", C22U, "VBAT", "GND", "power", C0603),  # Wi-Fi TX bursts
    ("U3", "horae:RT9080-33GJ5", "RT9080-33", "horae:TSOT-23-5_L2.9-W1.6-P0.95-LS2.8-BL", "C841192",
     {"1": "VBAT", "2": "GND", "3": "VBAT", "5": "+3V3"}, "power"),
    C("C16", "1uF", C1U, "VBAT", "GND", "power"),
    C("C17", "10uF", C10U, "+3V3", "GND", "power", C0402),
    R("R3", "10M", R10M, "VBAT", "BAT_ADC", "power"),     # 0.2 uA divider
    R("R4", "10M", R10M, "BAT_ADC", "GND", "power"),
    C("C18", "100nF", C100N, "BAT_ADC", "GND", "power"),
    ("U4", "Power_Protection:USBLC6-2P6", "USBLC6-2P6", "Package_TO_SOT_SMD:SOT-666", "C2827693",
     {"1": "USB_DP", "2": "GND", "3": "USB_DM", "4": "USB_DM", "5": "VBUS", "6": "USB_DP"}, "power"),
    R("R7", "22", R22, "USB_DP", "ESP_DP", "power"),
    R("R8", "22", R22, "USB_DM", "ESP_DM", "power"),

    # --- sensors ---
    ("U5", "horae:RV-3032-C732.768KHZ-2.5PPM-TA-QC", "RV-3032-C7", "horae:OSC-SMD_8P-L3.2-W1.5-P0.90-BL", "C5127802",
     {"1": "GND", "2": "I2C_SDA", "3": "RTC_INT", "4": "GND", "5": "GND", "6": "+3V3", "8": "I2C_SCL"}, "sensors"),
    C("C19", "100nF", C100N, "+3V3", "GND", "sensors"),
    ("U6", "horae:LIS2DUX12TR", "LIS2DUX12", "horae:LGA-12_L2.0-W2.0-P0.50-TL_LIS2DUX12TR", "C17548754",
     {"1": "I2C_SCL", "2": "+3V3", "3": "GND", "4": "I2C_SDA", "6": "GND", "7": "GND", "8": "GND", "9": "+3V3",
      "10": "+3V3", "11": "ACC_INT2", "12": "ACC_INT1"}, "sensors"),   # CS=VDDIO -> I2C, SA0=GND -> 0x18; RES to GND (verify)
    C("C20", "100nF", C100N, "+3V3", "GND", "sensors"),
    # I2C uses the ESP32 internal pull-ups (~45k): ~0.6 us rise at 100 kHz on this short bus

    # --- display: GDEM0097T61 via FH34SRJ, booster per GD typical application circuit ---
    ("J1", "horae:FH34SRJ-18S-0.5SH", "FH34SRJ-18S-0.5SH(50)", "horae:FFC-SMD_18P-P0.50_FH34SRJ-18S-0.5SH", "C3169386",
     {"1": "EPD_GDR", "2": "EPD_RESE", "3": "EPD_VSHR", "4": "EPD_BUSY", "5": "EPD_RES", "6": "EPD_DC",
      "7": "EPD_CS", "8": "EPD_SCK", "9": "EPD_MOSI", "10": "+3V3", "11": "GND", "12": "EPD_VDD",
      "14": "EPD_VSH1", "15": "PREVGH", "16": "EPD_VSL", "17": "PREVGL", "18": "EPD_VCOM",
      "19": "GND", "20": "GND"}, "display"),          # pin 13 (VPP) NC per datasheet
    ("Q1", "Transistor_FET:AO3400A", "AO3400A", "Package_TO_SOT_SMD:SOT-23", "C20917",
     {"1": "EPD_GDR", "2": "EPD_RESE", "3": "EPD_SW"}, "display"),
    ("L4", "Device:L", "47uH", "Inductor_SMD:L_Sunlord_SWPA3012S", "C83420", {"1": "+3V3", "2": "EPD_SW"}, "display"),
    R("R11", "1M", R1M, "EPD_GDR", "GND", "display"),
    R("R12", "2.2", R2R2, "EPD_RESE", "GND", "display", R0402),   # booster current sense: keep 0402 for power
    ("D1", "Device:D_Schottky", "B5819WS", "Diode_SMD:D_SOD-323", "C64886", {"1": "EPD_PUMP", "2": "PREVGL"}, "display"),
    ("D2", "Device:D_Schottky", "B5819WS", "Diode_SMD:D_SOD-323", "C64886", {"1": "GND", "2": "EPD_PUMP"}, "display"),
    ("D3", "Device:D_Schottky", "B5819WS", "Diode_SMD:D_SOD-323", "C64886", {"1": "PREVGH", "2": "EPD_SW"}, "display"),
    C("C22", "4.7uF/25V", C4U7_25, "EPD_SW", "EPD_PUMP", "display", C0603),
    C("C24", "1uF/25V", C1U25, "PREVGL", "GND", "display", C0402),
    C("C25", "1uF/25V", C1U25, "PREVGH", "GND", "display", C0402),
    C("C26", "1uF/25V", C1U25, "EPD_VSHR", "GND", "display", C0402),
    C("C27", "1uF/25V", C1U25, "EPD_VDD", "GND", "display", C0402),
    C("C28", "1uF/25V", C1U25, "EPD_VSH1", "GND", "display"),
    C("C29", "1uF/25V", C1U25, "EPD_VSL", "GND", "display", C0402),
    C("C30", "1uF/25V", C1U25, "EPD_VCOM", "GND", "display", C0402),

    # --- UI: capacitive touch + haptics ---
    TP("TCH1", "TOUCH_UP", "horae:TouchPad_4.0x1.6mm", "ui"), TP("TCH2", "TOUCH_DOWN", "horae:TouchPad_4.0x1.6mm", "ui"),
    TP("TCH3", "TOUCH_MENU", "horae:TouchPad_4.0x1.6mm", "ui"), TP("TCH4", "TOUCH_BACK", "horae:TouchPad_4.0x1.6mm", "ui"),
    ("Q2", "horae:CJ3134K_C62503", "CJ3134K", "horae:SOT-723_L1.2-W0.8-P0.40-LS1.2-BR", "C62503",
     {"1": "VIB", "2": "GND", "3": "MOT_N"}, "ui"),            # coin ERM low-side switch (~80 mA)
    R("R13", "1M", R1M, "VIB", "GND", "ui"),                     # gate pull-down: motor off while the ESP32 boots
    ("D4", "Device:D_Schottky", "B5819WS", "Diode_SMD:D_SOD-323", "C64886", {"1": "VBAT", "2": "MOT_N"}, "ui"),   # flyback

    # --- pads (bottom side; no parts) ---
    TP("TP1", "VBUS", PAD10, "pads"), TP("TP2", "USB_DM", PAD10, "pads"),
    TP("TP3", "USB_DP", PAD10, "pads"), TP("TP4", "GND", PAD10, "pads"),
    TP("TP5", "VBAT", PAD20, "pads"), TP("TP6", "GND", PAD20, "pads"),          # battery wires
    TP("TP7", "VBAT", PAD15, "pads"), TP("TP8", "MOT_N", PAD15, "pads"),        # coin motor: spring contacts or wires
    TP("TP9", "TXD0", PAD10, "pads"), TP("TP10", "RXD0", PAD10, "pads"),
    TP("TP14", "I2C_SDA", PAD10, "pads"), TP("TP15", "I2C_SCL", PAD10, "pads"), TP("TP16", "PPG_INT", PAD10, "pads"),   # PPG flex hookup
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
