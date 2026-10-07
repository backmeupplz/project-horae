# Building Horae rev A

Print, bring-up, assembly and the firmware rules the hardware depends on. Parts and where to buy them: [ORDER.md](ORDER.md).
Everything is held by the closed case: no glue and no screws. The only soldering is 2 battery wires, 2 motor wires and the
dock's 4 wires.

## 1. Print

Print the two plates on the A1 mini with a 0.4 nozzle and a textured PEI plate. Files are in `cad/out/plates/`.

| Plate | Filament | Settings |
|---|---|---|
| `petg.3mf`: both shells, dock tray and lid | PETG Basic or Matte | 0.1 mm layers **with a 0.1 mm first layer**, because the first layer is the skin over the watch's magnets. No supports. |
| `tpu.3mf`: bezel gasket, shell seal, 4 glass cushions, pogo seal, mic seal, dock grip pad | TPU 90A, dried, from the external spool | 0.1 mm layers. Give the bezel gasket 0.08 mm layers in its object settings (it is 2 layers). Print slowly: 15 mm/s for the gasket. |

The carbon-fibre version uses `petg-cf.3mf` (PETG-CF, hardened nozzle) and `petg-cf-set.3mf` (the colour-matched PETG
parts) instead of `petg.3mf`. Use TPU 90A for every TPU part: 95A is about twice as stiff and overloads the snaps.

After printing:
- **Pin bores:** drill the 4 pin bores in the bottom shell with a 1.0 mm bit in a pin vise, because FDM prints small
  holes undersize.
- **Ear holes:** check that a spring bar's tips go into the 1.1 mm ear holes. If not, ream them with the same bit.
- **Mic vent:** cut a 1.4 × 1.0 mm patch of bare 0.25 mm ePTFE film (no adhesive) with a fresh blade.

**Test print checklist** (no electronics needed):
- The empty shells close with 4 clicks. They open again with a spudger in the pry notch at either end.
- A 3 × 1 mm magnet clicks into each well in the bottom shell from the inside and doesn't fall out when you turn the
  shell over.
- The spring bars and strap fit the ears.
- The dock lid snaps into the tray.

## 2. Check the parts

- **Cell:** measure it before you build. It must be at most 21.4 × 16.0 × 3.25 mm including the protection board (that
  end at most 3.5 thick and 2.5 long). Buy cells no thicker than 3.05 mm. A "301520" cell is listed at 20 ± 2 mm and must
  measure 21.4 or less.
- **Board:**
  - Break it out of its frame and file every tab nub flush with the edge. The board sits on six small crush ribs, so
    keep the edge clean.
  - Under a loupe, check U4's pin-1 dot. Also check that J1's pins aren't bridged.
- **Display:** hold it by the glass edges. Don't crease its ribbon near the glass.

## 3. Bring-up on the bench, before closing anything

The charger can't run the board without a cell, so bring the board up from a bench supply in place of the cell.

1. **Power.** Set the supply to 3.8 V with a 50 mA current limit. Connect + to the square pad TP5 and − to the round pad
   TP6 on the bottom. A blank ESP32 waits in its ROM bootloader and draws a few tens of mA. Check 3.3 V on TP13.
2. **Display.** Flip J1's actuator up and push the ribbon straight into the slot on the −X side (the board end without
   the antenna) as far as it goes. Then close the actuator. J1 has contacts top and bottom.
3. **USB.** Connect GND, D− and D+ to the pogo pads, through a finished dock or a cut USB cable. Leave VBUS off while the
   bench supply powers the board. The ESP32-S3 appears as a USB-Serial/JTAG device and flashes with `esptool.py`.
4. **First flash.** Burn eFuse `DIS_USB_OTG_DOWNLOAD_MODE` (`espefuse.py burn_efuse DIS_USB_OTG_DOWNLOAD_MODE`).
   USB-Serial/JTAG flashing keeps working, and the ROM's USB-OTG download mode can no longer change the mic pins.
5. **Test each block:**
   - display refresh;
   - accelerometer at I²C address 0x19 on GPIO8/9;
   - mic capture;
   - motor at reduced PWM (see section 7);
   - battery ADC;
   - the charger's CHG line with VBUS applied.
6. **Touch.** Read touch raw counts in the closed case before relying on them.
7. **Antenna.** If you have a VNA, check the antenna match in the closed case, strap on (`hardware/README.md`, review item 4).

## 4. Solder the battery and motor

- **Battery:**
  - Trim the cell's leads to about 15 mm and tin them.
  - Solder **red to the square pad (TP5, +)** and **black to the round pad (TP6, −)**. The bottom also has + and − marks.
  - A reversed cell is shorted through the chips until its protection trips. Check twice.
- **Motor:** solder its two leads to TP7 and TP8 (an ERM has no polarity).
- **Leads:** fold each lead into a small slack loop for the bottom shell's lead channel.

## 5. Assemble the watch (upside down)

1. **Top shell:** lip face down.
2. **Vent and gasket:** lay the vent patch on the lip over the mic outlet and slide its outer edge into the slot. Then
   lay the bezel gasket on the lip.
3. **Display:** face down, with its ribbon already plugged into the board.
4. **Cushions:** one on each glass corner.
5. **Mic seal:** into its relief.
6. **Board:** fold it over the display, parts down, between the crush ribs.
7. **Battery and motor:** into their places, with the lead loops in the channel.
8. **Pogo seal:** the one-piece seal onto the pogo pads.
9. **Magnets:**
   - To get the poles right, stick each 3 × 1 mm magnet onto the dock magnet it will sit over. The face that touches the
     dock faces out.
   - Click each magnet into its well from the inside.
   - Seen from the outside, with the watch on the dock the right way round, the back magnet's N pole faces down and the
     front one's S pole.
10. **Close:** put the seal ring on the floor plate and press the bottom shell on until all 4 snaps click.
11. **Strap:** fit the spring bars and the strap.

To open the case again, use a spudger in the pry notch under the strap at either end.

## 6. Build the dock

Spring pins in the lid, wired to the Adafruit 6050 on the tray's pegs; the lid then snaps into the tray.

Seen from above into the open tray (lid off), with the USB-C port toward you, the 4 pins form a 2 × 2 group at the left
end:

| Pin | Net | Wire to the 6050 pad marked |
|---|---|---|
| back-left | VBUS | VBUS |
| back-right | D− | D- |
| front-left | GND | GND |
| front-right | D+ | D+ |

- **Wires:** use 2–3 cm of 30 AWG, and twist the D+ and D− pair. Leave the SBU and CC pads free; the 6050's own
  5.1 kΩ CC resistors make any USB-C charger give 5 V.
- **Magnets:** 3 × 3 mm, back row S pole up and front row N pole up, at both ends. Press them into the lid from below, up
  to the retaining lip.
- **Order:** press the pins' collars up under the lid plate, seat the 6050 on its two pegs and snap the lid in. Then
  press the TPU grip pad's 4 stems into the tray floor.
- **Check:** docked the right way round, the watch's mic hole faces you and its pin end is on the left. Turned end for
  end, the magnets push it off, so VBUS never lands on GND.

Diagram: `media/2026-10-07/cad-dock-wiring.png`.

## 7. Firmware rules the hardware depends on

- **Motor:** the VC0625B001L is rated 2.5 V (2.0–3.5 V), but Q2 switches it from the battery at 3.5–4.2 V. Drive it
  with 20–25 kHz PWM at a duty of 2.5 V / VBAT, never above 3.5 V / VBAT, and soft-start it over 10–20 ms.
- **Deep sleep:**
  - Hold GPIO38–40 (the mic) low with `gpio_hold_en` and `gpio_deep_sleep_hold_en`.
  - Hold the display's CS and RES high and DC, SCK and MOSI low.
  - Don't enable a pull-down on BUSY.
  - Put the panel in deep sleep (0x10, 0x01) and resend the image after waking, because the panel loses its RAM.
- **Wake:**
  - Wake on the accelerometer's wrist-tilt or double-tap interrupt and on CHG_STAT, both through EXT1. Set the
    accelerometer interrupt active-low to match CHG.
  - Also enable one touch channel, scanning every 100–200 ms with few charge cycles, and scan all four after waking.
  - Never use ESP-IDF's default touch settings in deep sleep: they cost hundreds of µA.
  - Expect about 27 days on 40 mAh and 37 days on 55 mAh with a refresh every minute.
- **Battery ADC:** the divider is 10 MΩ / 10 MΩ, so calibrate each board at the 4.20 V end of charge.
- **Power safety:**
  - Use the highest brown-out level, and refuse flash writes below about 3.4 V.
  - On these tiny cells, cap Wi-Fi TX power, keep BLE at 0 dBm or below, and avoid the radio below about 3.6 V.
- **I²C:** run it at 100 kHz, because the bus uses the ESP32's internal pull-ups. The ULP has to bit-bang it:
  GPIO10/11 aren't ULP I²C pins.
- **Charging:**
  - The charger has a 10-hour safety timer. Deep-sleep while docked and stay awake only to flash.
  - Use USB-Serial/JTAG, not TinyUSB, so automatic download mode keeps working.
