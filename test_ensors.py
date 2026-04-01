#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BBB Sensor Test - Terminal + CSV
Fixes applied:
  1. BBB ADC driver bug: read twice, use second value
  2. Floating AIN pin detection and clear error messages
  3. GPS via direct serial with pyserial
  4. SPI overlay loaded for spidev
  5. All values only update when pot physically moved (deadband=5)

WIRING (exact - do not deviate):

  P9 HEADER (left side, from top)
  P9.1   DGND          Encoder GND, GPS GND
  P9.3   3.3V          GPS VCC, Encoder VCC
  P9.4   3.3V          (spare)
  P9.11  UART4_RX      GPS TX  pin
  P9.13  UART4_TX      GPS RX  pin (optional)
  P9.32  VDD_ADC 1.8V  Pot1 Pin1, Pot2 Pin1  <-- MUST BE THIS PIN, NOT P9.3
  P9.34  GNDA_ADC      Pot1 Pin3, Pot2 Pin3  <-- MUST BE THIS PIN, NOT P9.1

  P9.39  AIN0          Pot1 Pin2 (wiper) -> GAUGE
  P9.40  AIN1          Pot2 Pin2 (wiper) -> CROSS-LEVEL

  P8 HEADER (right side)
  P8.11  GPIO45        Encoder CLK
  P8.12  GPIO44        Encoder DT
  P8.14  GPIO26        Encoder SW

  POTENTIOMETER (any 10k linear, 3 pins):
    Pin1 -> P9.32 (1.8V)
    Pin2 -> P9.39 or P9.40 (wiper = signal)
    Pin3 -> P9.34 (AGND)
    When you turn knob fully one way: raw~0, other way: raw~4095

  GPS u-blox NEO-M8P-2:
    VCC -> P9.3  (3.3V)
    GND -> P9.1  (DGND)
    TX  -> P9.11 (UART4_RX on BBB)
"""

import os, sys, time, csv, subprocess
from datetime import datetime

ADC0      = "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"
ADC1      = "/sys/bus/iio/devices/iio:device0/in_voltage1_raw"
GPIO_BASE = "/sys/class/gpio"
CLK_GPIO  = 45
DT_GPIO   = 44
SW_GPIO   = 26
GPS_PORT  = "/dev/ttyS4"
GPS_BAUD  = 9600

GAUGE_STD = 1676.0
ADC_MID   = 2048
ADC_FULL  = 4096
GAUGE_MPC = 150.0 / ADC_FULL
INCL_FS   = 30.0
DEG_TO_MM = 17.453
TWIST_M   = 3.5
DEADBAND  = 5
PPR       = 20
WHEEL_MM  = 62.0


def run(cmd):
    subprocess.call(cmd, stdout=open(os.devnull, "w"),
                    stderr=open(os.devnull, "w"))


def load_hw():
    # On Debian Trixie: config-pin is REMOVED. Overlays load at boot via uEnv.txt.
    # Only modprobe calls are safe to make at runtime.
    run(["sudo", "modprobe", "ti_am335x_adc"])
    run(["sudo", "modprobe", "spidev"])
    time.sleep(0.5)
    # UART4 check -- cannot be fixed at runtime on Trixie
    if not os.path.exists("/dev/ttyS4"):
        print("[UART4] /dev/ttyS4 missing. GPS unavailable.")
        print("[UART4] To fix: add to /boot/uEnv.txt and reboot:")
        print("[UART4]   uboot_overlay_addr4=/lib/firmware/BB-UART4-00A0.dtbo")


def adc_read_twice(path):
    """
    BBB ADC driver bug: first read returns stale value.
    Read twice, return second value. This is the documented fix.
    """
    try:
        with open(path) as f:
            f.read()
        with open(path) as f:
            return int(f.read().strip())
    except Exception:
        return -1


def gpio_export(num):
    val = "{}/gpio{}/value".format(GPIO_BASE, num)
    if not os.path.exists(val):
        try:
            with open("{}/export".format(GPIO_BASE), "w") as f:
                f.write(str(num))
            time.sleep(0.05)
            with open("{}/gpio{}/direction".format(GPIO_BASE, num), "w") as f:
                f.write("in")
        except Exception:
            pass


def gpio_read(num):
    try:
        with open("{}/gpio{}/value".format(GPIO_BASE, num)) as f:
            return int(f.read().strip())
    except Exception:
        return 1


enc_count    = 0
enc_last_clk = None


def enc_tick():
    global enc_count, enc_last_clk
    clk = gpio_read(CLK_GPIO)
    dt  = gpio_read(DT_GPIO)
    if enc_last_clk is None:
        enc_last_clk = clk
        return
    if clk != enc_last_clk:
        enc_count += 1 if dt != clk else -1
    enc_last_clk = clk


def enc_dist():
    return round(abs(enc_count) / max(1, PPR) * (3.14159265 * WHEEL_MM) / 1000.0, 3)


prev_raw0    = -1
prev_raw1    = -1
gauge_stable = GAUGE_STD
cross_stable = 0.0


def update_gauge(raw0, zero, mpc):
    global prev_raw0, gauge_stable
    if raw0 < 0:
        return gauge_stable
    if raw0 < 10:
        # raw=0 means wiper not connected -- show 0.0 so fault is visible
        gauge_stable = 0.0
        prev_raw0 = raw0
        return gauge_stable
    if prev_raw0 < 0 or abs(raw0 - prev_raw0) >= DEADBAND:
        prev_raw0    = raw0
        g = GAUGE_STD + (raw0 - zero) * mpc
        gauge_stable = round(max(1601.0, min(1751.0, g)), 1)
    return gauge_stable


def update_cross(raw1, offset):
    global prev_raw1, cross_stable
    if raw1 < 0:
        return cross_stable
    if raw1 > 4085:
        # saturated -- Pin1 is at 3.3V instead of 1.8V (P9.32)
        cross_stable = 999.0
        prev_raw1 = raw1
        return cross_stable
    if prev_raw1 < 0 or abs(raw1 - prev_raw1) >= DEADBAND:
        prev_raw1    = raw1
        angle = (raw1 - ADC_MID) / float(ADC_MID) * INCL_FS - offset
        cross_stable = round(max(-150.0, min(150.0, angle * DEG_TO_MM)), 2)
    return cross_stable


gps_ser  = None
gps_buf  = ""
gps_lat  = 0.0
gps_lon  = 0.0
gps_spd  = 0.0
gps_fix  = 0
gps_sats = 0


def open_gps():
    global gps_ser
    if not os.path.exists(GPS_PORT):
        print("[GPS] /dev/ttyS4 not found")
        print("[GPS] Fix: config-pin P9.11 uart  then restart script")
        return
    try:
        import serial
        gps_ser = serial.Serial(GPS_PORT, GPS_BAUD,
                                bytesize=8, parity="N",
                                stopbits=1, timeout=0.1)
        print("[GPS] Opened /dev/ttyS4 OK")
    except ImportError:
        print("[GPS] pyserial missing -- run: pip3 install pyserial")
    except Exception as e:
        print("[GPS] Error opening port: {}".format(e))


def nmea_deg(s, d):
    try:
        s = s.strip()
        if not s or "." not in s:
            return 0.0
        i   = s.index(".")
        deg = float(s[:i - 2])
        mn  = float(s[i - 2:])
        dec = deg + mn / 60.0
        return round(-dec if d.upper() in ("S", "W") else dec, 7)
    except Exception:
        return 0.0


def parse_nmea(line):
    global gps_lat, gps_lon, gps_spd, gps_fix, gps_sats
    try:
        if "*" in line:
            line = line[:line.rindex("*")]
        if not line.startswith("$"):
            return
        p   = line.split(",")
        tag = p[0].upper()
        if "GGA" in tag and len(p) >= 10:
            q = int(p[6]) if p[6].strip().isdigit() else 0
            gps_fix = q
            if q >= 1 and p[2] and p[4]:
                la = nmea_deg(p[2], p[3])
                lo = nmea_deg(p[4], p[5])
                if la or lo:
                    gps_lat, gps_lon = la, lo
            try:
                gps_sats = int(p[7]) if p[7].strip().isdigit() else gps_sats
            except Exception:
                pass
        elif "RMC" in tag and len(p) >= 8 and p[2].upper() == "A":
            if len(p) > 5 and p[3] and p[5]:
                la = nmea_deg(p[3], p[4])
                lo = nmea_deg(p[5], p[6])
                if la or lo:
                    gps_lat, gps_lon = la, lo
            if len(p) > 7 and p[7].strip():
                gps_spd = round(float(p[7]) * 1.852, 1)
    except Exception:
        pass


def poll_gps():
    global gps_buf
    if gps_ser is None:
        return
    try:
        n = gps_ser.in_waiting
        if n > 0:
            gps_buf += gps_ser.read(n).decode("ascii", errors="replace")
            while "\n" in gps_buf:
                line, gps_buf = gps_buf.split("\n", 1)
                parse_nmea(line.strip())
    except Exception:
        pass


def check_wiring(raw, name, pin):
    if raw < 0:
        return "ERROR reading {}".format(pin)
    if raw < 20:
        return "WIRING FAULT: {} raw={} -- Pin1 not at 1.8V (P9.32) or wiper disconnected from {}".format(name, raw, pin)
    if raw > 4075:
        return "WIRING FAULT: {} raw={} -- Using 3.3V instead of 1.8V. Move Pin1 to P9.32".format(name, raw)
    return "{} raw={} -- OK ({:.0f}%)".format(name, raw, raw / 40.96)


def main():
    print("Loading hardware modules (ADC, SPI, UART4)...")
    load_hw()

    for g in (CLK_GPIO, DT_GPIO, SW_GPIO):
        gpio_export(g)

    has0 = os.path.exists(ADC0)
    has1 = os.path.exists(ADC1)

    print()
    print("HARDWARE CHECK")
    print("  AIN0 (gauge)  : {}".format("OK" if has0 else "MISSING -- sudo modprobe ti_am335x_adc"))
    print("  AIN1 (cross)  : {}".format("OK" if has1 else "MISSING -- same module needed"))
    print("  GPS /dev/ttyS4: {}".format("OK" if os.path.exists(GPS_PORT) else "MISSING -- config-pin P9.11 uart"))
    print("  SPI /dev/spi  : {}".format("OK" if os.path.exists("/dev/spidev1.0") else "MISSING (not critical for pots)"))
    print()

    if not has0:
        print("CRITICAL: ADC not found. Cannot read potentiometers.")
        print("Run: sudo modprobe ti_am335x_adc")
        sys.exit(1)

    r0_start = adc_read_twice(ADC0) if has0 else -1
    r1_start = adc_read_twice(ADC1) if has1 else -1
    print(check_wiring(r0_start, "AIN0 GAUGE",  "P9.39"))
    print(check_wiring(r1_start, "AIN1 CROSS",  "P9.40"))
    print()

    open_gps()

    cfg_zero   = ADC_MID
    cfg_mpc    = GAUGE_MPC
    cfg_offset = 0.0
    if os.path.exists("rail_config.json"):
        try:
            import json
            c = json.load(open("rail_config.json"))
            cfg_zero   = c.get("adc",  {}).get("zero",   ADC_MID)
            cfg_mpc    = c.get("adc",  {}).get("mpc",    GAUGE_MPC)
            cfg_offset = c.get("incl", {}).get("offset", 0.0)
            print("[CFG] Loaded calibration: zero={} mpc={:.5f} offset={:.3f}".format(
                  cfg_zero, cfg_mpc, cfg_offset))
        except Exception:
            pass

    fname = "sensor_log_{}.csv".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
    fout  = open(fname, "w", newline="")
    wcsv  = csv.writer(fout)
    wcsv.writerow(["timestamp",
                   "gauge_mm", "adc0_raw",
                   "cross_mm", "adc1_raw",
                   "twist_mm_per_m", "distance_m", "enc_count",
                   "lat", "lon", "speed_kmh", "gps_fix", "gps_sats"])
    print("Logging to: {}".format(fname))
    print("Ctrl+C to stop")
    print()

    HDR = ("{:<13} {:>9} {:>6}  {:>10} {:>6}  {:>7} {:>8}  "
           "{:>11} {:>11} {:>5}  GPS").format(
          "TIME", "GAUGE mm", "ADC0", "CROSS mm", "ADC1",
          "TWIST", "DIST m", "LAT", "LON", "SPD")
    print(HDR)
    print("-" * 118)

    prev_cross = 0.0
    rows       = 0

    try:
        while True:
            for _ in range(50):
                enc_tick()
                time.sleep(0.01)

            r0    = adc_read_twice(ADC0) if has0 else -1
            r1    = adc_read_twice(ADC1) if has1 else -1
            gauge = update_gauge(r0, cfg_zero, cfg_mpc)
            cross = update_cross(r1, cfg_offset)
            twist = round(abs(cross - prev_cross) / TWIST_M, 3)
            prev_cross = cross
            dist  = enc_dist()
            poll_gps()

            now   = datetime.now().strftime("%H:%M:%S.%f")[:13]
            gstat = "FIX{} {}sat".format(gps_fix, gps_sats) if gps_fix > 0 else "NO FIX"

            g_disp = "DISCONNECTED" if gauge == 0.0    else "{:.1f}".format(gauge)
            c_disp = "3.3V-ERROR"   if cross == 999.0   else "{:.2f}".format(cross)
            print("{:<13} {:>13} {:>6}  {:>13} {:>6}  {:>7.3f} {:>8.3f}  "
                  "{:>11.6f} {:>11.6f} {:>5.1f}  {}".format(
                  now, g_disp, r0, c_disp, r1,
                  twist, dist, gps_lat, gps_lon, gps_spd, gstat))

            wcsv.writerow([datetime.now().isoformat(),
                           gauge, r0, cross, r1,
                           twist, dist, enc_count,
                           gps_lat, gps_lon, gps_spd, gps_fix, gps_sats])
            fout.flush()
            rows += 1

    except KeyboardInterrupt:
        fout.close()
        print()
        print("Stopped. {} rows -> {}".format(rows, fname))
        print()
        print("FINAL WIRING DIAGNOSIS:")
        print(check_wiring(adc_read_twice(ADC0) if has0 else -1, "AIN0", "P9.39"))
        print(check_wiring(adc_read_twice(ADC1) if has1 else -1, "AIN1", "P9.40"))
        if gps_ser is None:
            print("GPS: not connected or pyserial missing (pip3 install pyserial)")
        elif gps_fix == 0:
            print("GPS: port open but no fix -- take unit outside, wait 60 seconds")
        else:
            print("GPS: fix={} sats={} lat={} lon={}".format(
                  gps_fix, gps_sats, gps_lat, gps_lon))


if __name__ == "__main__":
    main()
