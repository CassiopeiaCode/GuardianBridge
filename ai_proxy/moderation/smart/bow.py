"""
词袋模型（BoW）训练和预测模块
使用 jieba 分词 + TF-IDF + SGDClassifier
支持大规模数据的增量训练
"""
import os
import time
import random
import jieba
import joblib
import numpy as np
from typing import List, Dict, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier, LogisticRegression

from ai_proxy.moderation.smart.profile import ModerationProfile
from ai_proxy.moderation.smart.storage import SampleStorage
from ai_proxy.moderation.smart.ai import ModerationResult


# 模型缓存：{profile_name: (vectorizer, clf, model_mtime, vectorizer_mtime)}
_model_cache: Dict[str, Tuple[object, object, float, float]] = {}


def tokenize_for_bow(text: str, use_char_ngram: bool = True) -> str:
    """
    文本预处理和分词
    混合词级分词 + 字符级 n-gram
    
    Args:
        text: 原始文本
        use_char_ngram: 是否使用字符级 n-gram
        
    Returns:
        空格分隔的 token 序列
    """
    # 词级分词
    word_tokens = list(jieba.cut(text))
    
    tokens = word_tokens
    
    # 字符级 bigram（可选）
    if use_char_ngram:
        char_bigrams = [text[i:i+2] for i in range(len(text)-1)]
        char_trigrams = [text[i:i+3] for i in range(len(text)-2)]
        tokens.extend(char_bigrams)
        tokens.extend(char_trigrams)
    
    return " ".join(tokens)


def train_bow_model(profile: ModerationProfile):
    """
    训练词袋线性模型（支持大规模数据的增量训练）
    
    优化特性:
    1. 随机打乱训练顺序（避免样本顺序偏差）
    2. 训练时间限制（默认最多5分钟）
    3. 批量增量训练（使用 partial_fit）
    4. 内存友好的数据访问方式
    """
    cfg = profile.config.bow_training
    db_path = profile.get_db_path()
    storage = SampleStorage(db_path)
    
    max_samples = cfg.max_samples
    batch_size = cfg.batch_size
    max_seconds = cfg.max_seconds
    
    print(f"[BOW] 开始训练 profile={profile.profile_name}")
    print(f"[BOW] 配置: max_samples={max_samples}, batch_size={batch_size}, max_seconds={max_seconds}秒")
    start_time = time.time()
    
    # 0. 数据库清理（在训练前执行）
    max_db_items = cfg.max_db_items
    print(f"[BOW] 数据库限制: max_db_items={max_db_items}")
    storage.cleanup_excess_samples(max_db_items)
    
    # 1. 查询总样本数
    total = storage.get_sample_count()
    if total < cfg.min_samples:
        print(f"[BOW] 样本数不足 {cfg.min_samples}，当前={total}，跳过训练")
        return
    
    print(f"[BOW] 总样本数: {total}")
    
    # 2. 取出要参与训练的样本 ID 列表（只取最新的 max_samples 条）
    ids = storage.get_sample_ids(limit=min(max_samples, total))
    print(f"[BOW] 选取样本数: {len(ids)}")
    
    # 3. 随机打乱（避免样本顺序偏差）
    random.shuffle(ids)
    print(f"[BOW] 样本顺序已随机打乱")
    
    # 4. 准备 TF-IDF 向量器和分类器
    word_ngram = cfg.word_ngram_range
    vectorizer = TfidfVectorizer(
        max_features=cfg.max_features,
        ngram_range=tuple(word_ngram) if cfg.use_word_ngram else (1, 1),
        min_df=2,
        max_df=0.8
    )
    
    # 只有 SGDClassifier 支持 partial_fit
    model_type = cfg.model_type
    if model_type != "sgd_logistic":
        print(f"[BOW] 大规模训练需要使用 sgd_logistic 模型，当前配置为 {model_type}，将强制使用 sgd_logistic")
    
    clf = SGDClassifier(
        loss="log_loss",
        class_weight="balanced",
        max_iter=1000,
        n_jobs=1,
        random_state=42
    )
    classes = np.array([0, 1])  # 预定义类别
    
    # 5. 第一批：fit (建立词表)
    first_batch_size = min(batch_size, len(ids))
    first_batch_ids = ids[:first_batch_size]
    
    print(f"[BOW] 第一批训练: {len(first_batch_ids)} 样本")
    first_samples = storage.load_by_ids(first_batch_ids)
    
    if not first_samples:
        print(f"[BOW] 无法加载第一批样本，训练终止")
        return
    
    # 预处理第一批
    use_char_ngram = cfg.use_char_ngram
    texts0 = [tokenize_for_bow(s.text, use_char_ngram) for s in first_samples]
    y0 = np.array([s.label for s in first_samples])
    
    # 时间检查
    if time.time() - start_time > max_seconds:
        print("[BOW] 训练时间已达上限（准备 fit 前），终止")
        return
    
    # fit 第一批（建立词表）
    X0 = vectorizer.fit_transform(texts0)
    clf.partial_fit(X0, y0, classes=classes)
    
    elapsed = time.time() - start_time
    print(f"[BOW] 第一批完成，耗时 {elapsed:.1f}秒，词表大小 {len(vectorizer.get_feature_names_out())}")
    
    # 6. 剩余样本：分批随机顺序训练，每个 batch 前检查时间
    total_batches = (len(ids) - first_batch_size + batch_size - 1) // batch_size
    current_batch = 0
    
    for i in range(first_batch_size, len(ids), batch_size):
        # 时间到了就停
        elapsed = time.time() - start_time
        if elapsed > max_seconds:
            print(f"[BOW] 训练时间已达上限 ({elapsed:.1f}秒)，提前停止")
            print(f"[BOW] 已完成 {current_batch}/{total_batches} 批次")
            break
        
        current_batch += 1
        batch_ids = ids[i:i + batch_size]
        
        # 加载批次样本
        samples = storage.load_by_ids(batch_ids)
        if not samples:
            continue
        
        # 预处理
        texts = [tokenize_for_bow(s.text, use_char_ngram) for s in samples]
        y = np.array([s.label for s in samples])
        
        # 增量训练
        X = vectorizer.transform(texts)
        clf.partial_fit(X, y)
        
        # 进度报告（每10批或最后一批）
        if current_batch % 10 == 0 or i + batch_size >= len(ids):
            elapsed = time.time() - start_time
            print(f"[BOW] 进度: {current_batch}/{total_batches} 批次，已用时 {elapsed:.1f}秒")
    
    # 7. 保存模型 + 向量器
    joblib.dump(vectorizer, profile.get_vectorizer_path())
    joblib.dump(clf, profile.get_model_path())
    
    total_elapsed = time.time() - start_time
    print(f"[BOW] 训练完成，总耗时 {total_elapsed:.1f}秒")
    print(f"[BOW] 最终词表大小: {len(vectorizer.get_feature_names_out())}")
    print(f"[BOW] 训练样本数: {min(len(ids), current_batch * batch_size + first_batch_size)}")


def bow_model_exists(profile: ModerationProfile) -> bool:
    """检查词袋模型是否存在"""
    return (os.path.exists(profile.get_model_path()) and 
            os.path.exists(profile.get_vectorizer_path()))


def _load_model_with_cache(profile: ModerationProfile) -> Tuple[object, object]:
    """
    加载模型（带缓存，避免重复加载和内存泄漏）
    
    Returns:
        (vectorizer, clf)
    """
    profile_name = profile.profile_name
    model_path = profile.get_model_path()
    vectorizer_path = profile.get_vectorizer_path()
    
    # 获取文件修改时间
    model_mtime = os.path.getmtime(model_path)
    vectorizer_mtime = os.path.getmtime(vectorizer_path)
    
    # 检查缓存
    if profile_name in _model_cache:
        cached_vec, cached_clf, cached_model_mtime, cached_vec_mtime = _model_cache[profile_name]
        
        # 如果文件没有更新，重用缓存
        if model_mtime == cached_model_mtime and vectorizer_mtime == cached_vec_mtime:
            print(f"[DEBUG] 重用缓存的模型: {profile_name}")
            return cached_vec, cached_clf
        else:
            print(f"[DEBUG] 模型文件已更新，重新加载: {profile_name}")
            # 清理旧模型（帮助GC回收内存）
            del _model_cache[profile_name]
    
    # 加载模型
    print(f"[DEBUG] 加载模型文件: {profile_name}")
    vectorizer = joblib.load(vectorizer_path)
    clf = joblib.load(model_path)
    
    # 保存到缓存
    _model_cache[profile_name] = (vectorizer, clf, model_mtime, vectorizer_mtime)
    
    return vectorizer, clf


def bow_predict_proba(text: str, profile: ModerationProfile) -> float:
    """
    使用词袋模型预测违规概率
    
    Args:
        text: 待预测文本
        profile: 配置
        
    Returns:
        违规概率 (0-1)
    """
    print(f"[DEBUG] 词袋模型预测")
    
    # 加载模型（带缓存）
    vectorizer, clf = _load_model_with_cache(profile)
    
    print(f"  模型类型: {type(clf).__name__}")
    print(f"  特征数量: {len(vectorizer.get_feature_names_out())}")
    
    # 预处理
    use_char_ngram = profile.config.bow_training.use_char_ngram
    corpus = [tokenize_for_bow(text, use_char_ngram)]
    X = vectorizer.transform(corpus)
    
    print(f"  文本特征维度: {X.shape}")
    print(f"  非零特征数: {X.nnz}")
    
    # 预测概率
    if hasattr(clf, 'predict_proba'):
        # SGDClassifier(loss="log_loss") 和 LogisticRegression 都支持
        proba = clf.predict_proba(X)[0]
        print(f"  概率分布: [正常={proba[0]:.3f}, 违规={proba[1]:.3f}]")
        if len(proba) > 1:
            return float(proba[1])  # 类别 1 = 违规
        return 0.0
    else:
        # 如果模型不支持 predict_proba，使用 decision_function
        score = clf.decision_function(X)[0]
        print(f"  决策函数值: {score:.3f}")
        # 简单的 sigmoid 转换
        import math
        prob = 1.0 / (1.0 + math.exp(-score))
        print(f"  转换后概率: {prob:.3f}")
        return prob


def bow_predict(text: str, profile: ModerationProfile) -> ModerationResult:
    """
    使用词袋模型进行预测（返回完整结果）
    """
    proba = bow_predict_proba(text, profile)
    
    # 根据阈值判断
    low_t = profile.config.probability.low_risk_threshold
    high_t = profile.config.probability.high_risk_threshold
    
    if proba < low_t:
        violation = False
        reason = f"BoW model: low risk (p={proba:.3f} < {low_t})"
    elif proba > high_t:
        violation = True
        reason = f"BoW model: high risk (p={proba:.3f} > {high_t})"
    else:
        # 中间不确定，需要 AI 复核
        violation = False
        reason = f"BoW model: uncertain (p={proba:.3f}), needs AI review"
    
    return ModerationResult(
        violation=violation,
        category=None,
        reason=reason,
        source="bow_model",
        confidence=proba
    )