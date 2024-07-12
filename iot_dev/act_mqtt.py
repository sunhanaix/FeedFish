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
import function as f
from pwm_servo import mov
from hx711 import Scales

def act_ask_data(client,topic,msg,VERSION,wifi_info):#收到/xx/xx/ask_data时，进行对应响应
    gc.collect()
    global got_msg
    gc.collect()
    json_data=json.loads(msg)
    act=json_data.get('act')
    data={}
    if act=='query': #要是只是请求查询数据，那就返回数据
        data['ip']=wifi_info.get('ip')
        data['mac']=wifi_info.get('mac')
        data['model']=sys.platform
        data['client_id']=cfg.mqtt_client_id
        data['version']=VERSION
        data['ssid']=wifi_info.get('ssid')
        data['rssi']=wifi_info.get('rssi')
        data['uptime']=wifi_info.get('uptime')
        data['now_time']=f.now()
        w=Scales(d_out=cfg.hx711_dt,pd_sck=cfg.hx711_sck)
        weight=w.stable_weight()
        data['weight']=weight
        #micropython.mem_info(1)
        cfg_data=open('config.ini','r',encoding='utf8').read()
        data['cfg_data']=cfg_data
        pub_payload=json.dumps(data)
        f.mylog(f"act_ask_data(): got subscribe,topic={topic},msg={msg}")
        f.mylog(f"try to publish {cfg.pub_topic} by {pub_payload} ,and sleep {cfg.mqtt_update_interval}")
        client.publish(cfg.pub_topic, pub_payload.encode())
        client.publish(cfg.log_topic, f'{f.now()} action=query , pub_payload={pub_payload}'.encode()) 
    elif act=='reboot': #要是请求重启
        wait=json_data.get('wait',1) #获得等等多久重启
        f.mylog(f"act={act},wait={wait}")
        client.publish(cfg.log_topic, f'{f.now()} action=reboot received , will do'.encode()) #前面执行完舵机后，把执行信息做下记录发给服务器
        time.sleep(wait)
        machine.reset()
    elif act=='do' or act=='mov': #要是请求旋转舵机，那就操作舵机
        steps=json_data.get('steps',180) #获得旋转舵机角度后，默认180度
        wait=json_data.get('wait',2) #获得旋转舵机旋转步数后，等待几秒，默认2秒
        back_steps=json_data.get('back_steps',0) #获得旋转舵机角度后，默认0度
        f.mylog(f"act={act},steps={steps},wait={wait},back_steps={back_steps}")
        mov(steps,wait,back_steps)
        client.publish(cfg.log_topic, f'{f.now()} action={act} received , mov({steps},{wait},{back_steps})'.encode()) #前面执行完舵机后，把执行信息做下记录发给服务器
    elif act=='set_cfg': #要是请求更新config.ini文件
        cfg_data=json_data.get('cfg_data')
        if not cfg_data:
            return
        fh=open('config.ini','wb',encoding='utf8')
        fh.write(cfg_data)
        fh.close()
        f.mylog(f"cfg_data={cfg_data} was writen to config.ini")
        client.publish(cfg.log_topic, f'{f.now()} action=set_cfg , cfg_data={cfg_data}'.encode()) 
        time.sleep(1) #等1秒，把cache内容刷新到文件里面去
        machine.reset() #通过重启来刷新crontab作业

def act_fw_cmd(client,msg): #收到请求执行某个动作
    gc.collect()
    cmd=msg.get('cmd')
    f.mylog(f"try to return {cmd} to {cfg.fw_done_topic}")
    try:
        res=eval(cmd)
    except Exception as e:
        data={'code':1,'msg':f'run {cmd} failed,reason:{e}'}
        pub_payload=json.dumps(data).encode()
        f.mylog(f"try to return {cmd} to {cfg.fw_done_topic},pub_payload={pub_payload}")
        client.publish(cfg.fw_done_topic, pub_payload)
        return
    data={'code':0,'msg':'ok','res':res}
    pub_payload=json.dumps(data).encode()
    f.mylog(f"try to return {cmd} to {cfg.fw_done_topic},pub_payload={pub_payload}")
    client.publish(cfg.fw_done_topic, pub_payload)
    client.publish(cfg.log_topic, f'{f.now()} action=fw_cmd , cmd={cmd}'.encode()) 
    return    

def act_fw_get(client,msg): #收到请求某个文件时的动作
    gc.collect()
    fname=msg.get('fname')
    f.mylog(f"try to return {fname} to {cfg.fw_done_topic}")
    if not fname in os.listdir():
        data={'code':1,'msg':f'not found {fname}'}
        pub_payload=json.dumps(data).encode()
        client.publish(cfg.fw_done_topic, pub_payload)
        return
    #除了esp32情况，还要考虑esp8266的小内存情况，要把每个文件分片发送
    file_size=os.stat(fname)[6]
    if file_size % cfg.file_piece_size==0:
        piece_num=int(file_size/cfg.file_piece_size)
    else:
        piece_num=int(file_size/cfg.file_piece_size)+1
    i=0
    fh=open(fname,'rb')
    cur_size=0
    while cur_size<file_size:
        i+=1
        f.mylog(f"dealing with {fname} pieces: {i}/{piece_num}")
        buf=fh.read(cfg.file_piece_size)
        if len(buf)==0:
            break
        sha1=f.calc_sha1(buf)
        ss=binascii.b2a_base64(buf)
        ss=ss.decode()
        data={'code':0,'msg':'ok','no.':i,'num':piece_num,'data':ss,'sha1':sha1}
        pub_payload=json.dumps(data).encode()
        client.publish(cfg.fw_done_topic, pub_payload)
        cur_size+=cfg.file_piece_size
    fh.close()
    client.publish(cfg.log_topic, f'{f.now()} action=fw_get , fname={fname} file_size={file_size},piece_num={piece_num}'.encode()) 
    return

def act_fw_update(client,msg): #收到请求更新某个文件时的动作
    gc.collect()
    fname=msg.get('fname')
    new_name=f'{fname}_new'
    f.mylog(f"try to update {fname},no.{msg.get('no.')} in this appliance")
    if msg.get('no.')==1:
        fh=open(new_name,'wb')
    else:
        fh=open(new_name,'ab+')
        fh.seek(0,2) #2表示从后往前，0表示最后0字节；整体表示挪到文件末尾
    data=msg.get('data')
    data=binascii.a2b_base64(data)
    fh.write(data)
    fh.close()
    if msg.get('no.')==msg.get('num'): #要是这次收到的是最后一片文件碎片，那么覆盖原文件
        f.mylog(f"trying to copy {fname} to {fname}-org")
        f.copy_file(fname,f'{fname}-org')
        f.mylog(f"trying to copy {new_name} to {fname} ")
        f.copy_file(new_name,fname)
        tgt_sha1=f.calc_sha1(open(fname,'rb'))
        print(f"tgt_sha1={tgt_sha1},src_sha1={msg.get('sha1')}")
        if tgt_sha1==msg.get('sha1'):
            res=True
        else:
            res=False
        f.mylog(f"sha1 {fname} result res={res}")
        if res:
            data={'code':0,'msg':f'update ok'}
        else:
            data={'code':1,'msg':f'update {fname} failed, sha1 are not same'}
        pub_payload=json.dumps(data).encode()
        client.publish(cfg.fw_done_topic, pub_payload)
        client.publish(cfg.log_topic, f'{f.now()} action=fw_update , fname={fname} piece_num={msg.get("num")}'.encode()) 
        #time.sleep(1) #等1秒，再重启，确保publish消息出去成功了
        #machine.reset()
        return

def act_firmware(client,topic,msg): #收到/xx/xx/firmware时，进行响应
    gc.collect()
    #micropython.mem_info(1)
    f.mylog(f"act_firmware(): entry ok")
    try:
        msg=json.loads(msg)
    except Exception as e:
        f.mylog(f"msg={msg}, can not be decoded as JSON")
        return
    fname=msg.get('fname')
    if msg.get('act')=='get':
        act_fw_get(client,msg)
        return
    if msg.get('act')=='update':
        act_fw_update(client,msg)
        return
    if msg.get('act')=='cmd':
        act_fw_cmd(client,msg)
        return
    f.mylog(f"unknow action:{msg.get('act')} was found, will no response")
    data={'code':3,'msg':f'unknow action'}
    pub_payload=json.dumps(data).encode()
    client.publish(cfg.fw_done_topic, pub_payload)
    return

