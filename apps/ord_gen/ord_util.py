#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import json
import logging.config

import torch
from langchain_core.prompts import ChatPromptTemplate

from common import cfg_util, agt_util
from common.cm_utils import extract_md_content, rmv_think_block

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

