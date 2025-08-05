import time
import board
import busio
from adafruit_pcf8575 import PCF8575
import adafruit_bme680
import smtplib
from email.mime.text import MIMEText
from collections import deque
import matplotlib.pyplot as plt

plt.ion()
fig,ax = plt.subplots()
times=[]
concentrations=[]
line, = ax.plot(times,concentrations,label='VOC Concentration')

ax.set_xlabel('Sample Number')
ax.set_ylabel('VOC Index / Concentration')
ax.set_title('Real-Time VOC Concentration')
ax.legend()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "dvootkuri@gmail.com"
EMAIL_PASSWORD = "wxmjdqmfdsugnwyr"
EMAIL_RECIPIENTS = ["dvootkuri@gmail.com"]

def send_email(subject,body):
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

i2c = busio.I2C(board.SCL,board.SDA)
bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c,0x76)

print(bme680.temperature)

while not i2c.try_lock():
	pass

i2c.unlock()

expander = PCF8575(i2c,address=0x27)

relays = []
for i in range(16):
	pin = expander.get_pin(i)
	pin.switch_to_output(value=True)
	relays.append(pin)

RING_BUFFER_SIZE = 15
ring_buffer = deque(maxlen=RING_BUFFER_SIZE)

THRESHOLD_1H = 80000
THRESHOLD_4H = 60000

current_tube = 0
sampling_mode = None
start_time = None

def concentrationValue():
	return bme680.gas

def start_sampling(tube_index,mode):
	global sampling_mode, start_time
	sampling_mode = mode
	start_time = time.time()

	for relay in relays:
		relay.value = True
	relays[tube_index].value = False

	print(f"[SAMPLING STARTED] Tube {tube_index + 1} in {mode} mode.")
	send_email(f"Sampling Started: {mode}", f"Started {mode} sampling on Tube {tube_index + 1}.")

def stop_all_relays():
	for relay in relays:
		relay.value = True
	print("[ALL RELAYS OFF]")

def average_ring_buffer():
	return sum(ring_buffer) / len(ring_buffer) if ring_buffer else 0

print("Starting relay sampling system")

while True:
	now = time.time()
	newValue = concentrationValue()

	ring_buffer.append(newValue)
	print(f"[BUFFER] {list(ring_buffer)}")

	times.append(len(times))
	concentrations.append(newValue)
	line.set_xdata(times)
	line.set_ydata(concentrations)
	ax.relim()
	ax.autoscale_view()
	plt.draw()
	plt.pause(0.01)

	if len(ring_buffer) < RING_BUFFER_SIZE:
		print("[INFO] Waiting for full 15-minute buffer...")
		time.sleep(1)
		continue

	avg_15min = average_ring_buffer()
	print(f"[15-MIN AVERAGE] {avg_15min:.2f}")

	if sampling_mode == "1h" and (now - start_time) >= 15:
		current_tube += 1
		start_sampling(current_tube, "1h")
	elif sampling_mode == "4h" and (now-start_time) >= 30:
		current_tube += 1
		start_sampling(current_tube, "4h")

	if avg_15min >= THRESHOLD_1H:
		print("[DECISION] Above 1-hour sampling.")
		if sampling_mode is None:
			start_sampling(current_tube, "1h")
		elif sampling_mode == "1h":
			print("[INFO] Continuing 1-hour sampling.")
		elif sampling_mode == "4h":
			elapsed = now - start_time
			if elapsed < 15:
				print("[ACTION] Switching from 4-hour to 1-hour sampling.")
				start_sampling(current_tube, "1h")
			else:
				print("[ACTION] 4-hour sampling exceed 1 hour. Moving to next tube.")
				send_email("Tube Complete",f"Completed Tube {current_tube+1}. Moving to next tube.")
				current_tube += 1
				if current_tube >= len(relays):
					print("[INFO] All tubes sampled. Stopping.")
					send_email("All Tubes Sampled","Sampling finished for all 14 tubes.")
					stop_all_relays()
					break
				start_sampling(current_tube,"1h")
	elif avg_15min >= THRESHOLD_4H:
		print("[DECISION] Between 4-hour and 1-hour thresholds.")
		if sampling_mode is None:
			start_sampling(current_tube, "4h")
		elif sampling_mode == "1h":
			print("[ACTION] Extending current 1-hour sampling to 4-hour.")
			sampling_mode = "4h"
			send_email("Sampling Extended", f"Tube {current_tube + 1} sampling extending to 4-hour mode.")
		elif sampling_mode == "4h":
			print("[INFO] Continuing 4-hour sampling.")
	else:
		print("[DECISION] Below 4-hour threshold. Stopping sampling if active.")
		if sampling_mopde is not None:
			send_email("Sampling Stopped", f"Average dropped. Stopping sampling on Tube {current_tube + 1}.")
		sampling_mode = None
		stop_all_relays()

	
	time.sleep(1)

print("Done")
