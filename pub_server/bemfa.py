#!/usr/local/bin/python3
import os,sys,re,json,random,time
import paho.mqtt.client as mqtt
import config as cfg
import MyMQTT
#本程序监听巴法云上的订阅消息，然后根据消息内容，执行相应的操作（发mqtt消息，给ESP32，让它喂鱼）

mylogger=cfg.logger

class SubMsg(): #订阅者模式，初始化订阅哪些topic，然后一直loop等待收到消息巴法云的消息
    def __init__(self,broker=cfg.bemfa_broker,port=cfg.bemfa_port,user=cfg.bemfa_username,passwd=cfg.bemfa_password):
        #client_id = f'mqtt-subscriber-{random.randint(0, 1000)}'
        self.client_id = cfg.bemfa_id
        self.keepalive_time=cfg.bemfa_heartbeat # 设置keepalive的时间间隔
        self.broker=broker
        self.port=port
        self.client = mqtt.Client(client_id=self.client_id,clean_session=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect=self.on_disconnect
        self.client.on_message = self.on_message
        self.client.username_pw_set(username=user, password=passwd)
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)  # 设置自动重连间隔
        try:
            self.client.connect(self.broker, self.port, self.keepalive_time)  
            self.client.loop_start()  # 使用非阻塞的loop_start替代loop_forever
        except Exception as e:
            mylogger.error(f"MQTT连接失败: {e}")
            # 这里可以根据需要增加更复杂的重连逻辑

    def sub_all(self): #从配置文件config.py中，读取topic主题，并订阅它
        for topic in cfg.bemfa_topics:
            mylogger.info(f"client_id={self.client_id},topic={topic} was subscribed")
            self.client.subscribe(topic=f'{topic}', qos=0)

    def on_connect(self,client, userdata, flags, rc):
        mylogger.info(f"SubMsg Connected with result code: {rc},client_id={self.client_id}")
        self.sub_all()  # 确保重连后重新订阅
    
    def on_disconnect(self,client, userdata, flags, rc):
        #检测到Subscriber异常断开连接了，那么就断开连接，重新连接，重新订阅，重新发起loop循环
        mylogger.error(f"SubMsg Disconnected with result code: {rc},client_id={self.client_id}")
        self.client.disconnect()
        self.client.connect(self.broker, self.port, self.keepalive_time)  
        self.sub_all()
        self.client.loop_forever()
        
    def on_message(self,client, userdata, msg):
        mylogger.info(f"on topic={msg.topic},got msg,mid={msg.mid},qos={msg.qos}")
        topic=msg.topic
        payload=msg.payload.decode()
        if topic=='FeedFish001':
            payload=json.dumps({'act':'do','steps':cfg.steps,'wait':cfg.wait,'back_steps':cfg.back_steps})
            MyMQTT.publish(cfg.pub_topic, payload)
            return

def bemfa_listener():
    sub_msg = SubMsg()  # 在单独的线程中实例化SubRespone类
    mylogger.info(f"bemfa client_id={sub_msg.client_id}")
    try:
        while True:
            time.sleep(1)  # 确保进程不会过早退出
    except KeyboardInterrupt:
        sub_msg.client.disconnect()  # 在接收到键盘中断时断开连接

if __name__=='__main__':

    mylogger.info("启动巴法云mqtt通讯服务")
    bemfa_listener
