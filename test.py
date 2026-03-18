import Adafruit_BBIO.ADC as ADC
import Adafruit_BBIO.GPIO as GPIO
import time

# --- ADC Setup ---
ADC.setup()

# --- Rotary Encoder Pins ---
CLK = "P8_11"
DT = "P8_12"
SW = "P8_14"

GPIO.setup(CLK, GPIO.IN)
GPIO.setup(DT, GPIO.IN)
GPIO.setup(SW, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# --- Encoder State ---
counter = 0
last_clk = GPIO.input(CLK)

print("Starting sensor test...\n")

while True:
    try:
        # --- Read Potentiometers ---
        pot1 = ADC.read("P9_39")   # AIN0
        pot2 = ADC.read("P9_40")   # AIN1

        # Convert to voltage (BBB ADC is 1.8V max)
        pot1_v = pot1 * 1.8
        pot2_v = pot2 * 1.8

        # --- Read Encoder ---
        clk_state = GPIO.input(CLK)
        dt_state = GPIO.input(DT)

        if clk_state != last_clk:
            if dt_state != clk_state:
                counter += 1
            else:
                counter -= 1

        last_clk = clk_state

        # --- Button Press ---
        if GPIO.input(SW) == 0:
            print("Button Pressed → Reset Counter")
            counter = 0
            time.sleep(0.3)  # debounce

        # --- Print Everything ---
        print(f"POT1 (AIN0): {pot1_v:.3f} V | POT2 (AIN1): {pot2_v:.3f} V | Encoder: {counter}")

        time.sleep(0.2)

    except KeyboardInterrupt:
        print("\nExiting...")
        GPIO.cleanup()
        break
