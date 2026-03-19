#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BBB Sensor Terminal Test
Prints all sensor readings to terminal and logs to CSV.
Devices: Rotary Encoder (GPIO), Gauge Pot (AIN0), Inclinometer Pot (AIN1), GPS (ttyS4)
"""

import os, sys, time, csv, subprocess
from datetime import datetime

# -- paths ---------------------------------------------------------------------
ADC0       = "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"
ADC1       = "/sys/bus/iio/devices/iio:device0/in_voltage1_raw"
GPIO_BASE  = "/sys/class/gpio"
CLK_GPIO   = 45   # P8.11
DT_GPIO    = 44   # P8.12
SW_GPIO    = 26   # P8.14
GPS_PORT   = "/dev/ttyS4"
CSV_FILE   = "sensor_log_{}.csv".format(datetime.now().strftime("%Y%m%d_%H%M%S"))

# -- Indian Railways RDSO constants --------------------------------------------
ADC_MID    = 2048
GAUGE_STD  = 1676.0    # Indian BG mm
GAUGE_MPC  = 0.036621  # mm per ADC count
INCL_FS    = 30.0      # SCL3300 full scale degrees
DEG_TO_MM  = 17.453    # 1 deg = 17.453 mm over 1676 mm base
TWIST_CHORD= 3.5       # RDSO chord metres
PPR        = 20        # encoder pulses per revolution
WHEEL_DIAM = 62.0      # trolley wheel mm

# -- load kernel modules --------------------------------------------------------
def load_modules():
    for mod in ["ti_am335x_adc"]:
        subprocess.call(["sudo","modprobe",mod],
                        stdout=open(os.devnull,"w"), stderr=open(os.devnull,"w"))
    for pin in ["P9.11","P9.13"]:
        subprocess.call(["config-pin", pin, "uart"],
                        stdout=open(os.devnull,"w"), stderr=open(os.devnull,"w"))
    time.sleep(1)

# -- GPIO helpers --------------------------------------------------------------
def gpio_export(num):
    val = "{}/gpio{}/value".format(GPIO_BASE, num)
    if not os.path.exists(val):
        try:
            open("{}/export".format(GPIO_BASE), "w").write(str(num))
            time.sleep(0.1)
            open("{}/gpio{}/direction".format(GPIO_BASE, num), "w").write("in")
        except Exception:
            pass

def gpio_read(num):
    try:
        return int(open("{}/gpio{}/value".format(GPIO_BASE, num)).read().strip())
    except Exception:
        return 1

# -- ADC helper ----------------------------------------------------------------
def adc_read(path):
    try:
        return int(open(path).read().strip())
    except Exception:
        return ADC_MID

# -- encoder state -------------------------------------------------------------
enc_count   = 0
enc_last_clk= None

def encoder_tick():
    global enc_count, enc_last_clk
    clk = gpio_read(CLK_GPIO)
    dt  = gpio_read(DT_GPIO)
    if enc_last_clk is None:
        enc_last_clk = clk
        return
    if clk != enc_last_clk:
        if dt != clk:
            enc_count += 1
        else:
            enc_count -= 1
    enc_last_clk = clk

def encoder_distance():
    circ = 3.14159265 * WHEEL_DIAM
    return round(abs(enc_count) / max(1, PPR) * circ / 1000.0, 3)

# -- gauge ---------------------------------------------------------------------
def read_gauge():
    raw   = adc_read(ADC0)
    gauge = GAUGE_STD + (raw - ADC_MID) * GAUGE_MPC
    return round(max(1601.0, min(1751.0, gauge)), 1), raw

# -- cross-level ---------------------------------------------------------------
def read_cross():
    raw       = adc_read(ADC1)
    angle_deg = (raw - ADC_MID) / float(ADC_MID) * INCL_FS
    cross_mm  = angle_deg * DEG_TO_MM
    return round(max(-150.0, min(150.0, cross_mm)), 2), raw

# -- GPS -----------------------------------------------------------------------
gps_ser = None
gps_buf = ""
lat, lon, speed_kmh = 0.0, 0.0, 0.0

def open_gps():
    global gps_ser
    if not os.path.exists(GPS_PORT):
        return
    try:
        import serial
        gps_ser = serial.Serial(GPS_PORT, baudrate=9600,
                                bytesize=8, parity="N", stopbits=1, timeout=0.1)
        print("[GPS] Opened {}".format(GPS_PORT))
    except Exception as e:
        print("[GPS] Could not open {}: {}".format(GPS_PORT, e))

def nmea_deg(raw, direction):
    try:
        raw = raw.strip()
        if not raw or "." not in raw:
            return 0.0
        dot = raw.index(".")
        d   = dot - 2
        if d < 1:
            return 0.0
        deg = float(raw[:d])
        mn  = float(raw[d:])
        dec = deg + mn / 60.0
        if direction.upper() in ("S","W"):
            dec = -dec
        return round(dec, 7)
    except Exception:
        return 0.0

def parse_nmea(sentence):
    global lat, lon, speed_kmh
    try:
        if "*" in sentence:
            sentence = sentence[:sentence.rindex("*")]
        sentence = sentence.strip()
        if not sentence.startswith("$"):
            return
        parts = sentence.split(",")
        if len(parts) < 6:
            return
        tag = parts[0].upper()
        if "GGA" in tag and len(parts) >= 10:
            fix_q = int(parts[6]) if parts[6].strip().isdigit() else 0
            if fix_q >= 1 and parts[2] and parts[4]:
                la = nmea_deg(parts[2], parts[3])
                lo = nmea_deg(parts[4], parts[5])
                if la != 0.0 or lo != 0.0:
                    lat, lon = la, lo
        elif "RMC" in tag and len(parts) >= 8:
            if parts[2].upper() == "A":
                if len(parts) > 5 and parts[3] and parts[5]:
                    la = nmea_deg(parts[3], parts[4])
                    lo = nmea_deg(parts[5], parts[6])
                    if la != 0.0 or lo != 0.0:
                        lat, lon = la, lo
                if len(parts) > 7 and parts[7].strip():
                    speed_kmh = round(float(parts[7]) * 1.852, 1)
    except Exception:
        pass

def poll_gps():
    global gps_buf
    if gps_ser is None:
        return
    try:
        n = gps_ser.in_waiting
        if n > 0:
            chunk = gps_ser.read(n).decode("ascii", errors="replace")
            gps_buf += chunk
            while "\n" in gps_buf:
                line, gps_buf = gps_buf.split("\n", 1)
                parse_nmea(line.strip())
    except Exception:
        pass

# -- CSV setup -----------------------------------------------------------------
def setup_csv():
    f = open(CSV_FILE, "w", newline="")
    w = csv.writer(f)
    w.writerow(["timestamp","gauge_mm","gauge_raw","cross_mm","cross_raw",
                "twist_mm_per_m","distance_m","enc_count","lat","lon","speed_kmh"])
    return f, w

# -- main loop -----------------------------------------------------------------
def main():
    global enc_count

    print("Loading kernel modules...")
    load_modules()

    print("Exporting GPIO pins...")
    for g in (CLK_GPIO, DT_GPIO, SW_GPIO):
        gpio_export(g)

    has_adc0 = os.path.exists(ADC0)
    has_adc1 = os.path.exists(ADC1)
    has_gps  = os.path.exists(GPS_PORT)

    print("ADC0 (gauge)      : {}".format("OK " + ADC0 if has_adc0 else "NOT FOUND - check wiring P9.39"))
    print("ADC1 (cross-level): {}".format("OK " + ADC1 if has_adc1 else "NOT FOUND - check wiring P9.40"))
    print("GPS  (ttyS4)      : {}".format("OK " + GPS_PORT if has_gps  else "NOT FOUND - check config-pin P9.11"))
    print("Encoder CLK GPIO  : {} -> {}".format(CLK_GPIO, "OK" if os.path.exists("{}/gpio{}".format(GPIO_BASE,CLK_GPIO)) else "NOT FOUND"))
    print()

    open_gps()

    csv_file, csv_writer = setup_csv()
    print("Logging to: {}\n".format(CSV_FILE))
    print("{:<20} {:>10} {:>8} {:>10} {:>8} {:>8} {:>10} {:>12} {:>12} {:>8}".format(
        "TIME", "GAUGE mm", "ADC0", "CROSS mm", "ADC1", "TWIST", "DIST m", "LAT", "LON", "SPD km/h"))
    print("-" * 110)

    prev_cross = 0.0
    tick       = 0

    try:
        while True:
            # poll encoder at ~50 Hz inside 500ms window
            for _ in range(50):
                encoder_tick()
                time.sleep(0.01)

            gauge_mm,  raw0 = read_gauge()
            cross_mm,  raw1 = read_cross()
            dist_m          = encoder_distance()
            twist           = round(abs(cross_mm - prev_cross) / TWIST_CHORD, 3)
            prev_cross      = cross_mm
            poll_gps()

            now = datetime.now().strftime("%H:%M:%S.%f")[:12]

            print("{:<20} {:>10.1f} {:>8d} {:>10.2f} {:>8d} {:>8.3f} {:>10.3f} {:>12.7f} {:>12.7f} {:>8.1f}".format(
                now, gauge_mm, raw0, cross_mm, raw1, twist, dist_m, lat, lon, speed_kmh))

            csv_writer.writerow([
                datetime.now().isoformat(),
                gauge_mm, raw0,
                cross_mm, raw1,
                twist, dist_m, enc_count,
                lat, lon, speed_kmh
            ])
            csv_file.flush()
            tick += 1

    except KeyboardInterrupt:
        csv_file.close()
        print("\nStopped. {} rows written to {}".format(tick, CSV_FILE))

if __name__ == "__main__":
    main()
