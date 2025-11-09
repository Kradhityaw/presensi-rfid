"""
MFRC522 RFID Reader Library for MicroPython
Compatible with ESP32
Version: 1.1 (Fixed UID reading and sensitivity)
"""

from machine import Pin
import time

class MFRC522:
    # MFRC522 registers
    CommandReg = 0x01
    ComIEnReg = 0x02
    ComIrqReg = 0x04
    ErrorReg = 0x06
    Status2Reg = 0x08
    FIFODataReg = 0x09
    FIFOLevelReg = 0x0A
    ControlReg = 0x0C
    BitFramingReg = 0x0D
    ModeReg = 0x11
    TxControlReg = 0x14
    TxASKReg = 0x15
    TxModeReg = 0x12
    RxModeReg = 0x13
    CRCResultRegM = 0x21
    CRCResultRegL = 0x22
    TModeReg = 0x2A
    TPrescalerReg = 0x2B
    TReloadRegH = 0x2C
    TReloadRegL = 0x2D
    TxAutoReg = 0x15
    VersionReg = 0x37
    
    # MFRC522 commands
    PCD_IDLE = 0x00
    PCD_AUTHENT = 0x0E
    PCD_RECEIVE = 0x08
    PCD_TRANSMIT = 0x04
    PCD_TRANSCEIVE = 0x0C
    PCD_RESETPHASE = 0x0F
    PCD_CALCCRC = 0x03
    
    # PICC commands
    PICC_REQIDL = 0x26
    PICC_REQALL = 0x52
    PICC_ANTICOLL = 0x93
    PICC_SELECTTAG = 0x93
    PICC_AUTHENT1A = 0x60
    PICC_AUTHENT1B = 0x61
    PICC_READ = 0x30
    PICC_WRITE = 0xA0
    PICC_HALT = 0x50
    
    # Status codes
    OK = 0
    NOTAGERR = 1
    ERR = 2
    
    # Request modes
    REQIDL = 0x26
    REQALL = 0x52
    
    def __init__(self, spi, cs, rst):
        self.spi = spi
        self.cs = cs
        self.rst = rst
        
        self.cs.init(Pin.OUT)
        self.rst.init(Pin.OUT)
        
        # Hard reset
        self.rst.value(0)
        time.sleep_ms(50)
        self.rst.value(1)
        time.sleep_ms(50)
        
        self.init()
    
    def read(self, addr):
        """Read from MFRC522 register"""
        self.cs.value(0)
        self.spi.write(bytearray([((addr << 1) & 0x7E) | 0x80]))
        val = self.spi.read(1)
        self.cs.value(1)
        return val[0]
    
    def write(self, addr, val):
        """Write to MFRC522 register"""
        self.cs.value(0)
        self.spi.write(bytearray([(addr << 1) & 0x7E, val]))
        self.cs.value(1)
    
    def set_bitmask(self, reg, mask):
        """Set bit mask"""
        tmp = self.read(reg)
        self.write(reg, tmp | mask)
    
    def clear_bitmask(self, reg, mask):
        """Clear bit mask"""
        tmp = self.read(reg)
        self.write(reg, tmp & (~mask))
    
    def antenna_on(self):
        """Turn antenna on with maximum gain"""
        temp = self.read(self.TxControlReg)
        if not (temp & 0x03):
            self.set_bitmask(self.TxControlReg, 0x03)
        
        # Set maximum antenna gain for better sensitivity
        self.write(0x26, 0x88)  # RFCfgReg - Maximum gain (48 dB)
    
    def antenna_off(self):
        """Turn antenna off"""
        self.clear_bitmask(self.TxControlReg, 0x03)
    
    def init(self):
        """Initialize MFRC522 with improved sensitivity settings"""
        self.reset()
        
        # Timer settings
        self.write(self.TModeReg, 0x8D)
        self.write(self.TPrescalerReg, 0x3E)
        self.write(self.TReloadRegL, 30)
        self.write(self.TReloadRegH, 0)
        
        # TX settings for better power
        self.write(self.TxASKReg, 0x40)
        self.write(self.ModeReg, 0x3D)
        
        # Improved RX settings
        self.write(self.RxModeReg, 0x00)
        self.write(self.TxModeReg, 0x00)
        
        # Set CRC preset to 0x6363
        self.write(self.ModeReg, 0x3D)
        
        self.antenna_on()
    
    def reset(self):
        """Reset MFRC522"""
        self.write(self.CommandReg, self.PCD_RESETPHASE)
        time.sleep_ms(50)
    
    def request(self, req_mode):
        """Request card with improved error handling"""
        self.write(self.BitFramingReg, 0x07)
        tag_type = [req_mode]
        (stat, recv, bits) = self.card_write(self.PCD_TRANSCEIVE, tag_type)
        
        if (stat != self.OK) or (bits != 0x10):
            stat = self.ERR
        
        return (stat, bits)
    
    def card_write(self, command, send_data):
        """Write data to card with improved timing"""
        recv_data = []
        bits = irq_en = wait_irq = n = 0
        stat = self.ERR
        
        if command == self.PCD_AUTHENT:
            irq_en = 0x12
            wait_irq = 0x10
        
        if command == self.PCD_TRANSCEIVE:
            irq_en = 0x77
            wait_irq = 0x30
        
        self.write(self.ComIEnReg, irq_en | 0x80)
        self.clear_bitmask(self.ComIrqReg, 0x80)
        self.set_bitmask(self.FIFOLevelReg, 0x80)
        self.write(self.CommandReg, self.PCD_IDLE)
        
        for data in send_data:
            self.write(self.FIFODataReg, data)
        
        self.write(self.CommandReg, command)
        
        if command == self.PCD_TRANSCEIVE:
            self.set_bitmask(self.BitFramingReg, 0x80)
        
        # Increased timeout for better reliability
        i = 2000
        while True:
            n = self.read(self.ComIrqReg)
            i -= 1
            if not ((i != 0) and not (n & 0x01) and not (n & wait_irq)):
                break
        
        self.clear_bitmask(self.BitFramingReg, 0x80)
        
        if i != 0:
            if (self.read(self.ErrorReg) & 0x1B) == 0x00:
                stat = self.OK
                
                if n & irq_en & 0x01:
                    stat = self.NOTAGERR
                
                if command == self.PCD_TRANSCEIVE:
                    n = self.read(self.FIFOLevelReg)
                    last_bits = self.read(self.ControlReg) & 0x07
                    
                    if last_bits != 0:
                        bits = (n - 1) * 8 + last_bits
                    else:
                        bits = n * 8
                    
                    if n == 0:
                        n = 1
                    
                    if n > 16:
                        n = 16
                    
                    for _ in range(n):
                        recv_data.append(self.read(self.FIFODataReg))
            else:
                stat = self.ERR
        
        return (stat, recv_data, bits)
    
    def anticoll(self):
        """Anti-collision detection - FIXED for correct UID length"""
        ser_num = []
        ser_num_check = 0
        
        self.write(self.BitFramingReg, 0x00)
        ser_num.append(self.PICC_ANTICOLL)
        ser_num.append(0x20)
        
        (stat, recv_data, bits) = self.card_write(self.PCD_TRANSCEIVE, ser_num)
        
        if stat == self.OK:
            if len(recv_data) == 5:
                # Validate checksum
                for i in range(4):
                    ser_num_check = ser_num_check ^ recv_data[i]
                
                if ser_num_check != recv_data[4]:
                    stat = self.ERR
                else:
                    # PENTING: Return hanya 4 byte pertama (bukan 5)
                    # Byte ke-5 adalah checksum, bukan bagian dari UID
                    recv_data = recv_data[:4]
            else:
                stat = self.ERR
        
        return (stat, recv_data)
    
    def SelectTag(self, ser_num):
        """Select tag - FIXED to accept 4-byte UID"""
        buf = []
        buf.append(self.PICC_SELECTTAG)
        buf.append(0x70)
        
        # Hanya gunakan 4 byte UID
        for i in range(min(4, len(ser_num))):
            buf.append(ser_num[i])
        
        # Calculate checksum
        checksum = 0
        for i in range(4):
            checksum ^= ser_num[i]
        buf.append(checksum)
        
        pOut = self.CalulateCRC(buf)
        buf.append(pOut[0])
        buf.append(pOut[1])
        
        (stat, recv_data, bits) = self.card_write(self.PCD_TRANSCEIVE, buf)
        
        if (stat == self.OK) and (bits == 0x18):
            return self.OK
        else:
            return self.ERR
    
    def SelectTagSN(self):
        """Select tag and return serial number (4 bytes only)"""
        (stat, uid) = self.anticoll()
        if stat == self.OK and len(uid) == 4:
            if self.SelectTag(uid) == self.OK:
                return (self.OK, uid)
        return (self.ERR, [])
    
    def CalulateCRC(self, pIn_data):
        """Calculate CRC"""
        self.clear_bitmask(self.ComIrqReg, 0x04)
        self.set_bitmask(self.FIFOLevelReg, 0x80)
        
        for data in pIn_data:
            self.write(self.FIFODataReg, data)
        
        self.write(self.CommandReg, self.PCD_CALCCRC)
        
        i = 0xFF
        while True:
            n = self.read(self.ComIrqReg)
            i -= 1
            if not ((i != 0) and not (n & 0x04)):
                break
        
        pOut_data = []
        pOut_data.append(self.read(self.CRCResultRegL))
        pOut_data.append(self.read(self.CRCResultRegM))
        
        return pOut_data
    
    def auth(self, mode, addr, sect, ser_num):
        """Authenticate"""
        buf = [mode, addr]
        buf += sect
        buf += ser_num[:4]
        
        (stat, recv, bits) = self.card_write(self.PCD_AUTHENT, buf)
        
        if not (stat == self.OK):
            print("AUTH ERROR!!")
        
        if not (self.read(self.Status2Reg) & 0x08) != 0:
            print("AUTH ERROR(status2reg & 0x08) != 0")
        
        return stat
    
    def stop_crypto1(self):
        """Stop crypto"""
        self.clear_bitmask(self.Status2Reg, 0x08)
    
    def read_card(self, addr):
        """Read card data"""
        data = [self.PICC_READ, addr]
        data += self.CalulateCRC(data)
        (stat, recv, _) = self.card_write(self.PCD_TRANSCEIVE, data)
        return recv if stat == self.OK else None
    
    def write_card(self, addr, data):
        """Write card data"""
        buf = [self.PICC_WRITE, addr]
        buf += self.CalulateCRC(buf)
        (stat, recv, bits) = self.card_write(self.PCD_TRANSCEIVE, buf)
        
        if not (stat == self.OK) or not (bits == 4) or not ((recv[0] & 0x0F) == 0x0A):
            stat = self.ERR
        
        if stat == self.OK:
            buf_w = []
            for i in range(16):
                buf_w.append(data[i])
            
            buf_w += self.CalulateCRC(buf_w)
            (stat, recv, bits) = self.card_write(self.PCD_TRANSCEIVE, buf_w)
            
            if not (stat == self.OK) or not (bits == 4) or not ((recv[0] & 0x0F) == 0x0A):
                stat = self.ERR
        
        return stat
    
    def halt(self):
        """Halt card communication"""
        buf = [self.PICC_HALT, 0]
        crc = self.CalulateCRC(buf)
        buf += crc
        self.card_write(self.PCD_TRANSCEIVE, buf)
        self.clear_bitmask(self.Status2Reg, 0x08)
        if (self.read(self.ErrorReg) & 0x1B) == 0x00:
            stat = self.OK
            
            if n & irq_en & 0x01:
                stat = self.NOTAGERR
            
            if command == self.PCD_TRANSCEIVE:
                n = self.read(self.FIFOLevelReg)
                last_bits = self.read(self.ControlReg) & 0x07
                
                if last_bits != 0:
                    bits = (n - 1) * 8 + last_bits
                else:
                    bits = n * 8
                
                if n == 0:
                    n = 1
                
                if n > 16:
                    n = 16
                
                for _ in range(n):
                    recv_data.append(self.read(self.FIFODataReg))
        else:
            stat = self.ERR
        
        return (stat, recv_data, bits)
    
    def anticoll(self):
        """Anti-collision detection"""
        ser_num = []
        ser_num_check = 0
        
        self.write(self.BitFramingReg, 0x00)
        ser_num.append(self.PICC_ANTICOLL)
        ser_num.append(0x20)
        
        (stat, recv_data, bits) = self.card_write(self.PCD_TRANSCEIVE, ser_num)
        
        if stat == self.OK:
            if len(recv_data) == 5:
                for i in range(4):
                    ser_num_check = ser_num_check ^ recv_data[i]
                
                if ser_num_check != recv_data[4]:
                    stat = self.ERR
            else:
                stat = self.ERR
        
        return (stat, recv_data)
    
    def SelectTag(self, ser_num):
        """Select tag"""
        buf = []
        buf.append(self.PICC_SELECTTAG)
        buf.append(0x70)
        
        for i in range(5):
            buf.append(ser_num[i])
        
        pOut = self.CalulateCRC(buf)
        buf.append(pOut[0])
        buf.append(pOut[1])
        
        (stat, recv_data, bits) = self.card_write(self.PCD_TRANSCEIVE, buf)
        
        if (stat == self.OK) and (bits == 0x18):
            return self.OK
        else:
            return self.ERR
    
    def SelectTagSN(self):
        """Select tag and return serial number"""
        (stat, uid) = self.anticoll()
        if stat == self.OK:
            if self.SelectTag(uid) == self.OK:
                return (self.OK, uid)
        return (self.ERR, [])
    
    def CalulateCRC(self, pIn_data):
        """Calculate CRC"""
        self.clear_bitmask(self.ComIrqReg, 0x04)
        self.set_bitmask(self.FIFOLevelReg, 0x80)
        
        for data in pIn_data:
            self.write(self.FIFODataReg, data)
        
        self.write(self.CommandReg, self.PCD_CALCCRC)
        
        i = 0xFF
        while True:
            n = self.read(self.ComIrqReg)
            i -= 1
            if not ((i != 0) and not (n & 0x04)):
                break
        
        pOut_data = []
        pOut_data.append(self.read(self.CRCResultRegL))
        pOut_data.append(self.read(self.CRCResultRegM))
        
        return pOut_data
    
    def auth(self, mode, addr, sect, ser_num):
        """Authenticate"""
        buf = [mode, addr]
        buf += sect
        buf += ser_num[:4]
        
        (stat, recv, bits) = self.card_write(self.PCD_AUTHENT, buf)
        
        if not (stat == self.OK):
            print("AUTH ERROR!!")
        
        if not (self.read(self.Status2Reg) & 0x08) != 0:
            print("AUTH ERROR(status2reg & 0x08) != 0")
        
        return stat
    
    def stop_crypto1(self):
        """Stop crypto"""
        self.clear_bitmask(self.Status2Reg, 0x08)
    
    def read_card(self, addr):
        """Read card data"""
        data = [self.PICC_READ, addr]
        data += self.CalulateCRC(data)
        (stat, recv, _) = self.card_write(self.PCD_TRANSCEIVE, data)
        return recv if stat == self.OK else None
    
    def write_card(self, addr, data):
        """Write card data"""
        buf = [self.PICC_WRITE, addr]
        buf += self.CalulateCRC(buf)
        (stat, recv, bits) = self.card_write(self.PCD_TRANSCEIVE, buf)
        
        if not (stat == self.OK) or not (bits == 4) or not ((recv[0] & 0x0F) == 0x0A):
            stat = self.ERR
        
        if stat == self.OK:
            buf_w = []
            for i in range(16):
                buf_w.append(data[i])
            
            buf_w += self.CalulateCRC(buf_w)
            (stat, recv, bits) = self.card_write(self.PCD_TRANSCEIVE, buf_w)
            
            if not (stat == self.OK) or not (bits == 4) or not ((recv[0] & 0x0F) == 0x0A):
                stat = self.ERR
        
        return stat