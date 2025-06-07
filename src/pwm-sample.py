import itertools
from periphery import PWM
import time

pwm = PWM(5, 0)

pwm.frequency = 1000
pwm.duty_cycle = 0
pwm.polarity = "normal"
pwm.enable()

duties = [0.000001 * (10 ** i) for i in range(6)] + [0.1 * (2 ** i) for i in range(4)]

for d in itertools.cycle(duties):
    pwm.duty_cycle = d
    print(f"Using duty cycle: {d}")
    sleep(0.1)




while True:
    dc = float(input("Press Enter for next duty cycle..."))
    pwm.duty_cycle = dc
    print(f"Using duty cycle: {dc}")