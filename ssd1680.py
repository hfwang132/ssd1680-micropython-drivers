from machine import Pin
from machine import SPI
import time
from math import ceil, floor

busy = Pin(7, Pin.IN)
res = Pin(8, Pin.OUT)
cs = Pin(9, Pin.OUT)
dc = Pin(10, Pin.OUT)

class TimeoutError(Exception):
    def __init__(self, msg):
        super().__init__(msg)
        
class Color():
    BLACK = 0x00
    WHITE = 0xff
    
class Rotate():
    ROTATE_0 = 0
    ROTATE_90 = 1
    ROTATE_180 = 2
    ROTATE_270 = 3

class Screen():
    def __init__(self, width=128, height=296):
        self.width = width
        self.height = height
        self.width_bytes = ceil(width / 8)
        self.height_bytes = height
        
    def __repr__(self):
        print("screen width: %d" % self.screen.width)
        print("screen height: %d" % self.screen.height)
        print("screen width bytes: %d" % self.screen.width_bytes)
        print("screen height bytes: %d" % self.screen.height_bytes)

class Paint():
    def __init__(self, screen=Screen(), rotate=Rotate.ROTATE_90, bg_color=Color.WHITE):
        self.screen = screen
        self.img = bytearray(self.screen.width_bytes * self.screen.height_bytes)
        self.rotate = rotate
        self.bg_color = bg_color
        
        if self.rotate == Rotate.ROTATE_0 or self.rotate == Rotate.ROTATE_180:
            self.width = self.screen.width
            self.height = self.screen.height
        else:
            self.width = self.screen.height
            self.height = self.screen.width
        
    def __repr__(self):
        self.screen.__repr__()
        print("rotate: %d" % self.rotate)
        print("background color: 0x%x" % self.bg_color)
            
    def clear(self, color):
        self.bg_color = color
        for y in range(self.screen.height_bytes):
            for x in range(self.screen.width_bytes):
                addr = x + y * self.screen.width_bytes
                self.img[addr] = self.bg_color
                
    def draw_point(self, x_pos, y_pos, start_from_one=True):
        if self.rotate == Rotate.ROTATE_0:
            x = x_pos
            y = y_pos
        elif self.rotate == Rotate.ROTATE_90:
            x = self.screen.width - y_pos - 1
            y = x_pos
        elif self.rotate == Rotate.ROTATE_180:
            x = self.screen.width - x_pos - 1
            y = self.screen.height - y_pos - 1
        else:
            x = y_pos
            y = self.screen.height - x_pos - 1
        
        if start_from_one:
            x = x - 1
            y = y - 1
        
        addr = floor(x / 8) + y * self.screen.width_bytes
        raw = self.img[addr]
        
        if (self.bg_color == Color.WHITE):
            self.img[addr] = raw & ~(0x80 >> (x % 8))
        else:
            self.img[addr] = raw | (0x80 >> (x % 8))
        

class SSD1680():
    def __init__(self, spi, dc, busy, cs, res):
        super().__init__()
        self.spi = spi
        self.dc = dc
        self.busy = busy
        self.cs = cs
        self.res = res
        self.screen = Screen()
        self.paint = Paint(self.screen, rotate=Rotate.ROTATE_90, bg_color=Color.WHITE)
        
        self.dc(1)
        self.chip_sel()
        
    def chip_sel(self):
        self.cs(0)
        
    def chip_desel(self):
        self.cs(1)
        
    def read_busy(self, info="wait busy timeout!", timeout=5):
        st = time.time()
        while self.busy.value() == 1:
            if (time.time() - st) > timeout:
                raise TimeoutError(info)
        
    def hw_rst(self):
        print("hardware resetting...")
        self.res(0)
        time.sleep(0.2)
        self.res(1)
        time.sleep(0.2)
        self.read_busy("hardware reset timeout!")
        print("hardware reset successful")
        
    def sw_rst(self):
        print("software resetting...")
        self.write_cmd(0x12)
        self.read_busy("software reset timeout!")
        print("software reset successful")
        
    def write_cmd(self, cmd: bytearray):
        self.dc(0)
        self.spi.write(cmd.to_bytes(1, 'big'))
        self.dc(1)
        
    def write_data(self, data: bytearray):
        self.spi.write(data.to_bytes(1, 'big'))
        
    def init(self):
        self.hw_rst()
        self.sw_rst()
        
        # deriver output control
        self.write_cmd(0x01)
        self.write_data(0x27)
        self.write_data(0x01)
        self.write_data(0x01)
        
        # data entry mode
        self.write_cmd(0x11)
        self.write_data(0x01)
        
        # set ram-x addr start/end pos
        self.write_cmd(0x44)
        self.write_data(0x00)
        self.write_data(0x0F)
        
        # set ram-y addr start/end pos
        self.write_cmd(0x45)
        self.write_data(0x27)
        self.write_data(0x01)
        self.write_data(0x00)
        self.write_data(0x00)
        
        # border waveform
        self.write_cmd(0x3c)
        self.write_data(0x05)
        
        # display update control
        self.write_cmd(0x21)
        self.write_data(0x00)
        self.write_data(0x80)
        
        # set ram-x addr cnt to 0
        self.write_cmd(0x4e)
        self.write_data(0x00)
        # set ram-y addr cnt to 0x127
        self.write_cmd(0x4F)
        self.write_data(0x27)
        self.write_data(0x01)
        
    def update_mem(self):
        print("updating the memory...")
        self.write_cmd(0x24)
        for k in range(self.paint.screen.height_bytes * self.paint.screen.width_bytes):
            byte = self.paint.img[k]
            self.write_data(byte)
        print("updating memory successful")
        
    def update_screen(self):
        # display update control
        self.write_cmd(0x22)
        self.write_data(0xF7)
        # update
        print("updating the screen...")
        self.write_cmd(0x20)
        self.read_busy("update screen timeout!")
        print("update screen successful")
        
    def update(self):
        self.update_mem()
        self.update_screen()
        
    def clear(self, color):
        self.paint.clear(color)
        
    def draw_point(self, x_pos, y_pos):
        self.paint.draw_point(x_pos, y_pos)
        
        
if __name__ == "__main__":
    spi_ssd1680 = SPI(
            0,
            baudrate=400000,
            polarity=0,
            phase=0,
            sck=Pin(2),
            mosi=Pin(3),
            miso=Pin(4)
            )

    ssd1680 = SSD1680(
            spi_ssd1680,
            dc,
            busy,
            cs,
            res,
            )

    ssd1680.init()
    ssd1680.clear(Color.WHITE)
    ssd1680.draw_point(295, 127)
    ssd1680.update()
