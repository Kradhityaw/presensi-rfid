# ============================================
# MATERI 05: SISTEM PRESENSI + SD CARD STORAGE
# Program: Menyimpan data presensi ke SD Card
# Platform: MicroPython ESP32
# ============================================

from machine import Pin, SPI, I2C, PWM
import time
import ujson as json
import os

# Import library
from mfrc522 import MFRC522
from ssd1306 import SSD1306_I2C
from ds3231 import DS3231
import sdcard

# ============================================
# KONFIGURASI PIN
# ============================================

PIN_I2C_SCL = 22
PIN_I2C_SDA = 21

PIN_RFID_CS = 5
PIN_RFID_SCK = 18
PIN_RFID_MOSI = 23
PIN_RFID_MISO = 19
PIN_RFID_RST = 4

PIN_SD_CS = 25
PIN_SD_SCK = 14
PIN_SD_MOSI = 13
PIN_SD_MISO = 12

PIN_BUZZER = 15

# ============================================
# KONFIGURASI FILE SD CARD
# ============================================

FILE_PRESENSI = '/sd/presensi.json'
FILE_BACKUP = '/sd/backup_presensi.json'

# ============================================
# DATA DUMMY
# ============================================

DATABASE_KARTU = {
    "a1b2c3d4": {"nama": "Budi Santoso", "kelas": "XII TKJ", "member_id": 1},
    "e5f6g7h8": {"nama": "Ani Wijaya", "kelas": "XII RPL", "member_id": 2},
    "i9j0k1l2": {"nama": "Candra Putra", "kelas": "XII TKJ", "member_id": 3},
}

# ============================================
# INISIALISASI HARDWARE
# ============================================

def init_i2c():
    """Inisialisasi I2C"""
    try:
        i2c = I2C(0, scl=Pin(PIN_I2C_SCL), sda=Pin(PIN_I2C_SDA), freq=400000)
        print(f"✓ I2C OK: {[hex(d) for d in i2c.scan()]}")
        return i2c
    except Exception as e:
        print(f"✗ I2C error: {e}")
        return None

def init_oled(i2c):
    """Inisialisasi OLED"""
    try:
        oled = SSD1306_I2C(128, 64, i2c, addr=0x3C)
        oled.fill(0)
        oled.show()
        print("✓ OLED OK")
        return oled
    except Exception as e:
        print(f"✗ OLED error: {e}")
        return None

def init_rtc(i2c):
    """Inisialisasi RTC"""
    try:
        rtc = DS3231(i2c)
        dt = rtc.date_time()
        print(f"✓ RTC OK: {dt[0]}-{dt[1]:02d}-{dt[2]:02d} {dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}")
        return rtc
    except Exception as e:
        print(f"✗ RTC error: {e}")
        return None

def init_rfid():
    """Inisialisasi RFID"""
    try:
        spi = SPI(1, baudrate=1000000, polarity=0, phase=0,
                  sck=Pin(PIN_RFID_SCK), mosi=Pin(PIN_RFID_MOSI), miso=Pin(PIN_RFID_MISO))
        rfid = MFRC522(spi, Pin(PIN_RFID_CS), Pin(PIN_RFID_RST))
        print("✓ RFID OK")
        return rfid
    except Exception as e:
        print(f"✗ RFID error: {e}")
        return None

def init_sd_card():
    """Inisialisasi SD Card"""
    print("Menginisialisasi SD Card...")
    try:
        spi = SPI(2, baudrate=1000000, polarity=0, phase=0,
                  sck=Pin(PIN_SD_SCK), mosi=Pin(PIN_SD_MOSI), miso=Pin(PIN_SD_MISO))
        sd = sdcard.SDCard(spi, Pin(PIN_SD_CS))
        
        # Mount SD Card
        try:
            os.mount(sd, '/sd')
        except:
            try:
                os.umount('/sd')
            except:
                pass
            os.mount(sd, '/sd')
        
        # Test write/read
        with open('/sd/test.txt', 'w') as f:
            f.write('OK')
        with open('/sd/test.txt', 'r') as f:
            test = f.read()
        os.remove('/sd/test.txt')
        
        if test == 'OK':
            print("✓ SD Card OK dan siap digunakan")
            return True
        else:
            print("✗ SD Card tidak bisa write/read")
            return False
    except Exception as e:
        print(f"✗ SD Card error: {e}")
        return False

def init_buzzer():
    """Inisialisasi Buzzer"""
    try:
        buzzer = PWM(Pin(PIN_BUZZER), freq=2000, duty=0)
        print("✓ Buzzer OK")
        return buzzer
    except:
        return None

# ============================================
# FUNGSI BUZZER
# ============================================

def beep(buzzer, freq, ms):
    if buzzer:
        buzzer.freq(freq)
        buzzer.duty(512)
        time.sleep_ms(ms)
        buzzer.duty(0)

def bunyi_sukses(buzzer):
    beep(buzzer, 1500, 100)
    time.sleep_ms(50)
    beep(buzzer, 2000, 100)

def bunyi_error(buzzer):
    beep(buzzer, 500, 200)
    time.sleep_ms(100)
    beep(buzzer, 500, 200)

def bunyi_save(buzzer):
    """Bunyi konfirmasi data tersimpan"""
    beep(buzzer, 1000, 50)

# ============================================
# FUNGSI RTC
# ============================================

def get_timestamp_string(rtc):
    """Timestamp format ISO8601"""
    dt = rtc.date_time()
    return f"{dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d}T{dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}+00:00"

def get_waktu_display(rtc):
    """Waktu untuk tampilan"""
    dt = rtc.date_time()
    return f"{dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}"

def get_tanggal_display(rtc):
    """Tanggal untuk tampilan"""
    dt = rtc.date_time()
    bulan = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{dt[2]:02d} {bulan[dt[1]]} {dt[0]}"

# ============================================
# FUNGSI OLED
# ============================================

def tampilkan_teks(oled, lines):
    """Tampilkan teks di OLED"""
    oled.fill(0)
    y = 0
    for line in lines[:4]:
        if line:
            text = str(line)[:16]
            x = max(0, (128 - len(text) * 8) // 2)
            oled.text(text, x, y, 1)
        y += 16
    oled.show()

def tampilkan_home(oled, rtc):
    """Tampilan home"""
    tampilkan_teks(oled, [
        "SMKN 100 Malang",
        get_waktu_display(rtc),
        "",
        "Scan Kartu Anda"
    ])

def tampilkan_presensi_sukses(oled, nama, kelas, waktu):
    """Tampilan presensi sukses"""
    tampilkan_teks(oled, [
        "PRESENSI SUKSES",
        nama[:16],
        kelas[:16],
        waktu
    ])

def tampilkan_kartu_tidak_terdaftar(oled):
    """Tampilan kartu tidak terdaftar"""
    tampilkan_teks(oled, [
        "KARTU TIDAK",
        "TERDAFTAR",
        "Hubungi Admin"
    ])

# ============================================
# FUNGSI RFID
# ============================================

def bytes_to_hex(data):
    """Konversi bytes ke hex"""
    return ''.join(['{:02x}'.format(b) for b in data[:4]])

def baca_kartu_rfid(rfid):
    """Baca kartu RFID"""
    try:
        (stat, tag_type) = rfid.request(rfid.REQIDL)
        if stat == rfid.OK:
            (stat, uid) = rfid.SelectTagSN()
            if stat == rfid.OK:
                return bytes_to_hex(uid)
    except:
        pass
    return None

# ============================================
# FUNGSI SD CARD - OPERASI FILE
# ============================================

def simpan_presensi_ke_sd(record):
    """
    Simpan 1 record presensi ke SD Card
    Format: append ke file JSON array
    """
    try:
        # Baca data existing
        data_existing = []
        if 'presensi.json' in os.listdir('/sd'):
            with open(FILE_PRESENSI, 'r') as f:
                content = f.read()
                if content:
                    data_existing = json.loads(content)
        
        # Tambahkan record baru
        data_existing.append(record)
        
        # Simpan kembali ke file
        with open(FILE_PRESENSI, 'w') as f:
            f.write(json.dumps(data_existing))
        
        print(f"  → Data tersimpan ke SD Card (Total: {len(data_existing)} records)")
        return True
    except Exception as e:
        print(f"  ✗ Error simpan ke SD: {e}")
        return False

def load_presensi_dari_sd():
    """
    Load semua data presensi dari SD Card
    Return: list of records atau []
    """
    try:
        if 'presensi.json' in os.listdir('/sd'):
            with open(FILE_PRESENSI, 'r') as f:
                content = f.read()
                if content:
                    data = json.loads(content)
                    print(f"✓ Loaded {len(data)} records dari SD Card")
                    return data
        print("⚠ File presensi.json tidak ditemukan")
        return []
    except Exception as e:
        print(f"✗ Error load dari SD: {e}")
        return []

def backup_presensi_ke_sd():
    """
    Buat backup file presensi
    Copy presensi.json ke backup_presensi.json
    """
    try:
        if 'presensi.json' in os.listdir('/sd'):
            with open(FILE_PRESENSI, 'r') as f:
                data = f.read()
            with open(FILE_BACKUP, 'w') as f:
                f.write(data)
            print("✓ Backup file berhasil dibuat")
            return True
    except Exception as e:
        print(f"✗ Error backup: {e}")
        return False

def hapus_presensi_sd():
    """
    Hapus file presensi (gunakan dengan hati-hati!)
    """
    try:
        if 'presensi.json' in os.listdir('/sd'):
            os.remove(FILE_PRESENSI)
            print("✓ File presensi dihapus")
        return True
    except Exception as e:
        print(f"✗ Error hapus: {e}")
        return False

def lihat_isi_sd():
    """
    Tampilkan isi SD Card
    """
    print("\n" + "="*60)
    print("ISI SD CARD")
    print("="*60)
    try:
        files = os.listdir('/sd')
        print(f"Total file: {len(files)}")
        for f in files:
            try:
                stat = os.stat(f'/sd/{f}')
                size = stat[6]
                print(f"  - {f:30s} ({size:>8} bytes)")
            except:
                print(f"  - {f}")
    except Exception as e:
        print(f"Error: {e}")
    print("="*60 + "\n")

def export_csv_ke_sd(data_presensi):
    """
    Export data presensi ke format CSV
    """
    try:
        with open('/sd/presensi.csv', 'w') as f:
            # Header CSV
            f.write("Nama,Kelas,UID,Tanggal,Waktu,Timestamp\n")
            
            # Data rows
            for record in data_presensi:
                line = f"{record['nama']},{record['kelas']},{record['uid']},"
                line += f"{record['tanggal']},{record['waktu']},{record['timestamp']}\n"
                f.write(line)
        
        print("✓ File CSV berhasil dibuat: /sd/presensi.csv")
        return True
    except Exception as e:
        print(f"✗ Error export CSV: {e}")
        return False

# ============================================
# FUNGSI PRESENSI
# ============================================

def proses_presensi(uid, rtc, buzzer, sd_available):
    """
    Proses presensi dengan auto-save ke SD Card
    """
    data = DATABASE_KARTU.get(uid)
    
    if data:
        # Presensi SUKSES
        timestamp = get_timestamp_string(rtc)
        waktu = get_waktu_display(rtc)
        tanggal = get_tanggal_display(rtc)
        
        # Buat record presensi
        record = {
            "member_id": data['member_id'],
            "nama": data['nama'],
            "kelas": data['kelas'],
            "uid": uid,
            "timestamp": timestamp,
            "waktu": waktu,
            "tanggal": tanggal
        }
        
        # Print ke serial
        print(f"\n{'='*60}")
        print(f"✓ PRESENSI BERHASIL")
        print(f"{'='*60}")
        print(f"Nama      : {data['nama']}")
        print(f"Kelas     : {data['kelas']}")
        print(f"Tanggal   : {tanggal}")
        print(f"Waktu     : {waktu}")
        print(f"Timestamp : {timestamp}")
        
        # Simpan ke SD Card
        if sd_available:
            if simpan_presensi_ke_sd(record):
                bunyi_save(buzzer)  # Bunyi konfirmasi save
        else:
            print("  ⚠ SD Card tidak tersedia, data tidak tersimpan!")
        
        print(f"{'='*60}\n")
        
        bunyi_sukses(buzzer)
        return (True, data, waktu)
    else:
        # Kartu TIDAK TERDAFTAR
        print(f"\n{'='*60}")
        print(f"✗ KARTU TIDAK TERDAFTAR")
        print(f"{'='*60}")
        print(f"UID: {uid}")
        print(f"{'='*60}\n")
        
        bunyi_error(buzzer)
        return (False, None, None)

# ============================================
# PROGRAM UTAMA
# ============================================

def main():
    """Program utama"""
    print("\n" + "="*60)
    print("SISTEM PRESENSI RFID - MATERI 05")
    print("Dengan SD Card Storage")
    print("Teaching Factory SMKN 100 Malang")
    print("="*60 + "\n")
    
    # Inisialisasi hardware
    i2c = init_i2c()
    oled = init_oled(i2c) if i2c else None
    rtc = init_rtc(i2c) if i2c else None
    rfid = init_rfid()
    sd_available = init_sd_card()
    buzzer = init_buzzer()
    
    if not oled or not rfid:
        print("FATAL: OLED atau RFID error!")
        return
    
    if not rtc:
        print("WARNING: RTC tidak tersedia")
    
    # Cek data existing di SD Card
    if sd_available:
        print("\n" + "="*60)
        print("CEK DATA PRESENSI DI SD CARD")
        print("="*60)
        data_existing = load_presensi_dari_sd()
        if data_existing:
            print(f"Ditemukan {len(data_existing)} record presensi tersimpan")
            print("Data dapat diekspor ke komputer")
        else:
            print("Belum ada data presensi tersimpan")
        print("="*60 + "\n")
        
        # Lihat isi SD Card
        lihat_isi_sd()
    
    # Sistem siap
    print("="*60)
    print("SISTEM SIAP!")
    print("="*60)
    print(f"SD Card      : {'Tersedia' if sd_available else 'Tidak tersedia'}")
    print(f"Kartu terdaftar: {len(DATABASE_KARTU)}")
    print("\nTekan Ctrl+C untuk melihat data dan keluar")
    print("="*60 + "\n")
    
    tampilkan_home(oled, rtc)
    
    # Variable tracking
    last_card = None
    last_time = 0
    COOLDOWN_MS = 5000
    
    # Loop utama
    try:
        while True:
            card_id = baca_kartu_rfid(rfid)
            
            if card_id:
                current_time = time.ticks_ms()
                
                # Cek cooldown
                if card_id == last_card:
                    if time.ticks_diff(current_time, last_time) < COOLDOWN_MS:
                        time.sleep_ms(100)
                        continue
                
                last_card = card_id
                last_time = current_time
                
                # Proses presensi
                sukses, data, waktu = proses_presensi(card_id, rtc, buzzer, sd_available)
                
                if sukses:
                    tampilkan_presensi_sukses(oled, data['nama'], data['kelas'], waktu)
                else:
                    tampilkan_kartu_tidak_terdaftar(oled)
                
                time.sleep(1)
                tampilkan_home(oled, rtc)
            
            time.sleep_ms(100)
    
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("PROGRAM DIHENTIKAN")
        print("="*60 + "\n")
        
        # Tampilkan data presensi dari SD Card
        if sd_available:
            data_presensi = load_presensi_dari_sd()
            
            if data_presensi:
                print("="*60)
                print(f"TOTAL PRESENSI TERSIMPAN: {len(data_presensi)}")
                print("="*60)
                print("\nData Presensi (10 terakhir):")
                print("-" * 60)
                for record in data_presensi[-10:]:
                    print(f"{record['nama']:20s} | {record['kelas']:10s} | {record['waktu']}")
                print("-" * 60)
                
                print("\n" + "="*60)
                print("EKSPOR DATA (Format CSV)")
                print("="*60)
                print("Nama,Kelas,UID,Tanggal,Waktu,Timestamp")
                for record in data_presensi:
                    print(f"{record['nama']},{record['kelas']},{record['uid']},"
                          f"{record['tanggal']},{record['waktu']},{record['timestamp']}")
                print("="*60 + "\n")
                
                # Buat backup
                backup_presensi_ke_sd()
                
                # Export ke CSV
                export_csv_ke_sd(data_presensi)
            else:
                print("Tidak ada data presensi\n")
        
        tampilkan_teks(oled, ["Sistem", "Dihentikan"])
        if buzzer:
            buzzer.deinit()

if __name__ == "__main__":
    main()


# ============================================
# PENJELASAN & CARA PENGGUNAAN
# ============================================
"""
FITUR BARU DI MATERI 05:
1. ✓ Auto-save setiap presensi ke SD Card (format JSON)
2. ✓ Load data existing saat sistem start
3. ✓ Backup file presensi otomatis
4. ✓ Export data ke format CSV
5. ✓ Bunyi konfirmasi saat data tersimpan
6. ✓ Statistik lengkap saat program dihentikan

STRUKTUR FILE DI SD CARD:
/sd/presensi.json         → File utama data presensi (JSON array)
/sd/backup_presensi.json  → File backup (dibuat saat exit)
/sd/presensi.csv          → File CSV untuk Excel (dibuat saat exit)

FORMAT DATA JSON:
[
  {
    "member_id": 1,
    "nama": "Budi Santoso",
    "kelas": "XII TKJ",
    "uid": "a1b2c3d4",
    "timestamp": "2025-01-15T08:30:45+00:00",
    "waktu": "08:30:45",
    "tanggal": "15 Jan 2025"
  },
  ...
]

CARA TESTING:
1. Pastikan SD Card terpasang dan terformat (FAT32)
2. Upload library yang diperlukan:
   - mfrc522.py
   - ssd1306.py
   - ds3231.py
   - sdcard.py (biasanya sudah built-in)
3. Upload program ini ke ESP32
4. Tap beberapa kartu RFID untuk presensi
5. Data otomatis tersimpan ke SD Card
6. Tekan Ctrl+C untuk melihat:
   - Total presensi tersimpan
   - Daftar 10 presensi terakhir
   - Data lengkap format CSV
7. File backup dan CSV otomatis dibuat

CARA MENGAMBIL DATA DARI SD CARD:
1. Matikan ESP32
2. Cabut SD Card
3. Masukkan ke card reader komputer
4. Buka file:
   - presensi.json (data lengkap dalam format JSON)
   - presensi.csv (bisa dibuka di Excel/Spreadsheet)
5. Copy data CSV dari Serial Monitor juga bisa

CARA MENAMBAH KARTU BARU:
1. Tap kartu baru di reader
2. Catat UID yang muncul (contoh: "12345678")
3. Edit dictionary DATABASE_KARTU:
   "12345678": {"nama": "Nama Siswa", "kelas": "Kelas", "member_id": 4}
4. Upload ulang program

KEUNGGULAN SD CARD STORAGE:
✓ Data aman meski ESP32 mati
✓ Kapasitas penyimpanan besar (ribuan record)
✓ Mudah diakses untuk laporan/analisis
✓ Format JSON standar, mudah di-parse
✓ Bisa diekspor ke Excel

TIPS TROUBLESHOOTING:
- SD Card tidak terdeteksi: Cek koneksi SPI, pastikan format FAT32
- Error saat write: Cek apakah SD Card full atau write-protected
- Data hilang: Selalu buat backup sebelum hapus file
- Slow performance: Gunakan SD Card yang cepat (Class 10)

NEXT STEP (Materi 06):
- Integrasi dengan database Supabase
- Upload data ke cloud secara otomatis
- Sinkronisasi real-time
- Mode online/offline dengan fallback ke SD Card
"""