#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install qrcode[pil] lxml
"""
import logging.config
import qrcode
import qrcode.image.svg
from io import BytesIO

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


def get_qr(address: str) -> str:
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(address, image_factory=factory)

    with BytesIO() as buffer:
        img.save(buffer)
        return buffer.getvalue().decode('utf-8')





if __name__ == "__main__":
    my_qr = get_qr("https://m.baidu.com")
    logger.info(f"my_qr:\n{my_qr}\n")

    my_qr = get_qr("http://klrq.cnpc.com.cn/klrq/")
    logger.info(f"my_qr:\n{my_qr}\n")

    my_qr = get_qr("https://mp.weixin.qq.com/s/wO5Q0_caUEyIcOsPQ-411Q")
    logger.info(f"my_qr:\n{my_qr}\n")