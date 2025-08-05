import time
import board
import busio
import socket
import ntplib
import adafruit_ds3231
from datetime import datetime

i2c = busio.I2C(board.SCL,board.SDA)
rtc = adafruit_ds3231.DS3231(i2c)

def internet_available():
	try:
		socket.create_connection(("pool.ntp.org",123),timeout=2)
		return True
	except OSError:
		return False

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

while True:
	if internet_available():
		print(get_ntp_time())
		sync_rtc_to_ntp()
	print(rtc.datetime)
	time.sleep(5)
