import time
import board
import busio
import adafruit_ads1x15.ads1015 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL,board.SDA)

ads = ADS.ADS1015(i2c)
ads.gain = 1

chan = AnalogIn(ads,ADS.P0)

divider_ratio = 1.0

while True:
	raw_voltage = chan.voltage
	battery_voltage = raw_voltage * divider_ratio
	print(f"Battery Voltage: {battery_voltage:.2f} V")
	time.sleep(1)
