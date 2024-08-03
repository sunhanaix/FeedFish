from machine import PWM,Pin
import time
import iot_config as cfg
pwm= PWM(Pin(cfg.moto_pin, Pin.OUT),freq=50)

'''
MG995舵机的中点位置是1500微秒（usec），
脉冲宽度范围是500到2500微秒，死区宽度是8微秒。
舵机的控制信号通常遵循以下规律：
当脉冲宽度小于中点位置时，舵机向一个方向转动。
当脉冲宽度大于中点位置时，舵机向相反方向转动。
当脉冲宽度等于中点位置时，舵机停止转动。
因此由脉冲宽度范围是500到2500微秒可知，
  当设置pwm.duty_ns(2500*1000)时，舵机反转速度最大
  当设置pwm.duty_ns(500*1000)时，舵机正转速度最大
'''

def rotate_servo(steps, direction='clockwise',rotation_speed=1000):
    pwm= PWM(Pin(cfg.moto_pin, Pin.OUT))  # 使用GPIO13
    pwm.freq(50)
    pwm.duty_ns(0)  # 发送停止信号
    time.sleep(0.5)  # 等待舵机反应
    if steps >0 and direction == 'clockwise':
        pulse_width = 1000  # 顺时针转动的脉冲宽度
    elif steps <0 and direction == 'clockwise':
        pulse_width = 2000  # 逆时针转动的脉冲宽度
    elif steps <0  :
        pulse_width = 1000  # 顺时针转动的脉冲宽度
    else:
        pulse_width = 2000  # 逆时针转动的脉冲宽度
    # 计算需要转动的时间
    time_needed = abs(steps) / rotation_speed  # 计算转动指定角度所需的时间（秒）
    print(f"in rotate_servo(),{steps=},{rotation_speed=},{time_needed=}")
    pwm.duty_ns(pulse_width * 1000)  # 设置脉冲宽度
    time.sleep(time_needed)  # 等待足够的转动时间
    pwm.duty_ns(0)  # 发送停止信号
    time.sleep(0.5)  # 等待舵机反应
    # 清理，停止PWM
    pwm.deinit()
    
def mov_old(steps,wait,back_steps):
    #正转steps度，等wait秒，再反转back_steps度
    steps=int(steps)
    wait=int(wait)
    back_steps=int(back_steps)
    rotate_servo(steps, direction='clockwise') #正转steps度，只是大致数值
    time.sleep(wait)
    rotate_servo(back_steps, direction='reverse') #反转back_steps度
    

def set_angle(angle):
    #0.5ms--0度
    #1.0ms--45度
    #1.5ms--90度
    #2.0ms--135度
    #2.5ms--180度
    if angle <0 or angle >180:
        return
    time.sleep(0.5)  # 等待舵机反应
    #把角度(0-180度的角度）映射到ms范围
    ns=int(angle/(180/(2500000-500000))+500000)
    print(f"{ns=}")
    pwm.duty_ns(ns)
    time.sleep(0.5) # 等待舵机反应    

def mov(angle1,wait,angle2):
    #正转到angle1度，等wait秒，再转到angle1度
    angle1=int(angle1)
    wait=int(wait)
    angle2=int(angle2)
    set_angle(angle1) #正转到angle1度
    time.sleep(wait)
    set_angle(angle2) #正转到angle2度