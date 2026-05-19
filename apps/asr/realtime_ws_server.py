# -*- encoding: utf-8 -*-
"""
实时语音转写 WebSocket 代理服务器。

用法：
    python apps/asr/realtime_ws_server.py
    python apps/asr/realtime_ws_server.py --port 19002 --bind 0.0.0.0

客户端协议：
  step 1 [客户端→服务端] JSON 配置消息（连接后首先发送）：
       {"wav_name": "mic", "audio_fs": 16000}

  step 2 [客户端→服务端] 持续发送二进制 PCM 音频数据 (16kHz, 16bit, 单声道)

  step 3 [服务端→客户端] 实时推送识别结果 JSON：
       {"text": "当前识别文本", "mode": "2pass-online", "is_final": false}

  step 4 [客户端→服务端] 发送结束信号（可选）：
       {"is_speaking": false}

  step 5 [服务端→客户端] 最终结果：
       {"text": "完整文本", "mode": "2pass-offline", "is_final": true}
  之后服务端关闭连接。

工作流程：
  客户端 WebSocket  <-->  本代理  <-->  FunASR WebSocket 服务
"""

import argparse
import asyncio
import json
import logging
import os
import ssl
import sys

import websockets
import yaml


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("realtime_ws_server")


def load_cfg(cfg_path="cfg.yml") -> dict:
    """加载 YAML 配置文件，读取 FunASR 服务地址。"""
    if not os.path.exists(cfg_path):
        print(f"[ERROR] 配置文件 {cfg_path} 不存在")
        sys.exit(1)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


class RealtimeASRProxy:
    """WebSocket 代理：客户端 ↔ FunASR 实时转写。"""

    def __init__(
        self,
        funasr_host: str,
        funasr_port: int,
        *,
        bind_host: str = "0.0.0.0",
        bind_port: int = 19001,
        chunk_size=None,
        chunk_interval: int = 10,
        encoder_chunk_look_back: int = 4,
        decoder_chunk_look_back: int = 0,
        mode: str = "2pass",
        use_itn: int = 1,
        ssl_enabled: bool = False,
    ):
        self.funasr_host = funasr_host
        self.funasr_port = funasr_port
        self.bind_host = bind_host
        self.bind_port = bind_port
        self.chunk_size = chunk_size or [5, 10, 5]
        self.chunk_interval = chunk_interval
        self.encoder_chunk_look_back = encoder_chunk_look_back
        self.decoder_chunk_look_back = decoder_chunk_look_back
        self.mode = mode
        self.use_itn = use_itn
        self.ssl_enabled = ssl_enabled

    # ------------------------------------------------------------------
    # 启动入口
    # ------------------------------------------------------------------

    def run(self):
        """启动服务器（阻塞）。"""
        asyncio.run(self._serve())

    async def _serve(self):
        logger.info(
            "服务启动: ws://%s:%s  →  FunASR %s:%s  (mode=%s, chunk_size=%s)",
            self.bind_host, self.bind_port,
            self.funasr_host, self.funasr_port,
            self.mode, self.chunk_size,
        )
        async with websockets.serve(
            self._handle_client,
            self.bind_host,
            self.bind_port,
            ping_interval=None,
        ):
            logger.info("监听中... 等待客户端连接")
            await asyncio.Future()  # 一直运行

    # ------------------------------------------------------------------
    # 客户端连接处理
    # ------------------------------------------------------------------

    async def _handle_client(self, client_ws):
        """处理一个客户端 WebSocket 连接。"""
        funasr_ws = None
        client_addr = client_ws.remote_address
        logger.info("[%s] 新客户端连接", client_addr)
        try:
            # ---- 1. 接收客户端配置消息 ----
            raw = await client_ws.recv()
            config = json.loads(raw) if isinstance(raw, str) else {}

            wav_name = config.get("wav_name", "realtime_audio")
            audio_fs = config.get("audio_fs", 16000)
            hotword_msg = config.get("hotwords", "")
            logger.info("[%s] 配置: wav_name=%s, audio_fs=%s", client_addr, wav_name, audio_fs)

            # ---- 2. 连接 FunASR ----
            funasr_ws = await self._connect_funasr()

            # ---- 3. 发送初始化消息给 FunASR ----
            init_msg = json.dumps({
                "mode": self.mode,
                "chunk_size": self.chunk_size,
                "chunk_interval": self.chunk_interval,
                "encoder_chunk_look_back": self.encoder_chunk_look_back,
                "decoder_chunk_look_back": self.decoder_chunk_look_back,
                "audio_fs": audio_fs,
                "wav_name": wav_name,
                "wav_format": "pcm",
                "is_speaking": True,
                "hotwords": hotword_msg,
                "itn": self.use_itn == 1,
            })
            await funasr_ws.send(init_msg)
            logger.info("[%s] 已连接 FunASR，开始转发", client_addr)

            # ---- 4. 并发双向转发 ----
            await asyncio.gather(
                self._relay_audio(client_ws, funasr_ws),
                self._relay_results(funasr_ws, client_ws),
            )

        except websockets.exceptions.ConnectionClosed:
            pass  # 正常断开
        except Exception as e:
            logger.error("[%s] 错误: %s", client_addr, e, exc_info=True)
            try:
                await client_ws.send(json.dumps({"error": str(e), "is_final": True}))
            except Exception:
                pass
        finally:
            if funasr_ws:
                await funasr_ws.close()
            logger.info("[%s] 连接关闭", client_addr)

    # ------------------------------------------------------------------
    # FunASR 连接
    # ------------------------------------------------------------------

    async def _connect_funasr(self):
        """建立到 FunASR 的 WebSocket 连接。"""
        if self.ssl_enabled:
            ssl_ctx = ssl.SSLContext()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            uri = f"wss://{self.funasr_host}:{self.funasr_port}"
        else:
            ssl_ctx = None
            uri = f"ws://{self.funasr_host}:{self.funasr_port}"

        return await websockets.connect(
            uri,
            subprotocols=["binary"],
            ping_interval=None,
            close_timeout=30,
            ssl=ssl_ctx,
        )

    # ------------------------------------------------------------------
    # 双向转发
    # ------------------------------------------------------------------

    @staticmethod
    async def _relay_audio(source, dest):
        """将客户端的音频数据转发给 FunASR。"""
        try:
            async for msg in source:
                if isinstance(msg, bytes):
                    await dest.send(msg)
                elif isinstance(msg, str):
                    data = json.loads(msg)
                    if not data.get("is_speaking", True):
                        await dest.send(json.dumps({"is_speaking": False}))
                        break
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            try:
                await dest.send(json.dumps({"is_speaking": False}))
            except Exception:
                pass

    @staticmethod
    async def _relay_results(source, dest):
        """将 FunASR 的识别结果转发给客户端。"""
        try:
            async for msg in source:
                result = json.loads(msg)
                payload = {
                    "text": result.get("text", ""),
                    "mode": result.get("mode", ""),
                    "is_final": result.get("is_final", False),
                    "timestamp": result.get("timestamp", ""),
                }
                await dest.send(json.dumps(payload))
                if payload["is_final"]:
                    break
        except websockets.exceptions.ConnectionClosed:
            pass


# ======================================================================
# 命令行入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="实时语音转写 WebSocket 代理")
    parser.add_argument("--port", type=int, default=19001, help="本服务监听端口 (默认: 19001)")
    parser.add_argument("--bind", type=str, default="0.0.0.0", help="本服务绑定地址 (默认: 0.0.0.0)")
    parser.add_argument("--cfg", type=str, default="cfg.yml", help="配置文件路径 (默认: cfg.yml)")
    parser.add_argument("--funasr-host", type=str, default=None, help="覆盖 cfg.yml 中的 funasr.host")
    parser.add_argument("--funasr-port", type=int, default=None, help="覆盖 cfg.yml 中的 funasr.port")
    parser.add_argument("--mode", type=str, default="2pass", choices=["2pass", "online", "offline"],
                        help="识别模式 (默认: 2pass)")
    parser.add_argument("--ssl", action="store_true", help="启用 SSL 连接 FunASR")
    args = parser.parse_args()

    # 加载配置
    cfg = load_cfg(args.cfg)
    funasr_cfg = cfg.get("funasr", {})
    funasr_host = args.funasr_host or funasr_cfg.get("host", "127.0.0.1")
    funasr_port = args.funasr_port or funasr_cfg.get("port", 10095)

    # 启动代理
    proxy = RealtimeASRProxy(
        funasr_host=funasr_host,
        funasr_port=funasr_port,
        bind_host=args.bind,
        bind_port=args.port,
        mode=args.mode,
        ssl_enabled=args.ssl,
    )
    proxy.run()


if __name__ == "__main__":
    main()
