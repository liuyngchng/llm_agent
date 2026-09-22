#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
import subprocess

import logging.config

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO, format=LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
CONVERTED_DIR = BASE_DIR / 'converted'
RESULTS_DIR = BASE_DIR / 'results'
DB_PATH = BASE_DIR / 'asr.db'


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


def run_asr_transmit(wav_path, output_dir, asr_host, asr_port, task_id=None):
    """运行 FunASR 识别（直接调用 wss_client，不再通过子进程）"""
    from apps.asr.wss_client import run_offline_asr

    wav_size_mb = Path(wav_path).stat().st_size / (1024 * 1024)
    logger.info(f"{task_id}, call_funasr_server, host={asr_host}:{asr_port}, wav_size={wav_size_mb:.1f}MB, output_dir={output_dir}")

    _last_logged_pct = [0]  # 用列表避免 nonlocal 问题

    def _progress(pct):
        if task_id:
            asr_tasks.update_task(task_id, progress=pct)
        # 每 20% 记录一次进度日志
        if pct - _last_logged_pct[0] >= 20 or pct >= 100:
            _last_logged_pct[0] = pct
            logger.info(f"{task_id}, asr_progress={pct}%")

    def _sent():
        # 音频全部发送完毕，进入服务端推理阶段
        if task_id:
            asr_tasks.update_task(task_id, status='transcribing')
            logger.info(f"{task_id}, all_chunks_sent, waiting_for_funasr_inference")

    run_offline_asr(
        audio_in=str(wav_path),
        output_dir=str(output_dir),
        host=asr_host,
        port=asr_port,
        ssl=0,
        mode='offline',
        use_itn=1,
        progress_callback=_progress,
        sent_callback=_sent,
    )
    logger.info(f"{task_id}, funasr_transmit_finished")


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


class ASRTaskStore:
    """SQLite-backed ASR 任务管理"""

    def __init__(self, db_path):
        self._lock = threading.Lock()
        self.db_path = str(db_path)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS asr_tasks (
                task_id TEXT PRIMARY KEY,
                uid INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                original_path TEXT NOT NULL DEFAULT '',
                converted_path TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'converting',
                result_text TEXT,
                progress INTEGER DEFAULT 0,
                error TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
        """)
        conn.commit()
        conn.close()

    def create_task(self, original_filename, original_path, converted_path, uid=0):
        """创建新任务，返回 task_id"""
        task_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO asr_tasks (task_id, uid, original_filename, original_path, converted_path, status) "
                "VALUES (?, ?, ?, ?, ?, 'converting')",
                (task_id, uid, original_filename, str(original_path), str(converted_path) if converted_path else ''),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info(f"create_task {task_id}, uid={uid}, file={original_filename}")
        return task_id

    def update_task(self, task_id, **kwargs):
        """更新任务字段"""
        allowed = {'status', 'result_text', 'progress', 'error', 'converted_path', 'original_path'}
        fields = {}
        for k, v in kwargs.items():
            if k in allowed:
                fields[k] = v

        if not fields:
            return

        fields['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        set_clause = ', '.join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [task_id]

        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE asr_tasks SET {set_clause} WHERE task_id = ?", values)
            conn.commit()
        finally:
            conn.close()

    def get_task(self, task_id):
        """获取单个任务"""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM asr_tasks WHERE task_id = ?", (task_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_user_tasks(self, uid, limit=100):
        """获取用户的任务列表，按创建时间倒序"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM asr_tasks WHERE uid = ? ORDER BY created_at DESC LIMIT ?",
                (uid, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_task(self, task_id):
        """删除任务及其临时文件"""
        task = self.get_task(task_id)
        if not task:
            return

        # 清理临时文件
        for key in ('original_path', 'converted_path'):
            path = task.get(key)
            if path and Path(path).exists():
                try:
                    Path(path).unlink()
                except Exception:
                    pass

        # 清理结果目录
        result_dir = RESULTS_DIR / task_id
        if result_dir.exists():
            import shutil
            try:
                shutil.rmtree(result_dir)
            except Exception:
                pass

        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM asr_tasks WHERE task_id = ?", (task_id,))
            conn.commit()
        finally:
            conn.close()
        logger.info(f"delete_task {task_id}")


# 全局实例
asr_tasks = ASRTaskStore(DB_PATH)


def process_audio_async(task_id, input_path, asr_host, asr_port):
    """异步处理音频文件"""
    original_name = Path(input_path).name
    try:
        file_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
        logger.info(f"{task_id}, === START task, file={original_name}, size={file_size_mb:.1f}MB ===")

        # 更新状态：转换中
        asr_tasks.update_task(task_id, status='converting')
        logger.info(f"{task_id}, step1_converting_format, file={original_name}")

        # 生成输出路径
        original_filename = Path(input_path).stem
        wav_filename = f"{original_filename}_{uuid.uuid4().hex[:8]}.wav"
        wav_path = CONVERTED_DIR / wav_filename
        abs_path = os.path.abspath(wav_path)

        # 1. 转换为 WAV
        convert_to_wav(input_path, wav_path)
        logger.info(f"{task_id}, step1_done, converted to 16kHz mono WAV")
        asr_tasks.update_task(task_id, converted_path=str(wav_path), status='processing')

        # 2. 执行 ASR 识别
        asr_tasks.update_task(task_id, progress=0)
        result_dir = RESULTS_DIR / task_id
        result_dir.mkdir(exist_ok=True)
        logger.info(f"{task_id}, step2_start_asr, sending to FunASR...")
        run_asr_transmit(wav_path, result_dir, asr_host, asr_port, task_id=task_id)

        # 3. 获取识别结果
        result_content = get_recognition_result(result_dir)
        if result_content:
            text = extract_text_from_result(result_content)
            text_len = len(text)
            asr_tasks.update_task(
                task_id,
                status='completed',
                result_text=text,
                progress=100,
            )
            # 保存结果到文件供下载
            result_file = RESULTS_DIR / f"{task_id}.txt"
            with open(result_file, 'w', encoding='utf-8') as f:
                f.write(text)
            logger.info(f"{task_id}, === DONE, status=completed, text_length={text_len}, file={original_name} ===")
        else:
            raise Exception("未获取到识别结果")

        # 清理上传的原始文件
        if Path(input_path).exists():
            Path(input_path).unlink()

    except Exception as e:
        asr_tasks.update_task(task_id, status='failed', error=str(e))
        logger.error(f"{task_id}, === FAILED, error={e}, file={original_name} ===")