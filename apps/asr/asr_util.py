#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import uuid
from datetime import datetime
from pathlib import Path
import os
import subprocess

import logging.config


log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
CONVERTED_DIR = BASE_DIR / 'converted'
RESULTS_DIR = BASE_DIR / 'results'

def convert_to_wav(input_path, output_path):
    """使用 ffmpeg 将音频转换为 WAV 格式"""
    cmd = [
        'ffmpeg',
        '-i', str(input_path),
        '-acodec', 'pcm_s16le',  # PCM 16bit
        '-ar', '16000',  # 16kHz 采样率
        '-ac', '1',  # 单声道
        '-y',  # 覆盖输出文件
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"FFmpeg 转换失败: {result.stderr}")

    return output_path


def run_asr_recognition(wav_path, output_dir, asr_host, asr_port):
    """运行 FunASR 识别"""
    # 使用与之前相同的命令
    cmd = [
        'python', './wss_client.py',
        '--host', asr_host,
        '--port', str(asr_port),
        '--ssl', '0',
        '--mode', 'offline',
        '--audio_in', str(wav_path),
        '--output_dir', str(output_dir)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)

    if result.returncode != 0:
        raise Exception(f"ASR 识别失败: {result.stderr}")

    return result


def get_recognition_result(result_dir, file_prefix='text.0_0'):
    """获取识别结果"""
    result_file = Path(result_dir) / file_prefix
    if result_file.exists():
        with open(result_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        return content
    return None


def extract_text_from_result(result_content):
    """从结果中提取纯文本（去掉时间戳）"""
    if not result_content:
        return ""

    # 格式: "文件名\t文本\t时间戳" 或 "文件名\t文本"
    parts = result_content.split('\t')
    if len(parts) >= 2:
        return parts[1]
    return result_content


class ASRTask:
    """ASR 任务管理类"""

    def __init__(self):
        self.tasks = {}

    def create_task(self, original_filename, original_path, converted_path):
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            'id': task_id,
            'original_filename': original_filename,
            'original_path': original_path,
            'converted_path': converted_path,
            'status': 'converting',  # converting, processing, completed, failed
            'result_text': None,
            'timestamp': datetime.now(),
            'error': None
        }
        return task_id

    def update_task(self, task_id, **kwargs):
        if task_id in self.tasks:
            self.tasks[task_id].update(kwargs)

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def delete_task(self, task_id):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            # 清理临时文件
            for path in [task.get('original_path'), task.get('converted_path')]:
                if path and Path(path).exists():
                    try:
                        Path(path).unlink()
                    except:
                        pass
            del self.tasks[task_id]


asr_tasks = ASRTask()


def process_audio_async(task_id, input_path):
    """异步处理音频文件"""
    try:
        # 更新状态：转换中
        asr_tasks.update_task(task_id, status='converting')

        # 生成输出路径
        original_filename = Path(input_path).stem
        wav_filename = f"{original_filename}_{uuid.uuid4().hex[:8]}.wav"
        wav_path = CONVERTED_DIR / wav_filename

        # 1. 转换为 WAV
        convert_to_wav(input_path, wav_path)
        asr_tasks.update_task(task_id, converted_path=str(wav_path), status='processing')

        # 2. 执行 ASR 识别
        result_dir = RESULTS_DIR / task_id
        result_dir.mkdir(exist_ok=True)

        run_asr_recognition(wav_path, result_dir)

        # 3. 获取识别结果
        result_content = get_recognition_result(result_dir)
        if result_content:
            text = extract_text_from_result(result_content)
            asr_tasks.update_task(
                task_id,
                status='completed',
                result_text=text,
                full_result=result_content
            )
        else:
            raise Exception("未获取到识别结果")

        # 可选：保存结果到文件供下载
        result_file = RESULTS_DIR / f"{task_id}.txt"
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(text)

        # 清理临时文件
        if Path(input_path).exists():
            Path(input_path).unlink()

    except Exception as e:
        asr_tasks.update_task(task_id, status='failed', error=str(e))