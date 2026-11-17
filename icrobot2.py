from machine import Pin,SoftI2C
import esp_uart
import esp_camera2 as esp_camera
import _thread,time,gc,uos,ujson
import bluetooth,math

import esp_audio2 as esp_audio

esp32_version = 223
stm32_version = 200
lkey = Pin(0, Pin.IN, Pin.PULL_UP)
rkey = Pin(42, Pin.IN, Pin.PULL_UP)
mkey = Pin(41, Pin.IN, Pin.PULL_UP)

SERVICE_UUID = bluetooth.UUID("0000fff0-0000-1000-8000-00805f9b34fb")
RX1_UUID = bluetooth.UUID("0000fff1-0000-1000-8000-00805f9b34fb")

i2c1 = SoftI2C(scl=Pin(2), sda=Pin(1),freq=100000, timeout=255)
i2c2 = SoftI2C(scl=Pin(6), sda=Pin(5),freq=100000, timeout=255)
i2c3 = SoftI2C(scl=Pin(4), sda=Pin(3),freq=100000, timeout=255)

file_start_flag = False
file_flag = True

mode_flag = False
start = False
starttime = 0
now_channel = 0
dianji_flag = False
with open("/language.txt", "r") as f:
    language =  f.read().strip()
    lang = 'flash_' + language
#Internal function call; no modification required.
def crc(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

#Internal function call; no modification required.
def init_i2c(num):
    """Initialize the I2C bus"""
    global i2c1,i2c2,i2c3
    if num == 1:
        i2c1 = SoftI2C(scl=Pin(2), sda=Pin(1),freq=100000, timeout=255)
    if num == 2:
        i2c2 = SoftI2C(scl=Pin(6), sda=Pin(5),freq=100000, timeout=255)
    if num == 3:
        i2c3 = SoftI2C(scl=Pin(4), sda=Pin(3),freq=100000, timeout=255)

#Internal function call; no modification required.
def send_nocheck(command):
    total_len = len(command) + 4
    buffer = bytearray(total_len)
    for i in range(len(command)):
        buffer[i] = command[i]
    crc_val = crc(buffer[:len(command)])
    buffer[len(command)] = crc_val & 0xFF
    buffer[len(command)+1] = (crc_val >> 8) & 0xFF

    buffer[-2] = 0x66
    buffer[-1] = 0xbb
    esp_uart.send(buffer)

#Internal function call; no modification required.
def send_command(command):
    max_retries = 5  
    total_len = len(command) + 4
    buffer = bytearray(total_len)
    for i in range(len(command)):
        buffer[i] = command[i]
    crc_val = crc(buffer[:len(command)])
    buffer[len(command)] = crc_val & 0xFF
    buffer[len(command)+1] = (crc_val >> 8) & 0xFF

    buffer[-2] = 0x66
    buffer[-1] = 0xbb
    for attempt in range(max_retries):
        esp_uart.send(buffer)  
        start_time = time.ticks_ms()  
        while True:
            if esp_uart.reply() == 1: 
                return True  
            elif esp_uart.reply() == 0:  
                break  
            if time.ticks_diff(time.ticks_ms(), start_time) > 10:
                break 

    return False 

#Battery Management
class Power:
    def __init__(self):
        self.power = [0xaa, 0x55, 0x00,0x00,0x00]
    def shuts_down(self):
        """
        Shut down
        """
        self.power[3:] = [0x00] * 2
        self.power[3] = 0xff
        send_command(self.power) 
    def restart(self):
        """
        Restart
        """
        self.power[3:] = [0x00] * 2
        self.power[3] = 0xfe
        send_command(self.power)   
    def set_status(self,status):
        """
        Set status, no need to change
        """
        self.power[3:] = [0x00] * 2
        self.power[4] = status
        send_command(self.power)  
    def value(self):
        """
        Get the power value
        """
        return esp_uart.power()
power = Power()

#This project was not used.
class Camera:
    def __init__(self):
        self.camera_flag = False
        self.camera_num = -1
    def open(self,num):
        """
        打开摄像头
        """
        if self.camera_flag and self.camera_num == num:
            return
        if self.camera_num != -1: 
            camera.close()
        time.sleep(0.1)
        gc.collect()
        time.sleep(0.1)
        gc.collect()
        time.sleep(0.1)
        try:
            if num == 0:
                cam = esp_camera.init(0, format=esp_camera.RGB565, framesize=esp_camera.FRAME_QVGA, xclk_freq=16000000)
            elif num == 1:
                cam = esp_camera.init(0, format=esp_camera.GRAYSCALE, framesize=esp_camera.FRAME_QVGA, xclk_freq=16000000)
        except Exception as e:
            self.camera_flag = False
            self.camera_num = -1
            return False
        if cam:
            self.camera_flag = True
            self.camera_num = num
            return True
    def web_open(self):
        """
        打开摄像头
        """
        time.sleep(0.1)
        gc.collect()
        time.sleep(0.1)
        gc.collect()
        time.sleep(0.1)
        if not self.camera_flag:
            try:
                cam = esp_camera.init(0,framesize = esp_camera.FRAME_VGA)
            except Exception as e:
                self.camera_flag = False
                return "failed"
            if cam:
                print("Camera ready")
                self.camera_flag = True
                return "true"
    def close(self):
        """
        关闭摄像头
        """
        if self.camera_flag:
            time.sleep(0.1)
            gc.collect()
            time.sleep(0.1)
            esp_camera.deinit()
            time.sleep(0.5)
            gc.collect()
            self.camera_flag = False
camera = Camera()

#Audio module initialization
class Audio:
    def __init__(self):
        pass
    def init(self):
        """
        Turn on the audio
        """
        esp_audio.I2C_init()
        time.sleep_ms(20)
        esp_audio.I2S_init()
        time.sleep_ms(20)
        num = 1
        es8311 = None
        while True:
            try:
                es8311 = esp_audio.es8311_init()
                if es8311:
                    break
                else:
                    if num == 100:
                        break
                    num = num+1
                    time.sleep_ms(20)
                    continue
            except Exception as e:
                if num == 100:
                    break
                num = num+1
                time.sleep_ms(20)
                continue
        time.sleep_ms(20)
        esp_audio.music_vol_set(100)
    def audio_test(self):
        """
        Audio Test
        """
        esp_audio.audio_test()  
audio = Audio()

#Audio playback related functions
class Speaker:
    def __init__(self):
        self.music_flag = False
        self.music_start = False
    def music_play_thread(self,filename):
        """
        Music playback thread
        """
        self.music_start = True
        self.music_flag = True
        with open(filename, 'rb') as f:
            f.seek(1024)     
            while self.music_flag:
                data = f.read(1024)
                if not data:
                    break
                esp_audio.music_play(data)
                time.sleep_ms(2)
            self.music_flag = False
            self.music_start = False
    def play_music(self,filename):
        """
        Play music (non-blocking)
        """
        if self.music_flag:
            self.music_flag = False
        while self.music_start:
            pass
        gc.collect()
        _thread.start_new_thread(self.music_play_thread, 3*1024,(filename,))   
    def stop_sounds(self):
        """
        Stop all sounds
        """
        self.music_flag = False       
    def set_volume(self,vol):
        """
        Set speaker volume
        """
        vol = max(0, min(10, int(vol)))
        if vol == 0:
            esp_audio.music_vol_set(vol)
        else:
            esp_audio.music_vol_set(37+(vol-1)*7)
    def play_music_until_done(self,filename):
        """
        Play music (blocking)
        """
        if self.music_flag:
            self.music_flag = False
            time.sleep(0.1)
        self.music_flag = True
        with open(filename, 'rb') as f:
            f.seek(1024)  # 跳过 WAV 文件头部，直接读取音频数据     
            while self.music_flag:
                data = f.read(1024)
                if not data:  # 文件结束时退出
                    break
                esp_audio.music_play(data)  # 发送音频数据进行播放
                time.sleep_ms(2)
            self.music_flag = False
speaker = Speaker()

#This project was not used.
class ASR:
    def vol(self):
        vol=esp_audio.audio_vol()
        return vol   
asr = ASR()

#Motor-related functions
class Motor:
    def __init__(self):
        self.move = [0xaa, 0x55, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
    def clear_distance(self):
        """
        Clear movement distance
        """
        self.move[3:] = [0x00] * 10
        self.move[3] = 0x15
        send_command(self.move) 
    def move_stop(self):
        """
        Stop movement
        """
        self.move[3:] = [0x00] * 10
        send_command(self.move)   
    def drive(self,left_speed,right_speed):
        """
        Rotate at (left_speed, right_speed)
        """
        self.move[3:] = [0x00] * 10
        self.move[3] = 0x03
        self.move[8] = 0x03
        left_speed = max(-100, min(100, int(left_speed)))
        right_speed = max(-100, min(100, int(right_speed)))
        if left_speed < 0:
            self.move[4] = left_speed>>8
            self.move[5] = left_speed&0xff
        else:
            self.move[5] = left_speed
        if right_speed < 0:
            self.move[9] = right_speed>>8
            self.move[10] = right_speed&0xff
        else:
            self.move[10] = right_speed
        send_command(self.move)
    def leftmotor_drive(self,speed,duration=-1,distance=-1):
        """
        Drive the left motor at (speed) for (duration) or (distance)
        """
        global file_flag,file_start_flag
        self.move[3:] = [0x00] * 10
        self.move[4] = 0x01
        speed = max(-100, min(100, int(speed)))
        if speed < 0:
            self.move[5] = speed>>8
            self.move[6] = speed&0xff
        else:
            self.move[6] = speed
        if distance !=-1 and duration == -1:
            self.move[3] = 0x22
            distance = int(distance * 10)
            self.move[7] = (distance >> 8) & 0xFF
            self.move[8] = distance & 0xFF
            send_command(self.move)
            while esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break
 
                time.sleep_ms(10)
            time.sleep_ms(50)
        elif duration !=-1 and distance == -1:
            self.move[3] = 0x21
            duration = int(duration * 10)
            self.move[7] = (duration >> 8) & 0xFF
            self.move[8] = duration & 0xFF
            send_command(self.move) 
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break

 
                time.sleep_ms(10)
            time.sleep_ms(50)
        elif duration == -1 and distance == -1:
            self.move[3] = 0x23
            send_command(self.move) 
    def rightmotor_drive(self,speed,duration=-1,distance=-1):
        """
        Drive the right motor at (speed) for (duration) or (distance)
        """
        global file_flag,file_start_flag
        self.move[3:] = [0x00] * 10
        self.move[4] = 0x02
        speed = max(-100, min(100, int(speed)))
        if speed < 0:
            self.move[5] = speed>>8
            self.move[6] = speed&0xff
        else:
            self.move[6] = speed
        if distance !=-1 and duration == -1:
            self.move[3] = 0x22
            distance = int(distance * 10)
            self.move[7] = (distance >> 8) & 0xFF
            self.move[8] = distance & 0xFF
            send_command(self.move) 
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break

 
                time.sleep_ms(10)
            time.sleep_ms(50)
        elif duration !=-1 and distance == -1:
            self.move[3] = 0x21
            duration = int(duration * 10)
            self.move[7] = (duration >> 8) & 0xFF
            self.move[8] = duration & 0xFF
            send_command(self.move) 
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break

 
                time.sleep_ms(10)
            time.sleep_ms(50)
        elif duration == -1 and distance == -1:
            self.move[3] = 0x23
            send_command(self.move) 
    def move_forward(self,speed,duration=-1,distance=-1):
        """
        The robot moves forward at (speed) speed for (time) seconds
        The robot moves forward at (speed) speed for (distance) cm
        If both time and distance are None, it keeps moving forward
        """
        global file_flag,file_start_flag
        self.move[3:] = [0x00] * 10
        self.move[4]=0x02
        speed = max(-100, min(100, int(speed)))
        if speed < 0:
            self.move[5] = speed>>8
            self.move[6] = speed&0xff
        else:
            self.move[6] = speed
        if distance !=-1 and duration == -1:
            self.move[3] = 0x12
            distance = int(distance * 10)
            self.move[7] = (distance >> 8) & 0xFF
            self.move[8] = distance & 0xFF
            send_command(self.move) 
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                time.sleep_ms(1)
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break
                time.sleep_ms(1)
            time.sleep_ms(50)
        elif duration !=-1 and distance == -1:
            self.move[3] = 0x11
            duration = int(duration * 10)
            self.move[7] = (duration >> 8) & 0xFF
            self.move[8] = duration & 0xFF
            send_command(self.move) 
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                time.sleep_ms(1)
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break
 
 
                time.sleep_ms(1)
            time.sleep_ms(50)
        elif duration == -1 and distance == -1:
            self.move[3] = 0x13
            send_command(self.move) 
    def move_backward(self,speed,duration=-1,distance=-1):
        """
        The robot moves backward at (speed) speed for (time) seconds
        The robot moves backward at (speed) speed for (distance) cm
        If both time and distance are None, it keeps moving backward
        """
        global file_flag,file_start_flag
        self.move[3:] = [0x00] * 10
        self.move[4]=0x04
        speed = max(-100, min(100, int(speed)))
        if speed < 0:
            self.move[5] = speed>>8
            self.move[6] = speed&0xff
        else:
            self.move[6] = speed
        if distance !=-1 and duration == -1:
            self.move[3] = 0x12
            distance = int(distance * 10)
            self.move[7] = (distance >> 8) & 0xFF
            self.move[8] = distance & 0xFF
            send_command(self.move)
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                time.sleep_ms(1)
                pass
            
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break
                time.sleep_ms(1)
            time.sleep_ms(50)
        elif duration !=-1 and distance == -1:
            self.move[3] = 0x11
            duration = int(duration * 10)
            self.move[7] = (duration >> 8) & 0xFF
            self.move[8] = duration & 0xFF
            send_command(self.move) 
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                time.sleep_ms(1)
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break
 
    
                time.sleep_ms(1)
            time.sleep_ms(50)   
        elif duration == -1 and distance == -1:
            self.move[3] = 0x13
            send_command(self.move) 
    def turn_left(self,speed,duration=-1,distance=-1):
        """
        The robot turns left at (speed) speed for (time) seconds
        The robot turns left at (speed) speed for (distance) cm
        If both time and distance are None, it keeps turning left
        """
        global file_flag,file_start_flag
        self.move[3:] = [0x00] * 10
        self.move[4]=0x06
        speed = max(-100, min(100, int(speed)))
        if speed < 0:
            self.move[5] = speed>>8
            self.move[6] = speed&0xff
        else:
            self.move[6] = speed
        if distance !=-1 and duration == -1:
            self.move[3] = 0x12
            distance = int(distance)
            self.move[7] = (distance >> 8) & 0xFF
            self.move[8] = distance & 0xFF
            send_command(self.move)  
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                time.sleep_ms(1)
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break
                time.sleep_ms(1)
            time.sleep_ms(100)
        elif duration !=-1 and distance == -1:
            self.move[3] = 0x11
            duration = int(duration * 10)
            self.move[7] = (duration >> 8) & 0xFF
            self.move[8] = duration & 0xFF
            send_command(self.move)
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                time.sleep_ms(1)
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break
                time.sleep_ms(1)
            time.sleep_ms(100)    
        elif duration == -1 and distance == -1:
            self.move[3] = 0x13
            send_command(self.move)  
    def turn_right(self,speed,duration=-1,distance=-1):
        """
        The robot turns right at (speed) speed for (time) seconds
        The robot turns right at (speed) speed for (distance) cm
        If both time and distance are None, it keeps turning right
        """
        global file_flag,file_start_flag
        self.move[3:] = [0x00] * 10
        self.move[4]=0x08
        speed = max(-100, min(100, int(speed)))
        if speed < 0:
            self.move[5] = speed>>8
            self.move[6] = speed&0xff
        else:
            self.move[6] = speed
        if distance !=-1 and duration == -1:
            self.move[3] = 0x12
            distance = int(distance)
            self.move[7] = (distance >> 8) & 0xFF
            self.move[8] = distance & 0xFF
            send_command(self.move)
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                time.sleep_ms(1)
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break
 
 
                time.sleep_ms(1)
            time.sleep_ms(50)
        elif duration !=-1 and distance == -1:
            self.move[3] = 0x11
            duration = int(duration * 10)
            self.move[7] = (duration >> 8) & 0xFF
            self.move[8] = duration & 0xFF
            send_command(self.move)  
            while  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                time.sleep_ms(1)
                pass
            while True:
                if  esp_uart.lmotor_mode() == 0 or esp_uart.rmotor_mode() == 0:
                    break  
                time.sleep_ms(1)
            time.sleep_ms(50)   
        elif duration == -1 and distance == -1:
            self.move[3] = 0x13
            send_command(self.move)  
    def left_speed(self):
        """
        Get the speed of the left motor
        """
        return esp_uart.lmotor_speed()
    def left_moving_distance(self):
        """
        Get the distance moved by the left motor
        """
        return esp_uart.lmotor_distance()
    def right_speed(self):
        """
        Get the speed of the right motor
        """
        return esp_uart.rmotor_speed()
    def right_moving_distance(self):
        """
        Get the distance moved by the right motor
        """
        return esp_uart.rmotor_distance()
motor = Motor()

#Tail Light Control Function
class Taillight:
    def rgb(self, *args):
        """
        Set the color of the tail light

        3 parameters: Set all tail lights to the same color
        15 parameters: Set each of the 5 tail lights independently
        """
        if len(args) == 3:
            r, g, b = args
            color = [0xaa, 0x55, 0x04, r, g, b]

        elif len(args) == 15:
            color = [0xaa, 0x55, 0x04] + list(args)

        else:
            raise ValueError("rgb() requires 3 or 15 parameters")

        send_command(color)


taillight = Taillight()       

#Display control function
class Display:
    def __init__(self):
        self.brightness = 1
        self.oled = [0x00] *36
        self.num = 0
    def set_brightness(self,lum):
        """
        Set the brightness to [lum]
        """
        self.oled[:5] = [0xaa, 0x55, 0x03, 0x01, lum]
        send_command(self.oled[:5])       
    def show_image(self,image,mode):
        """
        Custom data for dot matrix display,mode set to 0
        eg.icrobot.display.show_image([0x0,0x0,0x0,0x0,0x0,0x0,0x38,0x47,0x91,0x8A,0x92,0x82,0x82,0x92,0x8A,0x91,0x47,0x38,0x0,0x0,0x0,0x0,0x0,0x0],0)
        """
        self.oled[:5] = [0xaa, 0x55, 0x03, 0x02, mode]
        self.oled[5:29] = image 
        send_command(self.oled[:29]) 
    def show_text(self,var):
        """
        Display a string on the dot matrix
        """
        var_bytes = var.encode('utf-8')
        text_len = min(len(var_bytes), 60) 
        self.oled[:6] = [0xaa, 0x55, 0x03, 0x03, 0x00, text_len]
        # 填充文本数据
        self.oled[6:6+text_len] = list(var_bytes[:text_len])
        send_command(self.oled[:6+text_len]) 
    def show_expression(self,num):
        """
        Display an expression on the dot matrix
        num: 
            0x00 Blink
            0x01 Push glasses
            0x02 Universe startup
            0x03 Progress bar
            0x04 Sad
            0x05 Angry
            0x06 Heart
            0x07 Dynamic to static anxiety
            0x08 Sleep (special tail light)

            0xB0 Happy (yellow light)
            0xB1 Calm (light green)
            0xB2 Sad (light blue)
            0xB3 Angry (red)
            0xB4 Fear (gray)
            0xB5 Love (pink)
            0xB6 Encounter obstacle (twist red tail light flashes three times)

            0xC0 AP
            0xC1 STA
            0xC2 BT
            0xC3 USB
            0xC4 BACK
            0xC5 Xiao Zhi listen
            0xC6 Xiao Zhi speak
            0xC7 Xiao Zhi standby
            0xC8 Dance (special tail light)
            0xC9 Dynamic anxiety

            0xD0 Static 1
            0xD1 Static 2
            0xD2 Static 3
            0xD3 Static 4
            0xD4 Static 5
            0xD5 Set selection
            0xD6 MOD selection
        """
        self.oled[:5] = [0xaa, 0x55, 0x03, 0x04,num]
        send_command(self.oled[:5])   
    def set_pixel(self,pos_x,pos_y):
        """
        Light up the specified dot (only)
        """
        if not (0 <= pos_x < 24 and 0 <= pos_y < 8):
            return 
        image = [0x00] * 24 
        inverted_pos_y = 7 - pos_y  # 将 Y 坐标从顶部变到底部
        image[pos_x] |= (1 << inverted_pos_y)
        self.oled[:5] = [0xaa, 0x55, 0x03, 0x02, 0x00]
        self.oled[5:29] = image
        send_command(self.oled[:29]) 
    def add_pixel(self,pos_x,pos_y):
        """
        Light up a specific dot (add)
        """
        if not (0 <= pos_x < 24 and 0 <= pos_y < 8):
            return 
        self.oled[:7] = [0xaa, 0x55, 0x03, 0x05, 1,pos_x,pos_y]
        send_command(self.oled[:7]) 
    def clear_pixel(self,pos_x,pos_y):
        """
        Light up a specific dot (delete)
        """
        if not (0 <= pos_x < 24 and 0 <= pos_y < 8):
            return 
        self.oled[:7] = [0xaa, 0x55, 0x03, 0x05, 0,pos_x,pos_y]
        send_command(self.oled[:7]) 
    def toggle_pixel(self,pos_x,pos_y):
        """
        Light up a specific dot (toggle)
        """
        if not (0 <= pos_x < 24 and 0 <= pos_y < 8):
            return 
        self.oled[:7] = [0xaa, 0x55, 0x03, 0x05, 2,pos_x,pos_y]
        send_command(self.oled[:7]) 
    def clear(self):
        """
        Clear the display
        """
        self.oled[:29] = [0xaa, 0x55, 0x03, 0x02,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00]
        send_command(self.oled[:29])
display = Display()        

#Line-following sensor related functions
class Rgb_sensor:
    def __init__(self):
        self.line_flag = False
        self.color = [0xaa, 0x55, 0x02, 0x00,0x00]
    def start_grayscale_learning(self):
        """
        Start grayscale learning
        """
        self.color[3] = 0x04
        send_command(self.color) 
    def start_color_learning(self,num):
        """
        Start color learning
        :num:  1-7: Red to Purple
        """
        self.color[3] = 0x05
        self.color[4] = num
        send_command(self.color) 
    def set_line_mode(self,mode):
        """
        Set the line-following sensor mode
        :mode: 1 : Binary  2: Grayscale 3: Color
        """
        self.color[3] = mode
        send_command(self.color) 
        time.sleep(1)
    def close(self):
        """
        Close the line-following sensor
        """
        self.color[3] = 0
        send_command(self.color)
    def read_line_value(self,num):
        """
        Read the value of the sensor (num)
        """
        time.sleep_ms(1)
        if num == 5:
            data = esp_uart.line()
        else:
            data = esp_uart.line()[num]
        return data
    def line_tracking_until(self,speed,line_data):
        """
        Auto line tracking until a condition is met
        """
        line_data = [x ^ 0x01 for x in line_data]
        self.track = [0xaa, 0x55, 0x02, 0x06,speed-1,0x01,line_data[0],line_data[1],line_data[2],line_data[3],line_data[4]]
        send_command(self.track)
        time.sleep(0.2)
        while True:
            if esp_uart.line_mode() == 0:
                break
            if file_flag == True and file_start_flag == False:
                break
            time.sleep_ms(10)
    def line_tracking(self,speed):
        """
        Auto line tracking
        """
        self.track = [0xaa, 0x55, 0x02, 0x06,speed-1,0x00,0x00,0x00,0x00,0x00,0x00]
        send_command(self.track)
    def stop_line_tracking(self):
        """
        Stop auto line tracking
        """
        self.track = [0xaa, 0x55, 0x02, 0x06,0xFF,0x00,0x00,0x00,0x00,0x00,0x00]
        send_command(self.track)
rgb_sensor = Rgb_sensor()    

#Left click function
class Leftkey:
    def value(self):
        return lkey.value()
leftkey = Leftkey()

#Right click function
class Rightkey:
    def value(self):
        return rkey.value()
rightkey = Rightkey()

#This project was not used.
class Privacy_switch:
    def value(self):
        return esp_uart.privacy_switch()
privacy_switch = Privacy_switch()

#This project was not used.
class Gripper:
    def __init__(self):
        self.read_buffer = bytearray(5)
    def open(self,port):
        """
        端口(port)机械手松开
        """
        if port == 1:
            try: 
                i2c1.writeto(0x06, b'\x01\x01\x01\x01\x01')
            except Exception as e:
                init_i2c(1)
                time.sleep(0.1) 
        elif port == 2:
            try: 
                i2c2.writeto(0x06, b'\x01\x01\x01\x01\x01')
            except Exception as e:
                init_i2c(2)
                time.sleep(0.1) 
        else:
            try: 
                i2c3.writeto(0x06, b'\x01\x01\x01\x01\x01')
            except Exception as e:
                init_i2c(3)
                time.sleep(0.1) 
        
    def close(self,port):
        """
        端口(port)机械手抓取
        """
        if port == 1:
            try: 
                i2c1.writeto(0x06, b'\x02\x02\x02\x02\x02')
            except Exception as e:
                init_i2c(1)
                time.sleep(0.1) 
        elif port == 2:
            try: 
                i2c2.writeto(0x06, b'\x02\x02\x02\x02\x02')
            except Exception as e:
                init_i2c(2)
                time.sleep(0.1)  
        else:
            try: 
                i2c3.writeto(0x06, b'\x02\x02\x02\x02\x02')
            except Exception as e:
                init_i2c(3)
                time.sleep(0.1)
    
    def open_until_done(self,port):
        """
        端口(port)机械手动作直到完成
        """
        if port == 1:
            try: 
                i2c1.writeto(0x06, b'\x01\x01\x01\x01\x01')
            except Exception as e:
                init_i2c(1)
                time.sleep(0.1) 
                return
            time.sleep_ms(100)
            while True:
                try:
                    self.read_buffer = bytearray(5) 
                    i2c1.readfrom_into(0x06, self.read_buffer)  # 复用 `bytearray`
                    if self.read_buffer[0] == 0x0b:
                        break
                    time.sleep_ms(1)
                    if file_flag == True and file_start_flag == False:
                        break
                except OSError as e:
                    break  # 发生异常直接退出
        elif port == 2:
            try: 
                i2c2.writeto(0x06, b'\x01\x01\x01\x01\x01')
            except Exception as e:
                init_i2c(2)
                time.sleep(0.1) 
                return
            time.sleep_ms(100)
            while True:
                try:
                    self.read_buffer = bytearray(5) 
                    i2c2.readfrom_into(0x06, self.read_buffer)  # 复用 `bytearray`
                    if self.read_buffer[0] == 0x0b:
                        break
                    time.sleep_ms(1)
                    if file_flag == True and file_start_flag == False:
                        break
                except OSError as e:
                    break  # 发生异常直接退出
        else:
            try: 
                i2c3.writeto(0x06, b'\x01\x01\x01\x01\x01')
            except Exception as e:
                init_i2c(3)
                time.sleep(0.1) 
                return
            time.sleep_ms(100)
            while True:
                try:
                    self.read_buffer = bytearray(5) 
                    i2c3.readfrom_into(0x06, self.read_buffer)  # 复用 `bytearray`
                    if self.read_buffer[0] == 0x0b:
                        break
                    time.sleep_ms(1)
                    if file_flag == True and file_start_flag == False:
                        break
                except OSError as e:
                    break  # 发生异常直接退出

    def close_until_done(self,port):
        """
        端口(port)机械手抓取直到完成
        """
        if port == 1:
            try: 
                i2c1.writeto(0x06, b'\x02\x02\x02\x02\x02')
            except Exception as e:
                init_i2c(1)
                time.sleep(0.1)
                return 
            time.sleep_ms(100)
            while True:
                try:
                    self.read_buffer = bytearray(5) 
                    i2c1.readfrom_into(0x06, self.read_buffer)  # 复用 `bytearray`
                    if self.read_buffer[0] == 0x0b:
                        break
                    time.sleep_ms(1)
                    if file_flag == True and file_start_flag == False:
                        break
                except OSError as e:
                    break  # 发生异常直接退出
        elif port == 2:
            try: 
                i2c2.writeto(0x06, b'\x02\x02\x02\x02\x02')
            except Exception as e:
                init_i2c(2)
                time.sleep(0.1) 
                return
            time.sleep_ms(100)
            while True:
                try:
                    self.read_buffer = bytearray(5) 
                    i2c2.readfrom_into(0x06, self.read_buffer)  # 复用 `bytearray`
                    if self.read_buffer[0] == 0x0b:
                        break
                    time.sleep_ms(1)
                    if file_flag == True and file_start_flag == False:
                        break
                except OSError as e:
                    break  # 发生异常直接退出
        else:
            try: 
                i2c3.writeto(0x06, b'\x02\x02\x02\x02\x02')
            except Exception as e:
                init_i2c(3)
                time.sleep(0.1) 
                return
            time.sleep_ms(100)
            while True:
                try:
                    self.read_buffer = bytearray(5) 
                    i2c3.readfrom_into(0x06, self.read_buffer)  # 复用 `bytearray`
                    if self.read_buffer[0] == 0x0b:
                        break
                    time.sleep_ms(1)
                    if file_flag == True and file_start_flag == False:
                        break
                except OSError as e:
                    break  # 发生异常直接退出
gripper = Gripper()

#This project was not used.
class Gun:
    def __init__(self):
        self.read_buffer = bytearray(5)
        self.send_data = bytearray(5)
        self.send_data[0] = 0x01
        self.send_data[2] = 0x01
        self.send_data[3] = 0x01
        self.send_data[4] = 0x01
    def fire(self,port,num):
        """
        端口(port)炮台发射(num)颗弹珠
        """
        if port == 1:
            try: 
                self.send_data[1] = num
                i2c1.writeto(0x0b,self.send_data)
            except Exception as e:
                init_i2c(1)
                time.sleep(0.1) 
        elif port == 2:
            try: 
                self.send_data[1] = num
                i2c2.writeto(0x0b,self.send_data)
            except Exception as e:
                init_i2c(2)
                time.sleep(0.1)  
        else:
            try: 
                self.send_data[1] = num
                i2c3.writeto(0x0b,self.send_data)
            except Exception as e:
                init_i2c(3)
                time.sleep(0.1)

    def fire_until_done(self,port,num):
        """
        端口(port)炮台发射是否完成
        """
        if port == 1:
            try: 
                self.send_data[1] = num
                i2c1.writeto(0x0b,self.send_data)
            except Exception as e:
                init_i2c(1)
                time.sleep(0.1) 
                return
            time.sleep_ms(100)
            while True:
                try:
                    self.read_buffer = bytearray(5) 
                    i2c1.readfrom_into(0x0b, self.read_buffer)  # 复用 `bytearray`
                    if self.read_buffer[0] == 0x0b or self.read_buffer[0] == 0xff:
                        break
                    if file_flag == True and file_start_flag == False:
                        break
                    time.sleep_ms(1)
                except OSError as e:
                    break  # 发生异常直接退出
        elif port == 2:
            try: 
                self.send_data[1] = num
                i2c2.writeto(0x0b,self.send_data)
            except Exception as e:
                init_i2c(2)
                time.sleep(0.1) 
                return
            time.sleep_ms(100)
            while True:
                try:
                    self.read_buffer = bytearray(5) 
                    i2c2.readfrom_into(0x0b, self.read_buffer)  # 复用 `bytearray`
                    if self.read_buffer[0] == 0x0b or self.read_buffer[0] == 0xff:
                        break
                    if file_flag == True and file_start_flag == False:
                        break
                    time.sleep_ms(1)
                except OSError as e:
                    break  # 发生异常直接退出
        else:
            try: 
                self.send_data[1] = num
                i2c3.writeto(0x0b,self.send_data)
            except Exception as e:
                init_i2c(3)
                time.sleep(0.1) 
                return
            time.sleep_ms(100)
            while True:
                try:
                    self.read_buffer = bytearray(5) 
                    i2c3.readfrom_into(0x0b, self.read_buffer)  # 复用 `bytearray`
                    if self.read_buffer[0] == 0x0b or self.read_buffer[0] == 0xff:
                        break
                    if file_flag == True and file_start_flag == False:
                        break
                    time.sleep_ms(1)
                except OSError as e:
                    break  # 发生异常直接退出
gun = Gun()

# Bluetooth central connection settings
TARGET_SERVICE_UUID = bluetooth.UUID("7e400001-b5a3-f393-e0a9-e50e24dcca9e")
TARGET_CHAR_UUID = bluetooth.UUID("7e400002-b5a3-f393-e0a9-e50e24dcca9e")
TARGET_SERVICE_UUID_BYTES = bytes((
    0x9E, 0xCA, 0xDC, 0x24, 0x0E, 0xE5, 0xA9, 0xE0,
    0x93, 0xF3, 0xA3, 0xB5, 0x01, 0x00, 0x40, 0x7E,
))


class ESP32S3_BLE:
    def __init__(self, name=None):
        self.name = name
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.config(mtu=517)
        self.ble.irq(self.ble_irq)
        self.connections = set()
        self.rx_queue = []
        self.flag = False
        self.send_flag = False
        self.conn_handle = None
        self.service_start_handle = None
        self.service_end_handle = None
        self.char_handle = None
        self.cccd_handle = None
        self.scan_devices = {}
        self.connecting = False
        self.pending_connection = None
        print("扫描目标服务设备，待连接名称:", self.name)
        self.ble.gap_scan(0, 30000, 30000)

    @staticmethod
    def _advertisement_name(adv_data):
        offset = 0
        while offset + 1 < len(adv_data):
            field_len = adv_data[offset]
            if field_len == 0 or offset + field_len + 1 > len(adv_data):
                break
            field_type = adv_data[offset + 1]
            if field_type in (0x08, 0x09):
                try:
                    return bytes(adv_data[offset + 2:offset + 1 + field_len]).decode()
                except Exception:
                    return ""
            offset += field_len + 1
        return ""

    @staticmethod
    def _advertises_target_service(adv_data):
        offset = 0
        while offset + 1 < len(adv_data):
            field_len = adv_data[offset]
            if field_len == 0 or offset + field_len + 1 > len(adv_data):
                break
            field_type = adv_data[offset + 1]
            if field_type in (0x06, 0x07):
                field_end = offset + 1 + field_len
                for uuid_offset in range(offset + 2, field_end, 16):
                    if adv_data[uuid_offset:uuid_offset + 16] == TARGET_SERVICE_UUID_BYTES:
                        return True
            offset += field_len + 1
        return False

    def _start_scan(self):
        self.conn_handle = None
        self.service_start_handle = None
        self.service_end_handle = None
        self.char_handle = None
        self.cccd_handle = None
        self.flag = False
        self.scan_devices = {}
        self.connecting = False
        self.ble.gap_scan(0, 30000, 30000)

    def connected(self):
        speaker.play_music_until_done('flash/ble_success.wav')
        self.flag = True
        print("目标服务和特征已连接")

    def disconnected(self):
        self.flag = False
        print("连接断开，重新扫描")
        speaker.play_music_until_done('flash/ble_dis.wav')
        self._start_scan()

    def process_pending_connection(self):
        if self.pending_connection is None:
            return
        addr_type, addr = self.pending_connection
        self.pending_connection = None
        try:
            self.ble.gap_scan(None)
            self.ble.gap_connect(addr_type, addr, 20000)
        except Exception as e:
            print("BLE连接启动失败:", e)
            self._start_scan()

    def ble_irq(self, event, data):
        try:
            if event == 5:  # IRQ_SCAN_RESULT
                addr_type, addr, _, rssi, adv_data = data
                addr_bytes = bytes(addr)
                device = self.scan_devices.get(addr_bytes)
                if device is None:
                    device = [addr_type, addr, "", False]
                    self.scan_devices[addr_bytes] = device
                device_name = self._advertisement_name(adv_data)
                if device_name:
                    device[2] = device_name
                if self._advertises_target_service(adv_data) and not device[3]:
                    device[3] = True
                    print("发现目标服务设备:", device[2] or "<名称待扫描响应>", addr_bytes, "RSSI:", rssi)
                if self.name and device[3] and device[2] == self.name and self.conn_handle is None and not self.connecting:
                    print("按保存的名称选择设备:", self.name)
                    self.connecting = True
                    self.pending_connection = (device[0], bytes(device[1]))
            elif event == 6:  # IRQ_SCAN_DONE
                if self.conn_handle is None and not self.connecting:
                    self._start_scan()
            elif event == 7:  # IRQ_PERIPHERAL_CONNECT
                conn_handle, _, _ = data
                self.conn_handle = conn_handle
                self.connecting = False
                self.connections.add(conn_handle)
                self.ble.gattc_discover_services(conn_handle, TARGET_SERVICE_UUID)
            elif event == 8:  # IRQ_PERIPHERAL_DISCONNECT
                conn_handle, _, _ = data
                self.connections.discard(conn_handle)
                self.disconnected()
            elif event == 9:  # IRQ_GATTC_SERVICE_RESULT
                conn_handle, start_handle, end_handle, uuid = data
                if conn_handle == self.conn_handle and uuid == TARGET_SERVICE_UUID:
                    self.service_start_handle = start_handle
                    self.service_end_handle = end_handle
                    print("目标服务句柄:", start_handle, end_handle)
            elif event == 10:  # IRQ_GATTC_SERVICE_DONE
                if self.service_start_handle is None:
                    print("设备未提供目标服务")
                    self.ble.gap_disconnect(self.conn_handle)
                else:
                    self.ble.gattc_discover_characteristics(
                        self.conn_handle,
                        self.service_start_handle,
                        self.service_end_handle,
                        TARGET_CHAR_UUID,
                    )
            elif event == 11:  # IRQ_GATTC_CHARACTERISTIC_RESULT
                conn_handle, _, value_handle, properties, uuid = data
                if conn_handle == self.conn_handle and uuid == TARGET_CHAR_UUID:
                    self.char_handle = value_handle
                    self.char_properties = properties
                    print("目标特征句柄/属性:", value_handle, hex(properties))
            elif event == 12:  # IRQ_GATTC_CHARACTERISTIC_DONE
                if self.char_handle is None:
                    print("设备未提供目标特征")
                    self.ble.gap_disconnect(self.conn_handle)
                elif self.char_properties & 0x10:
                    self.ble.gattc_discover_descriptors(
                        self.conn_handle,
                        self.char_handle + 1,
                        self.service_end_handle
                    )
                else:
                    self.connected()
            elif event == 13:  # IRQ_GATTC_DESCRIPTOR_RESULT
                conn_handle, descriptor_handle, uuid = data
                print("发现描述符:", descriptor_handle, repr(uuid))
                if conn_handle == self.conn_handle and uuid == bluetooth.UUID(0x2902):
                    self.cccd_handle = descriptor_handle
            elif event == 14:  # IRQ_GATTC_DESCRIPTOR_DONE
                if self.cccd_handle is None:
                    self.cccd_handle = self.char_handle + 1
                    print("未匹配到 0x2902，按目标固件布局尝试句柄:", self.cccd_handle)
                try:
                    self.ble.gattc_write(self.conn_handle, self.cccd_handle, b"\x01\x00", 1)
                    print("已提交通知订阅，CCCD句柄:", self.cccd_handle)
                except Exception as e:
                    print("CCCD写入失败:", e)
                    print("目标服务和特征已连接，通知功能不可用")
                    self.connected()
                else:
                    self.connected()
            elif event == 18:  # IRQ_GATTC_NOTIFY
                conn_handle, value_handle, value = data
                if conn_handle == self.conn_handle and value_handle == self.char_handle:
                    print(value)
                    if value:
                        self.rx_queue.append(value[5] if len(value) > 5 else value[0])
            elif event == 21:  # IRQ_MTU_EXCHANGED
                _, mtu = data
                self.max_payload = mtu - 3
        except Exception as e:
            print("BLE IRQ处理异常:", e)

    def send(self, data):
        if isinstance(data, int):
            data = bytes([data])
        elif isinstance(data, (list, tuple)):
            data = bytes(data)
        elif not isinstance(data, (bytes, bytearray)):
            raise TypeError("send() 仅支持 int, list/tuple[int], bytes/bytearray")

        if not self.flag or self.conn_handle is None or self.char_handle is None:
            return False
        try:
            self.ble.gattc_write(self.conn_handle, self.char_handle, data, 1)
            return True
        except Exception as e:
            print("发送失败:", e)
            return False

#Internal function call; no modification required.
class i2c_device:
    def __init__(self,i2c):
        self.i2c = i2c
        self.error = False

    # 安全读寄存器
    def read_reg(self, addr, reg_offset, length):
        try:
            data = self.i2c.readfrom_mem(addr, reg_offset, length)
            if len(data) != length:
                raise OSError("I2C read length mismatch")
            self.error = False
            return data
        except OSError as e:
            self.error = True
            return bytes([0]*length)
    # 安全写寄存器
    def write_reg(self, addr, reg_offset, data: bytes):
        try:
            self.i2c.writeto_mem(addr, reg_offset, data)
        except OSError as e:
            pass
    # 安全写
    def write_data(self,addr,buf:bytes):
        try:
            self.i2c.writeto(addr,buf)
        except OSError as e:
            pass    
    # 安全读
    def read_data(self,addr,length):
        try:
            data = self.i2c.readfrom(addr,length)
            if len(data) != length:
                raise OSError("I2C read length mismatch")
            return data
        except OSError as e:
            return bytes([0]*length)

#Fan module related functions
class Fan:
    def __init__(self):
        self.i2c = i2c_device(i2c1)
        self.addr = 0x2A
    def set_speed(self,speed):
        """
        Set fan speed(speed)
        0-100
        """
        self.i2c.write_reg(self.addr, 0x50 + 0x02, bytes([speed]))
    def set_mode(self,mode):
        """
        Set fan mode(mode)
        0: Off 1: Forward 2: Reverse
        """
        self.i2c.write_reg(self.addr, 0x50 + 0x01, bytes([mode]))
    def scan(self):
        try: 
            devices = i2c1.scan()
            if self.addr in devices:
                return True
            else:
                return False
        except Exception as e: 
            return False
fan = Fan()

#Colorful light module related functions
class RGB_LIGHT:
    def __init__(self):
        self.i2c = i2c_device(i2c1)
        self.addr = 0x24
    def set_all_colors(self,r,g,b,light=255):
        """
        Set all RGB light colors(r, g, b)
        """
        self.i2c.write_reg(self.addr, 0x0A + 0x00, bytes([light,r, g, b]))
    def set_color(self,r1,g1,b1,r2,g2,b2,r3,g3,b3,r4,g4,b4,r5,g5,b5,r6,g6,b6,r7,g7,b7):
        """
        Set individual RGB light colors(r, g, b)
        """
        self.i2c.write_reg(self.addr, 0x0A + 0x01, bytes([r1, g1, b1,r2,g2,b2,r3,g3,b3,r4,g4,b4,r5,g5,b5,r6,g6,b6,r7,g7,b7]))
    def scan(self):
        try: 
            devices = i2c1.scan()
            if self.addr in devices:
                return True
            else:
                return False
        except Exception as e: 
            return False
rgb_light = RGB_LIGHT()

#photosensitive resistor module related functions
class Photosensitive:
    def __init__(self):
        self.i2c = i2c_device(i2c1)
        self.addr = 0x20
    def value(self):
        """
        Read the value of the photosensitive resistor
        """
        return self.i2c.read_reg(self.addr, 0x0A + 0x00, 1)[0]
    def scan(self):
        try: 
            devices = i2c1.scan()
            if self.addr in devices:
                return True
            else:
                return False
        except Exception as e: 
            return False
photosensitive = Photosensitive()

#RFID module related functions
class RC522:
    def __init__(self):
        self.card = None
        pass

    def read_uid(self):
        """
        Read the UID of the RFID card
        """
        self.card = esp_uart.card()
        data = "".join(f"{b:02X}" for b in self.card[0:4])
        if data == "00000000":
            return "no card!"
        return data

    def read_block(self, block, key=[0xFF]*6):
        """
        Read data from a specific block of the RFID card
        """
        return self.card[4],self.card[5]
nfc = RC522()

#Magnetic Programming Mode Custom Action Modification
class BLEMODE_MESSAGE:
    def __init__(self):
        self.forward = [50,15] 
        self.forward3 = [50,45]
        self.backward = [50,15]
        self.left = [50,90]
        self.right = [50,90]
        self.wait = 4
        self.wait_light = [50,2] 
        self.melody = "car.wav"
        self.speaker = "im_Pixi.wav"
        self.light = [40,255,255,255,-1] # Brightness,r,g,b,time
        self.rainbow = 6
        self.fan = [1,100,3] # mode,speed,time
        self.shake = [1,2]
    def update(self, filename="/ble_message.txt"):
        """
        读取json文件更新BLE参数
        """
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = ujson.load(f)
            # 自动更新已有变量
            for key, value in data.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                else:
                    print("未知参数:", key)
            return 1
        except Exception as e:
            print("读取配置失败:", e)
            return 0
ble_mode_message = BLEMODE_MESSAGE()

#Custom Action Modification for RFID Card Reading Mode
class NFC_MESSAGE:
    def __init__(self):
        self.nfc_flag = False

        self.red = [0x01, 0x02, 0x03, 0x04]
        self.yellow = [0x05, 0x06, 0x07, 0x08]
        self.green = [0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E]
        self.blue = [0x0F, 0x10, 0x03, 0x04, 0x05, 0x06]

        self.command_map = {
            "forward":      0x01,
            "forward3":     0x02,
            "backward":     0x03,
            "left":         0x04,
            "right":        0x05,
            "wait":         0x06,
            "wait_light":   0x07,
            "melody":       0x08,
            "speaker":      0x09,
            "rainbow":      0x0A,
            "light":        0x0B,
            "fan":          0x0C,
            "shake":        0x0D,
            "happy":        0x0E,
            "sad":          0x0F,
            "crying":       0x10,
        }

    def update(self, filename="/nfc_message.txt"):
        """
        读取 JSON 文件并更新 NFC 参数
        """
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = ujson.load(f)
            if "nfc_flag" in data:
                if isinstance(data["nfc_flag"], bool):
                    self.nfc_flag = data["nfc_flag"]
                else:
                    print("nfc_flag 参数错误:", data["nfc_flag"])
            colors = {
                "red": self.red,
                "yellow": self.yellow,
                "green": self.green,
                "blue": self.blue
            }
            for color, card_list in colors.items():
                for i in range(len(card_list)):
                    key = color + str(i + 1)
                    if key not in data:
                        continue
                    name = data[key]
                    if name in self.command_map:
                        card_list[i] = self.command_map[name]
                    else:
                        print("未知指令:", name)
            return 1
        except Exception as e:
            print("读取配置失败:", e)
            return 0
nfc_message = NFC_MESSAGE()

#Custom action modification for color recognition mode
class COLOR_MESSAGE:
    def __init__(self):
        self.color_flag = False

        self.red = 0x01
        self.yellow = 0x02
        self.green = 0x03
        self.blue = 0x04

        self.command_map = {
            "forward":      0x01,
            "forward3":     0x02,
            "backward":     0x03,
            "left":         0x04,
            "right":        0x05,
            "wait":         0x06,
            "wait_light":   0x07,
            "melody":       0x08,
            "speaker":      0x09,
            "rainbow":      0x0A,
            "light":        0x0B,
            "fan":          0x0C,
            "shake":        0x0D,
            "happy":        0x0E,
            "sad":          0x0F,
            "crying":       0x10,
        }
    def update(self, filename="/color_message.txt"):
        """
        读取 JSON 文件并更新颜色指令
        """
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = ujson.load(f)
            # 更新开关
            if "color_flag" in data:
                if isinstance(data["color_flag"], bool):
                    self.color_flag = data["color_flag"]
                else:
                    print("color_flag 参数错误:", data["color_flag"])
            # 更新颜色对应指令
            color_list = [
                "red",
                "yellow",
                "green",
                "blue"
            ]
            for color in color_list:
                if color not in data:
                    continue
                command = data[color]
                if command in self.command_map:
                    setattr(
                        self,
                        color,
                        self.command_map[command]
                    )
                else:
                    print("未知指令:", command)
            return 1
        except Exception as e:
            print("读取配置失败:", e)
            return 0
color_message = COLOR_MESSAGE()

#Magnetic programming module action execution
class EXE_CODE:
    def __init__(self):
        pass
    def exe(self,data):
        """
        *Forward       		    0x01 
        *Forward x3    		    0x02 
        *Backward				0x03 
        *Left					0x04 
        *Right					0x05 
        *Wait					0x06 
        *Wait until light		0x07 
        *Play melody			0x08 
        *Speak					0x09 
        *Set color				0x0A 
        *Light on				0x0B 
        *Motor on				0x0C 
        *Shake / Dance			0x0D 
        *Happy					0x0E 
        *Sad					0x0F 
        *Cry					0x10 
        You can modify the actions of the module corresponding to the received message
        """
        if data == 0x01:
            motor.move_forward(ble_mode_message.forward[0], -1, ble_mode_message.forward[1])
        if data == 0x02:
            motor.move_forward(ble_mode_message.forward3[0], -1, ble_mode_message.forward3[1])
        if data == 0x03:
            motor.move_backward(ble_mode_message.backward[0], -1, ble_mode_message.backward[1])
        if data == 0x04:
            if ble_mode_message.left[1] == 90:
                motor.move_forward(50, -1, 1)
                motor.turn_left(ble_mode_message.left[0], -1, 90)
                motor.move_backward(50, -1, 2)
            else:
                motor.turn_left(ble_mode_message.left[0], -1, ble_mode_message.left[1])
        if data == 0x05:
            if ble_mode_message.right[1] == 90:
                motor.move_forward(50, -1, 1)
                motor.turn_right(ble_mode_message.right[0], -1, 90)
                motor.move_backward(50, -1, 2)
            else:
                motor.turn_right(ble_mode_message.right[0], -1, ble_mode_message.right[1])
        if data == 0x06:
            display.show_image([0x0,0x0,0x0,0x0,0x10,0x8,0x8,0x8,0x10,0x0,0x0,0x0,0x0,0x0,0x10,0x8,0x8,0x8,0x10,0x0,0x0,0x0,0x0,0x0],0)
            start_time = time.ticks_ms()
            start_time1 = time.ticks_ms()
            num = 0
            while time.ticks_diff(time.ticks_ms(), start_time) <= ble_mode_message.wait * 1000:
                if time.ticks_diff(time.ticks_ms(), start_time1) > 300:
                    if num == 0:
                        taillight.rgb(255,255,0)
                        num = 1
                    elif num == 1:
                        taillight.rgb(0,0,0)
                        num = 0
                    start_time1 = time.ticks_ms()
                time.sleep_ms(100)
            power.set_status(255)
        if data == 0x07:
            if not photosensitive.scan():
                speaker.play_music_until_done("/"+lang+"/"+"Sensor.wav")
            else:
                threshold = ble_mode_message.wait_light[0]
                wait_seconds = ble_mode_message.wait_light[1]
                while True:
                    lightvalue = photosensitive.value()
                    if lightvalue > threshold:
                        start_time = time.ticks_ms()
                        flag = True
                        while time.ticks_diff(time.ticks_ms(), start_time) < wait_seconds * 1000:
                            lightvalue = photosensitive.value()
                            if lightvalue <= threshold:
                                flag = False
                                break
                            time.sleep(0.1)
                        if flag:
                            break
                    time.sleep(0.1)
        if data == 0x08:
            speaker.play_music_until_done("/flash/"+ble_mode_message.melody)
        if data == 0x09:
            speaker.play_music_until_done("/"+lang+"/"+ble_mode_message.speaker)
        if data == 0x0A:
            if not rgb_light.scan():
                speaker.play_music_until_done("/"+lang+"/"+"LED.wav")
            else:
                colors = [
                    (10, 0, 10),    # 洋红
                    (0, 0, 10),      # 蓝
                    (0, 10, 10),    # 青
                    (0, 10, 0),      # 绿
                    (10, 0, 0),      # 红
                    (10, 3, 0),     # 橙
                    (10, 0, 5),    # 玫红
                    (4, 0, 10),    # 紫
                    (10, 10, 0),    # 黄
                    (10, 10, 10),  # 白
                ]

                start = time.ticks_ms()
                index = 0
                while time.ticks_diff(time.ticks_ms(), start) < ble_mode_message.rainbow * 1000:
                    # 每颗灯使用不同颜色，并随时间滚动
                    pattern = [
                        colors[(index + i * 3) % len(colors)]
                        for i in range(7)
                    ]
                    # 7颗灯分别设置颜色
                    rgb_light.set_color(
                        *[c for rgb in pattern for c in rgb]
                    )
                    # 随机切换节奏，模拟舞厅闪变
                    time.sleep_ms(90 if index % 3 == 0 else 130)
                    index += 1
                # 结束后关闭全部灯
                rgb_light.set_all_colors(0, 0, 0, 0)
        if data == 0x0B:
            if not rgb_light.scan():
                speaker.play_music_until_done("/"+lang+"/"+"LED.wav")
            else:
                rgb_light.set_all_colors(ble_mode_message.light[1],ble_mode_message.light[2],ble_mode_message.light[3],ble_mode_message.light[0])
                if ble_mode_message.light[4] != -1:
                    time.sleep(ble_mode_message.light[4])
                    rgb_light.set_all_colors(0,0,0,0)
                time.sleep(0.1)
        if data == 0x0C:
            if not fan.scan():
                speaker.play_music_until_done("/"+lang+"/"+"Propeller.wav")
            else:
                fan.set_speed(ble_mode_message.fan[1])
                fan.set_mode(ble_mode_message.fan[0])
                if ble_mode_message.fan[2] != -1:
                    time.sleep(ble_mode_message.fan[2])
                    fan.set_mode(0)
                time.sleep(0.1)
        if data == 0x0D:
            start_time = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start_time) <= ble_mode_message.shake[1] * 1000:
                motor.turn_left(100,-1,-1)
                time.sleep(0.1)
                motor.turn_right(100,-1,-1)
                time.sleep(0.2)
                motor.turn_left(100,-1,-1)
                time.sleep(0.1)
            motor.move_stop()
        if data == 0x0E:
            display.show_expression(0xB0)
            speaker.play_music_until_done("/flash/happy.wav")
            time.sleep(0.5)
            power.set_status(255)
            time.sleep(0.1)
        if data == 0x0F:
            display.show_expression(0XB3)
            speaker.play_music_until_done("/flash/sad.wav")
            time.sleep(0.5)
            power.set_status(255)
            time.sleep(0.1)
        if data == 0x10:
            display.show_expression(0XB2)
            speaker.play_music_until_done("/flash/cry.wav")
            time.sleep(0.5)
            power.set_status(255)
            time.sleep(0.1)
exe_code = EXE_CODE()