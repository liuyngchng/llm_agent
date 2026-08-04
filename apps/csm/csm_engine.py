#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSM 硬编码客服问答引擎 — 对标 Go 版本 csm.go

背景：动态工作流配置（cfg.db workflow_def）已能满足复杂编排，但日常
业务上配置成本高。本模块把"客服"这一条问答逻辑用代码写死，
作为简单快速的业务实现，绕过数据库中的工作流配置。

逻辑与 cfg.db 中"燃气客服工作流"(workflow 1) 一致：
  意图分类(emergency/billing/business/repair/faq)
  → 按意图路由 → (紧急/业务直接回答，账单/维修/FAQ 先检索知识库)
  → LLM 流式生成最终回答

动态配置逻辑（engine.WorkflowEngine / classify / resolve_template）不受影响。
"""
import logging
import time

from apps.csm.engine import EngineEvent, FastTextPredictor, classify

logger = logging.getLogger(__name__)


class CsmEngine:
    """硬编码客服问答引擎 — 对标 Go csm.go"""

    # 硬编码流程的总步骤数（0=意图分类, 1=检索, 2=回答）
    # 供前端进度展示（EngineEvent.total）使用
    CSM_TOTAL_STEP = 3

    # 硬编码的知识库 ID 列表（账单/维修/FAQ 检索时使用）
    CSM_VDB_IDS = [3]

    # 硬编码的意图分类器配置（与 workflow 1 的 classifier 一致）
    CSM_CLASSIFIER = {
        "output_var": "intent",
        "prompt": "你是一个燃气公司客服意图分类器。根据用户输入，判断其意图属于以下哪个类别。\n请只输出类别名称，不要输出任何其他内容。",
        "categories": [
            {"name": "emergency", "description": "燃气泄漏、燃气味、报警等紧急安全情况",
             "keywords": ["漏气", "燃气味", "煤气味", "报警", "爆炸", "火灾", "着火", "泄漏", "冒烟", "异味", "刺鼻"]},
            {"name": "billing", "description": "账单查询、缴费、欠费、发票等财务问题",
             "keywords": ["账单", "缴费", "欠费", "余额", "发票", "价格", "费用", "多少钱", "扣费", "充值", "代扣", "阶梯价"]},
            {"name": "business", "description": "开户、过户、改名、报装、停气等业务办理",
             "keywords": ["开户", "过户", "改名", "报装", "停气", "新装", "移表", "增容", "改管", "安装", "开通", "搬迁", "换表"]},
            {"name": "repair", "description": "燃气设备维修、故障排查、保养、安检",
             "keywords": ["维修", "故障", "坏了", "打不着火", "点不着", "不着火", "保养", "安检", "检查", "熄火", "红火", "小火", "自动关", "打火"]},
            {"name": "faq", "description": "常见综合咨询：营业时间、电话、地址、投诉建议等",
             "keywords": ["营业时间", "电话", "地址", "投诉", "建议", "表扬", "几点", "在哪", "怎么去", "客服", "人工", "工作时间"]},
        ],
    }

    # 各意图智能体系统提示词（与 cfg.db agent_def 表内容一致）
    CSM_EMERGENCY_PROMPT = """你是燃气公司紧急调度员。用户遇到了紧急情况，你必须优先处理。
请引导用户立即采取安全措施：关闭燃气阀门、开窗通风、禁止明火、撤离现场，
同时告知用户已安排紧急维修人员尽快到达。
语气要冷静、专业，给用户安全感。"""

    CSM_BILLING_PROMPT = """你是燃气公司账单客服。根据检索到的账单信息，帮助用户解决账单查询、缴费方式、欠费处理等问题。
用亲切专业的中文回答，引导用户完成缴费操作。"""

    CSM_BUSINESS_PROMPT = """你是燃气公司业务办理专员。帮助用户办理开户、过户、改名、报装、停气等业务。
请告知用户所需材料、办理流程和注意事项。
语气亲切、专业，一步步引导用户完成业务办理。"""

    CSM_REPAIR_PROMPT = """你是燃气公司维修客服。根据检索到的维修信息，帮助用户进行故障诊断、保养指导、报修登记。
对于简单故障给出排查建议，无法解决的安排维修人员上门。
语气专业、耐心。"""

    CSM_FAQ_PROMPT = """你是燃气公司综合客服。根据检索到的FAQ信息，回答用户的各种常见问题，
如营业时间、服务电话、地址、投诉渠道等。
语气亲切、专业，解答清晰明了。"""

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

    def execute_stream_csm(self, workflow_id: int, user_query: str, uid: str,
                           messages: list[dict]):
        """流式执行硬编码 CSM 流程，通过 Generator 返回 EngineEvent。

        workflow_id 已不再用于加载数据库配置，仅保留参数以维持调用兼容。
        事件协议完全复用 EngineEvent（progress / chunk / done / error）。
        """
        return self._csm_run(user_query, uid, len(messages))

    def _csm_run(self, user_query: str, uid: str, history_count: int):
        """硬编码流程主逻辑。"""
        run_start = time.time()
        logger.info("csm_run_start: uid=%s, query=%s, query_len=%d, history=%d",
                    uid, truncate_str(user_query, 80), len(user_query), history_count)

        # 1. 意图分类（复用 classify，多级匹配：关键词 → fastText → 语义 → LLM → fallback）
        # 模型已训练好（dt/ft/model.ftz），直接加载使用，不触发训练
        classify_start = time.time()
        intent = classify(
            self.CSM_CLASSIFIER, user_query,
            self.base_llm, self.emb_client, self.ft_predictor,
        )
        if not intent:
            # 理论上 classify 至少会 fallback 到最后一个类别；此处兜底防御
            intent = "faq"
        logger.info("csm_classify_done: intent=%s, duration_ms=%d, query=%s",
                    intent, int((time.time() - classify_start) * 1000),
                    truncate_str(user_query, 80))
        yield EngineEvent("progress", step=0, total=self.CSM_TOTAL_STEP,
                          agent=f"意图分类: {intent}")

        # 2. 按意图路由
        branch = _csm_branch_name(intent)
        logger.info("csm_route: intent=%s, branch=%s", intent, branch)

        if intent == "emergency":
            yield from self._csm_answer_direct("紧急调度", self.CSM_EMERGENCY_PROMPT, user_query)
        elif intent == "billing":
            yield from self._csm_answer_with_kb("账单检索", "账单客服", self.CSM_BILLING_PROMPT, user_query, uid)
        elif intent == "business":
            yield from self._csm_answer_direct("业务办理", self.CSM_BUSINESS_PROMPT, user_query)
        elif intent == "repair":
            yield from self._csm_answer_with_kb("维修检索", "维修客服", self.CSM_REPAIR_PROMPT, user_query, uid)
        else:  # faq / 未识别
            yield from self._csm_answer_with_kb("FAQ检索", "综合FAQ", self.CSM_FAQ_PROMPT, user_query, uid)

        # 3. 完成
        yield EngineEvent("done", total=self.CSM_TOTAL_STEP)
        logger.info("csm_run_done: intent=%s, total_ms=%d",
                    intent, int((time.time() - run_start) * 1000))

    def _csm_answer_direct(self, agent_name: str, system_prompt: str, user_query: str):
        """直接回答（不检索知识库），用于紧急调度 / 业务办理。"""
        yield EngineEvent("progress", step=2, total=self.CSM_TOTAL_STEP, agent=agent_name)
        yield from self._csm_stream(agent_name, system_prompt, user_query)

    def _csm_answer_with_kb(self, retrieve_agent: str, answer_agent: str,
                            system_prompt: str, user_query: str, uid: str):
        """先检索知识库，再基于检索结果回答，用于账单 / 维修 / FAQ。"""
        yield EngineEvent("progress", step=1, total=self.CSM_TOTAL_STEP, agent=retrieve_agent)

        kb_context = self._csm_search_kb(user_query, uid)

        # 与 workflow 节点 InputTemplate "用户问题：{{user_query}}\n检索信息：{{xx_ctx}}" 保持一致
        user_message = f"用户问题：{user_query}\n检索信息：{kb_context}"

        yield EngineEvent("progress", step=2, total=self.CSM_TOTAL_STEP, agent=answer_agent)
        yield from self._csm_stream(answer_agent, system_prompt, user_message)

    def _csm_search_kb(self, user_query: str, uid: str) -> str:
        """在硬编码的知识库列表中检索用户问题，拼接上下文。"""
        start = time.time()
        logger.info("csm_kb_search_start: vdb_ids=%s, query=%s",
                    self.CSM_VDB_IDS, truncate_str(user_query, 80))

        parts = []
        for vdb_id in self.CSM_VDB_IDS:
            try:
                ctx = self.kb_mgr.search_in_kb(
                    user_query, vdb_id, uid,
                    self.cfg["kb"].get("top_k", 3),
                    self.cfg["kb"].get("score_threshold", 0.1),
                )
                if ctx:
                    parts.append(ctx)
            except Exception as e:
                logger.warning("csm_kb_search_failed: vdb_id=%s, error=%s", vdb_id, e)
                continue

        context = "\n".join(parts)
        logger.info("csm_kb_search_done: duration_ms=%d, context_len=%d",
                    int((time.time() - start) * 1000), len(context))
        return context

    def _csm_stream(self, agent_name: str, system_prompt: str, user_message: str):
        """流式调用 LLM，将输出以 chunk 事件逐段发出。"""
        start = time.time()
        logger.info("csm_llm_start: agent=%s, model=%s, prompt_len=%d, input_len=%d",
                    agent_name, self.base_llm.model_name,
                    len(system_prompt), len(user_message))

        output_parts = []
        chunk_count = 0
        try:
            for chunk in self.base_llm.chat_stream(system_prompt, user_message):
                output_parts.append(chunk)
                chunk_count += 1
                yield EngineEvent("chunk", step=2, total=self.CSM_TOTAL_STEP,
                                  agent=agent_name, content=chunk)
        except Exception as e:
            logger.error("csm_llm_error: agent=%s, error=%s, duration_ms=%d, chunks=%d",
                         agent_name, e, int((time.time() - start) * 1000), chunk_count)
            yield EngineEvent("error", content=f"[错误] {e}", error=e)
            return

        output = "".join(output_parts)
        logger.info("csm_llm_done: agent=%s, duration_ms=%d, chunks=%d, output_len=%d, output_preview=%s",
                    agent_name, int((time.time() - start) * 1000), chunk_count,
                    len(output), truncate_str(output, 80))


def _csm_branch_name(intent: str) -> str:
    """返回意图对应的路由分支描述（仅用于日志）。"""
    if intent == "emergency":
        return "emergency -> 紧急调度（直接回答）"
    if intent == "billing":
        return "billing -> 账单检索 + 账单客服"
    if intent == "business":
        return "business -> 业务办理（直接回答）"
    if intent == "repair":
        return "repair -> 维修检索 + 维修客服"
    return "faq -> FAQ检索 + 综合FAQ"


def truncate_str(s: str, n: int) -> str:
    """截断字符串用于日志预览（按字符截断避免切坏中文）。"""
    if not s:
        return ""
    if len(s) <= n:
        return s
    return s[:n] + "..."
