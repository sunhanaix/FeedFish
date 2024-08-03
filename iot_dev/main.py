import function as f
gc.collect()
import act_mqtt as act
from machine import Pin,Timer,SoftI2C
import ntptime
import time,json
import machine
import network
import binascii,sys
import os,hashlib,micropython
import umqtt.simple
import gc
import iot_config as cfg
from pwm_servo import mov
from hx711 import Scales

VERSION='1.6.20240803'
if sys.platform=='esp32': #要是esp32的话，降频节能
    machine.freq(80000000)
gc.collect()

#micropython.mem_info(1)
#下面给mqtt一个socket timeout，这里设置成5秒 
class timeout_socket(umqtt.simple.socket.socket):
    def __init__(self):
        super().__init__()
        self.settimeout(10)

    def setblocking(self, flag):
        # "setblocking()" está documentado como
        # variantes de "settimeout()".
        # https://docs.micropython.org/en/latest/esp8266/library/usocket.html#usocket.socket.setblocking
        timeout = 10 if flag else 0
        self.settimeout(timeout)

class timeout_socket_module:
    def __init__(self, socket):
        self._socket = socket

    def getaddrinfo(self, server, port):
        return self._socket.getaddrinfo(server, port)

    socket = staticmethod(timeout_socket)
    #def socket(self):
    #    return timeout_socket()

umqtt.simple.socket = timeout_socket_module(umqtt.simple.socket)
MQTTClient = umqtt.simple.MQTTClient

stime=time.time()
#ESP32和ESP8266的duty cycle是从0到1023，但ESP32默认是512，ESP8266默认是0，因此这里还是显示指定duty cycle
pwm0 = machine.PWM(machine.Pin(2),freq=20,duty=512) #初始化让pin2的LED灯以20Hz频率非常快速闪烁,提示在连接wifi中
wifi_info=f.conn_wifi() #连接wifi
etime=time.time()
print(f"VERSION={VERSION}")
print(f"stime={stime},etime={etime},delta={etime-stime}")
print(f'wifi_info={wifi_info}')

pwm0.freq(10) #10Hz频率中速闪烁LED，提示设置ntp中
f.sync_ntp()  #同步ntp的时间
wifi_info['uptime']=f.now()
pwm0.freq(5) #5Hz频率慢速闪烁LED，提示发送MQTT
try:
    cfg_data=open('config.ini','r',encoding='utf8').read()
    print("cfg_data=",cfg_data,"\n")
except Exception as e:
    print("can not read config.ini file, will reset")
    machine.reset()

steps=cfg_data.split("\n")[0].split('steps=')[-1]
steps=int(steps)
try:
    mov(steps,2,0) #初始化自检下，进行旋转检测下，然后返回0度
except Exception as e:
    print(f"ERROR when POST servo moto,reason:{e}")
    machine.reset()
    
crontabs=cfg_data.split("\n")[1:]
all_crontabs=[]
for line in crontabs:
    t=line.split()
    time_slice={'minute': t[0], 'hour': t[1], 'day': t[2], 'month': t[3], 'week': t[4]}
    func=t[5]
    params=t[6:]
    all_crontabs.append({'tslice':time_slice,'func':func,'params':params})
    
def on_msg(topic, msg):
    f.mylog(f"on_msg(), got msg,topic={topic},msg={msg}")
    global client,pub_topic,pub_payload,got_msg
    f.mylog(f"on_msg(), global client,pub_topic,pub_payload,got_msg ok")
    global VERSION,wifi_info
    f.mylog(f"on_msg(), global VERSION,wifi_info")
    got_msg=True
    topic=topic.decode()
    msg=msg.decode()
    f.mylog(f"msg=msg.decode() ok,msg={msg}")
    if topic==cfg.sub_topic:
        f.mylog(f"try to act_ask_data({topic},{msg})")
        act.act_ask_data(client,topic,msg,VERSION,wifi_info)
        return
    if topic==cfg.fw_topic:
        f.mylog(f"try to act_firmware({topic},{msg})")
        act.act_firmware(client,topic,msg)
        return
    f.mylog(f"not recognized which function to act this topic={topic}")
    
def connect_and_subscribe():
    global f
    client = MQTTClient(cfg.mqtt_client_id, cfg.mqtt_server,user=cfg.mqtt_user,password=cfg.mqtt_password,port=cfg.mqtt_port)
    client.set_callback(on_msg)
    client.connect()
    client.subscribe(cfg.sub_topic)
    client.subscribe(cfg.fw_topic)
    f.mylog(f'Connected to {cfg.mqtt_server} MQTT broker')
    f.mylog(f'subscribed to {cfg.sub_topic} topic')
    f.mylog(f'subscribed to {cfg.fw_topic} topic')
    return client

def check_and_reconnect_mqtt():
    global client
    try:
        # 尝试发送一个PING请求
        client.ping()
        #f.mylog("MQTT client is connected.")
    except Exception as e:
        mylog(f"MQTT client is disconnected. Attempting to reconnect: {e}")
        client = MQTTClient(cfg.mqtt_client_id, cfg.mqtt_server,user=cfg.mqtt_user,password=cfg.mqtt_password,port=cfg.mqtt_port)
        client.set_callback(on_msg)
        client.connect()
        client.subscribe(cfg.sub_topic)
        mylog("Reconnected to MQTT server.")


got_msg=False
pub_topic = cfg.pub_topic
sub_topic=cfg.sub_topic
f.mylog(f"try to connect_and_subscribe to MQTT server:{cfg.mqtt_server}")
try:
    client=connect_and_subscribe()
except Exception as e:
    f.mylog(f"ERROR: connect_and_subscribe to MQTT server:{cfg.mqtt_server},reason:{e}")
    machine.reset()
    
gc.collect()

time_ms_counter=0 #间隔计时器，到一个间隔了，就自动publish一次相关sensor状态信息
i=0
f.mylog(f"No.{i}, free_mem={gc.mem_free()},and sleep_ms {cfg.mqtt_update_interval}")

AlarmDone={} #全局变量，记录哪些时间已经闹钟广播过了，格式为AlarmDone['02181134']=True，类似这样的标记
try:
    client.publish(cfg.log_topic, f'{f.now()} action=boot ,try to boot'.encode()) #告知ESP32已经引导
except Exception as e:
    f.mylog(f"ERROR: client.publish boot info to MQTT server:{cfg.mqtt_server},reason:{e}")
    machine.reset()
    
def check_one_cron(one_cron):
    #给定一个闹钟的配置，检查当前时间是否匹配到，返回True/False表示是否这个闹钟要播报
    global AlarmDone
    current = time.localtime(time.time() + cfg.UTC_OFFSET)
    minute = current[4]
    hour = current[3]
    day = current[2]
    month = current[1]
    week = current[6] + 1
    time_mark=f"{month:02d}{day:02d}{hour:02d}{minute:02d}"
    if time_mark in AlarmDone: #要是闹钟已经播报过了，就不再播报了
        return False
    
    #f.mylog(f"time_mark={time_mark}")
    alarm=one_cron['tslice']
    if not alarm['minute'] == '*' and not int(alarm['minute']) == minute:
        return False
    if not alarm['hour'] == '*' and not int(alarm['hour']) == hour:
        return False
    if not alarm['day'] == '*' and not int(alarm['day']) == day:
        return False
    if not alarm['month'] == '*' and not int(alarm['month']) == month:
        return False
    if not alarm['week'] == '*' and not int(alarm['week']) == week:
        return False
    if alarm['minute'] == '*' or alarm['hour'] == '*' or alarm['day'] == '*' or alarm['month'] == '*' or alarm['week'] == '*':
        return True
    return True

while True:
    try:
        new_msg=None
        #f.mylog(f"bef got_msg={got_msg}")
        got_msg=False
        client.check_msg() #无阻塞模式，需要自己sleep
        #f.mylog(f"after client.check_msg() ")
        #new_msg=client.wait_msg() #阻塞模式，强制等待
        #f.mylog(f"aft got_msg={got_msg}")        
        if got_msg:
            time_ms_counter=0 #如果检测到获得了订阅消息，就认为已经自动publish状态，那么就重新计时
        else:
            time_ms_counter+=cfg.loop_interval_ms
        if time_ms_counter>=cfg.mqtt_update_interval:
            i+=1
            check_and_reconnect_mqtt() #检查是否mqtt的连接还在，不在的话，再重新连接下
            w=None
            weight=0
            if cfg.enable_hx711:
                w=Scales(d_out=cfg.hx711_dt,pd_sck=cfg.hx711_sck)
                weight=w.stable_weight()
            wifi_info['weight']=weight
            client.publish(cfg.log_topic, f'{f.now()} action=heartbeat ,{wifi_info}'.encode()) 
            f.mylog(f"No.{i}, free_mem={gc.mem_free()},and sleep_ms {cfg.mqtt_update_interval}")
            time_ms_counter=0
        #f.mylog(f"bef loop crontabs")
        for one_cron in all_crontabs:
            #f.mylog(f"one_cron={one_cron}")
            if check_one_cron(one_cron):
                f.mylog(f"check_one_cron condition ok, now do it")
                if one_cron['func']=='mov':
                    mov(*one_cron['params'])
                    client.publish(cfg.log_topic, f'{f.now()} action=crontab , mov {one_cron['params']}'.encode()) #前面执行完舵机后，把执行信息做下记录发给服务器
                elif one_cron['func']=='reboot':
                    client.publish(cfg.log_topic, f'{f.now()} action=crontab , try to reboot'.encode()) #前面执行完舵机后，把执行信息做下记录发给服务器
                    #等一段时间再重启，一个确保publish消息出去成功了，
                    #另一个是如果很快重启，起来后，还是crontab设置的这个重启时间，又发起重启了。
                    time.sleep(40) 
                    machine.reset()
                current = time.localtime(time.time() + cfg.UTC_OFFSET)
                minute = current[4]
                hour = current[3]
                day = current[2]
                month = current[1]
                week = current[6] + 1
                time_mark=f"{month:02d}{day:02d}{hour:02d}{minute:02d}"
                f.mylog(f"AlarmDone={AlarmDone}")
                AlarmDone[time_mark]=False
    except Exception as e:
        micropython.mem_info(1)
        f.mylog(f"in big loop,try except,reason:{e}")
        #raise
        machine.reset()
    time.sleep_ms(cfg.loop_interval_ms)
