#!/usr/bin/python3
#

import tkinter as tk
from tkinter import ttk
from labjack import ljm	
import json
import math
import time



class Motor:
    """Motor interface class
    
    M = Motor(handle)
    
After initializing an empty motor object, the motor is intialized by
setting the pulse frequency using the .set_clock() method.

    M.set_clock(roll, divisor)
        OR
    M.set_clock_hz(pulse_hz)
    
After initializing the clock settings, initialization is completed by
assigning the motor's pins.

    M.set_pins(dir_pin, pulse_pin, home_pin, invert)
        OR
    M.set_pins(dir_pin, pulse_pin)
    
If the default motor direction is opposite the desired positive
direction, the invert keyword may be set to True.
    
The motor object has the following attributes, all of which should be
regarded as READ ONLY.  DO NOT ATTEMPT TO WRITE TO THESE ATTRIBUTES.

* POSITIONING *
    counts      The current motor position in pulse counts
    invert      A bool flag that reverses the behavior of the dir_pin
        (INVERT is the only attribute that may be safely changed manually)
    lim_upper   Upper software limit of motion
    lim_lower   Lower software limit of motion
* CALIBRATION *
    cal_slope   position = cal_slope * (counts - cal_zero)
    cal_zero
    cal_units   Unit string for the calibrated position
* COMMUNICATION *
    handle      The device handle for the LabJack connection
    dir_pin     The integer DIO pin number for the direction pin
    dir_reg     The direciton pin register name
    pulse_pin   The integer DIO pin number for the pulse pin
    pulse_pin   The DIO#_EF_CONFIG_C register for the pulse out
    home_pin    The integer DIO pin number for the home pin
                (home_pin=-1 : not configured)
    home_reg    The home pin register name string
                (home_reg='' : not configured)
    
The behavior of the following methods is fully documented in the inline 
help for each.

* INITIALIZATION *
    set_clock( roll, divisor )
    set_clock_hz( pulse_rate_hz )
    set_pins( dir_pin, pulse_pin, home_pin )
    load( filename )
    save( filename )
* INIT STATUS *
    roll, divisor = get_clock()
    pulse_rate_hz = get_clock_hz()
* SOFTWARE LIMITS *
    set_lim_upper( ... )
    set_lim_lower( ... )
* SOFTWARE LIMIT STATUS *
    limstate = get_lim_state()
* POSITIONING *
    go( target )
    go_cal( target )
    increment( value )
    increment_cal( value )
* POSITIONING STATUS *
    counts = get()
    position = get_cal()

** PHYSICAL INTERFACE **

When motion is commanded, a series of pulses is generated at the pulse_pin.
Pulses are at a frequency set by set_clock() or set_clock_hz(), and with
a 50% duty cycle.  The direction pin is high for positive motion by 
default, but that behavior can be reversed by setting the M.invert
attribute to True at any time.


pulse pin
     ,----------.          ,----------.          ,----------.          ,
     |          |          |          |          |          |          |
-----'          `----------'          `----------'          `----------'

    dir pin (pos)           dir pin (neg)
    ,----------------------.
XXXX|                      |
    '                      `---------------------

Because no acceleration or deceleration is supported, it is vital that 
the pulse frequency is sufficiently slow to allow the motor to reach
its steady-state speed in a single pulse width.  


Author: Christopher R. Martin       
Originally Written: January 2024
Please modify, share, use freely!
"""
    def __init__(self, handle):
       
        self.handle = handle
        self.invert = False
        self.dir_pin = -1
        self.dir_reg = ''
        self.pulse_pin = -1
        self.pulse_reg = ''
        self.home_pin = -1
        self.home_reg = ''
        
        # Always wake up at zero counts
        self.counts = 0
        # Set up the calibration for counts by default
        self.cal_zero = 0
        self.cal_slope = 1
        self.cal_units = 'counts'
        
        # Set up software limits
        self.lim_upper = None
        self.lim_lower = None
        
    def save(self, filename):
        """Save the motor configuration to a file
    M.save(filename)

Writes a text file with configuration parameters for the motor
"""
        with open(filename, 'w') as ff:
            roll, divisor = self.get_clock()
            config = {
                'clock_roll': roll,
                'clock_divisor': divisor,
                'dir_pin': self.dir_pin,
                'pulse_pin': self.pulse_pin,
                'home_pin': self.home_pin,
                'invert': self.invert,
                'cal_slope': self.cal_slope,
                'cal_zero': self.cal_zero,
                'cal_units': self.cal_units,
                'lim_upper': self.lim_upper,
                'lim_lower': self.lim_lower
            }
            json.dump(config, indent=4)
        
    def load(self, filename):
        """Load the motor configuration and calibration from a file
    M.load(filename)

Reads from a text file with configuration parameters for the motor
"""
        # What are the mandatory configuration parameters?
        mandatory = {'clock_roll', 'clock_divisor', 'dir_pin', 'pulse_pin'}
        # What are the legal parameters?
        allowed = {'home_pin', 'cal_slope', 'cal_zero', 'cal_units',
            'lim_upper', 'lim_lower', 'invert'}
        allowed = allowed.union(mandatory)
        
        # Attempt to parse the json configuration file
        with open(filename, 'r') as ff:
            # Load the configuration parameters
            config = json.load(ff)
            
        # Check to see which if there were unrecognized parameters
        # or missing mandatory parameters
        has = set(config.keys())
        missing = mandatory.difference(has)
        illegal = has.difference(allowed)
        if any(missing):
            raise Exception('Missing mandatory parameters: ' + repr(missing))
        if any(illegal):
            raise Exception('Illegal configuration parameters: ' + repr(illegal))
        
        # Configure the clock
        roll = config['clock_roll']
        divisor = config['clock_divisor']
        self.set_clock(roll, divisor)
        
        # Configure the pins
        dir_pin = config['dir_pin']
        pulse_pin = config['pulse_pin']
        home_pin = -1
        if 'home_pin' in config:
            home_pin = config['home_pin']
        
        # Apply the pin settings
        self.set_clock(roll, divisor)
        self.set_pins(dir_pin=dir_pin, pulse_pin=pulse_pin, home_pin=home_pin)
        
        
        # Now, apply the optional parameters
        if 'invert' in config:
            self.invert = bool(config['invert'])
        if 'cal_slope' in config:
            self.cal_slope = config['cal_slope']
        if 'cal_zero' in config:
            self.cal_zero = config['cal_zero']
        if 'cal_units' in config:
            self.cal_units = config['cal_units']
        if 'lim_upper' in config:
            self.lim_upper = config['lim_upper']
        if 'lim_lower' in config:
            self.lim_lower = config['lim_lower']
        
        
        
        
    def __repr__(self):
        return f'<Motor Instance @ {self.get_cal()} {self.cal_units}>'
        

    def get_clock(self):
        """Return the clock roll and divisor settings
   roll, divisor = M.get_clock()
   
The T4 system clock is 80MHz, so the pulse frequency will be
    80MHz / roll / divisor
    
Divisor is always a power of 2, and is used for coarse setting of the
frequency.  The roll value can take on any integer value (32 bit) and
is used for fine tuning of the pulse frequency.
"""
        divisor = int(ljm.eReadName(self.handle, 'DIO_EF_CLOCK0_DIVISOR'))
        roll = int(ljm.eReadName(self.handle, 'DIO_EF_CLOCK0_ROLL_VALUE'))
        return roll, divisor

    def get_clock_hz(self):
        """Return the pulse rate in Hz
    rate = M.get_cock_hz(self)
"""
        roll,divisor = self.get_clock()
        return 80e6 / divisor / roll
        
    def set_clock(self, roll, divisor):
        """Set the T4 extended feature clock settings
    M.set_clock(roll, divisor)

The T4 system clock is 80MHz, so the pulse frequency will be
    80MHz / roll / divisor
    
Divisor is always a power of 2, and is used for coarse setting of the
frequency.  The roll value can take on any integer value (32 bit) and
is used for fine tuning of the pulse frequency.    
"""
        # Coerce to be an integer
        roll = int(roll)
        divisor = int(divisor)
        ljm.eWriteName(self.handle, 'DIO_EF_CLOCK0_ENABLE', 0)
        ljm.eWriteName(self.handle, 'DIO_EF_CLOCK0_ROLL_VALUE', roll)
        ljm.eWriteName(self.handle, 'DIO_EF_CLOCK0_DIVISOR', divisor)
        ljm.eWriteName(self.handle, 'DIO_EF_CLOCK0_ENABLE', 1)

        
    def set_clock_hz(self, rate):
        """Set the pulse rate in Hz
    M.set_clock_hz(self, rate)
"""
        roll = int(80e6 / abs(rate))
        divisor = 1
        while roll > 0xFFFFFFFF:
            roll >>= 1
            divisor <<= 1
        self.set_clock(roll, divisor)
        
        
    def set_pins(self, dir_pin, pulse_pin, home_pin=-1, invert=False):
        """Assign the direction, pulse, and home pin numbers
    M.set_pins(dir_pin, pulse_pin)
        OR
    M.set_pins(dir_pin, pulse_pin, home_pin, invert)
    
Accepts integer numbers for the DIO/FIO ports used for the direction,
pulse, and home pins.  Configures the T4 for pulse output on the pulse
pin, input on the home pin, and output on the dir pin.

This function assigns values to the following instance attributes:
    dir_pin         Integer pin number
    dir_reg         Register name string
    pulse_pin       ...
    pulse_reg
    home_pin
    home_reg
    invert          Boolean flag for reversing the motor direction

"""
        self.dir_pin = int(dir_pin)
        self.dir_reg = f'DIO{self.dir_pin}'
        self.pulse_pin = int(pulse_pin)
        self.pulse_reg = f'DIO{self.pulse_pin}_EF_CONFIG_C'
        self.invert = bool(invert)
        
        # Get the current IO mask
        iomask = int(ljm.eReadName(self.handle, 'DIO_DIRECTION'))
        # Set the pulse and dir pins to outputs
        iomask |= 1<<self.pulse_pin
        iomask |= 1<<self.dir_pin
        
        if home_pin >= 0:
            self.home_pin = int(home_pin)
            self.home_reg = f'DIO{self.home_pin}'
            # clear the home pin in the io mask
            iomask &= (0xFFFFFFFF ^ (1<<self.home_pin))
        else:
            self.home_pin = -1
            self.home_reg = ''
   
        # Figure out the timing parameters
        roll, divisor = self.get_clock()
   
        # Disable optional analog pins
        ljm.eWriteName(self.handle, 'DIO_ANALOG_ENABLE', 0x0F)
        # Write to the direction mask
        ljm.eWriteName(self.handle, 'DIO_DIRECTION', iomask)
        
        # Set the direction pin negative
        ljm.eWriteName(self.handle, self.dir_reg, 0)
        
        # Configure the extended feature for the pulse pin
        ljm.eWriteName(self.handle, f'DIO{self.pulse_pin}_EF_ENABLE', 0)    # Disable the extended feature while configuring
        ljm.eWriteName(self.handle, f'DIO{self.pulse_pin}_EF_INDEX', 2)     # 
        ljm.eWriteName(self.handle, f'DIO{self.pulse_pin}_EF_CONFIG_B', 0)      # Transition low->high at time 0
        ljm.eWriteName(self.handle, f'DIO{self.pulse_pin}_EF_CONFIG_A', roll//2)   # Transition high->low at time 5000
        ljm.eWriteName(self.handle, f'DIO{self.pulse_pin}_EF_CONFIG_C', 1)  # Do not move yet
        # Enable the EF channel
        ljm.eWriteName(self.handle, f'DIO{self.pulse_pin}', 0)              # Force the pin low
        ljm.eWriteName(self.handle, f'DIO{self.pulse_pin}_EF_ENABLE', 1)    # Go
        
        # Undo the step
        ljm.eWriteName(self.handle, self.dir_reg, 1)
        ljm.eWriteName(self.handle, self.pulse_reg, 1)
        
        
    def set_lim_upper(value=None, cal=False, here=False):
        """Set the upper software limit in counts
    M.set_lim_upper()           # Disable the limit
        OR
    M.set_lim_upper(value)      # Set in counts
        OR
    M.set_lim_upper(value, cal=True)    # Set in calibrated units
        OR
    M.set_lim_upper(here=True)  # Set to current position
    
The software limits set by set_lim_upper() and set_lim_lower() are the
most extreme positions to which the motor class will attemt to move the
motor.
"""
        # Deal with the case that no value is specified
        if value is None:
            # Should we be using the current location?
            if here:
                self.lim_upper = self.counts
            # If not, clear the limit
            else:
                self.lim_upper = None
            return
        # Do we need to calculate a position from a calibrated unit?
        if cal:
            value = value/self.cal_slope + self.cal_zero
        self.lim_upper = int(value)
        
    def set_lim_lower(value=None, cal=False, here=False):
        """Set the lower software limit in counts
See the set_lim_upper() help for details.
"""
        # Deal with the case that no value is specified
        if value is None:
            # Should we be using the current location?
            if here:
                self.lim_lower = self.counts
            # If not, clear the limit
            else:
                self.lim_lower = None
            return
        # Do we need to calculate a position from a calibrated unit?
        if cal:
            value = value/self.cal_slope + self.cal_zero
        self.lim_lower = int(value)
    
    def get_lim_state(self):
        """Return the boolean software limit state
    limstate = M.get_lim_state()

The state is True if the motor has reached one of the software limits
"""
        if self.lim_lower is not None and self.counts <= self.lim_lower:
            return True
        elif self.lim_upper is not None and self.counts >= self.lim_upper:
            return True
        return False
            
    def home(self, increment, max_tries=100):
        """Seek the motor home
    success = M.home(increment)
        OR
    success = M.home(increment, max_tries)
    
The home is the position at which counts is zero.  At initialization,
the Motor object is always presumed to be at home, but if a home pin
is configured, the motor can be incremented until home is discovered.

The home() method repeatedly advances the motor by [increment] counts
until the state of the home_pin changes.  Note that this algorithm is
not sensitive to the polarity of the home pin, since the algorithm
merely waits for a change.  By default this will be repeated a maximum 
of 100 increments unless a different max_tries is specified.

( increment>0 )
             v 
             ,------------.
             |            |
-------------'            `--------------------> (positive counts)
             ^
             |
             `-- Seeking Edge
             
( increment<0 )
                          v
             ,------------.
             |            |
-------------'            `--------------------> (positive counts)
                          ^
                          |
                          `-- Seeking Edge

Due to the hysteresis inherent in limit switches and photo interrupters,
home seeking should ALWAYS be done in the same direction for repeatability.

The choice of value for [increment] is critical.  If [increment] is too
large, it will be possible to completely miss the home pin pulse.  Also,
the increment value determines the precision of the homing process.
"""
        if not self.home_reg:
            raise Exception('The home channel was not configured.')
        # Detect the initial value of the home pin
        initial = ljm.eReadName(self.handle, self.home_reg)
        for try_count in range(max_tries):
            # Move the stage
            self.increment(increment,block=True)
            # Test the home pin
            if ljm.eReadName(self.handle, self.home_reg) != initial:
                return True
        return False
        

    def increment(self, value, block=False):
        """Increment the motor position in counts
    M.increment(value)
    
Accepts negative or positive values to increase or decrease motor
position.  To move to an absolute position, use the go() method.

If the optional keyword, block=True, the method will block program 
execution until the move has had time to complete.
"""
        value = int(value)
        # Detect the direction
        direction = value > 0
        # Apply the motor limits as appropriate
        if direction:
            # If the upper software limit is set
            if self.lim_upper is not None:
                value = min(value, self.lim_upper - self.counts)
        else:
            # If the lower software limit is set
            if self.lim_lower is not None:
                value = max(value, self.lim_lower - self.counts)

        # Invert the direction?
        if self.invert:
            direction = not direction
            
        # GO!
        ljm.eWriteName(self.handle, self.dir_reg, int(direction))
        ljm.eWriteName(self.handle, self.pulse_reg, abs(value))
        self.counts += value
        
        if block:
            time.sleep(abs(value) / self.get_clock_hz())
            
    def increment_cal(self, value, block=False):
        """Increment the motor position in calibrated units
    M.increment_cal(value)
    
Accepts negative or positive values to increase or decrease the motor 
position in calibrated units.  To move to an absolute position in 
calibrated units, use the go_cal() method.
"""
        value = value / self.cal_slope
        self.increment(value, block=block)
        
        
    def go(self, target, block=False):
        """Move the motor to a target position in counts
    M.go(target)
    
Use optional keyword, block=True, to block program execution until the
move has completed.
"""
        self.increment(target - self.counts, block=block)
        
    def go_cal(self, target):
        """Move the motor to a target in calibrated units
    M.go_cal(target)

Go to an aboslute position specified in calibrated units, such as an
angle or linear position.
"""
        self.go(target / self.cal_slope + self.cal_zero)
        
    def get(self):
        """Return the motor position in counts
    counts = M.get()
"""
        return self.counts
        
    def get_cal(self):
        """Return the motor position in calibrated units
    value = M.get_cal(self):
"""
        return self.cal_slope*(self.counts - self.cal_zero)
        
    def set_cal(self, zero, slope, units):
        """Set the motor's calibration units
    M.set_cal(zero, slope, units)
    
This sets up a linear calibration between the motor's position in pulse
counts and the motor's position in engineering units (like degrees).
    
    VALUE = slope * (COUNTS - zero)
    
zero    The motor's calibrated position is zero when counts == zero.
        Even though counts is always an integer, the zero can be a float.
        
slope   The relationship between the motor's position in pulse counts 
        and the calibrated position.  For example, a 400 pulse-per-
        rotation motor would have a slope=(360/400) for a calibration in
        degrees.  The slope MUST BE POSITIVE.
        
units   This is the units string used to express the units.
"""
        if slope <= 0:
            raise Exception('The slope MUST be a positive (non-zero) number.')
        self.cal_zero = zero
        self.cal_slope = slope
        self.cal_units = units


def global_init():
    """Global Initializer
    polarizer, monochrometer = global_init()
    
Returns instances of the Motor class for the polarizer and monochrometer
after opening a connection to the labjack and initializing the proper
channels.
"""
    # These parameters determine how the pin assignments are made
    # For firmware control of pulse output, the pulses MUST be output
    # from pins 6 and 7.  Software pulse control could be used, but that
    # would be silly.
    mono_pulse_pin = 7
    mono_dir_pin = 5
    mono_home_pin = 9
    polar_pulse_pin = 6
    polar_dir_pin = 4
    polar_home_pin = 8
    pulse_rate_hz = 1000

    # Open the connection to the device.
    # 440012418 is the serial number.
    # If the device is changed, this will need to be adjusted
    h = ljm.open(identifier='440012418')

    # Set up the motor control objects
    polarizer = Motor(h)
    polarizer.set_clock_hz(pulse_rate_hz)
    polarizer.set_pins(polar_dir_pin, polar_pulse_pin, polar_home_pin)
        
    monochrometer = Motor(h)
    # The clock is shared for all extended features.  There is no need
    # to set the clock again.
    # monochrometer.set_clock_hz(pulse_rate_hz)
    monochrometer.set_pins(mono_dir_pin, mono_pulse_pin, polar_home_pin)

    return polarizer, monochrometer
    



if __name__ == '__main__':

    # Create the master interface window
    root = tk.Tk()
    root.title('Rumble Spectroscopy')

    frame = ttk.Frame(root, width=400, height=200).grid(sticky='NSEW')

    # Initialize some internal global variables
    # Monochrometer target value in nanometers
    mono_target_nm = tk.DoubleVar()
    mono_increment_nm = tk.DoubleVar()
    # Polarizer target value in degrees
    polar_target_deg = tk.DoubleVar()
    
    def show_error(text):
        mono_status_nm.set(mono_target_nm.get())
    
    # Create some event handlers
    # monochrometer go
    def callback_mono_go(*args):
        value = mono_target_nm.get()
        print(f'Moving the monochrometer to {value} nm.')
        monochrometer.go_cal(mono_target_nm.get())
        

    def callback_mono_incr(*args):
        value = mono_increment_nm.get()
        print(f'Incrementing the monochrometer by {value} nm.')
        monochrometer.increment_cal(value)

    def callback_polar_vert(*args):
        polarizer.go_cal(0.)

    def callback_polar_hor(*args):
        polarizer.go_cal(90.)

    def callback_polar_ma(*args):
        polarizer.go_cal(45.)

    def callback_polar_go(*args):
        target = polar_target_deg.get()
        print(f'Moving the polarizer to {target} deg.')
        polarizer.go_cal(target)

    #
    # Create the UI elements
    #
    
    # Monochrometer entries
    ttk.Label(frame, text='Monochrometer').grid(\
            column=1, row=1, columnspan=3)
    mono_status = ttk.Label(frame, text='')
    mono_status.grid(column=1, row=2, columnspan=3)
    # Go line
    ttk.Entry(frame, width=7, textvariable=mono_target_nm).grid(\
            column=1, row=3)
    ttk.Label(frame, text='(nm)').grid(\
            column=2, row=3)
    ttk.Button(frame, text='Go', command=callback_mono_go, width=15).grid(\
            column=3, row=3, sticky='E')
    # Increment Line
    ttk.Entry(frame, width=7, textvariable=mono_increment_nm).grid(\
            column=1, row=4)
    ttk.Label(frame, text='(nm)').grid(\
            column=2, row=4)
    ttk.Button(frame, text='Increment', command=callback_mono_incr, width=15).grid(\
            column=3, row=4, sticky='E')
    
    # Polarizer entries
    ttk.Label(frame, text='Polarizer').grid(
            column=4, row=1, columnspan=3)
    polar_status = ttk.Label(frame, text='')
    polar_status.grid(column=4, row=2, columnspan=3)
    
    ttk.Button(frame, text='Vertical', command=callback_polar_vert, width=15).grid(\
            column=6, row=3)
    ttk.Button(frame, text='Horizontal', command=callback_polar_hor, width=15).grid(\
            column=6, row=4)
    ttk.Button(frame, text='Magic Angle', command=callback_polar_ma, width=15).grid(\
            column=6, row=5)
    ttk.Entry(frame, textvariable=polar_target_deg, width=7).grid(\
            column=4, row=6)
    ttk.Label(frame, text='(deg)').grid(\
            column=5, row=6)
    ttk.Button(frame, text='Go', command=callback_polar_go, width=15).grid(\
            column=6, row=6)
    
    
    #
    # Initialize the motor objects
    #
    monochrometer, polarizer = global_init()
    
    root.mainloop()
