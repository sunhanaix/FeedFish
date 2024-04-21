#!/usr/bin/python3
import os,sys,re,json,random
import time,base64
import paho.mqtt.client as mqtt
import config as cfg
import glob,importlib
import threading,subprocess

#封装的MQTT类，用于MQTT消息的发布，而订阅部分，专为微信的几个订阅消息进行了定制
mylogger=cfg.logger

class pull_iot_value():  # 往mqtt发一个请求，获得一个返回信息
    ts = None
    res_value = None
    sub_topic = None
    final_res = None
    final_num = 0

    def __init__(self, payload=b'ask22', max_retry=10):
        self.mqtt_server = cfg.mqtt_server
        self.mqtt_port = cfg.mqtt_port
        self.mqtt_user = cfg.mqtt_user
        self.mqtt_password = cfg.mqtt_password
        self.mqtt_client_id = cfg.mqtt_client_id
        self.max_retry = max_retry
        self.sub_topic = cfg.sub_topic
        self.payload = payload
        self.push_pull(cfg.pub_topic, cfg.sub_topic)

    def push_pull(self, pub_topic, sub_topic):  # 往一个请求topic上发信息，再一个订阅topic上收数据
        self.connect_and_subscribe(sub_topic)
        # mylogger.info("try to loop_start")
        self.client.loop_start()
        # mylogger.info("try to publish")
        self.client.publish(pub_topic, payload=self.payload)
        # mylogger.info("try to sleep a while")
        i = 0
        stime = time.time()
        while True:
            if self.final_num > 0 and self.final_num == len(self.final_res):
                break
            i += 1
            if i > self.max_retry:
                mylogger.info(f"have tried {self.max_retry} times, but can not get the response value,will give up")
                break
            time.sleep(0.5)  # 等一会儿，确认收到了对方汇报的数据
        # mylogger.info("try to loop_stop")
        etime = time.time()
        print(f"after publish,just only pull value which consumed:{etime - stime}")
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self, client, userdata, flags, rc):
        # mylogger.info(f"got subscribe on_connect: {client=},{userdata=},{flags=},{rc=}")
        pass

    def on_message(self, client, userdata, msg):
        # mylogger.info(f"got subscribe on_message: {client=},{userdata=},{msg.topic=},{msg.payload=},{msg.timestamp=}")
        self.ts = int(time.time())
        data = json.loads(msg.payload.decode())
        self.final_res = data

    def connect_and_subscribe(self, sub_topic):
        self.client = mqtt.Client(client_id=self.mqtt_client_id)
        self.client.username_pw_set(username=self.mqtt_user, password=self.mqtt_password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.mqtt_server, self.mqtt_port,
                            600)  # 600为keepalive的时间间隔，需要先connect，后subscribe才能收到message
        self.client.subscribe(sub_topic)
        # mylogger.info(f'Connected to {self.mqtt_server} MQTT broker, subscribed to {sub_topic} topic')

def publish(topic,payload):
    mqtt_server = cfg.mqtt_server
    mqtt_port = cfg.mqtt_port
    mqtt_user = cfg.mqtt_user
    mqtt_password = cfg.mqtt_password
    mqtt_client_id = f"{cfg.mqtt_client_id}-pub"
    client = mqtt.Client(client_id=mqtt_client_id)
    client.username_pw_set(username=mqtt_user, password=mqtt_password)
    client.connect(mqtt_server, mqtt_port,
                   600)
    client.publish(topic, payload=payload)
    client.disconnect()
    print(f'publish {payload} to {topic}')
    return

class SubRespone(): #订阅某一个topic，然后一直loop等待收到消息，收到消息后，响应处理消息
    def __init__(self,broker=cfg.mqtt_server,port=cfg.mqtt_port,user=cfg.mqtt_user,passwd=cfg.mqtt_password):
        self.client_id = f"{cfg.mqtt_client_id}-sub"
        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.username_pw_set(username=user, password=passwd)
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)  # 设置自动重连间隔
        try:
            self.client.connect(broker, port, 600)  # 600为keepalive的时间间隔
            self.client.loop_start()  # 使用非阻塞的loop_start替代loop_forever
        except Exception as e:
            mylogger.error(f"MQTT连接失败: {e}")
            # 这里可以根据需要增加更复杂的重连逻辑
        mylogger.info("end loop")
    def sub_all(self): #订阅哪些主题进行配置，可以抽象类继承时，定制化
        topics=['/xx/xx']
        for topic in topics:
            mylogger.info(f"topic={topic} was subscribed")
            self.client.subscribe(topic=topic, qos=0)

    def on_connect(self,client, userdata, flags, rc):
        mylogger.info(f"Connected with result code: {rc},userdata={userdata}")
        self.sub_all()

    def on_message(self,client, userdata, msg): #收到消息后，处理消息，并响应处理消息，可以抽象类继承时，定制化
        payload=msg.payload
        mylogger.info(f"topic={msg.topic},mid={msg.mid},qos={msg.qos},ret={ret}")
        openid=ret['data']['openid']
        if msg.topic==f'/{cfg.username}/xx/xx': #要是收到订阅的消息，就处理这个消息
            return

if __name__=='__main__':
    payload=json.dumps({'act':'query'})
    pv=pull_iot_value(payload=payload)
    print(pv.final_res)