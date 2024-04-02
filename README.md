#RUMBE

`rumble.py` defines a `Motor` class in Python for command-line interaction with a stepper motor.  When imported through the Python interpreter, the module exposes the `Motor` class and a `global_init()` function that automatically loads configuration files `mono.conf` and `polar.conf` for stepper motors that drive a monochrometer and polarizer in an optical experiment.  The returned objects can be used to interact with the motors through the command line.

When run as an executable, the script opens a Tkinter GUI for interacting with the motors.

For detailed documentation on the Motor class, see the in-line documentation.
