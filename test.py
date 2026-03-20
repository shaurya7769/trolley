#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BBB Sensor Terminal + CSV Logger  v2
Devices: Gauge Pot AIN0, Inclinometer Pot AIN1, Encoder GPIO, GPS ttyS4

CORRECT WIRING:
  GAUGE POT (10k linear):
    Pin 1  ->  P9.32  VDD_ADC 1.8V   (NOT P9.3 which is 3.3V)
    Pin 2  ->  P9.39  AIN0            wiper
    Pin 3  ->  P9.34  GNDA_ADC

  INCLINOMETER POT (10k linear):
    Pin 1  ->  P9.32  VDD_ADC 1.8V   (share same rail as gauge pot)
    Pin 2  ->  P9.40  AIN1            wiper
    Pin 3  ->  P9.34  GNDA_ADC        (share same ground)

  GPS (u-blox or any NMEA 3.3V module):
    VCC    ->  P9.3   3.3V
    GND    ->  P9.1   DGND
    TX     ->  P9.11  UART4_RX
    RX     ->  P9.13  UART4_TX

  ENCODER KY-040:
    VCC    ->  P9.4   3.3V
    GND    ->  P9.45  DGND
    CLK    ->  P8.11  GPIO45
    DT     ->  P8.12  GPIO44
    SW     ->  P8.14  GPIO26
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

GAUGE_STD  = 1676.0
GAUGE_MPC  = 0.036621
ADC_MID    = 2048
INCL_FS    = 30.0
DEG_TO_MM  = 17.453
TWIST_M    = 3.5
PPR        = 20
WHEEL_MM   = 62.0


def load_modules():
    subprocess.call(["sudo", "modprobe", "ti_am335x_adc"],
                    stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w"))
    for pin in ["P9.11", "P9.13"]:
        subprocess.call(["config-pin", pin, "uart"],
                        stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w"))
    time.sleep(1)


def gpio_export(num):
    p = "{}/gpio{}/value".format(GPIO_BASE, num)
    if not os.path.exists(p):
        try:
            open("{}/export".format(GPIO_BASE), "w").write(str(num))
            time.sleep(0.05)
            open("{}/gpio{}/direction".format(GPIO_BASE, num), "w").write("in")
        except Exception:
            pass


def gpio_read(num):
    try:
        return int(open("{}/gpio{}/value".format(GPIO_BASE, num)).read().strip())
    except Exception:
        return 1


def adc_read(path):
    try:
        return int(open(path).read().strip())
    except Exception:
        return -1


enc_count    = 0
enc_last_clk = None


def encoder_tick():
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


def gauge_from_raw(raw, zero, mpc):
    g = GAUGE_STD + (raw - zero) * mpc
    return round(max(1601.0, min(1751.0, g)), 1)


def cross_from_raw(raw, offset):
    angle = (raw - ADC_MID) / float(ADC_MID) * INCL_FS - offset
    return round(max(-150.0, min(150.0, angle * DEG_TO_MM)), 2)


def diagnose_adc(raw, name, pin):
    if raw < 0:
        return "READ ERROR on {}".format(pin)
    if raw < 10:
        return "{} raw={} -- SHORT TO GND or wiper disconnected. Check Pin2->{}".format(name, raw, pin)
    if raw > 4085:
        return "{} raw={} -- TOO HIGH: pot powered from 3.3V, move Pin1 to P9.32 (1.8V)".format(name, raw)
    if raw < 100 or raw > 3900:
        return "{} raw={} -- WARNING: pot at extreme end or wiring loose".format(name, raw)
    return "{} raw={} -- OK".format(name, raw)


gps_ser = None
gps_buf = ""
gps_lat = 0.0
gps_lon = 0.0
gps_spd = 0.0
gps_fix = 0


def open_gps():
    global gps_ser
    if not os.path.exists(GPS_PORT):
        print("[GPS] /dev/ttyS4 not found -- run: config-pin P9.11 uart && config-pin P9.13 uart")
        return
    try:
        import serial
        gps_ser = serial.Serial(GPS_PORT, 9600, bytesize=8,
                                parity="N", stopbits=1, timeout=0.1)
        print("[GPS] Opened /dev/ttyS4 at 9600 baud")
    except ImportError:
        print("[GPS] pyserial not installed -- run: pip3 install pyserial")
        print("[GPS] GPS will show 0.0 until pyserial is installed")
    except Exception as e:
        print("[GPS] Error: {}".format(e))


def nmea_to_dec(s, d):
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
    global gps_lat, gps_lon, gps_spd, gps_fix
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
                la = nmea_to_dec(p[2], p[3])
                lo = nmea_to_dec(p[4], p[5])
                if la or lo:
                    gps_lat, gps_lon = la, lo
        elif "RMC" in tag and len(p) >= 8 and p[2].upper() == "A":
            if len(p) > 5 and p[3] and p[5]:
                la = nmea_to_dec(p[3], p[4])
                lo = nmea_to_dec(p[5], p[6])
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


def main():
    print("Loading modules and enabling UART4...")
    load_modules()

    for g in (CLK_GPIO, DT_GPIO, SW_GPIO):
        gpio_export(g)

    has0 = os.path.exists(ADC0)
    has1 = os.path.exists(ADC1)

    if not has0:
        print("ERROR: ADC not found. Run: sudo modprobe ti_am335x_adc")
        sys.exit(1)

    open_gps()

    fname = "sensor_log_{}.csv".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
    fout  = open(fname, "w", newline="")
    wcsv  = csv.writer(fout)
    wcsv.writerow(["timestamp",
                   "gauge_mm", "gauge_raw",
                   "cross_mm", "cross_raw",
                   "twist_mm_per_m", "distance_m", "enc_count",
                   "lat", "lon", "speed_kmh", "gps_fix",
                   "gauge_diag", "cross_diag"])

    print("Logging to: {}".format(fname))
    print("Ctrl+C to stop and see wiring diagnosis")
    print()
    print("{:<13} {:>9} {:>6}  {:>10} {:>6}  {:>7} {:>8}  {:>12} {:>12} {:>7}  GPS".format(
          "TIME", "GAUGE mm", "RAW0", "CROSS mm", "RAW1",
          "TWIST", "DIST m", "LAT", "LON", "SPD"))
    print("-" * 120)

    prev_cross = 0.0
    rows       = 0
    # load calibration from config if present
    zero = ADC_MID
    mpc  = GAUGE_MPC
    offset = 0.0
    cfg_path = "rail_config.json"
    if os.path.exists(cfg_path):
        try:
            import json
            cfg    = json.load(open(cfg_path))
            zero   = cfg.get("adc",  {}).get("zero",   ADC_MID)
            mpc    = cfg.get("adc",  {}).get("mpc",    GAUGE_MPC)
            offset = cfg.get("incl", {}).get("offset", 0.0)
        except Exception:
            pass

    try:
        while True:
            for _ in range(50):
                encoder_tick()
                time.sleep(0.01)

            raw0 = adc_read(ADC0) if has0 else -1
            raw1 = adc_read(ADC1) if has1 else -1

            gauge = gauge_from_raw(raw0, zero, mpc) if raw0 > 0 else GAUGE_STD
            cross = cross_from_raw(raw1, offset)     if raw1 > 0 else 0.0

            twist = round(abs(cross - prev_cross) / TWIST_M, 3)
            prev_cross = cross
            dist  = enc_dist()
            poll_gps()

            ts    = datetime.now()
            now   = ts.strftime("%H:%M:%S.%f")[:13]
            gstat = "FIX{}".format(gps_fix) if gps_fix > 0 else "NOFIX"

            print("{:<13} {:>9.1f} {:>6}  {:>10.2f} {:>6}  {:>7.3f} {:>8.3f}  {:>12.7f} {:>12.7f} {:>7.1f}  {}".format(
                now, gauge, raw0, cross, raw1,
                twist, dist, gps_lat, gps_lon, gps_spd, gstat))

            wcsv.writerow([
                ts.isoformat(),
                gauge, raw0,
                cross, raw1,
                twist, dist, enc_count,
                gps_lat, gps_lon, gps_spd, gps_fix,
                diagnose_adc(raw0, "AIN0", "P9.39"),
                diagnose_adc(raw1, "AIN1", "P9.40"),
            ])
            fout.flush()
            rows += 1

    except KeyboardInterrupt:
        fout.close()
        print()
        print("Stopped. {} rows written to {}".format(rows, fname))
        print()
        print("=" * 60)
        print("WIRING DIAGNOSIS")
        print("=" * 60)
        r0 = adc_read(ADC0) if has0 else -1
        r1 = adc_read(ADC1) if has1 else -1
        print(diagnose_adc(r0, "AIN0 GAUGE", "P9.39"))
        print(diagnose_adc(r1, "AIN1 CROSS", "P9.40"))
        if gps_ser is None:
            print("GPS: not open -- install pyserial: pip3 install pyserial")
        elif gps_fix == 0:
            print("GPS: port open, waiting for fix (take outside, wait 60s)")
        else:
            print("GPS: fix={} lat={} lon={}".format(gps_fix, gps_lat, gps_lon))
        print("=" * 60)


if __name__ == "__main__":
    main()
