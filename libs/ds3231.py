"""
DS3231 RTC Library for MicroPython
Compatible with ESP32
Interface: I2C (SCL, SDA)
Features:
- High precision RTC with temperature compensated crystal
- I2C interface (address 0x68)
- No need for 32K and SQW pins (optional)
- Built-in battery backup
- Automatic leap year correction
"""

from machine import I2C
import time

class DS3231:
    """DS3231 Real Time Clock driver via I2C"""
    
    # I2C Address
    DS3231_I2C_ADDR = 0x68
    
    # Register addresses
    REG_SECONDS = 0x00
    REG_MINUTES = 0x01
    REG_HOURS = 0x02
    REG_DAY = 0x03      # Day of week (1-7)
    REG_DATE = 0x04     # Day of month (1-31)
    REG_MONTH = 0x05
    REG_YEAR = 0x06
    REG_CONTROL = 0x0E
    REG_STATUS = 0x0F
    REG_TEMP_MSB = 0x11
    REG_TEMP_LSB = 0x12
    
    def __init__(self, i2c):
        """
        Initialize DS3231
        i2c: I2C object (already initialized with SCL and SDA pins)
        
        Example:
            i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
            rtc = DS3231(i2c)
        """
        self.i2c = i2c
        self.addr = self.DS3231_I2C_ADDR
        
        # Check if DS3231 is connected
        devices = self.i2c.scan()
        if self.addr not in devices:
            raise OSError(f"DS3231 not found at address 0x{self.addr:02X}")
        
        # Initialize control register
        # Disable alarms and square wave output
        self._write_register(self.REG_CONTROL, 0x00)
        
        # Clear oscillator stop flag
        status = self._read_register(self.REG_STATUS)
        self._write_register(self.REG_STATUS, status & 0x7F)
        
        print(f"✓ DS3231 initialized at 0x{self.addr:02X}")
    
    def _bcd_to_dec(self, bcd):
        """Convert BCD to decimal"""
        return (bcd >> 4) * 10 + (bcd & 0x0F)
    
    def _dec_to_bcd(self, dec):
        """Convert decimal to BCD"""
        return ((dec // 10) << 4) | (dec % 10)
    
    def _read_register(self, reg):
        """Read single register"""
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]
    
    def _write_register(self, reg, value):
        """Write single register"""
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))
    
    def _read_registers(self, reg, length):
        """Read multiple registers"""
        return self.i2c.readfrom_mem(self.addr, reg, length)
    
    def date_time(self, datetime_tuple=None):
        """
        Get or set date and time
        datetime_tuple format: (year, month, day, hour, minute, second, weekday)
        Returns: (year, month, day, hour, minute, second, weekday)
        
        Note: weekday 1=Monday, 7=Sunday
        """
        if datetime_tuple is None:
            # Read date/time
            data = self._read_registers(self.REG_SECONDS, 7)
            
            seconds = self._bcd_to_dec(data[0] & 0x7F)
            minutes = self._bcd_to_dec(data[1] & 0x7F)
            hours = self._bcd_to_dec(data[2] & 0x3F)  # 24-hour format
            weekday = self._bcd_to_dec(data[3] & 0x07)
            day = self._bcd_to_dec(data[4] & 0x3F)
            month = self._bcd_to_dec(data[5] & 0x1F)
            year = self._bcd_to_dec(data[6]) + 2000
            
            return (year, month, day, hours, minutes, seconds, weekday)
        else:
            # Write date/time
            year, month, day, hours, minutes, seconds, weekday = datetime_tuple
            
            # Validate input
            if year < 2000 or year > 2099:
                raise ValueError("Year must be between 2000 and 2099")
            if month < 1 or month > 12:
                raise ValueError("Month must be between 1 and 12")
            if day < 1 or day > 31:
                raise ValueError("Day must be between 1 and 31")
            if hours < 0 or hours > 23:
                raise ValueError("Hours must be between 0 and 23")
            if minutes < 0 or minutes > 59:
                raise ValueError("Minutes must be between 0 and 59")
            if seconds < 0 or seconds > 59:
                raise ValueError("Seconds must be between 0 and 59")
            if weekday < 1 or weekday > 7:
                raise ValueError("Weekday must be between 1 and 7")
            
            # Convert to BCD and write
            data = bytes([
                self._dec_to_bcd(seconds),
                self._dec_to_bcd(minutes),
                self._dec_to_bcd(hours),
                self._dec_to_bcd(weekday),
                self._dec_to_bcd(day),
                self._dec_to_bcd(month),
                self._dec_to_bcd(year - 2000)
            ])
            
            self.i2c.writeto_mem(self.addr, self.REG_SECONDS, data)
    
    def get_time(self):
        """Get time as (hour, minute, second)"""
        dt = self.date_time()
        return (dt[3], dt[4], dt[5])
    
    def get_date(self):
        """Get date as (year, month, day)"""
        dt = self.date_time()
        return (dt[0], dt[1], dt[2])
    
    def set_time(self, hour, minute, second):
        """Set time only (keep existing date)"""
        dt = self.date_time()
        self.date_time((dt[0], dt[1], dt[2], hour, minute, second, dt[6]))
    
    def set_date(self, year, month, day):
        """Set date only (keep existing time)"""
        dt = self.date_time()
        # Calculate day of week (Zeller's congruence)
        if month < 3:
            month += 12
            year -= 1
        weekday = (day + (13 * (month + 1)) // 5 + year + year // 4 - year // 100 + year // 400) % 7
        if weekday == 0:
            weekday = 7
        
        self.date_time((year, month, day, dt[3], dt[4], dt[5], weekday))
    
    def is_running(self):
        """Check if oscillator is running"""
        status = self._read_register(self.REG_STATUS)
        return not bool(status & 0x80)  # OSF bit
    
    def get_temperature(self):
        """
        Get temperature from DS3231 internal sensor
        Returns: temperature in Celsius (float)
        Resolution: 0.25°C
        """
        msb = self._read_register(self.REG_TEMP_MSB)
        lsb = self._read_register(self.REG_TEMP_LSB)
        
        # Temperature is stored as 10-bit value in upper bits of two registers
        temp = msb + ((lsb >> 6) * 0.25)
        
        # Handle negative temperatures
        if msb & 0x80:
            temp = temp - 256
        
        return temp
    
    def format_datetime(self):
        """Format datetime as string YYYY-MM-DD HH:MM:SS"""
        dt = self.date_time()
        return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            dt[0], dt[1], dt[2], dt[3], dt[4], dt[5]
        )
    
    def format_iso8601(self):
        """Format datetime as ISO8601 string"""
        dt = self.date_time()
        return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}+00:00".format(
            dt[0], dt[1], dt[2], dt[3], dt[4], dt[5]
        )
    
    def format_time(self):
        """Format time as HH:MM:SS"""
        dt = self.date_time()
        return "{:02d}:{:02d}:{:02d}".format(dt[3], dt[4], dt[5])
    
    def format_date(self):
        """Format date as YYYY-MM-DD"""
        dt = self.date_time()
        return "{:04d}-{:02d}-{:02d}".format(dt[0], dt[1], dt[2])
    
    def set_alarm1(self, day=None, hour=None, minute=None, second=None):
        """
        Set alarm 1 (precise to seconds)
        Not implemented - DS3231 alarms are optional feature
        """
        pass
    
    def set_alarm2(self, day=None, hour=None, minute=None):
        """
        Set alarm 2 (precise to minutes)
        Not implemented - DS3231 alarms are optional feature
        """
        pass
    
    def clear_alarm(self, alarm=None):
        """Clear alarm flags"""
        status = self._read_register(self.REG_STATUS)
        if alarm == 1:
            status &= ~0x01
        elif alarm == 2:
            status &= ~0x02
        else:
            status &= ~0x03  # Clear both
        self._write_register(self.REG_STATUS, status)
    
    def enable_32khz(self, enable=True):
        """Enable/disable 32kHz output pin"""
        status = self._read_register(self.REG_STATUS)
        if enable:
            status |= 0x08  # EN32kHz bit
        else:
            status &= ~0x08
        self._write_register(self.REG_STATUS, status)
    
    def set_square_wave(self, freq=1):
        """
        Set square wave output frequency on SQW pin
        freq: 1, 1024, 4096, 8192 Hz
        0 to disable
        """
        control = self._read_register(self.REG_CONTROL)
        
        if freq == 0:
            # Disable square wave
            control |= 0x04  # INTCN bit
        else:
            control &= ~0x04  # Enable square wave
            control &= ~0x18  # Clear RS bits
            
            if freq == 1:
                control |= 0x00
            elif freq == 1024:
                control |= 0x08
            elif freq == 4096:
                control |= 0x10
            elif freq == 8192:
                control |= 0x18
        
        self._write_register(self.REG_CONTROL, control)