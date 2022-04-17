from socket import *
import threading
import urllib.parse
import os
import hashlib
import time
'''
    this is the proxy server
'''


def prox_the_connect(new_conect_soc, addr):
    """
    实现代理的方法 可被线程调度启动
    Args:
        new_conect_soc: 传入的为客户创建的新的socket
        addr: 用户的ip地址
    Returns:
        none
    """

    # 从客户端接受报文
    banned_web_list = ['today.hit.edu.cn']  # 禁止网站列表
    banned_user_list = ['127.0.0.1']  #   # 禁止用户列表
    fake_list = {'www.7k7k.com': 'cs.hit.edu.cn'}   # 重定向网站列表

    cache_size = 1000   # 设定缓存文件最多为1000个
    cache_dir = os.path.join(os.path.dirname(__file__), 'Cache')  # 指定缓存文件所在文件夹
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)

    new_conect_soc.settimeout(2)
    mes = new_conect_soc.recv(4096)
    try:
        while True:
            rec_buf = new_conect_soc.recv(4096)
            if rec_buf:
                mes += rec_buf
            else:
                break
    except:
        pass
    if not mes:  # 如果报文为空 断开该连接并返回
        new_conect_soc.close()
        return
    str_mes = mes.decode('gbk', 'ignore')
    print(str_mes)
    http_mes = str_mes.split('\r\n')
    req_line = http_mes[0]  # 获取首部字段请求行
    if 'CONNECT' in req_line:  # 本次实验不考虑CONNECT
        new_conect_soc.close()
        return
    print(req_line)

    target_url = req_line.split()[1]
    target_url = urllib.parse.urlparse(target_url)
    target_host = target_url.hostname
    print(target_host)

    target_port = 80 if target_url.port is None else target_url.port

    if addr[0] in banned_user_list:  # 判断请求用户是否在过滤列表内 若是则拒绝并关闭连接
        new_conect_soc.send(str.encode('HTTP/1.1 403 Forbidden\r\n'))  # 向客户端发送拒绝访问报文
        new_conect_soc.close()
        return
    if target_host in banned_web_list:  # 判断目标主机是否被禁止 处理同上
        new_conect_soc.send(str.encode('HTTP/1.1 403 Forbidden\r\n'))  # 通上，发送拒绝访问报文
        new_conect_soc.close()
        return
    if target_host in fake_list.keys():  # 判断是否在钓鱼网站列表中
        temp = mes.decode().replace(req_line.split()[1], "http://"+fake_list[target_host]+"/")
        temp = temp.replace(target_host, fake_list[target_host])
        http_mes = temp.split('\r\n')
        req_line = http_mes[0]
        target_url = req_line.split()[1]
        target_url = urllib.parse.urlparse(target_url)  # 重新解析url用于与目标server连接
        mes = str.encode(temp)  # 重新生成字节形式报文


    m = hashlib.md5()
    m.update(str.encode(target_url.netloc + target_url.path))
    filename = os.path.join(cache_dir, m.hexdigest() + '.cache')
    if os.path.exists(filename):  # 如果之前已经建立过缓存
        real_ser_sock = socket(AF_INET, SOCK_STREAM)
        real_ser_sock.settimeout(120)
        real_ser_sock.connect((target_url.hostname, target_port))

        temp = req_line + '\r\n'

        t = (time.strptime(time.ctime(os.path.getmtime(filename)),  # 获取缓存文件的最后修改时间并指定格式
                           "%a %b %d %H:%M:%S %Y"))
        temp += 'If-Modified-Since: ' + time.strftime(
            '%a, %d %b %Y %H:%M:%S GMT', t) + '\r\n'
        for line in http_mes[1:]:
            temp += line + '\r\n'
        real_ser_sock.sendall(str.encode(temp))

        flag = True
        while True:
            data = real_ser_sock.recv(4096)
            if flag:
                if data.decode('iso-8859-1').split()[1] == '304':  # 若响应报文条件码为304 不必更新
                    print('Cache hit: {path}'.format(path=target_url.hostname + target_url.path))
                    new_conect_soc.send(open(filename, 'rb').read())
                    break
                else:
                    cac_file = open(filename, 'wb')  # 原服务器已经更新
                    print('Cache updated: {path}'.format(path=target_url.hostname + target_url.path))
                    if len(data) > 0:
                        new_conect_soc.send(data)
                        cac_file.write(data)
                    else:
                        break
                    flag = False
            else:  # 前面没有hit 则多次从原服务器读取内容，直到没有内容可读
                cac_file = open(filename, 'ab')
                if len(data) > 0:
                    new_conect_soc.send(data)
                    cac_file.write(data)
                else:
                    break

    else:  # 否则重新从源服务器获取数据
        real_ser_sock = socket(AF_INET, SOCK_STREAM)  # 为连接至目标服务器创建套接字
        real_ser_sock.settimeout(120)  # 设置120s的超时时延
        real_ser_sock.connect((target_url.hostname, target_port))  # 连接至原服务器
        real_ser_sock.sendall(mes)
        cac_file = open(filename, 'ab')
        while True:
            buf = real_ser_sock.recv(4096)
            # 可以加入缓存
            if len(buf) > 0:
                new_conect_soc.send(buf)
                cac_file.write(buf)
            else:
                break
        cac_file.close()  # 关闭缓存文件、向目标服务器的连接以及客户端的连接
        real_ser_sock.close()
        new_conect_soc.close()

    cache_counter = 0
    cache_files = []
    for file in os.listdir(os.path.join(os.path.dirname(__file__), 'cache')):
        if file.endswith('.cache'):  # 计算cache文件的数量
            cache_counter += 1
            cache_files.append(file)
    if cache_counter > 1000:  # 当数量超过最大限度时删除一定量cache文件
        for i in range(len(cache_files) - 1):
            for j in range(i + 1, len(cache_files)):
                if os.path.getmtime(cache_files[i]) < os.path.getmtime(cache_files[j]):
                    temp = cache_files[i]
                    cache_files[i] = cache_files[j]
                    cache_files[j] = temp
        for file in cache_files[cache_size:]:
            os.remove(file)
    return


# 生成套接字，绑定至本地指定端口并开始listen
serv_ip = '127.0.0.1'  # local ip
serv_port = 10240
soc = socket(AF_INET, SOCK_STREAM)
soc.bind((serv_ip, serv_port))
soc.listen(30)  # 最多允许同时接听30个请求连接

try:
    while True:
        # 接受一个新的连接请求
        new_conect_soc, addr = soc.accept()
        # 创建一个字线程，并调用prox_the_connect函数进行代理
        pro_threa = threading.Thread(target=prox_the_connect, args=(new_conect_soc, addr))
        pro_threa.start()
finally:
    soc.close()
