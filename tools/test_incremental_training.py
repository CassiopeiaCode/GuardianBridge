"""
测试增量训练方案
用于验证:
1. 随机打乱训练顺序
2. 训练时间限制
3. 批量增量训练
4. 大规模数据处理能力
"""
import sys
import os
import time
import random
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_proxy.moderation.smart.profile import ModerationProfile
from ai_proxy.moderation.smart.storage import SampleStorage
from ai_proxy.moderation.smart.bow import train_bow_model, bow_model_exists


def create_test_samples(storage: SampleStorage, count: int):
    """创建测试样本"""
    print(f"创建 {count} 个测试样本...")
    
    # 违规样本
    violation_templates = [
        "这是违规内容{i}，包含敏感词汇",
        "不当言论{i}，违反规定",
        "色情内容{i}，需要审核",
        "暴力内容{i}，不适合展示",
        "政治敏感{i}，需要过滤"
    ]
    
    # 正常样本
    normal_templates = [
        "这是正常内容{i}，没有问题",
        "普通讨论{i}，合法合规",
        "技术交流{i}，学术讨论",
        "日常对话{i}，友好交流",
        "产品咨询{i}，客户服务"
    ]
    
    for i in range(count):
        if i % 2 == 0:
            # 违规样本
            text = random.choice(violation_templates).format(i=i)
            storage.save_sample(text, label=1, category="test")
        else:
            # 正常样本
            text = random.choice(normal_templates).format(i=i)
            storage.save_sample(text, label=0, category="test")
    
    print(f"测试样本创建完成")


def test_training_performance(profile_name: str = "default", sample_count: int = 10000):
    """测试训练性能"""
    print("=" * 60)
    print(f"测试增量训练方案")
    print(f"Profile: {profile_name}")
    print(f"样本数: {sample_count}")
    print("=" * 60)
    
    # 加载配置
    profile = ModerationProfile(profile_name)
    storage = SampleStorage(profile.get_db_path())
    
    # 检查现有样本数
    existing_count = storage.get_sample_count()
    print(f"\n现有样本数: {existing_count}")
    
    # 如果样本不足，创建测试样本
    if existing_count < sample_count:
        need_count = sample_count - existing_count
        print(f"需要创建 {need_count} 个测试样本")
        create_test_samples(storage, need_count)
    
    # 显示配置
    print(f"\n训练配置:")
    print(f"  max_samples: {profile.config.bow_training.max_samples}")
    print(f"  batch_size: {profile.config.bow_training.batch_size}")
    print(f"  max_seconds: {profile.config.bow_training.max_seconds}")
    print(f"  model_type: {profile.config.bow_training.model_type}")
    
    # 开始训练
    print(f"\n开始训练...")
    start_time = time.time()
    
    try:
        train_bow_model(profile)
        elapsed = time.time() - start_time
        print(f"\n训练成功完成!")
        print(f"总耗时: {elapsed:.2f} 秒")
        
        # 检查模型是否生成
        if bow_model_exists(profile):
            print(f"✓ 模型文件已生成")
        else:
            print(f"✗ 模型文件未找到")
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n训练失败!")
        print(f"错误: {str(e)}")
        print(f"已用时: {elapsed:.2f} 秒")
        raise


def test_time_limit(profile_name: str = "default"):
    """测试时间限制功能"""
    print("\n" + "=" * 60)
    print("测试时间限制功能")
    print("=" * 60)
    
    profile = ModerationProfile(profile_name)
    
    # 临时修改配置为更短的时间
    original_max_seconds = profile.config.bow_training.max_seconds
    profile.config.bow_training.max_seconds = 10  # 10秒
    
    print(f"临时设置 max_seconds = 10 秒")
    
    start_time = time.time()
    try:
        train_bow_model(profile)
        elapsed = time.time() - start_time
        
        print(f"\n实际训练时间: {elapsed:.2f} 秒")
        
        if elapsed <= 15:  # 留一些余量
            print("✓ 时间限制功能正常工作")
        else:
            print("✗ 时间限制可能未生效")
            
    finally:
        # 恢复配置
        profile.config.bow_training.max_seconds = original_max_seconds


def main():
    """主测试流程"""
    import argparse
    
    parser = argparse.ArgumentParser(description="测试增量训练方案")
    parser.add_argument("--profile", default="default", help="配置文件名")
    parser.add_argument("--samples", type=int, default=10000, help="测试样本数")
    parser.add_argument("--test-time-limit", action="store_true", help="测试时间限制功能")
    
    args = parser.parse_args()
    
    try:
        # 测试基本训练性能
        test_training_performance(args.profile, args.samples)
        
        # 可选：测试时间限制
        if args.test_time_limit:
            test_time_limit(args.profile)
        
        print("\n" + "=" * 60)
        print("所有测试完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()