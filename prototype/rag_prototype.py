# -*- coding: utf-8 -*-
"""
============================================================
报销助手智能体系统 · 阶段 1 —— 裸问答最小原型（单脚本版）
============================================================
功能流程：
    读取本地报销制度 Markdown → 500 字切片 → 向量化存入 FAISS
    → 命令行输入问题 → BM25 + 向量混合检索 Top3
    → 拼接提示词 → 调用 LLM → 输出回答

运行前准备：
    1. 安装依赖：pip install faiss-cpu rank_bm25 openai numpy
    2. 配置 LLM 供应商（三选一，设置环境变量）：
         OpenAI:    export RAG_API_KEY=sk-xxx
                    export RAG_BASE_URL=https://api.openai.com/v1
                    export RAG_MODEL=gpt-4o-mini
         DeepSeek:  export RAG_API_KEY=sk-xxx
                    export RAG_BASE_URL=https://api.deepseek.com/v1
                    export RAG_MODEL=deepseek-chat
         通义千问:   export RAG_API_KEY=sk-xxx
                    export RAG_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
                    export RAG_MODEL=qwen-plus
       （注意：Embedding 模型走 OpenAI 兼容接口，DeepSeek 不提供
         embedding，如用 DeepSeek 需把 EMBED_* 配置指向千问或 OpenAI）
    3. 运行：python rag_prototype.py data/报销制度示例.md

架构说明（与整体方案的对应关系）：
    标注【核心复用】的函数会在后续阶段原样或近似地迁移到
    app/rag/ 与 app/agent/ 目录下，是整个系统的地基。
============================================================
"""

import os
import re
import sys

import numpy as np
import faiss                      # 向量检索库（本地索引，无需服务）
from rank_bm25 import BM25Okapi   # BM25 关键词检索的经典实现
from openai import OpenAI         # 所有主流供应商都提供 OpenAI 兼容接口

# ============================================================
# 0. 配置区：LLM 供应商可配置的核心入口
# ============================================================
# 【核心复用】后续迁移到 app/core/config.py，改读 pydantic-settings
CONFIG = {
    # 对话模型配置（环境变量优先，便于不改动代码切换供应商）
    "llm_api_key":  os.getenv("RAG_API_KEY", ""),
    "llm_base_url": os.getenv("RAG_BASE_URL", "https://api.deepseek.com/v1"),
    "llm_model":    os.getenv("RAG_MODEL", "deepseek-chat"),
    # Embedding 模型配置（可与对话模型不同供应商）
    "embed_api_key":  os.getenv("EMBED_API_KEY", os.getenv("RAG_API_KEY", "")),
    "embed_base_url": os.getenv("EMBED_BASE_URL",
                                "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "embed_model":    os.getenv("EMBED_MODEL", "text-embedding-v3"),
    # 切片参数：500 字一片、相邻片重叠 80 字，防止条款被拦腰截断
    "chunk_size": 500,
    "chunk_overlap": 80,
    # 混合检索参数：各自取 top 几参与融合
    "top_k": 3,
    # RRF 融合常数，60 是论文推荐的经验值
    "rrf_k": 60,
}


# ============================================================
# 1. LLM 调用封装：供应商可配置的独立函数
# ============================================================
# 【核心复用】对应 app/agent/llm/base.py + deepseek.py 的统一入口。
# 关键设计：所有供应商都走 OpenAI 兼容协议，换供应商 = 换 base_url
# 和 model 两个配置项，业务代码零改动。
def llm_chat(messages: list, temperature: float = 0.3) -> str:
    """
    调用大模型生成回答（非流式，原型阶段从简）。

    参数:
        messages:    OpenAI 格式的消息列表，如
                     [{"role": "system", "content": "..."},
                      {"role": "user", "content": "..."}]
        temperature: 生成随机度。报销场景要求严谨，调低到 0.3
                     减少模型"编造制度条款"的概率。
    返回:
        模型回复的纯文本。
    """
    client = OpenAI(
        api_key=CONFIG["llm_api_key"],
        base_url=CONFIG["llm_base_url"],
    )
    resp = client.chat.completions.create(
        model=CONFIG["llm_model"],
        messages=messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content


def get_embeddings(texts: list) -> np.ndarray:
    """
    批量把文本转成向量（Embedding）。

    同样走 OpenAI 兼容接口，独立于 llm_chat，因为对话模型和
    Embedding 模型往往不是同一家供应商。

    【核心复用】对应 app/rag/embedder.py。
    """
    client = OpenAI(
        api_key=CONFIG["embed_api_key"],
        base_url=CONFIG["embed_base_url"],
    )
    resp = client.embeddings.create(
        model=CONFIG["embed_model"],
        input=texts,
    )
    # 按接口返回顺序取出向量，堆成 (n, dim) 的 float32 矩阵
    # （FAISS 要求 float32）
    return np.array([d.embedding for d in resp.data], dtype="float32")


# ============================================================
# 2. 文档加载与切片
# ============================================================
# 【核心复用】对应 app/rag/loader.py + splitter.py。
# 注意：原型用定长滑动窗口切片；正式版会改为"按 第X条 结构切分"，
# 因为制度文档天然按条款组织，按条款切检索质量更高——这个注释
# 本身就是迁移时要做的事。
def load_markdown(path: str) -> str:
    """读取 Markdown 文件全文，去掉图片/链接等噪音符号。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # 粗清理：图片语法 ![...](...) 和链接 [文字](地址) 只留文字
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text


def split_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list:
    """
    滑动窗口切片：每片 chunk_size 字，相邻片重叠 overlap 字。

    重叠的意义：若某条款恰好跨在两片边界上，重叠区能保证
    至少有一片包含该条款的完整上下文。
    """
    chunks = []
    step = chunk_size - overlap          # 每次前进的步长
    for i in range(0, len(text), step):
        piece = text[i:i + chunk_size]
        # 剩余不足 overlap 的尾巴并进上一片，避免产生碎片
        if len(piece) < overlap:
            break
        chunks.append(piece)
    return chunks


# ============================================================
# 3. 双路索引构建：BM25（关键词）+ FAISS（语义向量）
# ============================================================
def tokenize_zh(text: str) -> list:
    """
    极简中文分词：按标点/空白切 + 逐字 fallback。

    说明：原型阶段不引入 jieba，用"二元组(bigram)"近似——
    连续两个汉字组成一个词，兼顾召回与零依赖。
    正式版会替换为 jieba 或直接检索原文片段（BM25 只影响排序）。
    """
    # 先按标点和空白切成短句，再在短句内做 bigram
    segments = re.split(r"[，。；：、！？\s\n,.;:!?]+", text)
    tokens = []
    for seg in segments:
        if len(seg) <= 2:
            tokens.append(seg)
        else:
            tokens += [seg[i:i + 2] for i in range(len(seg) - 1)]
    return tokens


def build_indexes(chunks: list):
    """
    一次性构建 BM25 与 FAISS 两路索引。

    【核心复用】对应 app/rag/retriever.py 的索引构建部分。

    返回:
        bm25:   BM25Okapi 实例（关键词检索）
        index:  FAISS 索引（向量检索），IndexFlatIP = 内积 +
                归一化向量 = 余弦相似度，是最稳妥的精确检索
        chunks: 原始切片列表（检索结果要回原文）
    """
    # ---- 路 1：BM25 关键词索引 ----
    corpus_tokens = [tokenize_zh(c) for c in chunks]
    bm25 = BM25Okapi(corpus_tokens)

    # ---- 路 2：FAISS 向量索引 ----
    vectors = get_embeddings(chunks)
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)           # 内积索引
    faiss.normalize_L2(vectors)              # 归一化后内积 == 余弦相似度
    index.add(vectors)

    return bm25, index, chunks


# ============================================================
# 4. 混合检索：BM25 + 向量，RRF 融合取 Top-K
# ============================================================
# 【核心复用】对应 app/rag/retriever.py 的 hybrid_search()。
# 为什么两路都要：BM25 擅长精确词匹配（如"增值税""500元"），
# 向量擅长语义泛化（"打车"能召回"市内交通费"），二者互补。
def hybrid_retrieve(query: str, bm25, faiss_index, chunks: list,
                    top_k: int = 3, rrf_k: int = 60) -> list:
    """
    混合检索主函数。

    采用 RRF（Reciprocal Rank Fusion）融合：不比较两路分数的
    绝对值（BM25 分数和余弦分数根本不在一个量纲），只看排名：
        score(片段) = Σ 1 / (rrf_k + rank_i)
    这是工业界混合检索的默认做法，简单且稳健。

    返回:
        top_k 个片段组成的列表（按融合分数降序）
    """
    # 路 1：BM25 检索，多取一些候选（top_k*3）再融合
    bm25_scores = bm25.get_scores(tokenize_zh(query))
    bm25_ranked = np.argsort(bm25_scores)[::-1][:top_k * 3]

    # 路 2：向量检索，同样多取候选
    q_vec = get_embeddings([query])
    faiss.normalize_L2(q_vec)
    _, faiss_ids = faiss_index.search(q_vec, top_k * 3)
    faiss_ranked = faiss_ids[0]

    # ---- RRF 融合 ----
    rrf_scores = {}
    for rank, idx in enumerate(bm25_ranked):
        rrf_scores[int(idx)] = rrf_scores.get(int(idx), 0) + 1.0 / (rrf_k + rank + 1)
    for rank, idx in enumerate(faiss_ranked):
        if idx < 0:          # FAISS 候选不足时用 -1 填充，跳过
            continue
        rrf_scores[int(idx)] = rrf_scores.get(int(idx), 0) + 1.0 / (rrf_k + rank + 1)

    # 按融合分降序取前 top_k，返回对应原文切片
    best = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [chunks[idx] for idx, _ in best]


# ============================================================
# 5. 提示词组装
# ============================================================
# 【核心复用】对应 app/agent/prompts/qa.txt。模板文字本身
# 就是后续要版本化管理的资产。
PROMPT_TEMPLATE = """你是企业的报销制度助手。请严格依据下面提供的制度片段回答员工问题。

规则：
1. 只依据【制度片段】回答，不要编造制度里没有的规定；
2. 如果片段不足以回答，明确说"现有制度文档中未找到相关规定"，并建议咨询财务部；
3. 回答末尾注明依据了第几条内容（若片段中有条款号）。

【制度片段】
{context}

【员工问题】
{question}

请回答："""


def build_prompt(question: str, contexts: list) -> str:
    """把检索到的片段拼进模板，片段间加分隔便于模型区分来源。"""
    context = "\n---\n".join(
        f"片段{i+1}：{c}" for i, c in enumerate(contexts)
    )
    return PROMPT_TEMPLATE.format(context=context, question=question)


# ============================================================
# 6. 主流程：初始化索引 + 命令行问答循环
# ============================================================
def main():
    if len(sys.argv) < 2:
        print("用法: python rag_prototype.py <制度文档.md>")
        sys.exit(1)
    policy_path = sys.argv[1]

    print(f"[1/3] 读取制度文档: {policy_path}")
    text = load_markdown(policy_path)
    print(f"      共 {len(text)} 字")

    print(f"[2/3] 切片（每片{CONFIG['chunk_size']}字）并构建 BM25 + FAISS 索引...")
    chunks = split_text(text, CONFIG["chunk_size"], CONFIG["chunk_overlap"])
    print(f"      共 {len(chunks)} 片")
    bm25, faiss_index, chunks = build_indexes(chunks)

    print("[3/3] 就绪。输入问题开始问答，输入 q 退出。\n")
    while True:
        question = input("员工> ").strip()
        if not question:
            continue
        if question.lower() in ("q", "quit", "exit"):
            print("再见。")
            break

        # 混合检索 top3 → 组提示词 → 调 LLM
        contexts = hybrid_retrieve(
            question, bm25, faiss_index, chunks,
            CONFIG["top_k"], CONFIG["rrf_k"],
        )
        prompt = build_prompt(question, contexts)
        print("助手>", end=" ", flush=True)
        print(llm_chat([
            {"role": "user", "content": prompt},
        ]))
        print()


if __name__ == "__main__":
    main()
