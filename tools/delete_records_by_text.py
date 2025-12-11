#!/usr/bin/env python3
"""
删除包含特定文本的审核记录工具

用法:
    python tools/delete_records_by_text.py <profile_name> <search_text>
    
示例:
    python tools/delete_records_by_text.py default "You are Kilo Code, "
    python tools/delete_records_by_text.py 4claudecode "You are Kilo Code, "
"""
import sqlite3
import sys
import os
from typing import List, Tuple


def find_records_by_text(db_path: str, search_text: str) -> List[Tuple[int, str, int, str, str]]:
    """
    查找包含指定文本的记录
    
    Args:
        db_path: 数据库路径
        search_text: 要搜索的文本
        
    Returns:
        匹配的记录列表 [(id, text, label, category, created_at), ...]
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 使用 LIKE 查询包含指定文本的记录
    cursor.execute("""
        SELECT id, text, label, category, created_at 
        FROM samples 
        WHERE text LIKE ?
        ORDER BY id DESC
    """, (f'%{search_text}%',))
    
    records = cursor.fetchall()
    conn.close()
    
    return records


def delete_records_by_ids(db_path: str, ids: List[int]) -> int:
    """
    根据ID列表删除记录
    
    Args:
        db_path: 数据库路径
        ids: 要删除的记录ID列表
        
    Returns:
        实际删除的记录数
    """
    if not ids:
        return 0
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 批量删除
    placeholders = ','.join('?' * len(ids))
    cursor.execute(
        f"DELETE FROM samples WHERE id IN ({placeholders})",
        ids
    )
    
    deleted_count = cursor.rowcount
    conn.commit()
    
    # 执行 VACUUM 释放空间
    print(f"\n正在执行 VACUUM 释放空间...")
    cursor.execute("VACUUM")
    
    conn.close()
    
    return deleted_count


def get_db_stats(db_path: str) -> Tuple[int, int, int]:
    """
    获取数据库统计信息
    
    Returns:
        (总记录数, 通过数, 违规数)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 总数
    cursor.execute("SELECT COUNT(*) FROM samples")
    total = cursor.fetchone()[0]
    
    # 按标签统计
    cursor.execute("""
        SELECT label, COUNT(*) 
        FROM samples 
        GROUP BY label
    """)
    stats = cursor.fetchall()
    
    pass_count = 0
    violation_count = 0
    for label, count in stats:
        if label == 0:
            pass_count = count
        elif label == 1:
            violation_count = count
    
    conn.close()
    
    return total, pass_count, violation_count


def main():
    if len(sys.argv) < 3:
        print("用法: python tools/delete_records_by_text.py <profile_name> <search_text>")
        print("\n示例:")
        print("  python tools/delete_records_by_text.py default \"You are Kilo Code, \"")
        print("  python tools/delete_records_by_text.py 4claudecode \"You are Kilo Code, \"")
        sys.exit(1)
    
    profile_name = sys.argv[1]
    search_text = sys.argv[2]
    
    # 构建数据库路径
    db_path = f"configs/mod_profiles/{profile_name}/history.db"
    
    # 检查数据库是否存在
    if not os.path.exists(db_path):
        print(f"❌ 错误: 数据库不存在: {db_path}")
        print(f"\n可用的 profile:")
        profiles_dir = "configs/mod_profiles"
        if os.path.exists(profiles_dir):
            for item in os.listdir(profiles_dir):
                item_path = os.path.join(profiles_dir, item)
                if os.path.isdir(item_path):
                    db_file = os.path.join(item_path, "history.db")
                    if os.path.exists(db_file):
                        print(f"  - {item}")
        sys.exit(1)
    
    print(f"📊 数据库: {db_path}")
    print(f"🔍 搜索文本: {repr(search_text)}")
    print("="*80)
    
    # 获取删除前的统计
    total_before, pass_before, violation_before = get_db_stats(db_path)
    print(f"\n删除前统计:")
    print(f"  总记录数: {total_before}")
    print(f"  通过: {pass_before} ({pass_before/total_before*100:.1f}%)" if total_before > 0 else "  通过: 0")
    print(f"  违规: {violation_before} ({violation_before/total_before*100:.1f}%)" if total_before > 0 else "  违规: 0")
    
    # 查找匹配的记录
    print(f"\n正在查找包含 {repr(search_text)} 的记录...")
    records = find_records_by_text(db_path, search_text)
    
    if not records:
        print(f"✅ 未找到包含 {repr(search_text)} 的记录")
        sys.exit(0)
    
    print(f"\n找到 {len(records)} 条匹配记录:")
    print("-"*80)
    
    # 显示前10条记录预览
    preview_count = min(10, len(records))
    for i, record in enumerate(records[:preview_count]):
        id, text, label, category, created_at = record
        label_str = "❌ 违规" if label == 1 else "✅ 通过"
        text_preview = text[:100] + "..." if len(text) > 100 else text
        
        print(f"\n[{i+1}] ID: {id} | {label_str} | 类别: {category or 'N/A'}")
        print(f"    时间: {created_at}")
        print(f"    文本: {text_preview}")
    
    if len(records) > preview_count:
        print(f"\n... 还有 {len(records) - preview_count} 条记录未显示")
    
    print("\n" + "="*80)
    
    # 确认删除
    print(f"\n⚠️  警告: 即将删除 {len(records)} 条记录!")
    confirm = input("确认删除? (yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y']:
        print("❌ 已取消删除操作")
        sys.exit(0)
    
    # 执行删除
    print(f"\n正在删除 {len(records)} 条记录...")
    ids_to_delete = [record[0] for record in records]
    deleted_count = delete_records_by_ids(db_path, ids_to_delete)
    
    print(f"✅ 成功删除 {deleted_count} 条记录")
    
    # 获取删除后的统计
    total_after, pass_after, violation_after = get_db_stats(db_path)
    print(f"\n删除后统计:")
    print(f"  总记录数: {total_after} (减少 {total_before - total_after})")
    print(f"  通过: {pass_after} ({pass_after/total_after*100:.1f}%)" if total_after > 0 else "  通过: 0")
    print(f"  违规: {violation_after} ({violation_after/total_after*100:.1f}%)" if total_after > 0 else "  违规: 0")
    
    print("\n✅ 操作完成!")


if __name__ == "__main__":
    main()