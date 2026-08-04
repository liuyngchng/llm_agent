#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流执行引擎 — 对标 Go 版本 internal/engine/
包含：模板变量解析、意图分类器（多级）、DAG 执行引擎。
"""
import hashlib
import json
import logging
import os
import re
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional, Generator

logger = logging.getLogger(__name__)

# ============================================================
# 模板变量系统（对标 Go internal/engine/template.go）
# ============================================================

# 变量模式：支持 {{var}} 和 {{sys.xxx}} 带点号变量名
_VAR_PATTERN = re.compile(r'\{\{(\w+(?:\.\w+)*)\}\}')

# 合法系统变量白名单
VALID_SYS_VARS = {
    "sys.user_query": "用户当前问题",
    "sys.history": "历史对话记录",
    "sys.cur_date": "当前日期 (YYYY-MM-DD)",
    "sys.cur_week": "当前星期几（中文）",
    "sys.kb_context": "知识库检索结果（由智能体绑定的知识库检索得出）",
    "sys.intent": "意图分类结果（如有分类器）",
}

WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"]


def get_weekday_cn(d: int) -> str:
    """返回中文星期"""
    return WEEKDAYS[d] if 0 <= d <= 6 else ""


def get_system_vars() -> list[dict]:
    """返回所有可用的系统变量列表（供前端/第三方调用）"""
    return [{"name": name, "description": desc} for name, desc in VALID_SYS_VARS.items()]


def validate_template_vars(tmpl: str) -> list[str]:
    """校验模板中引用的系统变量是否合法。
    sys. 前缀的变量必须在白名单中，否则返回非法变量名列表。
    非 sys. 前缀的变量不校验，留给运行时解析。
    """
    matches = _VAR_PATTERN.findall(tmpl)
    seen = set()
    invalid = []
    for var_name in matches:
        if var_name in seen:
            continue
        seen.add(var_name)
        if var_name.startswith("sys."):
            if var_name not in VALID_SYS_VARS:
                invalid.append(var_name)
    return invalid


def resolve_template(tmpl: str, vars_dict: dict[str, str]) -> str:
    """替换模板中的 {{var}} 占位符。

    内置系统变量（sys. 前缀）：
      {{sys.user_query}} - 用户原始问题
      {{sys.history}}    - 历史对话记录
      {{sys.cur_date}}   - 当前日期 (YYYY-MM-DD)
      {{sys.cur_week}}   - 当前星期几（中文）
      {{sys.kb_context}} - 知识库检索结果
      {{sys.intent}}     - 意图分类结果

    兼容旧版变量名（无 sys. 前缀）：
      {{user_query}} {{history}} {{cur_date}} {{cur_week}} {{intent}}

    自定义变量来自上游节点的 OutputVar 和节点 ID。
    """
    def _replace(match):
        key = match.group(1)  # 去掉 {{ 和 }}
        return vars_dict.get(key, match.group(0))
    return _VAR_PATTERN.sub(_replace, tmpl)


def format_history(messages: list[dict]) -> str:
    """格式化历史消息为字符串"""
    if not messages:
        return "（无历史对话）"
    lines = []
    for msg in messages:
        if msg.get("role") == "user":
            lines.append(f"用户：{msg['content']}")
        else:
            lines.append(f"机器人：{msg['content']}")
    return "\n".join(lines)


# ============================================================
# FastText 意图分类器（对标 Go internal/fasttext/predictor.go）
# ============================================================

CONFIDENCE_THRESHOLD = 0.5
DEFAULT_WORK_DIR = "./dt/ft"

# 与燃气业务无关的输入样本，训练模型拒绝无关请求
NONE_SAMPLES = [
    "今天天气真好", "明天会下雨吗", "附近有什么好吃的",
    "帮我写首诗", "讲个笑话", "几点了",
    "你是谁", "你会做什么", "你好啊",
    "播放音乐", "设置闹钟", "帮我查快递",
    "翻译一下", "什么是人工智能", "怎么做红烧肉",
    "股票涨了", "最近有什么电影",
]


class FastTextPredictor:
    """fastText 意图分类器。
    从类别关键词+描述自动生成训练数据，训练模型，执行预测。
    """

    def __init__(self, work_dir: str = DEFAULT_WORK_DIR):
        self._lock = threading.Lock()
        self.work_dir = work_dir
        self.model_hash = ""  # 当前已训练模型的类别 hash
        os.makedirs(work_dir, exist_ok=True)

    def train(self, categories: list[dict], prompt: str = "") -> bool:
        """确保 fastText 模型可用。

        模型已训练好（磁盘上存在 model.ftz）时直接返回 True，不重新训练。
        只有 model.ftz 缺失时才执行训练（首次部署的兜底）。
        返回 True 表示模型可用或训练成功。
        """
        model_path = os.path.join(self.work_dir, "model.ftz")
        if os.path.exists(model_path):
            return True  # 模型已存在，直接加载使用

        hash_val = _hash_categories(categories, prompt)
        if hash_val == self.model_hash:
            return True  # 类别未变，无需重新训练

        with self._lock:
            # 双重检查
            if hash_val == self.model_hash:
                return True

            train_path = os.path.join(self.work_dir, "train.txt")
            model_path = os.path.join(self.work_dir, "model.ftz")

            try:
                _generate_train_data(train_path, categories)
                _train_model(train_path, model_path)
                self.model_hash = hash_val
                logger.info("fastText 模型训练完成: categories=%d, model=%s",
                            len(categories), model_path)
                return True
            except Exception as e:
                logger.warning("fastText 训练失败: %s", e)
                return False

    def predict(self, query: str) -> Optional[dict]:
        """预测用户 query 的意图类别。
        返回 {"label": str, "confidence": float} 或 None。
        如果预测结果是 "none"（无关输入），视为不匹配返回 None。
        """
        model_path = os.path.join(self.work_dir, "model.ftz")
        if not os.path.exists(model_path):
            return None

        tokens = _tokenize(query)

        try:
            # 调用 fasttext predict-prob
            result = subprocess.run(
                ["fasttext", "predict-prob", model_path, "-", "1"],
                input=tokens + "\n",
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning("fastText predict 失败: %s", result.stderr.strip())
                return None

            output = result.stdout.strip()
            parsed = _parse_predict_output(output)
            if not parsed:
                return None

            label = parsed["label"]
            if label == "none":
                logger.info("fastText 分类为 none（无关输入）: confidence=%.4f, query=%s",
                            parsed["confidence"], query[:50])
                return None

            return parsed
        except FileNotFoundError:
            logger.warning("fasttext CLI 未安装，跳过 fastText 分类层")
            return None
        except Exception as e:
            logger.warning("fastText predict 异常: %s", e)
            return None

    def is_trained(self) -> bool:
        """判断模型是否已训练"""
        return os.path.exists(os.path.join(self.work_dir, "model.ftz"))


def _tokenize(s: str) -> str:
    """按字切分中文文本（空格分隔每个字符）"""
    return " ".join(s)


def _generate_train_data(path: str, categories: list[dict]):
    """从类别定义生成训练数据"""
    with open(path, "w", encoding="utf-8") as f:
        for cat in categories:
            label = cat.get("name", "")
            # 关键词作为训练样本
            for kw in cat.get("keywords", []):
                f.write(f"__label__{label} {_tokenize(kw)}\n")
            # 描述作为训练样本
            desc = cat.get("description", "").strip()
            if desc:
                f.write(f"__label__{label} {_tokenize(desc)}\n")

        # none 类别：教模型拒绝不相关的输入
        for s in NONE_SAMPLES:
            f.write(f"__label__none {_tokenize(s)}\n")


def _train_model(train_path: str, model_path: str):
    """调用 fastText CLI 训练并量化模型"""
    output_prefix = model_path.replace(".ftz", "")

    # 第一步：训练
    cmd_train = [
        "fasttext", "supervised",
        "-input", train_path,
        "-output", output_prefix,
        "-epoch", "200",
        "-lr", "0.8",
        "-wordNgrams", "3",
        "-dim", "50",
        "-minCount", "1",
    ]
    result = subprocess.run(cmd_train, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"fasttext supervised 失败: {result.stderr.strip()}")

    # 第二步：量化压缩
    cmd_quant = [
        "fasttext", "quantize",
        "-input", train_path,
        "-output", output_prefix,
        "-qnorm",
        "-retrain",
        "-epoch", "25",
        "-cutoff", "50000",
    ]
    result = subprocess.run(cmd_quant, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"fasttext quantize 失败: {result.stderr.strip()}")

    if not os.path.exists(model_path):
        raise RuntimeError(f"模型文件未生成: {model_path}")

    # 清理未量化的 .bin 和 .vec 文件
    for ext in [".bin", ".vec"]:
        p = output_prefix + ext
        if os.path.exists(p):
            os.remove(p)


def _parse_predict_output(output: str) -> Optional[dict]:
    """解析 fasttext predict-prob 输出: "__label__xxx 0.999876" """
    output = output.strip()
    if not output:
        return None

    parts = output.split()
    if len(parts) < 2:
        return None

    label = parts[0]
    if label.startswith("__label__"):
        label = label[len("__label__"):]
    else:
        return None

    try:
        confidence = float(parts[1])
    except ValueError:
        return None

    return {"label": label, "confidence": confidence}


def _hash_categories(categories: list[dict], prompt: str) -> str:
    """基于类别配置生成 hash，用于检测变更"""
    parts = [prompt, "|"]
    for cat in categories:
        parts.append(cat.get("name", ""))
        parts.append(":")
        parts.append(cat.get("description", ""))
        parts.append(":")
        parts.append(",".join(cat.get("keywords", [])))
        parts.append(";")
    return hashlib.md5("".join(parts).encode()).hexdigest()


# ============================================================
# 意图分类器（对标 Go internal/engine/classifier.go）
# ============================================================

# 语义匹配的相似度阈值
SEMANTIC_THRESHOLD = 0.6

# 类别向量缓存
_cat_embedding_cache = {}  # key -> list of {"name": str, "vector": list[float]}
_cache_lock = threading.Lock()


class TierResult:
    """单层分类结果"""
    def __init__(self, name: str, matched: bool = False, result: str = "",
                 score: float = 0.0, elapsed: int = 0, skipped: bool = False):
        self.name = name
        self.matched = matched
        self.result = result
        self.score = score
        self.elapsed = elapsed
        self.skipped = skipped

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "matched": self.matched,
            "result": self.result,
            "elapsed_ms": self.elapsed,
        }
        if self.score:
            d["score"] = self.score
        if self.skipped:
            d["skipped"] = True
        return d


def classify_with_details(classifier_cfg: Optional[dict], user_query: str,
                          llm_client=None, emb_client=None,
                          ft_predictor: Optional[FastTextPredictor] = None) -> tuple[list[TierResult], str]:
    """意图分类（调试用），返回各层详细结果。"""
    tiers = []

    if not classifier_cfg or not classifier_cfg.get("categories"):
        return tiers, ""

    categories = classifier_cfg["categories"]
    prompt = classifier_cfg.get("prompt", "")

    # 1. 关键词匹配
    t0 = time.time()
    name = _match_keyword(user_query, categories)
    if name:
        elapsed = int((time.time() - t0) * 1000)
        tiers.append(TierResult("keyword", matched=True, result=name, elapsed=elapsed))
        return tiers, name
    tiers.append(TierResult("keyword", matched=False, elapsed=int((time.time() - t0) * 1000)))

    # 2. fastText
    if ft_predictor is not None:
        t0 = time.time()
        if not ft_predictor.is_trained():
            tiers.append(TierResult("fasttext", skipped=True, elapsed=int((time.time() - t0) * 1000)))
        else:
            result = ft_predictor.predict(user_query)
            elapsed = int((time.time() - t0) * 1000)
            if result and result.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
                tiers.append(TierResult("fasttext", matched=True,
                                        result=result["label"],
                                        score=result["confidence"],
                                        elapsed=elapsed))
                return tiers, result["label"]
            if result:
                tiers.append(TierResult("fasttext", matched=False,
                                        score=result["confidence"],
                                        elapsed=elapsed))
            else:
                tiers.append(TierResult("fasttext", skipped=True, elapsed=elapsed))

    # 3. Embedding 语义匹配
    if emb_client is not None:
        t0 = time.time()
        name = _match_semantic(classifier_cfg, user_query, emb_client)
        elapsed = int((time.time() - t0) * 1000)
        if name:
            tiers.append(TierResult("embedding", matched=True, result=name, elapsed=elapsed))
            return tiers, name
        tiers.append(TierResult("embedding", matched=False, elapsed=elapsed))

    # 4. LLM 分类
    if llm_client is not None:
        t0 = time.time()
        name = _llm_classify(classifier_cfg, user_query, llm_client)
        elapsed = int((time.time() - t0) * 1000)
        if name:
            tiers.append(TierResult("llm", matched=True, result=name, elapsed=elapsed))
            return tiers, name
        tiers.append(TierResult("llm", matched=False, elapsed=elapsed))

    # 5. Fallback：返回最后一个类别
    if categories:
        fallback = categories[-1].get("name", "")
        tiers.append(TierResult("fallback", matched=True, result=fallback))
        return tiers, fallback

    return tiers, ""


def classify(classifier_cfg: Optional[dict], user_query: str,
             llm_client=None, emb_client=None,
             ft_predictor: Optional[FastTextPredictor] = None) -> str:
    """意图分类：关键词 → 本地模型 → 语义匹配 → LLM 兜底。
    返回匹配到的 category name，如果全都没命中则返回空串。
    """
    if not classifier_cfg or not classifier_cfg.get("categories"):
        return ""

    categories = classifier_cfg["categories"]

    # 1. 关键词匹配（最快，0ms）
    name = _match_keyword(user_query, categories)
    if name:
        return name

    # 2. 本地模型（~5ms，比关键词准）
    if ft_predictor is not None:
        if not ft_predictor.is_trained():
            logger.warning("fastText 模型未找到，跳过 fastText 层: path=dt/ft/model.ftz")
        else:
            result = ft_predictor.predict(user_query)
            if result and result.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
                logger.info("classifier fastText 匹配: intent=%s, confidence=%.4f, query=%s",
                            result["label"], result["confidence"], user_query[:50])
                return result["label"]
            if result:
                logger.info("classifier fastText 低置信度: label=%s, confidence=%.4f, query=%s",
                            result["label"], result["confidence"], user_query[:50])

    # 3. 语义匹配（~100ms，embedding 向量相似度）
    if emb_client is not None:
        name = _match_semantic(classifier_cfg, user_query, emb_client)
        if name:
            return name

    # 4. LLM 分类（慢但最准，兜底）
    if llm_client is not None:
        name = _llm_classify(classifier_cfg, user_query, llm_client)
        if name:
            return name

    # 5. 最终 fallback：返回最后一个类别
    if categories:
        fallback = categories[-1].get("name", "")
        logger.info("classifier fallback: intent=%s, query=%s", fallback, user_query[:50])
        return fallback

    return ""


def _match_keyword(query: str, categories: list[dict]) -> str:
    """关键词匹配：在类别关键词中查找匹配"""
    query_lower = query.lower()
    best_match = ""
    best_len = 0

    for cat in categories:
        for kw in cat.get("keywords", []):
            kw_lower = kw.lower()
            if kw_lower in query_lower:
                if len(kw) > best_len:
                    best_len = len(kw)
                    best_match = cat.get("name", "")

    return best_match


# ============================================================
# 语义匹配（embedding 向量相似度）
# ============================================================

def _match_semantic(classifier_cfg: dict, user_query: str, emb_client) -> str:
    """用 embedding 向量相似度做意图匹配。"""
    categories = classifier_cfg.get("categories", [])

    # 获取分类别的归一化向量
    cat_vecs = _get_category_vectors(classifier_cfg, emb_client)
    if not cat_vecs:
        return ""

    # 计算用户 query 的向量
    try:
        query_vec = emb_client.embed_single(user_query)
    except Exception as e:
        logger.warning("semantic classifier: embed query 失败: %s", e)
        return ""

    # 计算相似度，找到最佳匹配
    best_score = 0.0
    best_name = ""
    for cv in cat_vecs:
        score = _cosine_similarity(query_vec, cv["vector"])
        if score > best_score:
            best_score = score
            best_name = cv["name"]

    if best_score >= SEMANTIC_THRESHOLD:
        logger.info("classifier semantic 匹配: intent=%s, score=%.4f, query=%s",
                    best_name, best_score, user_query[:50])
        return best_name

    logger.info("classifier semantic 未匹配: best_score=%.4f, threshold=%.2f",
                best_score, SEMANTIC_THRESHOLD)
    return ""


def _get_category_vectors(classifier_cfg: dict, emb_client) -> list[dict]:
    """获取分类器的各类别向量（带缓存）。"""
    cache_key = _build_category_cache_key(classifier_cfg)

    # 先查缓存
    with _cache_lock:
        if cache_key in _cat_embedding_cache:
            return _cat_embedding_cache[cache_key]

    categories = classifier_cfg.get("categories", [])

    # 构建每个类别的规范化文本
    cat_texts = [_build_category_text(cat) for cat in categories]

    # 批量计算向量
    try:
        embeddings = emb_client.embed(cat_texts)
    except Exception as e:
        logger.warning("semantic classifier: batch embed categories 失败: %s", e)
        return []

    if len(embeddings) != len(categories):
        logger.warning("embedding 数量不匹配: %d vs %d", len(embeddings), len(categories))
        return []

    # 组装结果
    result = [{"name": cat["name"], "vector": embeddings[i]} for i, cat in enumerate(categories)]

    # 写入缓存
    with _cache_lock:
        _cat_embedding_cache[cache_key] = result

    return result


def _build_category_text(cat: dict) -> str:
    """将类别定义拼接为一段规范文本用于向量化。"""
    parts = [cat.get("description", "")]
    parts.extend(cat.get("keywords", []))
    return " ".join(parts)


def _build_category_cache_key(classifier_cfg: dict) -> str:
    """基于分类器定义生成缓存 key。"""
    parts = [classifier_cfg.get("prompt", ""), "|"]
    for cat in classifier_cfg.get("categories", []):
        parts.append(cat.get("name", ""))
        parts.append(":")
        parts.append(cat.get("description", ""))
        parts.append(":")
        parts.append(",".join(cat.get("keywords", [])))
        parts.append(";")
    return hashlib.md5("".join(parts).encode()).hexdigest()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度"""
    if len(a) != len(b) or len(a) == 0:
        return 0.0

    dot_prod = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a)
    norm_b = sum(x * x for x in b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    import math
    return dot_prod / (math.sqrt(norm_a) * math.sqrt(norm_b))


# ============================================================
# LLM 分类（兜底）
# ============================================================

def _llm_classify(classifier_cfg: dict, user_query: str, llm_client) -> str:
    """用 LLM 做意图分类，要求模型输出类别名。"""
    system_prompt = _build_classifier_prompt(classifier_cfg)
    try:
        result = llm_client.chat(system_prompt, user_query)
        result = result.strip()
        # 验证结果是否为有效类别名
        valid_names = {cat.get("name", "") for cat in classifier_cfg.get("categories", [])}
        if result in valid_names:
            return result
        logger.warning("LLM 分类返回无效类别: %s", result)
    except Exception as e:
        logger.warning("LLM 分类失败: %s", e)
    return ""


def _build_classifier_prompt(classifier_cfg: dict) -> str:
    """构建分类器 system prompt"""
    prompt = classifier_cfg.get("prompt", "")
    parts = [prompt, "\n\n类别列表："]
    for cat in classifier_cfg.get("categories", []):
        name = cat.get("name", "")
        desc = cat.get("description", "")
        keywords = "、".join(cat.get("keywords", []))
        parts.append(f"- {name}：{desc}（关键词：{keywords}）")
    parts.append("\n请只回复类别名称，不要包含任何其他内容。")
    return "\n".join(parts)


# ============================================================
# DAG 执行引擎（对标 Go internal/engine/engine.go）
# ============================================================

class EngineEvent:
    """工作流执行事件"""
    def __init__(self, event_type: str = "", step: int = 0, total: int = 0,
                 agent: str = "", content: str = "", error: Exception = None,
                 node_id: str = "", parallel_group: str = ""):
        self.type = event_type  # "progress" | "chunk" | "done" | "error"
        self.step = step
        self.total = total
        self.agent = agent
        self.content = content
        self.error = error
        self.node_id = node_id
        self.parallel_group = parallel_group

    def to_dict(self) -> dict:
        d = {
            "type": self.type,
            "step": self.step,
            "total": self.total,
            "agent": self.agent,
            "content": self.content,
        }
        if self.node_id:
            d["node_id"] = self.node_id
        if self.parallel_group:
            d["parallel_group"] = self.parallel_group
        return d


def has_next_nodes(nodes: list[dict]) -> bool:
    """判断是否使用 DAG 模式（任一节点有 next_nodes 即为 DAG）"""
    for n in nodes:
        if n.get("next_nodes"):
            return True
    return False


def validate_workflow_graph(nodes: list[dict]) -> Optional[str]:
    """验证工作流图的有效性，返回错误信息或 None"""
    if not nodes:
        return "工作流至少需要一个节点"

    # 检查所有 next_nodes 引用是否存在
    node_ids = {n.get("id", "") for n in nodes}
    for n in nodes:
        for target_id in n.get("next_nodes", []):
            if target_id not in node_ids:
                return f"节点 {n.get('id')} 引用了不存在的下游节点 {target_id}"
            if target_id == n.get("id"):
                return f"节点 {n.get('id')} 不能引用自身"

    # 检查循环依赖（通过拓扑排序）
    dag = _build_dag(nodes)
    if dag is None:
        return "工作流图构建失败"
    try:
        _topological_levels(dag)
    except ValueError as e:
        return str(e)

    # 检查至少有一个 sink 节点
    has_sink = any(not n.get("next_nodes") for n in nodes)
    if not has_sink:
        return "工作流图必须至少有一个终点节点（无下游节点）"

    return None


def auto_detect_is_final(nodes: list[dict]):
    """DAG 模式下自动检测最终节点：没有下游节点的即为 sink（IsFinal = true），其余为 false"""
    for n in nodes:
        n["is_final"] = len(n.get("next_nodes", [])) == 0


def _build_dag(nodes: list[dict]) -> Optional[dict]:
    """从节点列表构建 DAG 邻接表"""
    dag = {}
    for n in nodes:
        nid = n.get("id", "")
        dag[nid] = {
            "node": n,
            "in_degree": 0,
            "out_edges": n.get("next_nodes", []),
        }

    for dn in dag.values():
        for target_id in dn["out_edges"]:
            if target_id not in dag:
                return None
            dag[target_id]["in_degree"] += 1

    return dag


def _topological_levels(dag: dict) -> list[list[dict]]:
    """Kahn 算法分层，返回按层级分组的节点"""
    # 收集入度为 0 的节点
    queue = [dn for dn in dag.values() if dn["in_degree"] == 0]
    levels = []
    processed = 0
    total = len(dag)

    while queue:
        level_size = len(queue)
        level = []
        next_queue = []

        for i in range(level_size):
            dn = queue[i]
            level.append(dn["node"])
            processed += 1

            for target_id in dn["out_edges"]:
                target = dag[target_id]
                target["in_degree"] -= 1
                if target["in_degree"] == 0:
                    next_queue.append(target)

        levels.append(level)
        queue = next_queue

    if processed != total:
        raise ValueError("工作流图中存在循环依赖，无法执行")

    return levels


class WorkflowEngine:
    """工作流执行引擎"""

    def __init__(self, cfg: dict, kb_manager, store,
                 emb_client=None, ft_predictor=None):
        self.cfg = cfg
        self.kb_mgr = kb_manager
        self.store = store
        self.emb_client = emb_client
        self.ft_predictor = ft_predictor or FastTextPredictor()

        # 默认 LLM 客户端
        from apps.csm.chat_agent import LLMClient
        api = self.cfg["api"]
        llm = self.cfg.get("llm", {})
        self.base_llm = LLMClient(
            api["llm_api_uri"],
            api["llm_api_key"],
            api["llm_model_name"],
            temperature=llm.get("temperature", 0.7),
            top_p=llm.get("top_p", 0.9),
            max_tokens=llm.get("max_tokens", 2048),
        )

    def execute_stream(self, workflow: dict, messages: list[dict],
                       uid: str, user_query: str) -> Generator[EngineEvent, None, None]:
        """流式执行工作流，通过 Generator 返回 EngineEvent

        workflow: 从数据库加载的工作流定义
        messages: 历史消息
        uid: 用户 ID
        user_query: 用户当前问题
        """
        nodes = workflow.get("nodes", [])
        total = len(nodes)
        classifier_cfg = workflow.get("classifier")

        # 初始化变量池
        cur_date = datetime.now().strftime("%Y-%m-%d")
        cur_week = get_weekday_cn(datetime.now().weekday())
        vars_dict = {
            # 新版命名（sys. 前缀）
            "sys.user_query": user_query,
            "sys.history": format_history(messages),
            "sys.cur_date": cur_date,
            "sys.cur_week": cur_week,
            "sys.kb_context": "",
            # 兼容旧版变量名
            "user_query": user_query,
            "history": format_history(messages),
            "cur_date": cur_date,
            "cur_week": cur_week,
        }
        classifier_output_var = "intent"

        # 意图分类（如果工作流配置了 Classifier）
        if classifier_cfg and classifier_cfg.get("categories"):
            # 确保 fastText 模型可用（存在 model.ftz 时直接跳过，不重复训练）
            try:
                self.ft_predictor.train(
                    classifier_cfg["categories"],
                    classifier_cfg.get("prompt", ""),
                )
            except Exception as e:
                logger.warning("fastText 训练失败，将跳过 fastText 层: %s", e)

            logger.info("classifier 开始: workflow=%s", workflow.get("name", ""))
            classify_start = time.time()
            intent = classify(
                classifier_cfg, user_query,
                self.base_llm, self.emb_client, self.ft_predictor,
            )
            classify_elapsed = int((time.time() - classify_start) * 1000)

            classifier_output_var = classifier_cfg.get("output_var") or "intent"
            if not classifier_output_var:
                classifier_output_var = "intent"
            vars_dict[classifier_output_var] = intent
            vars_dict["sys." + classifier_output_var] = intent

            yield EngineEvent(
                "progress", step=0, total=total,
                agent=f"意图识别：{intent}（{classify_elapsed}ms）",
            )
            logger.info("classifier 完成: workflow=%s, intent=%s, duration_ms=%d, query=%s",
                        workflow.get("name", ""), intent, classify_elapsed, user_query[:50])

        # 执行节点（DAG 或线性模式）
        if has_next_nodes(nodes):
            yield from self._execute_dag(nodes, vars_dict, classifier_output_var, uid, user_query)
        else:
            yield from self._execute_linear(nodes, total, vars_dict, classifier_output_var, uid, user_query)

        # 发送完成事件
        logger.info("workflow nodes 完成: workflow=%s, total_nodes=%d",
                    workflow.get("name", ""), total)
        yield EngineEvent("done", total=total)

    # ============================================================
    # 线性执行模式
    # ============================================================

    def _execute_linear(self, nodes: list[dict], total: int,
                        vars_dict: dict, classifier_output_var: str,
                        uid: str, user_query: str) -> Generator[EngineEvent, None, None]:
        """线性执行模式（保持向后兼容）"""
        logger.info("workflow nodes 开始 (linear): total_nodes=%d", total)
        for i, node in enumerate(nodes):
            # 条件路由
            condition = node.get("condition", "")
            if condition:
                current_intent = vars_dict.get(classifier_output_var, "")
                if current_intent != condition:
                    logger.info("skip node by condition: node=%s, agent=%s, condition=%s, current_intent=%s",
                                node.get("id"), node.get("agent_name"), condition, current_intent)
                    continue

            evt = self._execute_node(node, i + 1, total, vars_dict, uid, user_query)
            if evt is not None:
                yield evt
                if evt.type == "error":
                    return

    # ============================================================
    # DAG 执行模式
    # ============================================================

    def _execute_dag(self, nodes: list[dict], vars_dict: dict,
                     classifier_output_var: str, uid: str,
                     user_query: str) -> Generator[EngineEvent, None, None]:
        """DAG 模式执行"""
        logger.info("workflow nodes 开始 (DAG): total_nodes=%d", len(nodes))

        dag = _build_dag(nodes)
        if dag is None:
            yield EngineEvent("error", content="构建执行图失败",
                              error=ValueError("build DAG failed"))
            return

        try:
            levels = _topological_levels(dag)
        except ValueError as e:
            yield EngineEvent("error", content=f"工作流图拓扑排序失败: {e}", error=e)
            return

        logger.info("dag levels computed: levels=%d", len(levels))
        for li, level in enumerate(levels):
            logger.info("dag level start: level=%d, nodes=%d, total_levels=%d",
                        li + 1, len(level), len(levels))
            if len(level) == 1:
                # 单节点：同步执行
                node = level[0]
                condition = node.get("condition", "")
                if condition:
                    if vars_dict.get(classifier_output_var, "") != condition:
                        logger.info("skip node by condition (DAG): node=%s, agent=%s, condition=%s",
                                    node.get("id"), node.get("agent_name"), condition)
                        continue
                evt = self._execute_node(node, li + 1, len(levels), vars_dict, uid, user_query)
                if evt is not None:
                    yield evt
                    if evt.type == "error":
                        return
            else:
                # 多节点：并行执行
                yield from self._execute_parallel_level(level, li + 1, len(levels),
                                                        vars_dict, uid, user_query,
                                                        classifier_output_var)

    def _execute_parallel_level(self, level: list[dict], step: int, total: int,
                                vars_dict: dict, uid: str, user_query: str,
                                classifier_output_var: str) -> Generator[EngineEvent, None, None]:
        """并行执行同一层级的多个节点"""
        import queue

        results = []
        result_queue = queue.Queue()
        threads = []
        vars_lock = threading.Lock()

        def _run_node(node):
            try:
                # 条件路由
                condition = node.get("condition", "")
                if condition:
                    with vars_lock:
                        intent = vars_dict.get(classifier_output_var, "")
                    if intent != condition:
                        logger.info("skip node by condition (DAG parallel): node=%s, agent=%s, condition=%s",
                                    node.get("id"), node.get("agent_name"), condition)
                        # 发送跳过进度事件
                        label = node.get("agent_name", "") + " (已跳过)"
                        pg = node.get("parallel_group", "")
                        result_queue.put(EngineEvent(
                            "progress", step=step, total=total,
                            agent=label, node_id=node.get("id", ""),
                            parallel_group=pg,
                        ))
                        return

                # 发送进度事件
                pg = node.get("parallel_group", "")
                label = node.get("agent_name", "")
                if pg:
                    label = f"[并行:{pg}] {label}"
                else:
                    label = f"[并行] {label}"
                result_queue.put(EngineEvent(
                    "progress", step=step, total=total,
                    agent=label, node_id=node.get("id", ""),
                    parallel_group=pg,
                ))

                evt = self._execute_node_internal(node, step, total, vars_dict, uid, user_query, vars_lock)
                if evt is not None:
                    result_queue.put(evt)
            except Exception as e:
                logger.error("parallel node error: node=%s, error=%s", node.get("id"), e)
                result_queue.put(EngineEvent(
                    "error", content=f"节点 {node.get('id')} 执行异常: {e}",
                    error=e, node_id=node.get("id", ""),
                ))

        for node in level:
            t = threading.Thread(target=_run_node, args=(node,), daemon=True)
            threads.append(t)
            t.start()

        # 等待所有线程完成，同时收集事件
        for t in threads:
            t.join()

        # 收集所有事件
        while not result_queue.empty():
            evt = result_queue.get_nowait()
            yield evt

    # ============================================================
    # 单节点执行
    # ============================================================

    def _execute_node(self, node: dict, step: int, total: int,
                      vars_dict: dict, uid: str, user_query: str) -> Optional[EngineEvent]:
        """执行单个节点（无锁包装）"""
        return self._execute_node_internal(node, step, total, vars_dict, uid, user_query, None)

    def _execute_node_internal(self, node: dict, step: int, total: int,
                               vars_dict: dict, uid: str, user_query: str,
                               mu: Optional[threading.Lock]) -> Optional[EngineEvent]:
        """执行单个节点（核心逻辑），mu 非 None 时加锁访问 vars_dict"""
        # 加载 Agent
        agent_id = node.get("agent_id")
        agent = self.store.get_agent(agent_id)
        if not agent:
            msg = f"节点 {node.get('id')} 引用的智能体 (ID: {agent_id}) 不存在"
            logger.error("agent not found: node=%s, agent_id=%s", node.get("id"), agent_id)
            return EngineEvent("error", content=msg, error=ValueError(msg))

        if mu is None:
            logger.info("node start: node=%s, agent=%s, step=%d, total=%d",
                        node.get("id"), agent.get("name"), step, total)

        # 渲染输入模板
        input_template = node.get("input_template", "")
        if mu:
            mu.acquire()
        try:
            node_input = resolve_template(input_template, vars_dict)
        finally:
            if mu:
                mu.release()

        logger.info("node input ready: node=%s, agent=%s, input_len=%d",
                    node.get("id"), agent.get("name"), len(node_input))

        # 知识库检索（如果 agent 绑定了 vdb_ids）
        vdb_ids_str = agent.get("vdb_ids", "")
        if vdb_ids_str and vdb_ids_str != "[]":
            try:
                vdb_ids = json.loads(vdb_ids_str)
            except json.JSONDecodeError:
                vdb_ids = []
            if vdb_ids:
                logger.info("kb search start: node=%s, agent=%s, vdb_ids=%s",
                            node.get("id"), agent.get("name"), vdb_ids)
                kb_start = time.time()
                kb_parts = []
                for vdb_id in vdb_ids:
                    ctx = self.kb_mgr.search_in_kb(
                        user_query, vdb_id, uid,
                        self.cfg["kb"].get("top_k", 3),
                        self.cfg["kb"].get("score_threshold", 0.1),
                    )
                    if ctx:
                        kb_parts.append(ctx)
                kb_context = "\n".join(kb_parts)
                if mu:
                    mu.acquire()
                try:
                    vars_dict["sys.kb_context"] = kb_context
                finally:
                    if mu:
                        mu.release()
                kb_elapsed = int((time.time() - kb_start) * 1000)
                logger.info("kb search done: node=%s, agent=%s, kb_context_len=%d, duration_ms=%d",
                            node.get("id"), agent.get("name"), len(kb_context), kb_elapsed)

        # 构建 system prompt（用模板解析）
        system_prompt_template = agent.get("system_prompt", "")
        if mu:
            mu.acquire()
        try:
            system_prompt = resolve_template(system_prompt_template, vars_dict)
        finally:
            if mu:
                mu.release()

        # LLM 调用
        llm_client = self._get_llm_client(agent)
        logger.info("llm call start: node=%s, agent=%s, model=%s, system_prompt_len=%d",
                    node.get("id"), agent.get("name"), llm_client.model_name, len(system_prompt))
        llm_start = time.time()

        # 判断是否为最终节点（无下游节点）
        has_downstream = bool(node.get("next_nodes"))
        is_final = node.get("is_final", False) or not has_downstream

        if is_final:
            # 最终节点：同步调用
            try:
                full_output = llm_client.chat(system_prompt, node_input)
            except Exception as e:
                logger.error("node error: node=%s, agent=%s, error=%s",
                             node.get("id"), agent.get("name"), e)
                return EngineEvent(
                    "chunk", content=f"[错误] {e}",
                    step=step, total=total,
                    agent=agent.get("name", ""),
                    node_id=node.get("id", ""),
                )

            llm_elapsed = int((time.time() - llm_start) * 1000)
            logger.info("node done: node=%s, agent=%s, type=sync, duration_ms=%d, output_len=%d",
                        node.get("id"), agent.get("name"), llm_elapsed, len(full_output))

            # 存储输出
            if mu:
                mu.acquire()
            try:
                output_var = node.get("output_var", "")
                if output_var:
                    vars_dict[output_var] = full_output
                vars_dict[node.get("id", "")] = full_output
            finally:
                if mu:
                    mu.release()

            return EngineEvent(
                "chunk", content=full_output,
                step=step, total=total,
                agent=agent.get("name", ""),
                node_id=node.get("id", ""),
            )

        # 非最终节点：同步调用
        try:
            full_output = llm_client.chat(system_prompt, node_input)
        except Exception as e:
            logger.error("node error: node=%s, agent=%s, error=%s",
                         node.get("id"), agent.get("name"), e)
            full_output = f"[错误] {e}"

        llm_elapsed = int((time.time() - llm_start) * 1000)
        output_preview = full_output[:80] if len(full_output) > 80 else full_output
        logger.info("node done: node=%s, agent=%s, type=sync, duration_ms=%d, output_len=%d, output_preview=%s",
                    node.get("id"), agent.get("name"), llm_elapsed, len(full_output), output_preview)

        # 存储输出到变量池
        if mu:
            mu.acquire()
        try:
            output_var = node.get("output_var", "")
            if output_var:
                vars_dict[output_var] = full_output
            vars_dict[node.get("id", "")] = full_output
        finally:
            if mu:
                mu.release()

        return None  # 非最终节点不发送 chunk 事件

    def _get_llm_client(self, agent: dict):
        """获取 LLM 客户端（使用 Agent 特定参数或默认）"""
        from apps.csm.chat_agent import LLMClient
        api = self.cfg["api"]
        llm_defaults = self.cfg.get("llm", {})

        model_name = agent.get("model_name") or api.get("llm_model_name", "")
        temperature = agent.get("temperature")
        if temperature is None:
            temperature = llm_defaults.get("temperature", 0.7)
        top_p = agent.get("top_p")
        if top_p is None:
            top_p = llm_defaults.get("top_p", 0.9)
        max_tokens = agent.get("max_tokens")
        if max_tokens is None:
            max_tokens = llm_defaults.get("max_tokens", 2048)

        client = LLMClient(
            api.get("llm_api_uri", ""),
            api.get("llm_api_key", ""),
            model_name,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        return client
