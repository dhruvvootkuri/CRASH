import time
import socket
from collections import deque
import smtplib
from email.mime.text import MIMEText
import board
import busio
from statemachine import StateMachine, State
import pydot
from statemachine.contrib.diagram import DotGraphMachine
from datetime import datetime
import adafruit_ds3231
import ntplib
import adafruit_ads1x15.ads1015 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_bme680
from adafruit_mcp230xx.mcp23017 import MCP23017
from digitalio import Direction
import subprocess
import os
import sys

BRANCH = "main"
REPO = "origin"

print("Check for Software")

i2c = busio.I2C(board.SCL, board.SDA)
rtc = adafruit_ds3231.DS3231(i2c)
ads = ADS.ADS1015(i2c)
sensors = [adafruit_bme680.Adafruit_BME680_I2C(i2c,address=0x77)]

ads.gain = 1
chan = AnalogIn(ads,ADS.P0)
divider_ratio = 5.5453

daily_ping = False

def get_local_commit():
    return subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()

def get_remote_commit():
    return subprocess.check_output(['git','ls-remote',REPO,f'refs/heads/{BRANCH}']).decode().split()[0]

def update_needed():
    try:
        local = get_local_commit()
        remote = get_remote_commit()
        return local != remote
    except Exception as e:
        print(f"[UPDATE] Error checking for updates: {e}")
        return False

def self_update_and_restart():
    print("[UPDATE] Update detected! Pulling changes and restarting...")
    subprocess.run(['git','pull'],check = True)

    python = sys.executable
    os.execv(python,[python]+sys.argv)

def get_battery_voltage():
    try:
        raw_voltage = chan.voltage
        battery_voltage = raw_voltage * divider_ratio
        return battery_voltage
    except Exception as e:
        print(e)
        return "Unavailable"
    #print(f"Battery Voltage: {battery_voltage:.2f} V")

def get_ntp_time():
    client = ntplib.NTPClient()
    response = client.request('pool.ntp.org',version=3)
    return datetime.fromtimestamp(response.tx_time)

def datetime_to_struct_time(dt):
    return time.struct_time((dt.year,dt.month,dt.day,dt.hour,dt.minute,dt.second,dt.weekday(),0,-1))

def sync_rtc_to_ntp():
    try:
        ntp_time = get_ntp_time()
        rtc.datetime = datetime_to_struct_time(ntp_time)
        print(f"[SYNC] RTC set to NTP time: {ntp_time}")
    except Exception as e:
        print(f"[ERROR] NTP sync failed: {e}")

# === EMAIL CONFIGURATION ===
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "dvootkuri@gmail.com"
EMAIL_PASSWORD = "wxmjdqmfdsugnwyr"
EMAIL_RECIPIENTS = ["dvootkuri@gmail.com"]

def send_email(subject, body):
    """
    Sends an email alert with the specified subject and body.
    """
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = ", ".join(EMAIL_RECIPIENTS)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, EMAIL_RECIPIENTS, msg.as_string())

        print(f"[EMAIL SENT] {subject}")
    except Exception as e:
        print(f"[EMAIL FAILED] {e}")

# === INTERNET CONNECTIVITY CHECK ===
def has_internet_connection():
    """
    Returns True if the system can reach the internet (Google DNS).
    """
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

# === I2C RELAY BOARD SETUP ===
time.sleep(2)
expander = MCP23017(i2c, 0x20)

relays = []
for i in range(16):
    pin = expander.get_pin(i)
    pin.direction = Direction.OUTPUT
    relays.append(pin)

def stop_all_relays(absolute):
    count = 0
    for relay in relays:
        if ((not absolute) and (count == 6 or count == 7)):
            pass
        else:
            relay.value = False
        count += 1
    print("[RELAY] All relays OFF.")

def activate_relay(index):
    stop_all_relays(False)
    if (index < 8):
        relays[index+8].value = True
    else:
        relays[index-8].value = True
    print(f"[RELAY] Tube {index + 1} ON.")

def time_check(daily_ping,hour0,min0):
    hour = rtc.datetime.tm_hour 
    minute = rtc.datetime.tm_min

    if (hour == hour0 and minute == min0 and daily_ping == False):    
        return True
    return False

def send_ping():
    # PLACEHOLDER for turning on relay
    while (not has_internet_connection()):
        print("[INFO] Waiting for Internet connection to ping")
        time.sleep(10)

    if (update_needed()):
        self_update_and_restart()

    sync_rtc_to_ntp()
    body = "Readings listed: \n"
    body += (f"{get_battery_voltage():.2f} V \n\n")
    for sensor in sensors:    
        try:
            body += (f"Temp - {sensor.temperature:.2f} C\n")
            body += (f"Pressure - {sensor.pressure:.2f} hPa\n")
            body += (f"Humidity - {sensor.humidity:.2f} %\n")
            body += (f"Gas Resistance - {sensor.gas:.2f} Ohms\n\n")
        except:
            body += ("BME Data Unavailable \n\n")
    send_email(f"Device Active", body)

# === RING BUFFER ===
RING_BUFFER_SIZE = 5  # Smaller for faster testing
ring_buffer = deque(maxlen=RING_BUFFER_SIZE)

# === TESTING SAMPLING DURATIONS ===
ONE_HOUR_SECONDS = 15
FOUR_HOUR_SECONDS = 30
LOOP_WAIT_SECONDS = 1

# === SAMPLING THRESHOLDS ===
THRESHOLD_1H = 200
THRESHOLD_4H = 100

# === PLACEHOLDER SENSOR FUNCTION ===
def concentrationValue():
    """
    Replace this with your actual VOC sensor logic!
    """
    return 250
    # return float(input("Enter simulated VOC value: "))
    # return bme680.temperature

def generate_static_diagram(current_state):

    graph = DotGraphMachine(SamplingMachine)()
    
    for node in graph.get_nodes():
        label = node.get_attributes().get("label","")
        if current_state in label:
            node.set_style("filled")
            node.set_fillcolor("yellow")
        else:
            node.set_style("solid")
            node.set_fillcolor("white")

    graph.write_png("fsm_static.png")
    print("[INFO] FSM Diagram saved")



# === STATE MACHINE ===
class SamplingMachine(StateMachine):
    idle = State('Idle', initial=True)
    starting_up = State('StartingUp')
    one_hour = State('OneHour')
    four_hour = State('FourHour')
   
    start_starting_up = idle.to(starting_up)
    start_one_hour_from_starting_up = starting_up.to(one_hour)
    start_four_hour_from_starting_up = starting_up.to(four_hour)
    start_one_hour = idle.to(one_hour)
    start_four_hour = idle.to(four_hour)
    extend_to_four_hour = one_hour.to(four_hour)
    switch_to_one_hour = four_hour.to(one_hour)
    stop_sampling = one_hour.to(idle) | four_hour.to(idle)

    def __init__(self,controller):
        self.controller = controller
        super().__init__()

    def on_enter_starting_up(self):
        print("[STATE] Entering StartingUp")
        generate_static_diagram("starting_up")
        relays[6].value = True
        relays[7].value = True
        stop_all_relays(False)
        send_email("System Starting", "StartingUp: Relays 15 & 16 ON")

        # Wait for internet connectivity
        while not has_internet_connection():
            print("[WAITING] No internet. Retrying in 10 seconds...")
            time.sleep(10)

        if update_needed():
            self_update_and_restart()

        sync_rtc_to_ntp()

        print("[CONNECTED] Internet confirmed.")
        send_email("Internet Connected", "Internet connection confirmed. Proceeding to sampling.")
        self.export_state()
        self.controller.enter_next_mode()
        

    def on_enter_one_hour(self):
        generate_static_diagram("one_hour")
        self.controller.start_time = rtc.datetime
        activate_relay(self.controller.current_tube)
        send_email("Sampling Started", f"Started 1-hour sampling on Tube {self.controller.current_tube + 1}")
        self.export_state()

    def on_enter_four_hour(self):
        generate_static_diagram("four_hour")
        self.controller.start_time = rtc.datetime
        activate_relay(self.controller.current_tube)
        send_email("Sampling Started", f"Started 4-hour sampling on Tube {self.controller.current_tube + 1}")
        self.export_state()

    def restart_one_hour(self):
        self.controller.start_time = rtc.datetime
        activate_relay(self.controller.current_tube)
        send_email("Moving On", f"Started 1-hour sampling on Tube {self.controller.current_tube+1}")

    def restart_four_hour(self):
        self.controller.start_time = rtc.datetime
        activate_relay(self.controller.current_tube)
        send_email("Moving On", f"Started 4-hour sampling on Tube {self.controller.current_tube+1}")

    def export_state(self):
        with open("current_state.txt","w") as f:
            f.write(self.current_state.id)

    def on_enter_idle(self):
        generate_static_diagram("idle")
        stop_all_relays(True)
        self.controller.current_tube = 0
        try:
            send_email("Sampling Stopped", f"Stopped sampling on Tube {self.controller.current_tube + 1}")
        except:
            pass
        self.export_state()

# === SAMPLER CONTROLLER ===
class SamplerController:
    def __init__(self):
        self.current_tube = 0
        self.start_time = None
        self.next_mode = None
        self.machine = SamplingMachine(self)

    def elapsed_time(self):
        #print(self.start_time)
        #print("Times",time.mktime(rtc.datetime),time.mktime(self.start_time))
        return time.mktime(rtc.datetime) - time.mktime(self.start_time) if self.start_time else 0

    def move_to_next_tube(self, next_mode):
        self.current_tube += 1
        if self.current_tube >= 14:
            print("[INFO] All tubes sampled. Stopping.")
            send_email("All Tubes Sampled", "Sampling complete.")
            self.machine.stop_sampling()
        else:
            print(f"[INFO] Moving to Tube {self.current_tube + 1}")
            if next_mode == '1h':
                self.machine.restart_one_hour()
            elif next_mode == '4h':
                self.machine.restart_four_hour()

    def enter_next_mode(self):
        if self.next_mode == '1h':
            self.machine.start_one_hour_from_starting_up()
        elif self.next_mode == '4h':
            self.machine.start_four_hour_from_starting_up()

    def evaluate_thresholds(self, avg_voc):
        print(f"[STATE] {self.machine.current_state.id}, Avg VOC: {avg_voc:.2f}")
        elapsed = self.elapsed_time()
        #print("Elapsed",elapsed)

        # Timeout checks
        if self.machine.current_state.id == "one_hour" and elapsed >= ONE_HOUR_SECONDS:
            print("[INFO] 1-hour sampling complete. Moving to next tube.")
            self.move_to_next_tube('1h')
            return

        if self.machine.current_state.id == "four_hour" and elapsed >= FOUR_HOUR_SECONDS:
            print("[INFO] 4-hour sampling complete. Moving to next tube.")
            self.move_to_next_tube('4h')
            return

        # VOC threshold decisions
        if self.machine.current_state.id == "idle":
            if avg_voc >= THRESHOLD_1H:
                self.next_mode = '1h'
                print("Check1",self.machine.current_state.id)
                self.machine.start_starting_up()
            elif avg_voc >= THRESHOLD_4H:
                self.next_mode = '4h'
                print("Check2",self.machine.current_state.id)
                self.machine.start_starting_up()
            return

        if avg_voc >= THRESHOLD_1H:
            if self.machine.current_state.id == "one_hour":
                pass
            elif self.machine.current_state.id == "four_hour":
                if elapsed < ONE_HOUR_SECONDS:
                    self.machine.switch_to_one_hour()
                else:
                    self.move_to_next_tube('1h')

        elif avg_voc >= THRESHOLD_4H:
            if self.machine.current_state.id == "one_hour":
                self.machine.extend_to_four_hour()
            elif self.machine.current_state.id == "four_hour":
                pass

        else:
            if self.machine.current_state.id != "idle":
                self.machine.stop_sampling()

# === MAIN LOOP ===
print("Starting relay sampling system (TESTING TIMINGS, REAL LOGIC)...")

controller = SamplerController()

if __name__ == "__main__":
    generate_static_diagram("idle")

    send_ping()

    while True:

        new_value = concentrationValue()
        ring_buffer.append(new_value)
        print(f"[BUFFER] {list(ring_buffer)}")

        if len(ring_buffer) < RING_BUFFER_SIZE:
            print("[INFO] Filling buffer...")
            time.sleep(LOOP_WAIT_SECONDS)
            continue

        avg_15min = sum(ring_buffer) / len(ring_buffer)
        print(f"[AVG] Simulated average: {avg_15min:.2f}")

        print(rtc.datetime.tm_hour,rtc.datetime.tm_min,rtc.datetime.tm_sec)

        if (time_check(daily_ping,14,36)):
            print("[INFO] Pinging now")
            send_ping()
            daily_ping = True

        if (time_check(False,14,39)):
            daily_ping = False

        controller.evaluate_thresholds(avg_15min)

        time.sleep(LOOP_WAIT_SECONDS)
