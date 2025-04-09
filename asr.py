#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging.config

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)

def test():
    logger.info("test")




if __name__ == "__main__":
    """
    https://www.modelscope.cn/models/iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch
    """
    logger.info("test")