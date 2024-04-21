mqtt_server = 'x.x.x.x' #自己的MQTT服务器地址
mqtt_port = 1883 #自己的MQTT服务器端口
mqtt_user='zhangsan' #MQTT用户名
mqtt_password='pass123' #MQTT密码
mqtt_client_id='laptop-servo-client'
sub_topic = f"/{mqtt_user}/servo/data" #发送数据到指定topic
pub_topic=f"/{mqtt_user}/servo/action" #监听是否有人要请求数据访问
log_topic=f"/{mqtt_user}/servo/log" #做了哪些动作，进行下记录
fw_topic=f"/{mqtt_user}/servo/firmware"
fw_done_topic=f"/{mqtt_user}/servo/firmware_done"
loop_interval_ms=1000 #循环里面，间隔检测mqtt msg的间隔
mqtt_update_interval=60*1000  #往mqtt server发送数据的间隔，此处设置没60000ms（60s）一次
file_piece_size=704 #704是44*16块，实测，python源码704时，base64编码后大小是936字节，接近1k