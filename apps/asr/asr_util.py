#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sqlite3
import threading
import time
import uuid
import wave
from datetime import datetime
from pathlib import Path
import subprocess

import numpy as np
import sherpa_onnx

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

# 确保目录存在（asr_util 可独立于 app.py 使用）
for _d in (CONVERTED_DIR, RESULTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── VAD 配置 ───────────────────────────────────────────────
VAD_MODEL_PATH = os.environ.get(
    "ASR_VAD_MODEL",
    str(BASE_DIR / 'models' / 'silero_vad.onnx'),
)
MAX_SEGMENT_SECONDS = 300  # 5 分钟


# ── VAD 切分 ───────────────────────────────────────────────

def _build_vad_detector(sample_rate):
    """构建 sherpa-onnx VoiceActivityDetector。"""
    if not Path(VAD_MODEL_PATH).is_file():
        raise FileNotFoundError(f"VAD 模型文件不存在: {VAD_MODEL_PATH}")

    config = sherpa_onnx.VadModelConfig()
    config.silero_vad.model = VAD_MODEL_PATH
    config.silero_vad.threshold = 0.5
    config.silero_vad.min_silence_duration = 0.5  # 0.5 秒静音视为段边界
    config.silero_vad.min_speech_duration = 0.25  # 忽略 <0.25 秒的噪音
    config.silero_vad.max_speech_duration = MAX_SEGMENT_SECONDS  # 5 分钟上限
    config.sample_rate = sample_rate

    # buffer_size_in_seconds=30 可以避免大文件频繁扩容
    return sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)


def segment_wav_and_write(wav_path, output_dir):
    """对 WAV 文件做 VAD 切分并写入磁盘。

    流式处理：每次从 WAV 读 2 秒（VAD 判定边界的最小有效块），转 float32 后
    feed VAD，边出段边写盘。内存峰值仅 ~128KB，不受输入 WAV 总时长影响，
    支持 >12h 的大文件。

    关键：feed 块必须是 2 秒左右的小块，一次性喂大块会导致 VAD 内部
    is_speech 判定被 OR 合并，无法及时切段，circular buffer 持续膨胀 OOM。

    返回 list[(start_sec, dur_sec, seg_wav_path)]。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with wave.open(str(wav_path), 'rb') as wf:
        sr = wf.getframerate()
        total_frames = wf.getnframes()
        total_dur = total_frames / sr
    logger.info("vad_start, file=%s, duration=%.1fs",
                Path(wav_path).name, total_dur)

    vad = _build_vad_detector(sr)
    segment_paths = []

    FEED_SECONDS = 5  # 5 秒块 feed，足够检测 0.5s 静音边界，又不会过大导致 buffer 膨胀
    feed_frames = FEED_SECONDS * sr

    with wave.open(str(wav_path), 'rb') as wf:
        while True:
            pcm = wf.readframes(feed_frames)
            if not pcm:
                break
            chunk = np.frombuffer(pcm, dtype=np.int16).astype(np.float32, copy=False)
            del pcm
            chunk /= 32768.0
            vad.accept_waveform(chunk)
            del chunk
            _drain_vad_segments(vad, sr, output_dir, segment_paths)

    vad.flush()
    _drain_vad_segments(vad, sr, output_dir, segment_paths)

    total_speech = sum(p[1] for p in segment_paths)
    logger.info("vad_done, segments=%d, total_speech=%.1fs=%.1fmin",
                len(segment_paths), total_speech, total_speech / 60)
    return segment_paths


def _drain_vad_segments(vad, sr, output_dir, segment_paths):
    """Pop 所有已完成的 VAD 段，写入 WAV，追加元数据到 segment_paths。"""
    while not vad.empty():
        seg = vad.front
        dur = len(seg.samples) / sr
        start_sec = seg.start / sr if seg.start >= 0 else 0.0
        idx = len(segment_paths)
        seg_path = output_dir / f"seg_{idx:04d}.wav"
        write_segment_wav(seg.samples, sr, seg_path)
        segment_paths.append((start_sec, dur, seg_path))
        vad.pop()


def write_segment_wav(samples_float32, sample_rate, output_path):
    """将 float32 音频（numpy 或 pybind11 vector）写入 16-bit mono WAV 文件。"""
    if not isinstance(samples_float32, np.ndarray):
        samples_float32 = np.array(samples_float32, dtype=np.float32)
    # 原位缩放
    np.multiply(samples_float32, 32767.0, out=samples_float32)
    np.clip(samples_float32, -32768.0, 32767.0, out=samples_float32)
    int16_samples = samples_float32.astype(np.int16)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_samples.tobytes())


def _get_wav_duration_secs(wav_path):
    """读取 WAV 文件的音频时长（秒）。"""
    with wave.open(wav_path, 'rb') as wf:
        return wf.getnframes() / wf.getframerate()


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


def run_asr_transmit(wav_path, output_dir, asr_host, asr_port, task_id=None,
                     segment_progress_cb=None):
    """运行 FunASR 识别（直接调用 wss_client）。

    segment_progress_cb(inner_pct) 用于段内发送进度（0-100），可选。
    """
    from apps.asr.wss_client import run_offline_asr

    wav_size_mb = Path(wav_path).stat().st_size / (1024 * 1024)
    logger.info(
        "%s, call_funasr_server, host=%s:%s, wav_size=%.1fMB, output_dir=%s",
        task_id, asr_host, asr_port, wav_size_mb, output_dir,
    )

    def _progress(pct):
        if segment_progress_cb:
            segment_progress_cb(pct)

    def _sent():
        if task_id:
            logger.info("%s, segment_sent_finished, waiting_for_funasr_inference", task_id)

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
    logger.info("%s, funasr_transmit_finished", task_id)


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
                total_segments INTEGER DEFAULT 0,
                completed_segments INTEGER DEFAULT 0,
                segment_results TEXT DEFAULT '[]',
                audio_duration_secs REAL DEFAULT 0,
                processing_time_secs REAL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
        """)
        conn.commit()
        conn.close()

    def create_task(self, original_filename, original_path, converted_path, uid=0):
        """创建新任务，返回 task_id（毫秒时间戳，并发时自增防止碰撞）。"""
        with self._lock:
            base = str(int(time.time() * 1000))
            # 并发保护：同一毫秒内的第二个任务 +1ms
            tid = base
            n = 0
            while self.get_task(tid) is not None:
                n += 1
                tid = str(int(time.time() * 1000) + n)
            task_id = tid

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
        allowed = {
            'status', 'result_text', 'progress', 'error', 'converted_path', 'original_path',
            'total_segments', 'completed_segments', 'segment_results',
        }
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

# 用于防止同一个残留任务被重复拉起
_resume_lock = threading.Lock()
_resumed_task_ids = set()


def process_audio_async(task_id, input_path, asr_host, asr_port):
    """异步处理音频文件（VAD 分段 + 逐段 ASR + 断点续转写）。"""
    _process_audio_impl(task_id, input_path, asr_host, asr_port)


def resume_incomplete_tasks(asr_host, asr_port):
    """启动时检查 DB 中未完成的任务，重新拉起处理线程。"""
    with _resume_lock:
        conn = asr_tasks._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM asr_tasks "
                "WHERE status IN ('converting','processing') "
                "  AND completed_segments < total_segments "
                "ORDER BY created_at ASC",
            ).fetchall()
        finally:
            conn.close()

        resumed = 0
        for row in rows:
            task = dict(row)
            tid = task['task_id']
            if tid in _resumed_task_ids:
                continue
            _resumed_task_ids.add(tid)

            # 找到对应的原始文件路径
            wav_path = (task.get('converted_path') or task.get('original_path') or '')
            if not wav_path or not Path(wav_path).exists():
                logger.warning("resume_skip, task=%s, wav_not_found=%s", tid, wav_path)
                asr_tasks.update_task(tid, status='failed', error='音频文件丢失，无法恢复')
                continue

            logger.info(
                "resume_task, task=%s, file=%s, done=%d/%d",
                tid, task['original_filename'],
                task.get('completed_segments', 0), task.get('total_segments', 0),
            )
            t = threading.Thread(
                target=_process_audio_impl,
                args=(tid, Path(wav_path), asr_host, asr_port),
            )
            t.daemon = True
            t.start()
            resumed += 1

        if resumed:
            logger.info("resume_incomplete_tasks: resumed %d tasks", resumed)


def _process_audio_impl(task_id, input_path, asr_host, asr_port):
    """处理音频的实际实现（支持从断点恢复）。"""
    input_path = Path(input_path)
    original_name = input_path.name
    try:
        process_start = time.time()
        file_size_mb = input_path.stat().st_size / (1024 * 1024)
        logger.info(
            "%s, === START task, file=%s, size=%.1fMB ===",
            task_id, original_name, file_size_mb,
        )

        # 加载已有进度（断点续转写）
        task = asr_tasks.get_task(task_id)
        total_segments = task.get('total_segments', 0)
        completed_segments = task.get('completed_segments', 0)
        segment_results = json.loads(task.get('segment_results') or '[]')

        # ── Step 1: 如果还没做格式转换，先转 WAV ──
        wav_path = input_path
        if input_path.suffix.lower() != '.wav':
            asr_tasks.update_task(task_id, status='converting')
            logger.info("%s, step1_converting_format", task_id)
            wav_filename = f"{input_path.stem}_{uuid.uuid4().hex[:8]}.wav"
            wav_path = CONVERTED_DIR / wav_filename
            convert_to_wav(str(input_path), wav_path)
            logger.info("%s, step1_done, converted to 16kHz mono WAV", task_id)
            asr_tasks.update_task(task_id, converted_path=str(wav_path))

        # ── Step 2: VAD 切分（仅在首次或无段数时执行） ──
        segments_dir = CONVERTED_DIR / task_id
        if total_segments <= 0:
            asr_tasks.update_task(task_id, status='processing', progress=0)
            logger.info("%s, step2_vad_segmentation", task_id)

            segment_meta = segment_wav_and_write(str(wav_path), segments_dir)
            total_segments = len(segment_meta)
            if total_segments == 0:
                raise Exception("VAD 未检测到任何语音段")

            asr_tasks.update_task(task_id, total_segments=total_segments)
            logger.info(
                "%s, step2_done, total_segments=%d, seg_wavs written to %s",
                task_id, total_segments, segments_dir,
            )

            # 记录音频时长
            audio_dur = _get_wav_duration_secs(str(wav_path))
            asr_tasks.update_task(task_id, audio_duration_secs=audio_dur)
            logger.info("%s, audio_duration=%.1fs", task_id, audio_dur)
        else:
            logger.info(
                "%s, step2_skip_vad, already segmented: %d segments, resume from #%d",
                task_id, total_segments, completed_segments,
            )

        # ── Step 3: 逐段提交 FunASR ──
        result_dir = RESULTS_DIR / task_id
        result_dir.mkdir(exist_ok=True)

        for i in range(completed_segments, total_segments):
            seg_path = segments_dir / f"seg_{i:04d}.wav"
            if not seg_path.exists():
                raise Exception(f"段文件丢失: {seg_path}")

            seg_dur = seg_path.stat().st_size / (16000 * 2)  # 粗略估算
            logger.info(
                "%s, step3_segment[%d/%d], dur=~%.1fs",
                task_id, i + 1, total_segments, seg_dur,
            )

            seg_out_dir = result_dir / f"seg_{i:04d}"
            seg_out_dir.mkdir(parents=True, exist_ok=True)

            run_asr_transmit(seg_path, seg_out_dir, asr_host, asr_port, task_id=task_id)

            # 读取单段结果
            seg_text = ""
            for text_file in sorted(seg_out_dir.glob("text.*")):
                raw = text_file.read_text(encoding='utf-8').strip()
                seg_text += extract_text_from_result(raw) + "\n"

            seg_text = seg_text.strip()
            segment_results.append(seg_text)
            completed_segments = i + 1
            progress = int(completed_segments / total_segments * 100)

            # 每段完成后立即持久化（断点续转写的关键）
            asr_tasks.update_task(
                task_id,
                completed_segments=completed_segments,
                progress=progress,
                segment_results=json.dumps(segment_results, ensure_ascii=False),
            )
            logger.info(
                "%s, step3_segment_done[%d/%d], progress=%d%%, text_len=%d",
                task_id, completed_segments, total_segments, progress, len(seg_text),
            )

        # ── Step 4: 合并结果 ──
        logger.info("%s, step4_merging_results", task_id)
        full_text = "\n".join(seg for seg in segment_results if seg)
        processing_secs = round(time.time() - process_start, 1)
        asr_tasks.update_task(
            task_id,
            status='completed',
            result_text=full_text,
            progress=100,
            processing_time_secs=processing_secs,
        )
        logger.info(
            "%s, === DONE, status=completed, text_length=%d, processing_time=%.1fs, file=%s ===",
            task_id, len(full_text), processing_secs, original_name,
        )

        # 保存下载文件
        result_file = RESULTS_DIR / f"{task_id}.txt"
        result_file.write_text(full_text, encoding='utf-8')

        # 清理临时 segment WAV（保留合并结果）
        if segments_dir.exists():
            import shutil
            try:
                shutil.rmtree(segments_dir)
            except Exception:
                pass

        # 清理上传的原始文件
        if input_path.exists() and input_path.suffix.lower() != '.wav':
            input_path.unlink()

    except Exception as e:
        asr_tasks.update_task(task_id, status='failed', error=str(e))
        logger.error(
            "%s, === FAILED, error=%s, file=%s ===",
            task_id, e, original_name,
        )