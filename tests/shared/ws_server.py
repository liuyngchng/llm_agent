#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
pip install uvicorn websockets
uvicorn ws_server:start_server --ws websockets --host 0.0.0.0 --port 18765
"""
import json
import time

from my_enums import MsgType
from websockets import serve, ConnectionClosed
import asyncio
import logging.config
from cfg_util import get_user_name_by_uid

from websockets.legacy.server import WebSocketServerProtocol

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

MAX_CLIENTS = 1000
clients_lock = asyncio.Lock()

""" 
data structure 
{
    "uid1":{
        "ws":ws1, 
        "last_active":12134567
    }, 
    "uid2":{
        "ws":wss, 
        "last_active":2234567
    },   
}
"""
connected_clients = dict()


async def handler(websocket: WebSocketServerProtocol) -> None:
    """
    connection handler, to handle connected socket, client should not be disconnected immediately
    there is a timeout check in function check_timeout to delete the dead connected clients from server side
    """
    if len(connected_clients) >= MAX_CLIENTS:
        await websocket.send(build_msg("system", "", MsgType.ERROR.value, "连接数已饱和"))
        await websocket.close()
        return
    uid = "-1"
    try:
        # 先等待客户端发送UID注册, TODO 注册漏洞：未验证重复注册（允许UID劫持）
        register_msg = await websocket.recv()
        uid = json.loads(register_msg)['msg_from_uid']

        usr = get_user_name_by_uid(uid)
        if not usr:
            err_msg = build_msg("system", uid, MsgType.ERROR.value, "此用户不存在")
            await websocket.send(err_msg)
            await websocket.close()
            logger.error(f"illegal_user, {err_msg}")
            return
        connected_clients[uid] = {
            'ws': websocket,
            'last_active': time.time()
        }
        async for message in websocket:
            data = json.loads(message)
            logger.info(f"rcv_msg {data}")
            async with clients_lock:
                connected_clients[uid]['last_active'] = time.time()

            if data.get('type') == MsgType.HEARTBEAT.value:
                await websocket.send(
                    build_msg("server", uid, MsgType.HEARTBEAT_ACK.value, "pong", data.get('seq'))
                )
                continue
            if not all(key in data for key in ('msg_from_uid', 'msg', 'to')):
                logger.warning(f"Invalid message format: {data}")
                continue
            uid = data['msg_from_uid']
            msg = data['msg']
            to = data['to']
            logger.info(f"rcv_msg_from_client_{uid}, {msg}")
            if not to:
                logger.info("no_msg_route_information")
                continue
            if to in connected_clients:
                async with clients_lock:
                    await connected_clients[to]["ws"].send(
                        build_msg(uid, to, MsgType.MSG.value, msg)
                    )
            else:
                logger.error(f"msg_route_target_can_not_be_engaged, client {to} is offline")
                await websocket.send(
                    build_msg("system", uid, MsgType.WARN.value, "此用户目前不在线")
                )
    except (asyncio.TimeoutError, ConnectionClosed):
        logger.warning(f"client_disconnected, msg_from_uid {uid}")
    finally:
        logger.info("handler_finished")

async def check_timeout():
    while True:
        await asyncio.sleep(15)
        async with clients_lock:
            now = time.time()
            expired = [
                uid for uid, info in connected_clients.items()
                if now - info['last_active'] > 30
            ]  # 30秒无活动判定超时
            for uid in expired:
                await connected_clients[uid]['ws'].close()
                del connected_clients[uid]
                logger.info(f"user {uid} disconnected, removed_from_connected_clients")

async def start_server():
    async with serve(handler, "localhost", 18765):
        asyncio.create_task(check_timeout())
        await asyncio.Future()  # process blocked here


def build_msg(frm: str, to: str, msg_type: str, msg:str, seq="") -> str:
    """
    :param frm: where the msg from
    :param to: where the msg want to be sent to
    :param msg_type: msg type
    :param msg: the txt msg want to be delivered
    :param seq: the sequence number of msg, something like in TCP packet
    """
    return json.dumps({
        "from": frm,
        "to": to,
        "type": msg_type,
        "msg": msg,
        "seq": seq,
        "timestamp": time.time()
    }, ensure_ascii=False)

if __name__ == "__main__":
    """
    in production environment ,you can start the server like this
    unicorn your_py_file_without_suffix:start_server
    uvicorn ws_server:start_server --ws websockets --host 0.0.0.0 --port 18765
    uvicorn is developed base on NIO, so it is unnecessary to start a multi-thread start to run your program.
    accordingly, you can run with '-w 3 ' to start your program with 3 process, which is in multi-progress mode   
    and ,you can see, now some keep alive used in program, 
    you should make sure the max connection param in linux kernel config can satisfy your remand
    """
    asyncio.run(start_server())