#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOM表唯一约束迁移脚本
为bom_items表添加(product_code, material_code)唯一约束
"""

import sqlite3
import os
from datetime import datetime

def migrate_bom_unique_constraint(db_file="orders.db"):
    """迁移BOM表，添加唯一约束"""
    print("🔧 开始BOM表唯一约束迁移...")
    
    if not os.path.exists(db_file):
        print("❌ 数据库文件不存在，无需迁移")
        return
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='bom_items'
        """)
        
        if not cursor.fetchone():
            print("❌ bom_items表不存在，无需迁移")
            conn.close()
            return
        
        # 检查是否已有唯一约束
        cursor.execute("PRAGMA table_info(bom_items)")
        table_info = cursor.fetchall()
        
        # 检查约束是否已存在
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='bom_items' AND type='table'")
        create_sql = cursor.fetchone()[0]
        
        if "UNIQUE(product_code, material_code)" in create_sql:
            print("✅ BOM表已有唯一约束，无需迁移")
            conn.close()
            return
        
        print("📊 分析现有BOM数据...")
        
        # 查找重复记录
        cursor.execute("""
            SELECT product_code, material_code, COUNT(*) as duplicate_count
            FROM bom_items 
            GROUP BY product_code, material_code
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC
        """)
        
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"🔍 发现 {len(duplicates)} 组重复的BOM记录:")
            for dup in duplicates[:5]:  # 显示前5组
                print(f"  {dup[0]} -> {dup[1]}: {dup[2]}条重复")
            
            # 清理重复记录，保留最新的
            print("🗑️ 清理重复记录，保留最新数据...")
            cursor.execute("""
                DELETE FROM bom_items 
                WHERE id NOT IN (
                    SELECT MAX(id) 
                    FROM bom_items 
                    GROUP BY product_code, material_code
                )
            """)
            cleaned_count = cursor.rowcount
            print(f"🗑️ 已清理 {cleaned_count} 条重复记录")
        
        print("🔄 重建BOM表结构...")
        
        # 备份原表数据
        cursor.execute("SELECT * FROM bom_items")
        backup_data = cursor.fetchall()
        
        # 创建新表结构（带唯一约束）
        cursor.execute("DROP TABLE IF EXISTS bom_items_new")
        cursor.execute('''
            CREATE TABLE bom_items_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT NOT NULL,
                material_code TEXT NOT NULL,
                required_quantity REAL NOT NULL,
                unit TEXT DEFAULT '个',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_code, material_code),
                FOREIGN KEY (product_code) REFERENCES inventory_items (item_code),
                FOREIGN KEY (material_code) REFERENCES inventory_items (item_code)
            )
        ''')
        
        # 迁移数据
        if backup_data:
            print(f"📦 迁移 {len(backup_data)} 条BOM记录...")
            cursor.executemany('''
                INSERT OR REPLACE INTO bom_items_new 
                (id, product_code, material_code, required_quantity, unit, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', backup_data)
        
        # 重命名表
        cursor.execute("DROP TABLE bom_items")
        cursor.execute("ALTER TABLE bom_items_new RENAME TO bom_items")
        
        # 重建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bom_product ON bom_items (product_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bom_material ON bom_items (material_code)')
        
        # 验证迁移结果
        cursor.execute("SELECT COUNT(*) FROM bom_items")
        final_count = cursor.fetchone()[0]
        
        # 验证唯一约束
        cursor.execute("""
            SELECT product_code, material_code, COUNT(*) as cnt
            FROM bom_items 
            GROUP BY product_code, material_code
            HAVING COUNT(*) > 1
        """)
        remaining_duplicates = cursor.fetchall()
        
        conn.commit()
        conn.close()
        
        if remaining_duplicates:
            print(f"⚠️ 迁移完成但仍有 {len(remaining_duplicates)} 组重复记录")
            for dup in remaining_duplicates:
                print(f"  {dup[0]} -> {dup[1]}: {dup[2]}条")
        else:
            print(f"✅ BOM表迁移成功！最终记录数: {final_count}")
            print("🎉 已添加(product_code, material_code)唯一约束")
        
    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        conn.rollback()
        conn.close()

if __name__ == "__main__":
    migrate_bom_unique_constraint() 