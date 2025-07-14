#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Web界面上传Excel文件的处理逻辑
模拟app.py中upload_file函数的逻辑
"""

import pandas as pd
import os
from datetime import datetime
from excel_processor import OrderProcessor

def create_test_excel():
    """创建测试用的Excel文件"""
    import random
    
    test_order_id = f'WEB_TEST{random.randint(100, 999)}'
    
    # 创建测试数据
    test_data = [
        {
            '订单号': test_order_id,
            '客户姓名': 'Web测试客户',
            '订单日期': '2024-12-15',
            '产品编码': 'PROD001',
            '产品名称': '智能手机',
            '数量': 1,
            '销售单价': 2200.00
        }
    ]
    
    df = pd.DataFrame(test_data)
    
    # 模拟Web上传的文件命名方式
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_test_web_orders.xlsx"
    filepath = os.path.join("uploads", filename)
    
    # 确保uploads目录存在
    os.makedirs("uploads", exist_ok=True)
    
    df.to_excel(filepath, index=False)
    
    print(f"✅ 创建测试Excel文件: {filepath}")
    print(f"📋 订单内容: {test_data[0]['订单号']} - {test_data[0]['产品名称']} × {test_data[0]['数量']}")
    
    return filepath, test_order_id

def check_product_inventory():
    """检查成品库存状态"""
    import sqlite3
    
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT item_code, item_name, current_stock
        FROM inventory_items 
        WHERE item_category = '产品' AND item_code = 'PROD001'
    ''')
    
    product = cursor.fetchone()
    conn.close()
    
    if product:
        print(f"📦 {product[0]} - {product[1]}: {product[2]} 个")
        return product[2]
    else:
        print("⚠️ 没有找到PROD001产品库存记录")
        return 0

def test_web_upload_logic():
    """测试Web界面上传逻辑"""
    print("🚀 开始测试Web界面上传逻辑...")
    
    # 1. 检查上传前的库存
    print("\n📊 上传前成品库存:")
    before_stock = check_product_inventory()
    
    # 2. 创建测试Excel文件
    filepath, test_order_id = create_test_excel()
    
    # 3. 模拟Web界面的处理逻辑
    print(f"\n🔄 模拟Web界面处理逻辑...")
    print(f"📁 文件路径: {filepath}")
    
    # 这里完全模拟app.py中upload_file函数的逻辑
    processor = OrderProcessor(excel_file=filepath)
    processor.init_database()
    result = processor.process_excel_data()
    
    if result['success']:
        print(f"✅ Web上传处理成功！")
        print(f"📊 处理结果: {result}")
        
        # 生成二维码
        qr_result = processor.generate_qr_codes()
        if qr_result['success']:
            print(f"✅ 成功生成 {qr_result['count']} 个二维码")
        else:
            print(f"❌ 二维码生成失败: {qr_result['error']}")
    else:
        print(f"❌ Web上传处理失败: {result['error']}")
        return False, None
    
    # 4. 检查上传后的库存
    print(f"\n📊 上传后成品库存:")
    after_stock = check_product_inventory()
    
    # 5. 比较库存变化
    change = after_stock - before_stock
    print(f"\n📈 库存变化: {before_stock} → {after_stock} ({change:+})")
    
    if change == -1:
        print("✅ Web界面库存扣减正常！")
        return True, test_order_id
    else:
        print("❌ Web界面库存扣减异常！")
        return False, test_order_id

def check_transactions(order_id):
    """检查交易记录"""
    import sqlite3
    
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, item_code, transaction_type, quantity, 
               transaction_date, notes
        FROM inventory_transactions 
        WHERE notes LIKE ?
        ORDER BY transaction_date DESC
        LIMIT 5
    ''', (f'%{order_id}%',))
    
    transactions = cursor.fetchall()
    
    if transactions:
        print(f"\n📋 交易记录 ({order_id}):")
        for txn in transactions:
            print(f"🔄 {txn[1]} | {txn[2]} | {txn[3]} | {txn[4]} | {txn[5]}")
    else:
        print(f"\n⚠️ 没有找到 {order_id} 的交易记录")
    
    conn.close()

def cleanup():
    """清理测试文件"""
    import glob
    
    test_files = glob.glob("uploads/*test_web_orders.xlsx")
    for file in test_files:
        try:
            os.remove(file)
            print(f"🗑️ 清理测试文件: {file}")
        except:
            pass

def main():
    """主函数"""
    try:
        # 执行测试
        success, test_order_id = test_web_upload_logic()
        
        # 检查交易记录
        if test_order_id:
            check_transactions(test_order_id)
        
        # 清理测试文件
        cleanup()
        
        # 总结
        print(f"\n{'='*60}")
        print("🎯 测试结果总结")
        print(f"{'='*60}")
        
        if success:
            print("✅ Web界面上传逻辑测试通过！")
            print("🎉 库存扣减功能正常工作")
        else:
            print("❌ Web界面上传逻辑测试失败！")
            print("🔧 与启动时逻辑存在差异，需要进一步调试")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        cleanup()

if __name__ == "__main__":
    main() 