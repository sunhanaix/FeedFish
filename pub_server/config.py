import os,sys,re,json,logging
##自己的MQTT Server信息
mqtt_server = 'x.x.x.x' #自己的MQTT服务器地址
mqtt_port = 1883 #自己的MQTT服务器端口
mqtt_user='zhangsan' #MQTT用户名
mqtt_password='pass123' #MQTT密码
mqtt_client_id='pub-server-mqtt_client'
pub_topic=f"/{mqtt_user}/servo/action" #用这个向ESP32请求数据访问
sub_topic = f"/{mqtt_user}/servo/data" #监听数据topic
log_topic=f"/{mqtt_user}/servo/log" #监听log topic
fw_topic=f"/{mqtt_user}/servo/firmware"
fw_done_topic=f"/{mqtt_user}/servo/firmware_done"
##巴法云的信息
bemfa_broker = 'bemfa.com' #MQTT服务器地址
bemfa_port = 9501
bemfa_username='' #MQTT用户名
bemfa_password='' #MQTT密码
bemfa_heartbeat=30  #与公网server互相轮询的间隔秒数，公网处如果超过此时间没有收到这个心跳，则认为client离线了
bemfa_topics=['FeedFish001',] #这个要提前在巴法云上创建一个MQTT设备云，001表示设备是个插座，FeedFish这个弄成全局唯一就是，然后创建这个设备时，昵称为“喂鱼器”，这个是接入小爱时，喊的名称
bemfa_id='52dab87befc5409e91ac76f912345678'
enable_bemfa=True #是否开启巴法云支持

#给到html页面里面一次舵机动作的默认值
steps=180 #舵机正转转动的度数
wait=2 #舵机正转后等待的秒数
back_steps=0 #舵机反转转动的度数

loop_interval_ms=1000 #循环里面，间隔检测mqtt msg的间隔
mqtt_update_interval=60*1000  #往mqtt server发送数据的间隔，此处设置没60000ms（60s）一次
file_piece_size=704 #704是44*16块，实测，python源码704时，base64编码后大小是936字节，接近1k

db_file='./user.db.py' #web页面登录校验用户密码的数据库文件名
db_default_user='zhangsan' #设置数据库默认用户名
db_default_passwd='pass123' #设置数据库默认用户名对应密码
log_db='servo_log.db.py' #日志数据库文件名
exp_days = 90  # 设置cookie过期时间
home_url = 'http://localhost:45017'  #设置将来对外提供访问的URL地址
web_port=45017
#以下部分可以不用修改
#当前程序运行的绝对路径
app_path = os.path.dirname(os.path.abspath(sys.argv[0]))
#程序输出的log名字，这里用了"程序名.log"的格式
log_file = os.path.basename(sys.argv[0]).split('.')[0] + '.log'
log_file=os.path.join(app_path,log_file)
#定log输出格式，配置同时输出到标准输出与log文件
logger = logging.getLogger('mylogger')
logger.setLevel(logging.DEBUG)
log_format= logging.Formatter(
    '%(asctime)s - %(name)s - %(filename)s- %(levelname)s - %(message)s')
log_fh = logging.FileHandler(log_file)
log_fh.setLevel(logging.DEBUG)
log_fh.setFormatter(log_format)
log_ch = logging.StreamHandler()
log_ch.setLevel(logging.DEBUG)
log_ch.setFormatter(log_format)
logger.addHandler(log_fh)
logger.addHandler(log_ch)
