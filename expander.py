import board
import busio
from adafruit_mcp230xx.mcp23017 import MCP23017
from digitalio import Direction
import time

i2c = busio.I2C(board.SCL,board.SDA)
mcp = MCP23017(i2c,0x20)

solenoid_1 = mcp.get_pin(8)
solenoid_1.direction = Direction.OUTPUT

while True:
	solenoid_1.value = True
	time.sleep(1)
	solenoid_1.value = False
	time.sleep(1)
