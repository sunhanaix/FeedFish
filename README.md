## Overview
This project is based on ESP32 as the main control and MG995 as the servo, creating an outdoor automatic feeding device for fish.  
You can use voice control to feed through Xiao Ai;  
You can view status, log, feed operations, and schedule settings through a web page;  
You can perform corresponding operations (such as feeding or restarting yourself)   according to the scheduled schedule based on the timing settings;  
 [Operation video](https://www.bilibili.com/video/BV1Sw4m117XV)
 
## Function Description
**1 ESP32 section**  
When starting ESP32, the servo first performs an initialization, rotating forward for a certain period of time and reversing for a certain period of time;  
Then ESP32 starts sending some status information (start notifications, execute action notifications, etc.) to its MQTT server, subscribing to related topics   (/xxx/servo/action), and when receiving requests like {'act ':'xx'},  
Act is query: query the current connection information, plan task information, and throw the information to/xxx/servo/data in MQTT;  
act is reboot: restart oneself;  
act as do: Execute a fish feeding operation once;  
act is set_cfg: obtain cfg_data (scheduled task configuration information), write it to boot.ini, and then restart oneself to ensure that the new task takes effect;  
Due to the fact that micropython in ESP32 does not support threading, when executing multiple tasks, it is advisable to use a while loop to execute a particular task as much as possible;  
The configuration format for the planned task refers to the crontab configuration format in Linux (just a simple implementation, only partially simplified functions are completed);  
Since I haven't operated the servo before, I saw that the MG995 on Taobao is 360 degrees, and I thought 360 degrees would be better than 180 degrees, so I bought this one. During debugging, it was found that it could not be precise to a certain angle like other servos.  
MG995 can only give it forward or reverse instructions. Then it started spinning and couldn't stop.  
Until you give it another stop command, it stops again.  
>The midpoint position of the MG995 servo is 1500 microseconds (usec), with a pulse width range of 500 to 2500 microseconds and a dead zone width of 8 microseconds.  
>The control signal of a servo usually follows the following pattern: when the pulse width is less than the midpoint position, the servo rotates in one direction. When the pulse width is greater than the midpoint position, the servo rotates in the opposite direction.  
>When the pulse width is equal to the midpoint position, the servo stops rotating. Therefore, it can be inferred from the pulse width range of 500 to 2500 microseconds that,  
>When setting PWM. duty.ns (2500 * 1000), the maximum reverse speed of the servo is achieved  
>When setting PWM. duty.ns (500 * 1000), the maximum forward rotation speed of the servo is achieved  
That's all for it. Considering the servo power, power is drawn from the VIN and GND of ESP32 (with 5V).  
A 470uF capacitor was added between the positive and negative poles of the servo motor to prevent excessive current during startup.  
In actual testing, if no capacitor is added, starting the servo with load, the voltage is 5V, and the current is between 90mA-220mA, which is basically acceptable.
Connection as shown in the figure:  
![ESP32 and servo connection diagram](https://www.sunbeatus.com/img/conn_pic.png)
To prevent rain outdoors, the ESP32 and servo are placed in the takeout soup box.
I drilled two holes into the soup box, one plugged in a USB cable for power, and the other exposed the servo shaft outside.
Seal the leaking area with hot melt adhesive to avoid water ingress.
Fix the hat worn by the servo on the mineral water bottle with hot melt adhesive.
Above the mineral water bottle, there are many holes pierced with burnt iron wire. When it is inverted in the future, fish food will flow out from here.
To prevent rain and other situations, cut a small skirt around the neck of the bottle using a plastic bag and fix it with hot melt adhesive.
The complete appearance of the entire fish feeder is shown below:
![Physical Appearance](https://www.sunbeatus.com/img/whole_face.png)
ESP32 will send its heartbeat information to the mqtt server every minute to the theme/xxx/servo/log.
Considering the possibility of upgrading program code online, an additional section for transferring files through mqtt has been added to ESP32 to achieve its own "OTA"
**The directory of program files involved in ESP32 is: iot_dev**
-This is the code for the servo control part of the servo motor
-* act_mqtt. py * This is a response to various instructions sent by the mqtt protocol
-This is the configuration file section, where all key parameters are configured
->* main. py * This is the main program section
->* function. py * This is a section of commonly used functions that are encapsulated. In addition, due to the small RAM of ESP32, there may be inexplicably insufficient memory at times. After splitting some functions into function. py, this situation is resolved.
**2 Public network server section**
This part is deployed on a public network server (my own VPS, which is equipped with an MQTT server for Mosquito), for web front-end presentation and backend monitoring of several MQTT topics for response.
![Web Control Page](https://www.sunbeatus.com/img/FeedFishWeb.png)

**Listening for information from/xxx/servo/log:**  Store the logs sent by ESP32 into the local sqlite3 database. When loading the web management page, determine whether ESP32 is online or offline based on the records in the local sqlite3 database;    
**Listen to the corresponding topic FeedFish001 information of BaFaYun:** 
Received instructions from BaFaYun (or XiaoAi classmate), operate mqtt to send the startup command to ESP32 to execute the action;    
**The directory of program files involved in the public network server is: pub_server**  
- The * static/* directory is used to store JavaScript scripts, CSS, and other materials. There are many historical relics that cannot be removed even if copied back and forth.  
- The * templates * directory stores HTML template files;  
- [] logid_templ. HTML is the login template file;  
- [] *index. html*  is the homepage template file;  
- [] *logs. HTML* is the template file for displaying logs on the page;  
>- * server_web. py * This is the main page of the WEB  
>- * config. py * This is the various parameters involved in configuration on the public network server  
>MyDB. py is a database management module for web authentication  
>- * log2sqlite. py * This is an mqtt subscription that listens to/xxx/servo/log and stores it in the local sqlite library  
>- * bemfa. py * This is a subscription interaction for monitoring Bafa Cloud  
>- * MyMQTT. py * These are some modules of the encapsulated mqtt  
**3 Personal computer section**  
This mainly encapsulates a program update operation:
```
d: Op_firmware. py  
Usage: op_firmware. py [- h] [- t TOPIC] [- a ACTION] [- sf SOURCE-FILE] [- tf TARget-FILE]  
Op_firmware. py: error: No topic specified, add -- topic/x/x/x or - t/x/x/x/x  
d: \ perl_wrk \ ESP32uinit \ Python with servo motor \ laptop>op_firmware.py - h  
Usage: op_firmware. py [- h] [- t TOPIC] [- a ACTION] [- sf SOURCE-FILE] [- tf TARget-FILE]  
Manage IoT device operations  
Options:  
-h. -- help show this help message and exit  
-T TOPIC, -- topic TOPIC  
Which iot topic should be selected  
-Action, -- action Action  
Get/push/cmd  
-Sf SOURCE-FILE, -- source_file SOURCE-FILE  
Source file to be deal  
-Tf TARGETFILE, -- target_file TARGETFILE  
Target file to be deal  
Example 1, update local main. py to remote ESP32's main. py:  
Op_firmware. py - a push - t/ean/servo - sf main. py - tf main. py  
Example 2, get remote ESP32's main. py to local main_t. py:  
Op_firmware. py - a get - t/ean/servo - sf main. py - tf main_t. py  
```
**The directory where the relevant files are stored is: laptop**  
-Op_firmware. py This is the main microcode program for operating the ESP32 program  
-Pc_config.py is the corresponding configuration file  


## 简述

本项目基于ESP32做主控+MG995做舵机，做一个户外给鱼自动喂食的装置。

可以通过小爱同学，进行语音控制喂食；

可以通过web页面，进行状态查看，日志查看，喂食操作，定时设置；

可以根据定时设置情况，按定时计划，执行对应操作（比如喂食，比如重启自己）；

[操作视频](https://www.bilibili.com/video/BV1Sw4m117XV)

## 功能描述

**1. ESP32部分**

在ESP32启动时，舵机先做一个初始化，正转一定时间，反转一定时间；

然后ESP32开始向自己的MQTT服务器发送一些状态信息（启动通知，执行动作通知等），订阅相关的主题（/xxx/servo/action），当收到类似{'act':'xx'}请求时，

act为query：查询当前连接信息，计划任务信息，将信息扔给MQTT的/xxx/servo/data；

act为reboot：重启自己；

act为do：执行一次喂鱼操作；

act为set_cfg：获得cfg_data（计划任务配置信息），将之写入boot.ini，然后重启自己，确保新任务生效；

由于ESP32的micropython不支持threading，在执行多个任务时，尽可能通过while循环来进行某个任务的执行；

计划任务的配置格式，参考linux的crontab配置格式（只是一个简易实现，仅完成部分简化功能）；

由于之前没有操作过舵机，看淘宝上MG995是360度的，想着360度比180度的好，就买的这个。调试时发现，它没法儿像其它舵机那样，精确到某个角度。

MG995只能给它正转指令或者反转指令。然后它就开始转起来，停不下来了。

直到你再给它一个停止指令，它再停下来。

> MG995舵机的中点位置是1500微秒（usec）， 脉冲宽度范围是500到2500微秒，死区宽度是8微秒。

> 舵机的控制信号通常遵循以下规律： 当脉冲宽度小于中点位置时，舵机向一个方向转动。 当脉冲宽度大于中点位置时，舵机向相反方向转动。

> 当脉冲宽度等于中点位置时，舵机停止转动。 因此由脉冲宽度范围是500到2500微秒可知，

> 当设置pwm.duty_ns(2500*1000)时，舵机反转速度最大

> 当设置pwm.duty_ns(500*1000)时，舵机正转速度最大

也就这么将就着用了。考虑舵机功率，从ESP32的VIN和GND引电（有5V）。

怕舵机启动时电流过大，给它正负极之间加了一个470uF的电容。

实际测了下，不加电容的话，带负载情况下启动舵机，电压在5V，电流在90mA-220mA之间，基本也还能接受。

连接如图：

![ESP32和舵机连接图](https://www.sunbeatus.com/img/conn_pic.png)

为了在户外防雨，是把esp32和舵机放在外卖汤盒里面。

给汤盒钻了两个眼儿，一个插usb线供电，一个把舵机那个转轴露出到外面。

漏眼儿的地方，用热熔胶封上，避免进水。

矿泉水瓶子上把舵机戴的帽子用热熔胶固定在矿泉水瓶上。

矿泉水瓶上方瓶身处，用烧红的铁丝，扎许多洞洞，将来倒置它时，鱼食从此处流出来。

为了防止下雨等情况，给瓶身脖子处，拿塑料袋剪裁一个小裙子，也是热熔胶固定下。

下面是整个喂鱼器的完整外观，如下图：

![物理外观](https://www.sunbeatus.com/img/whole_face.png)

esp32会每隔一分钟，向主题/xxx/servo/log向mqtt服务器发送自己的心跳信息。

考虑到可能在线升级程序代码，给esp32增加了通过mqtt传送文件的部分，实现自己的“OTA”

**esp32涉及的程序文件目录为：iot_dev**

- > *pwm_servo.py* 这个是舵机操控部分代码

- > *act_mqtt.py* 这个是响应mqtt协议发过来的各种指令部分

- > *iot_config.py* 这个是配置文件部分，所有的关键参数，在这里进行配置

- > *main.py* 这个是主程序部分

- > *function.py* 这个是封装的一些常用函数部分。另外由于ESP32的RAM不大，有时会莫名其妙的内存不够，把一些功能拆分到function.py这里面后，这个情况就没有了。

**2. 公网服务器部分**

这部分部署在一个公网服务器上（我自己的VPS，上面装mosquitto的MQTT服务器），用于做web前端展现以及后端监听mqtt的几个主题进行响应。

![web控制页面](https://www.sunbeatus.com/img/FeedFishWeb.png)

**监听是/xxx/servo/log的信息：** 将esp32发来的日志，入库到本地的sqlite3数据库中。在载入web管理页面时，通过本地sqlite3数据库的记录，判断ESP32是在线状态还是离线状态；

**监听巴法云的对应主题FeedFish001信息：** 收到巴法云的指令（或者小爱同学），操作mqtt想/xxx/servo/action发送开机指令给esp32执行动作；

**公网服务器涉及的程序文件目录为：pub_server**

- > *static/* 这个目录是放javascript脚本，css等素材，很多历史遗留的东西，抄来抄去也就没去除无用东西了。

- > *templates* 这个目录存放html的模板文件；

- [ ] login_templ.html 是登录模板文件；

- [ ] *index.html* 是首页模板文件；

- [ ] *logs.html* 是日志展示页面模板文件；

> - *servo_web.py* 这个是WEB的主页面

> - *config.py* 这个是公网服务器上涉及配置的各个参数

> - *MyDB.py* 这个是web鉴权的数据库管理模块

> - *log2sqlite.py* 这个是监听/xxx/servo/log的mqtt订阅，然后存入本地sqlite库

> - *bemfa.py* 这个是监听巴法云的订阅交互

> - *MyMQTT.py* 这个是封装的mqtt的一些模块

**3. 个人电脑部分**

这个主要是封装一个程序更新操作：

```
d:\>op_firmware.py
usage: op_firmware.py [-h] [-t TOPIC] [-a ACTION] [-sf SOURCE_FILE] [-tf TARGET_FILE]
op_firmware.py: error: No topic specified, add --topic /x/x/x or -t /x/x/x

d:\perl_wrk\ESP32_init\python带伺服电机\laptop>op_firmware.py -h
usage: op_firmware.py [-h] [-t TOPIC] [-a ACTION] [-sf SOURCE_FILE] [-tf TARGET_FILE]

Manage IoT device operations

options:
  -h, --help            show this help message and exit
  -t TOPIC, --topic TOPIC
                        which iot topic should be selected
  -a ACTION, --action ACTION
                        get/push/cmd
  -sf SOURCE_FILE, --source_file SOURCE_FILE
                        source file to be deal
  -tf TARGET_FILE, --target_file TARGET_FILE
                        target file to be deal

example1, update local main.py to remote ESP32's main.py:
        op_firmware.py -a push -t /dean/servo -sf main.py -tf main.py

example2, get remote ESP32's main.py to local main_t.py:
        op_firmware.py -a get -t /dean/servo -sf main.py -tf main_t.py

```

**相关文件存放的目录为：laptop**
- op_firmware.py 这个是操作ESp32程序微码主程序

- pc_config.py 这个是对应的配置文件
