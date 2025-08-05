import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

button_pin = 4

GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

try:
	while True:
		if GPIO.input(button_pin) == GPIO.LOW:
			print("Button pressed!")
		else:
			print("Button not pressed.")
		time.sleep(0.2)
except KeyboardInterrupt:
	print("Exiting...")
finally:
	GPIO.cleanup()
