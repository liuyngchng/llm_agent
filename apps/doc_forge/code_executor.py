#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python code extraction and execution engine for document processing."""

import os
import re
import subprocess
import tempfile
import logging.config
import time

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO, format=LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

CODE_EXEC_TIMEOUT = 120  # seconds


def extract_python_blocks(text: str) -> list[str]:
    """Extract python code blocks from markdown text."""
    pattern = r'```python\s*\n(.*?)\n```'
    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches if m.strip()]


def find_new_files(before_files: set, directory: str) -> list[str]:
    """Find newly created files in a directory after code execution.

    Only returns files that actually exist on disk (verified via os.path.isfile).
    """
    if not os.path.exists(directory):
        return []
    after_files = set(os.listdir(directory))
    new_files = after_files - before_files
    # 仅返回确实存在的文件，过滤掉可能的临时文件或目录
    verified = []
    for f in sorted(new_files):
        full_path = os.path.join(directory, f)
        if os.path.isfile(full_path):
            verified.append(f)
        else:
            logger.warning(f"find_new_files 跳过不存在的文件: {full_path}")
    return verified


def snapshot_dir(directory: str) -> set:
    """Take a snapshot of files in a directory."""
    if not os.path.exists(directory):
        return set()
    return set(os.listdir(directory))


def execute_code(code: str, output_dir: str = "output_doc",
                 upload_dir: str = "upload_doc", timeout: int = CODE_EXEC_TIMEOUT) -> dict:
    """Execute Python code in a subprocess and return results.

    Returns:
        dict with keys: success, stdout, stderr, error, new_files
    """
    # Resolve to absolute paths relative to this file's directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(os.path.dirname(base_dir))  # repo root for common/ imports
    output_dir = os.path.join(base_dir, output_dir) if not os.path.isabs(output_dir) else output_dir
    upload_dir = os.path.join(base_dir, upload_dir) if not os.path.isabs(upload_dir) else upload_dir

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(upload_dir, exist_ok=True)

    before_snapshot = snapshot_dir(output_dir)

    # Write code to a temp file so we get proper tracebacks
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix='.py', prefix='docproc_')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            # Set up working directory and paths for the script
            f.write(f"""
import sys
import os
sys.path.insert(0, {workspace_root!r})
sys.path.insert(0, {base_dir!r})
os.chdir({output_dir!r})
UPLOAD_DIR = {upload_dir!r}
OUTPUT_DIR = {output_dir!r}
""")
            f.write(code)

        result = subprocess.run(
            ['python3', tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=base_dir,
            env={**os.environ, 'PYTHONPATH': base_dir}
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # Check for newly generated files
        new_files = find_new_files(before_snapshot, output_dir)

        success = result.returncode == 0

        logger.info(f"code_execution: success={success}, returncode={result.returncode}, "
                    f"stdout_len={len(stdout)}, stderr_len={len(stderr)}, new_files={new_files}")

        return {
            'success': success,
            'stdout': stdout,
            'stderr': stderr,
            'returncode': result.returncode,
            'new_files': new_files,
        }

    except subprocess.TimeoutExpired:
        logger.error(f"Code execution timed out after {timeout}s")
        return {
            'success': False,
            'stdout': '',
            'stderr': f'Script execution timed out after {timeout} seconds.',
            'returncode': -1,
            'new_files': [],
        }
    except Exception as e:
        logger.error(f"Code execution error: {str(e)}")
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1,
            'new_files': [],
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
