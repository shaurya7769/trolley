#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, time, subprocess

# Hardware Paths
ADC0      = "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"
ADC1      = "/sys/bus/iio/devices/iio:device0/in_voltage1_raw"
GPIO_BASE = "/sys/class/gpio"
CLK_GPIO  = 45
DT_GPIO   = 44
SW_GPIO   = 26
GPS_PORT  = "/dev/ttyS4"

def run_cmd(cmd):
    subprocess.call(cmd, stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w"))

def setup_hardware():
    print("Loading hardware drivers...")
    run_cmd(["sudo", "modprobe", "ti_am335x_adc"])
    run_cmd(["config-pin", "P9.11", "uart"])
    run_cmd(["config-pin", "P9.13", "uart"])
    time.sleep(1)

def read_adc(path):
    # BeagleBone ADC driver fix: read twice, use second value
    if not os.path.exists(path): return -1
    try:
        with open(path) as f: f.read()
        with open(path) as f: return int(f.read().strip())
    except:
        return -1

def setup_gpio(pin):
    path = "{}/gpio{}".format(GPIO_BASE, pin)
    if not os.path.exists(path):
        try:
            with open("{}/export".format(GPIO_BASE), "w") as f: f.write(str(pin))
            time.sleep(0.1)
            with open("{}/direction".format(path), "w") as f: f.write("in")
        except: pass

def read_gpio(pin):
    try:
        with open("{}/gpio{}/value".format(GPIO_BASE, pin)) as f: return int(f.read().strip())
    except: return 1 # Default HIGH (pull-up)

enc_count = 0
enc_last_clk = None

def poll_encoder():
    global enc_count, enc_last_clk
    clk = read_gpio(CLK_GPIO)
    dt = read_gpio(DT_GPIO)
    if enc_last_clk is None:
        enc_last_clk = clk
        return
    if clk != enc_last_clk: # State change
        enc_count += 1 if dt != clk else -1
    enc_last_clk = clk

def check_wiring(raw, name, pin):
    if raw < 0: return f"[{name}] ERROR: Not found at {pin}"
    if raw < 20: return f"[{name}] WIRING FAULT: reading {raw} (Disconnected or Pin1 not 1.8V)"
    if raw > 4075: return f"[{name}] WIRING FAULT: reading {raw} (Saturated, check if using 3.3V)"
    return f"[{name}] OK: reading {raw} (~{int((raw/4095)*100)}%)"

def main():
    setup_hardware()
    for p in (CLK_GPIO, DT_GPIO, SW_GPIO): setup_gpio(p)
    
    print("\nStarting live sensor testing...")
    print("Press Ctrl+C to Stop and view diagnostic summary.\n")
    print(f"{'ADC0 (Pot1)':<15} | {'ADC1 (Pot2)':<15} | {'Encoder Count':<15} | {'GPS /ttyS4':<15}")
    print("-" * 68)

    gps_status = "Available" if os.path.exists(GPS_PORT) else "Missing"
    
    try:
        while True:
            for _ in range(20): 
                poll_encoder()
                time.sleep(0.01) # Poll encoder rapidly
            
            val0 = read_adc(ADC0)
            val1 = read_adc(ADC1)
            
            # Print over the same line 
            sys.stdout.write(f"\r{val0:<15} | {val1:<15} | {enc_count:<15} | {gps_status:<15}")
            sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n\n" + "="*50)
        print(" KEYBOARD INTERRUPT DETECTED -> HARDWARE STATUS")
        print("="*50)
        
        final0 = read_adc(ADC0)
        final1 = read_adc(ADC1)
        
        print(check_wiring(final0, "POT 1 (Gauge)", "P9.39 / AIN0"))
        print(check_wiring(final1, "POT 2 (Cross)", "P9.40 / AIN1"))
        
        clk_val = read_gpio(CLK_GPIO)
        print(f"[ENCODER] Final Count: {enc_count} (CLK Pin state: {clk_val})")
        
        if os.path.exists(GPS_PORT):
            print(f"[GPS] OK: Port {GPS_PORT} is accessible.")
            print("[GPS] Hint: Use 'cat /dev/ttyS4' to see live NMEA sentences.")
        else:
            print(f"[GPS] FAULT: Port {GPS_PORT} not found. Did you run config-pin P9.11 uart?")
            
        print("="*50)

if __name__ == "__main__":
    main()
