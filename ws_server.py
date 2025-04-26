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

clients_lock = asyncio.Lock()
connected_clients = dict()


async def handler(websocket: WebSocketServerProtocol) -> None:
    """
    connection handler, to handle connected socket
    """
    uid = "-1"

    # 心跳检测协程
    async def heartbeat():
        while True:
            logger.info(f"connected_clients: {connected_clients.keys()}")
            await websocket.ping()
            await asyncio.sleep(10)  # 每10秒检测一次
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        # 先等待客户端发送UID注册
        register_msg = await websocket.recv()
        uid = json.loads(register_msg)['uid']
        connected_clients[uid] = websocket
        async for message in websocket:
            data = json.loads(message)
            logger.info(f"rcv_msg {data}")
            uid = data['uid']
            msg = data['msg']
            to = data['to']
            logger.info(f"rcv_msg_from_client {uid}, {msg}")
            if not to:
                logger.info("no_msg_route_information")
                return
            if to in connected_clients:
                async with clients_lock:
                    await connected_clients[to].send(json.dumps({
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
        if uid in connected_clients:
            logger.info(f"disconnect client {uid}")
            del connected_clients[uid]
        heartbeat_task.cancel()


async def start_server():
    async with serve(handler, "localhost", 18765):
        await asyncio.Future()  # blocked

if __name__ == "__main__":
    asyncio.run(start_server())