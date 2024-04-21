#!python
import sqlite3, requests
import sys, os, re, json, random, time
import config as cfg
from hashlib import md5

# sqlite3的用户表和登录日志表数据库维护管理
DEFAULT_DB_FILE='user.db.py'

def dict_factory(cursor, row):
    '''
    sqlite3中conn.row_factory方法的封装，用于处理没一个row信息，把它变成dict
    :param cursor: 传进来的sqlite3的cursor游标
    :param row:  #传进来的row数据
    :return: 返回这一行的dict结果
    '''
    #return dict((col[0], row[idx]) for idx, col in enumerate(cursor.description))
    res={}
    for idx, col in enumerate(cursor.description):
        if row[idx] is None: #如果此行，此列的field值为空，默认是返回None，这里强制转空字符串
            res[col[0]]=''
        else:
            res[col[0]]=row[idx]
    return res

def getLocByBaidu(ip):
    if not ip:
        return False
    url = "http://api.map.baidu.com/location/ip?ip=%s&coor=bd09ll&ak=IPHDEesBVxQaVxbH1G6SWwokD2K7wZeT" % ip;
    check_page = requests.get(url).content.decode('utf8')
    loc = json.loads(check_page)
    if not 'status' in loc:
        return False
    if not loc['status'] == 0:
        return False
    if not 'address' in loc:
        return False
    return loc['address']


class UserDB(object):
    conn = None
    cur = None

    def __init__(self, dbname=DEFAULT_DB_FILE, params=None):
        # print("dbname=%s" % dbname)
        self.conn = sqlite3.connect(dbname)
        self.cur = self.conn.cursor()
        self.conn.execute('pragma foreign_keys=on')  # 启用外键一致性检查
        if not os.path.isfile(dbname):
            print("not file:" + dbname)
            self.createUserDB()
            self.createLogTable()
            self.createSessionTable()
            self.createBloodPressureTable()

        # print(self.cur.fetchall())
        else:
            if not self.checkTable('user'):
                self.createUserTable()
            if not self.checkTable('log'):
                self.createLogTable()
            if not self.checkTable('session'):
                self.createSessionTable()
            if not self.checkTable('blood_pressure'):
                self.createBloodPressureTable()


    def randomStr(self, length=8, noSpecial=False):
        STR = [chr(i) for i in range(65, 91)]  # 65-91对应字符A-Z
        str = [chr(i) for i in range(97, 123)]  # a-z
        number = [chr(i) for i in range(48, 58)]  # 0-9
        special = ['!', '@', '#', '%', '^', '*', '(', ')', '-', '+', '[', ']', ',', '.', '/', '<', '>']  # 去掉了$和:等特殊字符
        if noSpecial:
            total = STR + str + number  # 所有可以出现的可见字符串，不要特殊字符串
        else:
            total = STR + str + number + special  # 所有可以出现的可见字符串
        salt = random.sample(total, length)
        return "".join(salt)

    def crypt(self, txtPassword, salt=None):
        if salt == None:  # 要是没提过salt参数，则随机生成一个8位的
            salt = self.randomStr(4)
        p = md5((salt + txtPassword).encode()).hexdigest()
        return "$1$%s$%s" % (salt, p)  # $1$xxxx$yyyyy , 1标识md5，xxxx为salt，yyyy为md5后的hexdigiest

    def decodePassword(self, encPassword):  # 密文密码，按$分隔符拆分出来salt和密文p
        t = encPassword.split('$')
        if len(t) < 4:
            return False
        return {'type': t[1], 'salt': t[2], 'p': t[3]}

    def addUser(self, user, passwd, valid=1, online=0, notes=''):
        # print("user=%s,passwd=%s,valid=%d,online=%d,notes=%s" % (user,passwd,valid,online,notes))
        passwd = self.crypt(passwd)
        crtime = int(time.time())
        sql = 'insert into user(user,passwd,crtime,valid,online,notes) values(?,?,?,?,?,?)'
        res = False
        try:
            res = self.cur.execute(sql, (user, passwd, crtime, valid, online, notes))
        except Exception as e:
            return False
        self.conn.commit()
        return True

    def addSession(self, user, startTime=int(time.time()), expireTime=(int(time.time() + 7 * 24 * 3600)), valid=1):
        # 给定一个用户，创建一个session
        sid = self.randomStr(20, noSpecial=True)
        sql = 'insert into session(sid,user,startTime,expireTime,valid) values(?,?,?,?,?)'
        res = self.cur.execute(sql, (sid, user, startTime, expireTime, valid))
        self.conn.commit()
        return sid

    def checkSession(self, sid, nowTime=int(time.time())):
        sql = '''select s.sid,s.user,s.startTime,s.expireTime,s.valid,u.admin
				 from session s left join user u on u.[user]=s.[user]
				 where sid=?'''
        # 增加个admin属性检查
        res = self.cur.execute(sql, (sid,))
        rec = self.cur.fetchone()  # 返回一个list： [sid,user,startTime,expireTime,valid]
        if not rec:
            return {'code': 1, 'msg': 'session does not exist'}
        if not rec[4] == 1:
            return {'code': 2, 'msg': 'session is not valid'}
        if rec[3] <= nowTime:
            return {'code': 3, 'msg': 'session was expired'}
        return {'code': 0, 'msg': 'OK', 'user': rec[1], 'admin': rec[5]}

    def delSession(self, sid):
        res = self.checkSession(sid)
        if res['code'] == 1:  # 要是session不存在
            return res
        sql = 'delete  from session where sid=?'
        res = self.cur.execute(sql, (sid,))
        self.conn.commit()
        return {'code': 0, 'msg': 'OK'}

    def modUser(self, user, passwd=None, valid=None, online=None, notes=None):
        if not passwd == None:
            passwd = self.crypt(passwd)
            sql = "update user set passwd=? where user=?"
            # print("sql=%s" % sql)
            # print("user=%s,passwd=%s" % (user,passwd))
            self.cur.execute(sql, (passwd, user))
            self.conn.commit()
        if not valid == None:
            sql = "update user set valid=? where user=?"
            self.cur.execute(sql, (valid, user))
            self.conn.commit()
        if not online == None:
            sql = "update user set online=? where user=?"
            self.cur.execute(sql, (online, user))
            self.conn.commit()
        if not notes == None:
            sql = "update user set notes=? where user=?"
            # print(sql)
            # print(notes)
            self.cur.execute(sql, (notes, user))
            self.conn.commit()
        return True

    def listUser(self, user=None):  # 列出指定的用户，或者列出所有用户信息
        if not user == None:
            sql = "select user,notes,datetime(crtime,'unixepoch','localtime'),valid,online,admin from user where user=?";
            self.cur.execute(sql, (user,))
            t = self.cur.fetchone()
        else:
            sql = "select user,notes,datetime(crtime,'unixepoch','localtime'),valid,online,admin from user";
            self.cur.execute(sql)
            t = self.cur.fetchall()
        title = ['用户名', '备注', '创建时间', 'valid', 'online', '管理权限']
        enTitle = ['user', 'notes', 'crtime', 'valid', 'online', 'admin']
        return {'title': title, 'enTitle': enTitle, 'data': t}

    def checkUserPass(self, user, passwd):  # 给定用户名密码，校验用户是否存在，以及密码正确
        sql = "select user,passwd,crtime,valid,online,notes,admin from user where user='%s'" % user;
        self.cur.execute(sql)
        rec = self.cur.fetchone()  # 返回一个list： [user,passwd,crtime,valid,online,notes]
        if not rec:
            return {'code': 1, 'msg': 'user does not exist'}
        if rec[3] == 0:
            return {'code': 2, 'msg': 'user is not valid now'}
        t = self.decodePassword(rec[1])
        calc_p = self.crypt(passwd, t['salt'])
        if calc_p == rec[1]:
            return {'code': 0, 'msg': 'OK', 'admin': rec[6]}
        else:
            return {'code': 3, 'msg': 'user & password is not right'}

    def delUser(self, user):  # 删除用户，但为了保持记录，只把valid记录设置为0
        check = self.checkUserPass(user, 'any')
        if check['code'] == 1:
            return False
        sql = "update user set valid=0 where user='%s'" % user;
        try:
            self.cur.execute(sql)
        except Exception as e:
            return False
        self.conn.commit()
        return True

    def activeUser(self, user):  # 激活用户，把valid记录设置为1
        check = self.checkUserPass(user, 'any')
        if check['code'] == 1:
            return check
        sql = "update user set valid=1 where user='%s'" % user;
        self.cur.execute(sql)
        self.conn.commit()

    def checkTable(self, tname):
        sql = "select count(*) from sqlite_master where type='table' and name='%s'" % tname;
        self.cur.execute(sql)
        count = self.cur.fetchone()[0]
        if count == 0:
            return False
        else:
            return True

    def addLog(self, user, operation, ip='', browser='', session=''):
        logtime = int(time.time())
        addr = getLocByBaidu(ip)
        if not addr:
            addr = ''
        sql = 'insert into log(user,operation,time,ip,addr,browser,session) values(?,?,?,?,?,?,?)'
        res = self.cur.execute(sql, (user, operation, logtime, ip, addr, browser, session))
        self.conn.commit()
        return res

    def accountLog(self):
        sql = 'select operation,count(*) cnt from log group by operation order by cnt desc'
        self.cur.execute(sql)
        res = self.cur.fetchall()
        title = ['operation', 'cnt']
        return {'title': title, 'data': res}

    def listLog(self, spage=0, n=10, orderby='time', nologin=0):  # 指定从哪里开始查看log
        sql = 'select count(*) from log %s'
        if nologin == 1:
            where = "where operation <>'logon' and operation <>'logout' "
        else:
            where = ''
        sql = sql % where
        self.cur.execute(sql)
        res = self.cur.fetchone()
        cnt = res[0]
        if orderby == 'user':
            orderby = 'l.user'
        sql = '''select l.user,l.session,u.notes,l.operation,datetime(l.time,'unixepoch','localtime'),l.ip,l.addr,l.browser 
						from log l left join user u on u.[user]=l.[user]
						 %s 
						order by %s desc limit ?,?
				'''
        sql = sql % (where, orderby)
        # print(sql,spage,n)
        res = self.cur.execute(sql, (spage, n))
        title = ['user', 'session', 'notes', 'operation', 'time', 'ip', 'addr', 'browser']
        data = self.cur.fetchall()
        return {'title': title, 'total': cnt, 'data': data}

    def createUserTable(self):
        sql = '''CREATE TABLE user(
									id integer PRIMARY KEY autoincrement,
									user text unique not null,
									passwd text not null,
									crtime integer unique not null,
									valid integer default 1,
									online integer default 0,
									admin integer default 0,
									notes text)
					'''
        self.cur.execute(sql)
        self.conn.commit()
        self.addUser(cfg.db_default_user, cfg.db_default_passwd)  # 添加一个默认用户和默认密码

    def createSessionTable(self):
        sql = '''CREATE TABLE session(
									sid text PRIMARY KEY,
									user text REFERENCES user(user) ,
									startTime integer not null,
									expireTime integer not null,
									valid integer default 0
									)
					'''
        self.cur.execute(sql)
        self.conn.commit()

    def createLogTable(self):
        sql = '''CREATE TABLE log(
									id integer PRIMARY KEY autoincrement,
									user text REFERENCES user(user) ,
									session text,
									ip text,
									addr text,
									browser text,
									time integer,
									operation text
									)
					'''
        self.cur.execute(sql)
        self.conn.commit()

    def addBP(self, BPRecord): #添加血压记录入库
        if not 'crtime' in BPRecord:
            BPRecord['crtime']=int(time.time())
        fields = list(BPRecord.keys())
        question_mark = ['?' for i in fields]
        values = [BPRecord[k] for k in fields]
        sql = 'insert into blood_pressure (%s) values(%s)' % (','.join(fields), ','.join(question_mark))
        print("sql=%s,values=%s" % (sql,values))
        res = self.cur.execute(sql, values)
        self.conn.commit()
        return res

    def listBP(self, num_rec=10,where_clause=None):
        '''
         列出指定的血压记录，或者列出所有信息
        :param where_clause:  给定SQL条件语句，进行筛选，不给定的话，返回全部
        :return:
        '''
        # self.conn.row_factory = sqlite3.Row
        self.conn.row_factory = dict_factory
        self.cur = self.conn.cursor()

        if not where_clause:
            sql = "select strftime('%Y-%m-%d %H:%M',datetime(crtime,'unixepoch','localtime')) as crtime,user,high_pressure,low_pressure,heartbeat,notes from blood_pressure order by crtime desc limit "+ " %d" %  num_rec;
            self.cur.execute(sql)
            t = self.cur.fetchall()
            return t
        sql = "select strftime('%Y-%m-%d %H:%M',datetime(crtime,'unixepoch','localtime')) as crtime,user,high_pressure,low_pressure,heartbeat,notes from blood_pressure  where " + where_clause +" order by crtime desc limit %d" %  num_rec;
        if os.environ.get('debug'):
            print("in listHost(),sql=%s" % sql)
        self.cur.execute(sql)
        t = self.cur.fetchall()
        return t

    def createBloodPressureTable(self):
        sql = '''CREATE TABLE blood_pressure(
									id integer PRIMARY KEY autoincrement,
									user text  not null,
									crtime integer not null,
									high_pressure integer not null,
									low_pressure integer not null,
									heartbeat integer not null,
									notes text)
					'''
        self.cur.execute(sql)
        self.conn.commit()

    def close(self):
        self.cur.close()
        self.conn.commit()
        self.conn.close()

class KeyValueStore(dict):  # 新造一个轮子，继承dict类，用于key/value持久化存储在sqlite3中
    #为了保留该值原来的str、int、list、dict属性，入库时用json，出库时再转回原来格式，从而保留原来值的类型
    def __init__(self, filename=DEFAULT_DB_FILE):
        self.conn = sqlite3.connect(filename)
        self.conn.execute("CREATE TABLE IF NOT EXISTS kv (key text unique, value text)")

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.commit()
        self.conn.close()

    def __len__(self):
        rows = self.conn.execute('SELECT COUNT(*) FROM kv').fetchone()[0]
        return rows if rows is not None else 0

    def iterkeys(self):
        c = self.conn.cursor()
        for row in self.conn.execute('SELECT key FROM kv'):
            yield row[0]

    def itervalues(self):
        c = self.conn.cursor()
        for row in c.execute('SELECT value FROM kv'):
            yield json.loads(row[0])

    def iteritems(self):
        c = self.conn.cursor()
        for row in c.execute('SELECT key, value FROM kv'):
            yield row[0], json.loads(row[1])

    def keys(self):
        return list(self.iterkeys())

    def values(self):
        return list(self.itervalues())

    def items(self):
        return list(self.iteritems())

    def __contains__(self, key):
        return self.conn.execute('SELECT 1 FROM kv WHERE key = ?', (key,)).fetchone() is not None

    def __getitem__(self, key):
        item = self.conn.execute('SELECT value FROM kv WHERE key = ?', (key,)).fetchone()
        if item is None:
            raise KeyError(key)
        return json.loads(item[0])

    def __setitem__(self, key, value):
        value=json.dumps(value,indent=2,ensure_ascii=False)
        self.conn.execute('REPLACE INTO kv (key, value) VALUES (?,?)', (key, value))
        self.commit()

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        self.conn.execute('DELETE FROM kv WHERE key = ?', (key,))
        self.commit()

    def __iter__(self):
        return self.iterkeys()


if __name__ == '__main__':
    db = UserDB('bs.db')
    # print(db.listLog())
    #oneSong = {'title': 'dd歌曲', 'audio': '/a/mp3/dd.mp3', 'id': 10}
    #db.addOneSong(oneSong)
    #db.delOneSong(1)
    #db.moveUpSong(1)
    #db.moveDownSong(6,2)
    #db.setValue('xx',[1,2,3])
    #idx=db.setPlayIndex(2)
    #idx=db.getPlayIndex()
    #songs=db.getSong(2)
    #print(songs)
    #kv=KeyValueStore()
    #kv['xx']=[1,2,3]
    #print(kv['xx'])
    #kv['t']=123
    #print(type(kv['xx']))
    #print(type(kv['t']))
    oneRS={'user':'hln','high_pressure':180,'low_pressure':120}
    db.addBP(oneRS)
    t=db.listBP(num_rec=10,where_clause='crtime >1611546946')
    print(json.dumps(t,indent=2,ensure_ascii=False))

# print(db.checkSession('bq3jg2zVyUZ-',nowTime=1548660788))
