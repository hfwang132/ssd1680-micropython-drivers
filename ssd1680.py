import time
from machine import Pin
from machine import SPI
from math import ceil, sqrt
from fonts import asc2_0806

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
    
    def _convert_coor(self, x_pos, y_pos, start_from_one=True):
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
            
        return x, y
    
    def draw_point(self, x_pos, y_pos, start_from_one=True):
        x, y = self._convert_coor(x_pos, y_pos)
        if x > self.screen.width or y > self.screen.height or x < 0 or y < 0:
            return
        
        addr = x // 8 + y * self.screen.width_bytes
        raw = self.img[addr]
        
        if (self.bg_color == Color.WHITE):
            self.img[addr] = raw & ~(0x80 >> (x % 8))
        else:
            self.img[addr] = raw | (0x80 >> (x % 8))
            
    def draw_line(self, x_start, y_start, x_end, y_end):
        dx = x_end - x_start
        dy = y_end - y_start
        points = []
        if abs(dx) > abs(dy):
            x_inc = (dx > 0) - (dx < 0)
            x_offset = 0
            for _ in range(abs(dx) + 1):
                x_tmp = x_start + x_offset
                y_tmp = y_start + round(dy / dx * x_offset)
                points.append((x_tmp, y_tmp))
                x_offset = x_offset + x_inc
        else:
            y_inc = (dy > 0) - (dy < 0)
            y_offset = 0
            for _ in range(abs(dy) + 1):
                y_tmp = y_start + y_offset
                x_tmp = x_start + round(dx / dy * y_offset)
                points.append((x_tmp, y_tmp))
                y_offset = y_offset + y_inc
                
        for point in points:
            self.draw_point(point[0], point[1])
            
    def draw_rectangle(self, x_start, y_start, x_end, y_end):
        self.draw_line(x_start, y_start, x_start, y_end)
        self.draw_line(x_start, y_start, x_end, y_start)
        self.draw_line(x_start, y_end, x_end, y_end)
        self.draw_line(x_end, y_start, x_end, y_end)

    def draw_circle(self, x_center, y_center, radius):
        points = []
        for x in range(x_center - radius, x_center + radius):
            y = y_center + round(sqrt(radius ** 2 - (x - x_center) ** 2))
            points.append((x, y))
            y = y_center - round(sqrt(radius ** 2 - (x - x_center) ** 2))
            points.append((x, y))
        for y in range(y_center - radius, y_center + radius):
            x = x_center + round(sqrt(radius ** 2 - (y - y_center) ** 2))
            points.append((x, y))
            x = x_center - round(sqrt(radius ** 2 - (y - y_center) ** 2))
            points.append((x, y))
        
        for point in points:
            self.draw_point(point[0], point[1])
            
    def show_char(self, char, x_start, y_start, font=asc2_0806, font_size=(6, 8), multiplier=1):
        tmp = 0x00
        char_idx = ord(char) - 32
        if multiplier == 1:
            for x_offset in range(font_size[0]):
                tmp = font[char_idx][x_offset]
                for y_offset in range(font_size[1]):
                    if tmp & 0x01:
                        self.draw_point(x_start + x_offset, y_start + y_offset)
                    tmp = tmp >> 1
        else:
            for x_offset in range(font_size[0] * multiplier):
                tmp = font[char_idx][x_offset // multiplier]
                for y_offset in range(font_size[1] * multiplier):
                    if tmp & 0x01:
                        self.draw_point(x_start + x_offset, y_start + y_offset)
                    if y_offset % multiplier == multiplier - 1:
                        tmp = tmp >> 1
                
    def show_string(self, string, x_start, y_start, font=asc2_0806, font_size=(6, 8), multiplier=1):
        for idx, char in enumerate(string):
            self.show_char(char, x_start + idx * font_size[0] * multiplier, y_start, font, font_size, multiplier)
            
    def show_bitmap(self, bitmap, x_start, y_start, multiplier=1):
        if multiplier == 1:
            for r, row in enumerate(bitmap):
                for c, col in enumerate(row):
                    if col == 1:
                        self.draw_point(x_start + c, y_start + r)
        else:
            for r in range(len(bitmap) * multiplier):
                for c in range(len(bitmap[0] * multiplier)):
                    if bitmap[r//multiplier][c//multiplier] == 1:
                        self.draw_point(x_start + c, y_start + r)
    
    def show_img(self, img_path, x_start, y_start):
        raise NotImplementedError


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
        
    def clear(self, *args, **kwargs):
        self.paint.clear(*args, **kwargs)
        
    def draw_point(self, *args, **kwargs):
        self.paint.draw_point(*args, **kwargs)
        
    def draw_line(self, *args, **kwargs):
        self.paint.draw_line(*args, **kwargs)
    
    def draw_rectangle(self, *args, **kwargs):
        self.paint.draw_rectangle(*args, **kwargs)
        
    def draw_circle(self, *args, **kwargs):
        self.paint.draw_circle(*args, **kwargs)
        
    def show_char(self, *args, **kwargs):
        self.paint.show_char(*args, **kwargs)
        
    def show_string(self, *args, **kwargs):
        self.paint.show_string(*args, **kwargs)
    
    def show_bitmap(self, *args, **kwargs):
        self.paint.show_bitmap(*args, **kwargs)
        
    def show_img(self, *args, **kwargs):
        self.paint.show_img(*args, **kwargs)
    

if __name__ == "__main__": # test
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
    ssd1680.draw_line(40, 20, 110, 20)
    ssd1680.draw_line(250, 100, 110, 20)
    ssd1680.draw_rectangle(18, 18, 28, 28)
    ssd1680.draw_rectangle(18, 38, 94, 48)
    ssd1680.draw_circle(60, 20, 10)
    ssd1680.draw_circle(90, 20, 10)
    ssd1680.show_char('h', 20, 20)
    ssd1680.show_string("hello world!", 20, 40)
    ssd1680.show_string("hello world!", 20, 60, multiplier=2)
    ssd1680.show_string("hello world!", 20, 90, multiplier=3)
    ssd1680.show_string("Godfly 1.9.2023", 200, 45)
    ssd1680.show_bitmap(
            [
                [0,0,1,0,0],
                [0,0,1,0,0],
                [1,1,0,1,1],
                [0,0,1,0,0],
                [0,0,1,0,0]
            ],
            240,
            10,
            multiplier=3
        )
    ssd1680.show_bitmap(
            [
                [0,0,1,0,0,0,1,0,0],
                [0,1,0,1,0,1,0,1,0],
                [1,0,0,0,1,0,0,0,1],
                [0,1,0,0,0,0,0,1,0],
                [0,0,1,0,0,0,1,0,0],
                [0,0,0,1,0,1,0,0,0],
                [0,0,0,0,1,0,0,0,0]
            ],
            260,
            80,
            multiplier=4
        )
    ssd1680.update()
