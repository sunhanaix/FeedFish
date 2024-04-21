#设置ESP32要连接wifi信息，可以设置多个，连接到哪一个算哪个
wifi_list={
    'wifi名字':'12345678',
    'wifi名字2':'passwd',
      }
#ntp_server='ntp1.aliyun.com' #使用阿里的ntp有时会10几次都连不上
ntp_server='x.x.x.x' #自己树莓派上的ntp服务，基本次就能连接成功
UTC_OFFSET = 8 * 60 * 60 #北京标准时差8小时
mqtt_server = 'x.x.x.x' #自己的MQTT服务器地址
mqtt_port = 1883 #自己的MQTT服务器端口
mqtt_user='zhangsan' #MQTT用户名
mqtt_password='pass123' #MQTT密码
mqtt_client_id='esp32-servo-client'
pub_topic = f"/{mqtt_user}/servo/data" #发送数据到指定topic
sub_topic=f"/{mqtt_user}/servo/action" #监听是否有人要请求数据访问
log_topic=f"/{mqtt_user}/servo/log" #做了哪些动作，进行下记录
fw_topic=f"/{mqtt_user}/servo/firmware"
fw_done_topic=f"/{mqtt_user}/servo/firmware_done"
loop_interval_ms=1000 #循环里面，间隔检测mqtt msg的间隔
mqtt_update_interval=60*1000  #往mqtt server发送数据的间隔，此处设置没60000ms（60s）一次
file_piece_size=704 #704是44*16块，实测，python源码704时，base64编码后大小是936字节，接近1k

moto_pin=13 #把舵机接在D13引脚上

ntp_retry=20 #最多尝试5次来获得ntp时间
wifi_retry=6 #最多尝试5次来连接wifi
