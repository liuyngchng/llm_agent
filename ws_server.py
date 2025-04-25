#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from websockets import serve
import asyncio
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

async def handler(websocket):
    async for message in websocket:
        logger.info(f"收到消息: {message}")
        await websocket.send(f"服务器回复: {message}")

async def start_server():
    async with serve(handler, "localhost", 18765):
        await asyncio.Future()  # blocked

if __name__ == "__main__":
    asyncio.run(start_server())