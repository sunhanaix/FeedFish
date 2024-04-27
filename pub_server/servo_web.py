#!/usr/local/bin/python3
import os,sys,re,json,time
from flask import Flask, render_template, request, Response, session, make_response, send_from_directory, jsonify, redirect
import datetime
import random,threading
import MyDB
import MyMQTT
import config as cfg
from log2sqlite import fetch_logs_from_db,mqtt_listener,get_last_log

VERSION = 'v1.1.0.20240427'

mylogger=cfg.logger
app = Flask(__name__,static_folder='static',static_url_path="/")
app.config[
    'SECRET_KEY'] = b'\xder\x884_\xe9\x8e\x05\xf62\xf8q\xab*\xd7/{1y\x08\x19\xee\xcc%'  # 设置一个固定字符串为加密盐，这样每次重启程序后，session也可以继续可用
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=cfg.exp_days)  # 设置session90天过期

def query_esp32_info():
    # MQTT请求ESP32发送config.ini文件内容
    payload=json.dumps({'act':'query'})
    try:
        pv = MyMQTT.pull_iot_value(payload=payload)
    except Exception as e:
        mylogger.error(f"can not MyMQTT.pull_iot_value，reason: {e=}")
        return {}
    mylogger.info(f"{pv.final_res=}")
    return pv.final_res
# 路由到主页
@app.route('/', methods=['GET', 'POST'])
def index():
    # session默认有效期和cookie一样，直到浏览器回话结束
    # 可以通过设置`session.permanent=True`来设置自定义的有效期
    session.permanent = True
    username=request.form.get('username')
    password=request.form.get('password')
    logout=request.args.get('logout')
    ip=request.remote_addr
    if ip.find('127.0.0.1')>-1:
        ip=request.headers.get('X-Forwarded-For')
    browser=request.headers.get("User-Agent")
    #把上述取得的变量用mylogger.info输出记录下
    mylogger.info(f"{ip=},{browser=},{username=},{session.get('user')=},{password=},{logout=}")
    db = MyDB.UserDB(cfg.db_file)
    if username and password:
        res=db.checkUserPass(username,password)
        print("res=%s" % str(res))
        if res and res['code']==0: #要是登录成功
            session['sid']=db.addSession(username,expireTime=(int(time.time()+cfg.exp_days*24*3600)))
            db.close()
            session['user']=username
        else:
            db.close()
            return render_template("login_templ.html",prompt="登录失败，请重新登录")
    else:
        db.close()
    if not ( session.get('sid') and session.get('user') ):
        return render_template("login_templ.html",prompt="请登录")
    if logout:
        mylogger.info(f"user:{session['user']} logout")
        del session['user']
        del session['sid']
        return redirect(cfg.home_url)

    info = {}
    config_data = {}
    return render_template("index.html",username=session['user'],version=VERSION, info=info,config=config_data,home_url=cfg.home_url)

@app.route("/esp32_info", methods=["GET"])
def esp32_info():
    if session.get("user"):
        mylogger.info(f"session user is: {session['user']}")
    else:
        return redirect(cfg.home_url)
    esp32_info=query_esp32_info()
    if not esp32_info:
        return jsonify({'code': 1, 'msg': 'can not MyMQTT.pull_iot_value'})
    info = {}
    config_data = {}
    #下面是正常返回信息
    info['ssid']=esp32_info['ssid']
    info['rssi']=esp32_info['rssi']
    info['mac']=esp32_info['mac']
    info['ip']=esp32_info['ip']
    info['model']=esp32_info['model']
    info['version']=esp32_info['version']
    info['client_id']=esp32_info['client_id']
    info['uptime'] = esp32_info['uptime']
    info['now_time'] = esp32_info['now_time']
    config_data['steps']=esp32_info['cfg_data'].split('\n')[0].split('steps=')[-1].lstrip().rstrip()
    config_data['crontabs'] = "\n".join(esp32_info['cfg_data'].split('\n')[1:])
    config_data['crontabs']=config_data['crontabs'].lstrip().rstrip()
    mylogger.info(f"{config_data['crontabs']=}")
    return  jsonify({'code': 0, 'msg': 'get value ok', 'info': info,'config_data': config_data})

# 路由处理更新配置请求
@app.route("/update_config", methods=["GET","POST"])
def update_config():
    if session.get("user"):
        mylogger.info(f"session user is: {session['user']}")
    else:
        return redirect(cfg.home_url)
    steps = request.form.get('steps')
    crontabs = request.form.get('movements')
    mylogger.info(f"{steps=}, {crontabs=}")
    if steps is None:
        return jsonify({'code': 1, 'msg': 'steps is None'})
    if crontabs is None:
        return jsonify({'code': 1, 'msg': 'crontabs is None'})
    new_config = f"steps={steps}\n{crontabs}"
    mylogger.info(f"{new_config=}")
    # 通过MQTT发送更新后的配置至ESP32
    payload = json.dumps({'act': 'set_cfg', 'cfg_data': new_config})
    try:
        MyMQTT.publish(cfg.pub_topic, payload)
        return jsonify({'code':0,'msg':'set_cfg action was sent successfully'})
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'set_cfg action was sent failed,reason:{e}'})


@app.route("/do", methods=["GET"])
def do():
    if session.get("user"):
        mylogger.info(f"session user is: {session['user']}")
    else:
        return redirect(cfg.home_url)
    steps = int(request.args.get('steps'))
    wait=int(request.args.get('wait'))
    back_steps = int(request.args.get('back_steps'))
    mylogger.info(f"{steps=}, {wait=}, {back_steps=}")
    # 通过MQTT发送更新后的配置至ESP32
    payload=json.dumps({'act':'do','steps':steps,'wait':wait,'back_steps':back_steps})
    try:
        MyMQTT.publish(cfg.pub_topic, payload)
        return jsonify({'code':0,'msg':'do action was sent successfully'})
    except Exception as e:
        return jsonify({'code':1,'msg':f'do action was sent failed,reason:{e}'})

@app.route("/reboot", methods=["GET"])
def reboot():
    if session.get("user"):
        mylogger.info(f"session user is: {session['user']}")
    else:
        return redirect(cfg.home_url)
    wait = int(request.args.get('wait',1))
    mylogger.info(f"in reboot(), {wait=}")
    # 通过MQTT发送更新后的配置至ESP32
    payload=json.dumps({'act':'reboot','wait':wait})
    try:
        MyMQTT.publish(cfg.pub_topic, payload)
        return jsonify({'code':0,'msg':'reboot action was sent successfully'})
    except Exception as e:
        return jsonify({'code':1,'msg':f'reboot action was sent failed,reason:{e}'})

@app.route("/get_last_log", methods=["GET"]) #取回最后一条日志
def return_last_log():
    if session.get("user"):
        mylogger.info(f"session user is: {session['user']}")
    else:
        return redirect(cfg.home_url)
    last_log=get_last_log()
    return jsonify(last_log)

@app.route('/fetch_logs') #取回给定时间段内的日志
def fetch_logs():
    if session.get("user"):
        mylogger.info(f"session user is: {session['user']}")
    else:
        return redirect(cfg.home_url)
    end_time = datetime.datetime.now()
    start_time = end_time - datetime.timedelta(days=1)
    str_start_time=start_time.strftime('%Y-%m-%d %H:%M:%S')
    #str_end_time=end_time.strftime('%Y-%m-%d %H:%M:%S')
    str_end_time = end_time.strftime('%Y-%m-%d')+" 23:59:59"
    str_start = request.args.get('start', str_start_time).replace('T', ' ')
    str_end = request.args.get('end', str_end_time).replace('T', ' ')
    exclude=request.args.get('exclude')
    mylogger.info(f"{str_start=}, {str_end=} ,{exclude=}")
    logs = fetch_logs_from_db(str_start, str_end, exclude)
    return render_template('logs.html', logs=logs, start_time=str_start, end_time=str_end,username=session['user'],version=VERSION, home_url=cfg.home_url)

if __name__ == "__main__":
    mylogger.info("启动MQTT消息监听线程")
    ct = threading.Thread(target=mqtt_listener)
    ct.daemon = True
    ct.start()
    if cfg.enable_bemfa: #如果启用了巴法云，则启动巴法云消息监听线程
        from bemfa import bemfa_listener
        mylogger.info("启动巴法云消息监听线程")
        ct2 = threading.Thread(target=bemfa_listener)
        ct2.daemon = True
        ct2.start()

    if os.environ.get('port'):  # 如果环境变量设置了port，那么用环境变量的port端口
        port = int(os.environ.get('port'))
    else:
        port = cfg.web_port
    mylogger.info("Version=%s" % VERSION)
    try:
        debug = int(os.environ.get('debug'))
    except:
        debug = 0
    mylogger.info(f"debug={debug} , port={port}")
    if debug:
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        #ct = threading.Thread(target=wait_and_launch_browser, args=(port, 2))
        #ct.start()
        from waitress import serve
        serve(app, host="0.0.0.0", port=port)
