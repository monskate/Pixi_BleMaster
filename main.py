import time,gc,ujson,esp_uart,os
from machine import Pin,Timer,unique_id

def is_firmware_present(fs_path="/", filename="icrobot_stm32.bin"):
    try:
        files = os.listdir(fs_path)
    except OSError as e:
        print(f"[ERROR] 无法访问文件系统: {e}")
        return None

    if filename in files:
        return True
    else:
        return False
esp_uart.init(45,46)
while True:
    if esp_uart.power_on() == 1:
        break
    time.sleep(0.1) 
esp_uart.send(bytearray([0xaa,0x55,0xff,0xff,0xff,0xff,0x15,0x89,0x66,0xbb]))
import icrobot2 as icrobot
import esp_camera2 as esp_camera

timeout = 10  # 设定10秒的超时时间
last_pressed_time = None  # 记录按键按下的时间
power = icrobot.mkey
file_id = None
low_power_flag = False
last_uid = None 
last_btuid = None
#This project was not used.
def battery_check(timer):
    global low_power_flag
    try:
        if esp_uart.power() == 1 and esp_uart.is_charging() == 0:
            low_power_flag = True
    except Exception as e:
        print("电量检测异常:", e)

#Middle button detection
def power_callback(pin):
    if power.value() == 0:
        icrobot.mode_flag = True
        icrobot.file_start_flag = not icrobot.file_start_flag
    if power.value() == 1:
        icrobot.mode_flag = False
def get_mac_address():
    uid = unique_id()
    mac_str = ':'.join('{:02X}'.format(b) for b in uid)  # 格式化为 MAC 地址
    return mac_str  

if __name__ == '__main__':
    #Boot device information print
    mac_info = {
        "mac": get_mac_address()
    }
    icrobot.audio.init()
    print(ujson.dumps(mac_info))
    print("hw_version:", esp_uart.hw_version())
    print("fw_version:", esp_uart.fw_version())
    print("esp32_version:", icrobot.esp32_version)
    gc.enable()
    power.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=power_callback)
    icrobot.send_nocheck(bytearray([0xaa,0x55,0xfe,0xfe,0xfe,0xfe]))

    #Startup sound
    icrobot.speaker.play_music_until_done("/flash/startup.wav")

    battery_timer = Timer(3)
    battery_timer.init(period=60000, mode=Timer.PERIODIC, callback=battery_check)

    # Set this to the saved name of the peripheral to connect to.
    ble = icrobot.ESP32S3_BLE() 

    #Update custom settings
    icrobot.ble_mode_message.update()
    icrobot.nfc_message.update()
    icrobot.color_message.update()
    time.sleep(1)
    #Turn on color recognition
    if icrobot.color_message.color_flag:
        icrobot.rgb_sensor.set_line_mode(3)
    while True:
        try:
            if not ble.flag:
                uid = icrobot.nfc.read_uid()
                if uid != "no card!" and uid != last_btuid:
                    last_btuid = uid
                    n1,n2 = icrobot.nfc.read_block(1)  
                    name = "ch{:02X}{:02X}".format(n1, n2)
                    print(name)
                    ble.name = name  
                ble.process_pending_connection()
            #Magnetic Programming Data Processing
            if ble.flag:
                if len(ble.rx_queue):
                    data = ble.rx_queue.pop(0)
                    icrobot.exe_code.exe(data)
                    ble.send(data)
            #RFID Data Processing
            if icrobot.nfc_message.nfc_flag:
                uid = icrobot.nfc.read_uid()

                if uid != "no card!" and uid != last_uid:
                    last_uid = uid

                    card1, card2 = icrobot.nfc.read_block(1)

                    if card1 is not None and card2 is not None:
                        color = int(card1)
                        number = int(card2)

                        action_config = icrobot.nfc_message.get_action(color, number)

                        if action_config:
                            print("NFC:", color, number, action_config)
                            icrobot.nfc_exe_code.exe(action_config)
            #Color Recognition Data Processing
            if icrobot.color_message.color_flag:
                color = icrobot.rgb_sensor.read_line_value(3)
                if color == 1:
                    icrobot.exe_code.exe(icrobot.color_message.red)
                if color == 3:
                    icrobot.exe_code.exe(icrobot.color_message.yellow)
                if color == 4:
                    icrobot.exe_code.exe(icrobot.color_message.green)
                if color == 6:
                    icrobot.exe_code.exe(icrobot.color_message.blue)
            time.sleep(0.1)
        except Exception as e: 
            pass


