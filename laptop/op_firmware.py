#!/usr/local/bin/python3
import os,sys,re,json,random
import time,base64,difflib
import argparse
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import base64,threading,hashlib
import pc_config as cfg
'''
实现一个OTA的功能
在pc上往/xx/xx/firmware发送一个请求，
  可以是{'act':'get','fname':fname}的请求，让ESP收到请求后，发fname的文件发过来；
  可以是{'act':'update','fname':to_fname,'data':bindata_base64,'sha1':sha1}，把本地的fname文件base64编码，发给ESP去
  （ESP收到后，如果校验sha1确认写成功后，会自动重启，以保障如果更新的是running的程序时，重启后让新版本生效)
'''

mqtt_attr={
        'mqtt_server':cfg.mqtt_server,
        'mqtt_port':cfg.mqtt_port,
        'mqtt_user':cfg.mqtt_user,
        'mqtt_password':cfg.mqtt_password,
        'mqtt_client_id':cfg.mqtt_client_id+'pub_tt'
    }
    
app_path = os.path.dirname(os.path.abspath(sys.argv[0]))
logname = os.path.basename(sys.argv[0]).split('.')[0] + '.log'

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def mylog(ss, log=os.path.join(app_path, logname)):
    ss = str(ss)
    print(now() + '  ' + ss)
    f = open(log, 'a+', encoding='utf8')
    f.write(now() + '  ' + ss + "\n")
    f.close()


def myerr(ss):
    mylog(ss)
    # print("按<回车>键退出")
    # a = input()
    sys.exit()

def binfile2mime(ss):
    if type(ss).__name__=='FileIO' or type(f).__name__=='BufferedReader':
        ss=ss.read()
    if type(ss)==str:
        bindata=ss.encode('utf8')
    else:
        bindata=ss
    return base64.b64encode(bindata).decode()

def calc_sha1(ss): #给定一个字符串，或者bytes，计算它的sha1
    print(f"type(ss)={type(ss)}")
    if type(ss).__name__=='FileIO' or type(ss).__name__=='BufferedReader':
        print("in file branch")
        ss=ss.read()
    if type(ss)==str:
        bindata=ss.encode('utf8')
    else:
        bindata=ss
    print(f"len={len(bindata)}")
    sha1=hashlib.sha1(bindata).hexdigest()
    return sha1

class pull_iot_value(): #往mqtt请求下载某一个文件，获得一个文件的多个分片信息
    ts=None
    res_value=None
    sub_topic=None
    final_res=[]
    final_num=0
    def __init__(self,mqtt_attr,pub_topic,sub_topic,payload=b'ask22',max_retry=10):
        self.mqtt_server=mqtt_attr.get('mqtt_server')
        self.mqtt_port=mqtt_attr.get('mqtt_port')
        self.mqtt_user=mqtt_attr.get('mqtt_user')
        self.mqtt_password=mqtt_attr.get('mqtt_password')
        self.mqtt_client_id=mqtt_attr.get('mqtt_client_id')
        self.max_retry=max_retry
        self.sub_topic=sub_topic
        self.payload=payload
        self.push_pull(pub_topic,sub_topic)

    def push_pull(self,pub_topic,sub_topic): #往一个请求topic上发信息，再一个订阅topic上收数据
        self.connect_and_subscribe(sub_topic)
        #mylog("try to loop_start")
        self.client.loop_start()
        #mylog("try to publish")
        self.client.publish(pub_topic, payload=self.payload)
        #mylog("try to sleep a while")
        i=0
        stime=time.time()
        while True:
            if self.final_num >0 and self.final_num==len(self.final_res):
                break
            i+=1
            if i>self.max_retry:
                mylog(f"have tried {self.max_retry} times, but can not get the response value,will give up")
                break
            time.sleep(0.5) #等一会儿，确认收到了对方汇报的数据
        #mylog("try to loop_stop")
        etime=time.time()
        print(f"after publish,just only pull value which consumed:{etime-stime}")
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self,client, userdata, flags, rc):
        #mylog(f"got subscribe on_connect: {client=},{userdata=},{flags=},{rc=}")
        pass

    def on_message(self,client, userdata, msg):
        #mylog(f"got subscribe on_message: {client=},{userdata=},{msg.topic=},{msg.payload=},{msg.timestamp=}")
        self.ts=int(time.time())
        data=json.loads(msg.payload.decode())
        piece_no=data.get('no.') #如果有分片号，那么就不停接收其它分片
        piece_num=data.get('num') #总共分了多少片
        if piece_no:
            print(f"if {piece_no=}")
            self.final_num=piece_num
            self.final_res.append(data)
            self.final_res.sort(key=lambda x:x['no.'])  #每次收到后，给它按从小到大排序下
        else:
            self.final_num=1
            self.final_res.append(data)
        
        #print(f"{self.res_value=}")

    def connect_and_subscribe(self,sub_topic):
        self.client = mqtt.Client(client_id=self.mqtt_client_id)
        self.client.username_pw_set(username=self.mqtt_user, password=self.mqtt_password)
        self.client.on_connect=self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.mqtt_server, self.mqtt_port, 600)  # 600为keepalive的时间间隔，需要先connect，后subscribe才能收到message
        self.client.subscribe(sub_topic)
        #mylog(f'Connected to {self.mqtt_server} MQTT broker, subscribed to {sub_topic} topic')

class push_iot_value(): #把一个文件，拆成多个分片，往mqtt上发送
    ts=None
    sub_topic=None
    final_res=None
    def __init__(self,mqtt_attr,pub_topic,sub_topic,payloads,max_retry=10):
        self.mqtt_server=mqtt_attr.get('mqtt_server')
        self.mqtt_port=mqtt_attr.get('mqtt_port')
        self.mqtt_user=mqtt_attr.get('mqtt_user')
        self.mqtt_password=mqtt_attr.get('mqtt_password')
        self.mqtt_client_id=mqtt_attr.get('mqtt_client_id')
        self.max_retry=max_retry
        self.sub_topic=sub_topic
        self.payloads=payloads
        self.push_pull(pub_topic,sub_topic)

    def push_pull(self,pub_topic,sub_topic): #往一个请求topic上发信息，在另一个订阅topic上收数据
        self.connect_and_subscribe(sub_topic)
        #mylog("try to loop_start")
        self.client.loop_start()
        #mylog("try to publish")
        for payload in self.payloads:
            mylog(f"publish {pub_topic=},{payload=}")
            self.client.publish(pub_topic, payload=payload)
            time.sleep(1) #每一个文件碎片，间隔1s，保障他们应该都是有序，逐个被esp收到，避免还要在esp上再进行碎片排序校准
        #mylog("try to sleep a while")
        i=0
        stime=time.time()
        while True:
            if self.final_res is not None:
                break
            i+=1
            if i>self.max_retry:
                mylog(f"have tried {self.max_retry} times, but can not get the response value,will give up")
                break
            time.sleep(0.5) #等一会儿，确认收到了对方汇报的数据
        #mylog("try to loop_stop")
        etime=time.time()
        print(f"after publish,just only pull value which consumed:{etime-stime}")
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self,client, userdata, flags, rc):
        #mylog(f"got subscribe on_connect: {client=},{userdata=},{flags=},{rc=}")
        pass

    def on_message(self,client, userdata, msg):
        #mylog(f"got subscribe on_message: {client=},{userdata=},{msg.topic=},{msg.payload=},{msg.timestamp=}")
        self.ts=int(time.time())
        data=json.loads(msg.payload.decode())
        self.final_res=data
        
        #print(f"{self.res_value=}")

    def connect_and_subscribe(self,sub_topic):
        self.client = mqtt.Client(client_id=self.mqtt_client_id)
        self.client.username_pw_set(username=self.mqtt_user, password=self.mqtt_password)
        self.client.on_connect=self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.mqtt_server, self.mqtt_port, 600)  # 600为keepalive的时间间隔，需要先connect，后subscribe才能收到message
        self.client.subscribe(sub_topic)
        #mylog(f'Connected to {self.mqtt_server} MQTT broker, subscribed to {sub_topic} topic')

    
def get_file_fr_esp(esp_topic,fname,to_fname=None): #给定ESP的topic信息，让它发送指定文件名的文件过来
    if not to_fname:
        to_fname=fname
    sub_topic=f"{esp_topic}/firmware_done"
    pub_topic=f"{esp_topic}/firmware"
    msg={'act':'get','fname':fname}
    payload=json.dumps(msg).encode()
    mylog(f"get_file_fr_esp(): {sub_topic=},{pub_topic=},{msg=}")
    q=pull_iot_value(mqtt_attr,pub_topic=pub_topic,sub_topic=sub_topic,payload=payload,max_retry=30)
    mylog(f"{q.sub_topic=},{q.final_res},{q.ts=}")
    mylog(f"q.final_res={json.dumps(q.final_res,indent=2,ensure_ascii=False)},")
    f=open(to_fname,'wb')
    for item in q.final_res:
        bindata=base64.b64decode(item['data'])
        sha1=calc_sha1(bindata)
        if sha1==item.get('sha1'):
            mylog(f"{sha1=} was right , will write {item['no.']=} data to file:{to_fname}")
            f.write(bindata)
        else:
            mylog(f"{sha1=} and {item.get('sha1')} was not equal , will quit")
            quit()
    f.close()
    
    
def push_file_to_esp(esp_topic,fname,to_fname=None): #给定ESP的topic信息，把一个文件上传到ESP指定地方
    if not to_fname:
        to_fname=os.path.basename(fname)
    sub_topic=f"{esp_topic}/firmware_done"
    pub_topic=f"{esp_topic}/firmware"
    mylog(f"push_file_to_esp(): {sub_topic=},{pub_topic=},{fname=},{to_fname=}")
    file_size=os.stat(fname)[6]
    if file_size % cfg.file_piece_size==0:
        piece_num=int(file_size/cfg.file_piece_size)
    else:
        piece_num=int(file_size/cfg.file_piece_size)+1
    i=0
    fh=open(fname,'rb')
    sha1=calc_sha1(fh)
    fh.seek(0)
    cur_size=0
    payloads=[]
    while cur_size<file_size:
        i+=1
        mylog(f"dealing with file pieces: {i}/{piece_num}")
        buf=fh.read(cfg.file_piece_size)
        if len(buf)==0:
            break
        ss=base64.b64encode(buf).decode()
        data={'act':'update','fname':to_fname,'no.':i,'num':piece_num,'data':ss,'sha1':sha1}
        payload=json.dumps(data).encode()
        payloads.append(payload)
        cur_size+=cfg.file_piece_size
    fh.close()    
    
    q=push_iot_value(mqtt_attr,pub_topic=pub_topic,sub_topic=sub_topic,payloads=payloads,max_retry=30*piece_num)
    mylog(f"{q.sub_topic=},{q.final_res=},{q.ts=}")
    v=q.final_res
    mylog(f"q.final_res={json.dumps(v,indent=2,ensure_ascii=False)},")
    if v['code']!=0:
        mylog(f"ERROR:can not update {fname} to ESP {to_fname},msg={v}")
        return False
    mylog(f"update {fname} to ESP {to_fname} OK")
    
def exec_cmd_on_esp(esp_topic,cmd): #给定ESP的topic信息，让它执行一个命令
    sub_topic=f"{esp_topic}/firmware_done"
    pub_topic=f"{esp_topic}/firmware"
    mylog(f"exec_cmd_on_esp(): {sub_topic=},{pub_topic=},{cmd=}")
    msg={'act':'cmd','cmd':cmd}
        
    payload=json.dumps(msg).encode()
    q=pull_iot_value(mqtt_attr,pub_topic=pub_topic,sub_topic=sub_topic,payload=payload,max_retry=30)
    mylog(f"{q.sub_topic=},{q.final_res=},{q.ts=}")
    v=q.final_res
    mylog(f"q.res_value={json.dumps(v,indent=2,ensure_ascii=False)},")
            

if __name__=='__main__':
    #op_firmware.py -a get -t /dean/servo -sf main.py -tf main_t.py //这个从ESP下载一个文件到本地
    #op_firmware.py -a push -t /dean/servo -sf main.py -tf main.py  //把本地文件上传到ESP
    stime=time.time()
    example_usage ="example1, update local main.py to remote ESP32's main.py:\n\top_firmware.py -a push -t /dean/servo -sf main.py -tf main.py\n\n"
    example_usage += "example2, get remote ESP32's main.py to local main_t.py:\n\top_firmware.py -a get -t /dean/servo -sf main.py -tf main_t.py\n"
    parser = argparse.ArgumentParser(
        description='Manage IoT device operations',
        epilog=example_usage,
        formatter_class=argparse.RawTextHelpFormatter  #不加这个，epilog的换行会失效
    )
    parser.add_argument('-t', "--topic", help="which iot topic should be selected")
    #parser.add_argument('-l', "--list", help="list current files/dirs in ESP")
    parser.add_argument('-a', "--action", help="get/push/cmd")
    parser.add_argument('-sf', "--source_file", help="source file to be deal")
    parser.add_argument('-tf', "--target_file", help="target file to be deal")
    args = parser.parse_args()
    if not (args.topic):
        parser.error('No topic specified, add --topic /x/x/x or -t /x/x/x')
    if not (args.action):
        parser.error('No action specified, add --action get/push/cmd or -a get/push/cmd')
    if args.action=='get':
        if not (args.source_file):
            parser.error('No source_file specified, add --source_file xxx or -sf xxx')
        
        if not (args.target_file):
            to_name=args.source_file
        else:
            to_name=args.target_file
        print(f"try to get {args.source_file} to {to_name}")
        get_file_fr_esp(args.topic,args.source_file,to_name)
    
    elif args.action=='push':
        if not (args.source_file):
            parser.error('No source_file specified, add --source_file xxx or -sf xxx')
        print(f"try to push {args.source_file}")
        if not (args.target_file):
            to_name=args.source_file
        else:
            to_name=args.target_file
        print(f"try to get {args.source_file} to {to_name}")
        push_file_to_esp(args.topic,args.source_file,to_name)
    elif args.action=='cmd':
        if not (args.source_file):
            parser.error('No source_file name specified which only be as cmd name here, add --source_file xxx or -sf xxx')
        exec_cmd_on_esp(args.topic,args.source_file)
    etime=time.time()
    mylog(f"consumed {etime-stime} seconds")

