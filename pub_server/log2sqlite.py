#!/usr/local/bin/python3
import os,sys,re,json,time
import sqlite3
import MyMQTT
import config as cfg
from datetime import datetime, timedelta

mylogger=cfg.logger
# 创建或连接SQLite数据库
def init_db():
    conn = sqlite3.connect(cfg.log_db)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()
# 插入日志到数据库
def insert_log(message):
    conn = sqlite3.connect(cfg.log_db)
    cursor = conn.cursor()
    dt_now = datetime.now()
    cursor.execute('INSERT INTO logs (message,timestamp) VALUES (?,?)', (message,dt_now.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

#给定起始时间和结束时间，返回数据库中该时间范围内的日志
def fetch_logs_from_db(start_time, end_time):
    # 确保时间格式正确，这里假设时间以字符串形式提供，格式为'YYYY-MM-DD HH:MM:SS'
    try:
        datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return "Invalid date format. Please use 'YYYY-MM-DD HH:MM:SS' format."

    conn = sqlite3.connect(cfg.log_db)
    cursor = conn.cursor()
    # 查询指定时间段的日志
    cursor.execute("SELECT message, timestamp FROM logs WHERE timestamp BETWEEN ? AND ?", (start_time, end_time))
    logs = cursor.fetchall()
    conn.close()
    return logs
#获得logs表中，最后一条日志的时间和内容
def get_last_log():
    conn = sqlite3.connect(cfg.log_db)
    cursor = conn.cursor()
    cursor.execute("SELECT message, timestamp FROM logs ORDER BY timestamp DESC LIMIT 1")
    log = cursor.fetchone()
    conn.close()
    return log

class SubMsg(MyMQTT.SubRespone): #继承MyMQTT.SubRespone响应类，重写sub_all和on_message方法
    def sub_all(self): #订阅哪些主题进行配置
        topics=[cfg.log_topic]
        for topic in topics:
            mylogger.info(f"client_id={self.client_id},topic={topic} was subscribed")
            self.client.subscribe(topic=topic, qos=0)
    def on_message(self, client, userdata, msg):  # 收到消息后，处理消息，并响应处理消息
        payload = msg.payload
        mylogger.info(f"on topic={msg.topic},got msg,mid={msg.mid},qos={msg.qos}")
        if msg.topic == cfg.log_topic:  # 要是收到订阅的消息，就处理这个消息
            insert_log(payload.decode())
            return


def mqtt_listener():
    sub_msg = SubMsg()  # 在单独的线程中实例化SubRespone类
    mylogger.info(f"mqtt client_id={sub_msg.client_id}")
    try:
        while True:
            time.sleep(1)  # 确保进程不会过早退出
    except KeyboardInterrupt:
        sub_msg.client.disconnect()  # 在接收到键盘中断时断开连接

if __name__ == '__main__':
    mqtt_listener()
