from machine import Pin,Timer,SoftI2C
import ntptime
import time,json
import machine
import network
import binascii,sys
import os,hashlib,micropython
import gc
gc.collect()
from umqtt.simple import MQTTClient
import iot_config as cfg

def now():
    tt=time.localtime(time.time() + cfg.UTC_OFFSET)
    Y=tt[0]
    m=tt[1]
    d=tt[2]
    H=tt[3]
    M=tt[4]
    S=tt[5]
    return f"{Y}-{m:02d}-{d:02d} {H:02d}:{M:02d}:{S:02d}" 

def mylog(ss):
    ss = str(ss)
    print(now() + '  ' + ss)

def conn_wifi():
    i=0
    sta = network.WLAN(network.STA_IF)
    wifi_ssid=None
    wifi_rssi=None
    sta.active(True)
    scan_res=sta.scan()
    mylog('connecting to network...')
    for wifi in scan_res:
        if wifi[0].decode() in cfg.wifi_list:
            wifi_ssid=wifi[0].decode()
            wifi_password=cfg.wifi_list[wifi_ssid]
            wifi_rssi=wifi[3]
    if not wifi_ssid: #要是没有扫描到列表里面预定义的wifi信息，就重启再继续扫描
        machine.reset()
    sta.connect(wifi_ssid, wifi_password)
    while not sta.isconnected(): #一般3.3秒左右完成wifi连接
        print(f"i={i}")
        time.sleep_ms(1000)
        i+=1
        if i > cfg.wifi_retry: #要是超过了重试次数，还没连接到wifi，就深度睡眠，等下次，再重来一把
            mylog(f"over wifi_try: {cfg.wifi_retry} times , can not connect to wifi, then give up, try to reset")
            machine.reset()
    ip_addr=sta.ifconfig()[0]
    mac_addr=binascii.hexlify(sta.config('mac'), ":").decode()    
    return {'ssid':wifi_ssid,'rssi':wifi_rssi,'mac':mac_addr,'ip': ip_addr}

def sync_ntp():
    for i in range(cfg.ntp_retry):
        print(f"try to set ntptime, in No.{i}")
        try:
            ntptime.host=cfg.ntp_server
            ntptime.settime()
            time.sleep_ms(500)
            break
        except Exception as e:
            mylog(f"can not get time from ntp,reson:{e}")

def copy_file(src,tgt): #没找到micropython的copy函数，只能造一个复制文件的轮子
    try:
        fh_src=open(src,'rb')
    except Exception as e:
        mylog(f"can not read {src} file,reason:{e}")
        return False
    try:
        fh_tgt=open(tgt,'wb')
    except Exception as e:
        mylog(f"can not write to {tgt} file,reason:{e}")
        return False
    buf=fh_src.read(cfg.file_piece_size)
    fh_tgt.write(buf)
    while len(buf)!=0:
        buf=fh_src.read(cfg.file_piece_size)
        fh_tgt.write(buf)
    fh_src.close()
    fh_tgt.close()
    return True

def calc_sha1(ss): #给定一个字符串，或者bytes，计算它的sha1
    gc.collect()
    #由于esp8266内存太小，还是得把文件拆成多个分片计算hash
    gc.collect()
    h=hashlib.sha1(b'')
    if type(ss).__name__=='FileIO': #要是一个文件句柄的话，那么分片读
        buf=ss.read(cfg.file_piece_size)
        h.update(buf)
        while len(buf)!=0:
            buf=ss.read(cfg.file_piece_size)
            h.update(buf)
        sha1=h.digest()
        return binascii.hexlify(sha1).decode()
    #下面是字符串或者bytes的情况
    if type(ss)==str: #如果是字符串，那么把它变成bytes
        bindata=ss.encode()
    else:
        bindata=ss
    #下面把这些bytes分片
    i=0
    while i<len(bindata):
        buf=bindata[i:i+cfg.file_piece_size]
        h.update(buf)
        i+=cfg.file_piece_size
    sha1=h.digest()
    return binascii.hexlify(sha1).decode()

def is_night(): #判断是否是夜晚
    tt=time.localtime(time.time() + cfg.UTC_OFFSET)
    H=tt[3]
    #mylog(f"in is_night(),H={H}")
    return H >= 22 or H <=6  #认为晚上22点后，或者早上6点前，是夜晚

