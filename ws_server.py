#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import time

from websockets import serve, ConnectionClosed
import asyncio
import logging.config

from websockets.legacy.server import WebSocketServerProtocol

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

MAX_CLIENTS = 1000
clients_lock = asyncio.Lock()

""" data structure 
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
    connection handler, to handle connected socket
    """
    if len(connected_clients) >= MAX_CLIENTS:
        await websocket.send(json.dumps({"error": "连接数已饱和"}))
        await websocket.close()
        return
    uid = "-1"
    try:
        # 先等待客户端发送UID注册, TODO 注册漏洞：未验证重复注册（允许UID劫持）
        register_msg = await websocket.recv()
        uid = json.loads(register_msg)['uid']
        connected_clients[uid] = {
            'ws': websocket,
            'last_active': time.time()
        }
        async for message in websocket:
            data = json.loads(message)
            logger.info(f"rcv_msg {data}")
            async with clients_lock:
                connected_clients[uid]['last_active'] = time.time()
            if data.get('type') == 'heartbeat':
                await websocket.send(json.dumps({
                    "type": "heartbeat_ack",
                    "seq": data.get('seq'),
                    "timestamp": time.time()
                }))
                continue
            if not all(key in data for key in ('uid', 'msg', 'to')):
                logger.warning(f"Invalid message format: {data}")
                continue
            uid = data['uid']
            msg = data['msg']
            to = data['to']
            logger.info(f"rcv_msg_from_client {uid}, {msg}")
            if not to:
                logger.info("no_msg_route_information")
                return
            if to in connected_clients:
                async with clients_lock:
                    await connected_clients[to]["ws"].send(json.dumps({
                        "type": "msg",
                        "from": uid,
                        "msg": msg,
                        "timestamp": time.time()
                    }))
            else:
                logger.error(f"msg route target {to} can't be engaged")
    except (asyncio.TimeoutError, ConnectionClosed):
        logger.warning(f"client {uid} disconnected")
    finally:
        logger.info("handler_finished")

async def check_timeout():
    while True:
        await asyncio.sleep(15)
        async with clients_lock:
            now = time.time()
            expired = [uid for uid, info in connected_clients.items()
                       if now - info['last_active'] > 30]  # 30秒无活动判定超时
            for uid in expired:
                await connected_clients[uid]['ws'].close()
                del connected_clients[uid]

async def start_server():
    async with serve(handler, "localhost", 18765):
        asyncio.create_task(check_timeout())
        await asyncio.Future()  # process blocked here

if __name__ == "__main__":
    asyncio.run(start_server())