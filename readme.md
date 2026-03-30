```bash
# ============================================================
# BEAGLEBONE BLACK -- COMPLETE SETUP FROM SCRATCH
# Run every command in this exact order as debian user
# ============================================================

# ── STEP 1: Update system ────────────────────────────────────
sudo apt-get update
sudo apt-get upgrade -y

# ── STEP 2: Install all required system packages ─────────────
# python3-pyqt5    : GUI framework
# tightvncserver   : VNC display server so we can see the app remotely
# gpsd gpsd-clients: GPS daemon for u-blox NEO-M8P-2
# git              : to clone the repo
# python3-pip      : to install Python packages
# bb-cape-overlays : BeagleBone device tree overlays for ADC, SPI, UART
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-pyqt5 \
    tightvncserver \
    gpsd \
    gpsd-clients \
    git \
    bb-cape-overlays

# ── STEP 3: Install Python packages ──────────────────────────
# pyserial: for reading GPS NMEA data from /dev/ttyS4
sudo pip3 install pyserial

# ── STEP 4: Load ADC kernel module now and on every boot ─────
# ti_am335x_adc: exposes /sys/bus/iio/devices/iio:device0/in_voltageN_raw
# Without this the potentiometers will not read anything
sudo modprobe ti_am335x_adc
echo 'ti_am335x_adc' | sudo tee -a /etc/modules

# ── STEP 5: Enable UART4 pins for GPS (/dev/ttyS4) ───────────
# P9.11 = UART4_RX (connects to GPS TX pin)
# P9.13 = UART4_TX (connects to GPS RX pin, optional)
# config-pin sets the pin mux so the hardware UART is activated
config-pin P9.11 uart
config-pin P9.13 uart

# Make UART4 pin config permanent on every boot
sudo bash -c 'cat >> /etc/rc.local << "RCEOF"
config-pin P9.11 uart
config-pin P9.13 uart
RCEOF'

# ── STEP 6: Set user permissions ─────────────────────────────
# gpio   : read encoder GPIO pins P8.11, P8.12, P8.14
# dialout: access /dev/ttyS4 for GPS without sudo
# video  : access /dev/fb0 framebuffer if needed
sudo adduser debian gpio
sudo adduser debian dialout
sudo adduser debian video

# ── STEP 7: Format and mount SD card ─────────────────────────
# /dev/mmcblk1p1 is the SD card on BBB (internal eMMC is mmcblk0)
# Skip mkfs line if SD is already formatted
sudo mkfs.ext4 /dev/mmcblk1p1
sudo mkdir -p /mnt/sd
sudo mount /dev/mmcblk1p1 /mnt/sd
sudo chown debian:debian /mnt/sd

# Mount SD card automatically on every boot
echo '/dev/mmcblk1p1  /mnt/sd  ext4  defaults,noatime  0  2' | sudo tee -a /etc/fstab

# ── STEP 8: Clone the repository onto SD card ────────────────
cd /mnt/sd
git clone https://github.com/shaurya7769/trolley.git
cd /mnt/sd/trolley

# ── STEP 9: Set VNC password (runs interactive prompt once) ──
# Enter your chosen VNC password when prompted, e.g. debian123
# Answer "n" when asked for view-only password
vncpasswd

# ── STEP 10: Create VNC systemd service ──────────────────────
# Starts tightvncserver at 1024x600 on display :1 (port 5901)
sudo tee /etc/systemd/system/vncserver.service << 'EOF'
[Unit]
Description=TightVNC Server
After=network.target

[Service]
User=debian
Group=debian
Environment=HOME=/home/debian
ExecStartPre=-/usr/bin/tightvncserver -kill :1
ExecStart=/usr/bin/tightvncserver :1 -geometry 1024x600 -depth 24
ExecStop=/usr/bin/tightvncserver -kill :1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# ── STEP 11: Create Rail GUI systemd service ─────────────────
# Starts after VNC is up, waits 5s for display to be ready
# Restarts automatically if it crashes
sudo tee /etc/systemd/system/railgui.service << 'EOF'
[Unit]
Description=Rail Inspection GUI
After=vncserver.service
Requires=vncserver.service

[Service]
User=debian
Group=debian
Environment=DISPLAY=:1
Environment=HOME=/home/debian
WorkingDirectory=/mnt/sd/trolley
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/python3 /mnt/sd/trolley/railgui_bbb_py35.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# ── STEP 12: Enable and start both services ──────────────────
sudo systemctl daemon-reload
sudo systemctl enable vncserver.service
sudo systemctl enable railgui.service
sudo systemctl start vncserver.service
sleep 5
sudo systemctl start railgui.service

# ── STEP 13: Verify everything is running ────────────────────
sudo systemctl status vncserver.service
sudo systemctl status railgui.service

# ── STEP 14: Reboot to confirm autostart works ───────────────
sudo reboot
```

---

```bash
# ============================================================
# HARDWARE PIN WIRING -- BEAGLEBONE BLACK P8/P9 HEADERS
# ============================================================

# GAUGE POTENTIOMETER (10k linear, 3 pins) on AIN0:
#   Pot Pin 1 --> P9.32  VDD_ADC 1.8V  (MUST be 1.8V, NOT 3.3V)
#   Pot Pin 2 --> P9.39  AIN0           (wiper = signal)
#   Pot Pin 3 --> P9.34  GNDA_ADC       (analog ground)

# INCLINOMETER POTENTIOMETER (10k linear, 3 pins) on AIN1:
#   Pot Pin 1 --> P9.32  VDD_ADC 1.8V  (share same 1.8V rail)
#   Pot Pin 2 --> P9.40  AIN1           (wiper = signal)
#   Pot Pin 3 --> P9.34  GNDA_ADC       (share same analog ground)

# ROTARY ENCODER KY-040:
#   VCC --> P9.4   3.3V digital
#   GND --> P9.45  DGND
#   CLK --> P8.11  GPIO45  (quadrature A phase)
#   DT  --> P8.12  GPIO44  (quadrature B phase)
#   SW  --> P8.14  GPIO26  (push button zero/mark)

# GPS u-blox NEO-M8P-2:
#   VCC --> P9.3   3.3V
#   GND --> P9.1   DGND
#   TX  --> P9.11  UART4_RX  (GPS transmits, BBB receives)
#   RX  --> P9.13  UART4_TX  (optional, for sending commands to GPS)

# VERIFY PINS ARE WORKING:
cat /sys/bus/iio/devices/iio:device0/in_voltage0_raw   # gauge pot
cat /sys/bus/iio/devices/iio:device0/in_voltage1_raw   # inclinometer pot
cat /dev/ttyS4                                          # GPS NMEA stream
ls /sys/class/gpio/gpio45                               # encoder CLK
```

---

```bash
# ============================================================
# PC -- VIEW THE APP OVER VNC
# ============================================================

# ── Linux / Mac: install a VNC viewer ────────────────────────
# Ubuntu/Debian
sudo apt-get install -y tigervnc-viewer
# Mac
brew install tiger-vnc

# ── Find the BBB IP address (run this ON the BBB) ────────────
hostname -I

# ── Connect from PC (replace with your BBB IP) ───────────────
# Port 5901 = VNC display :1
vncviewer BBB_IP_ADDRESS:5901

# ── Windows: download RealVNC Viewer ─────────────────────────
# https://www.realvnc.com/en/connect/download/viewer/
# Open it, type:  BBB_IP_ADDRESS:5901
# Password: whatever you set in vncpasswd

# ── Mac built-in Screen Sharing ──────────────────────────────
# Finder -> Go -> Connect to Server
# Type:  vnc://BBB_IP_ADDRESS:5901

# ── Check logs if app does not appear ────────────────────────
ssh debian@BBB_IP_ADDRESS
sudo journalctl -u vncserver.service --no-pager -n 30
sudo journalctl -u railgui.service --no-pager -n 30

# ── Manually restart if needed ───────────────────────────────
ssh debian@BBB_IP_ADDRESS
sudo systemctl restart vncserver.service
sudo systemctl restart railgui.service
```
