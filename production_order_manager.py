#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductionOrderManager:
    """生产订单管理器"""
    
    def __init__(self, db_path='orders.db'):
        self.db_path = db_path
    
    def get_sales_demand(self):
        """获取销售订单需求汇总"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT product_code, SUM(quantity) as total_demand
            FROM orders 
            GROUP BY product_code 
            ORDER BY product_code
        ''')
        
        sales_demand = cursor.fetchall()
        conn.close()
        
        return sales_demand
    
    def get_bom_requirements(self, product_code, quantity):
        """根据BOM获取生产所需原料"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT material_code, required_quantity
            FROM bom_items 
            WHERE product_code = ?
        ''', (product_code,))
        
        bom_items = cursor.fetchall()
        conn.close()
        
        # 计算总需求量
        material_requirements = []
        for material_code, required_qty in bom_items:
            total_needed = required_qty * quantity
            material_requirements.append((material_code, total_needed))
        
        return material_requirements
    
    def get_current_inventory(self, material_code):
        """获取当前库存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT current_stock
            FROM inventory_items 
            WHERE item_code = ?
        ''', (material_code,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else 0
    
    def deduct_material_inventory(self, material_code, quantity, order_reference):
        """扣减原料库存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 获取当前库存
            current_stock = self.get_current_inventory(material_code)
            new_stock = current_stock - quantity
            
            # 更新库存
            cursor.execute('''
                UPDATE inventory_items 
                SET current_stock = ?, last_updated = ?
                WHERE item_code = ?
            ''', (new_stock, datetime.now().isoformat(), material_code))
            
            # 记录库存交易
            cursor.execute('''
                INSERT INTO inventory_transactions 
                (item_code, transaction_type, quantity, unit_price, total_amount, 
                transaction_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                material_code, 
                '生产出库', 
                -quantity,  # 负数表示出库
                0,  # 单价，生产出库不涉及金额
                0,  # 总金额
                datetime.now().isoformat(),
                f'生产订单原料消耗: {order_reference} - {material_code} × {quantity}'
            ))
            
            conn.commit()
            
            logger.info(f"✅ 原料出库: {material_code} × {quantity} (剩余: {new_stock})")
            return True, f"库存扣减成功，剩余: {new_stock}"
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ 扣减原料库存失败: {e}")
            return False, str(e)
        finally:
            conn.close()
    
    def create_production_order(self, product_code, quantity):
        """创建生产订单并扣减原料库存"""
        
        print(f"\n🏭 创建生产订单: {product_code} × {quantity}")
        
        # 获取BOM需求
        material_requirements = self.get_bom_requirements(product_code, quantity)
        
        if not material_requirements:
            print(f"❌ 产品 {product_code} 没有找到BOM配方")
            return False
        
        print(f"📋 根据BOM计算原料需求:")
        
        # 检查库存并扣减
        production_order_id = f"PROD_{product_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        all_success = True
        
        for material_code, needed_quantity in material_requirements:
            current_stock = self.get_current_inventory(material_code)
            
            print(f"   🔧 {material_code}: 需要 {needed_quantity}, 库存 {current_stock}")
            
            if current_stock < needed_quantity:
                print(f"   ⚠️ {material_code}: 库存不足 (缺少 {needed_quantity - current_stock})")
                # 继续执行，允许负库存
            
            # 扣减库存
            success, message = self.deduct_material_inventory(
                material_code, needed_quantity, production_order_id
            )
            
            if not success:
                print(f"   ❌ {material_code}: 扣减失败 - {message}")
                all_success = False
            else:
                print(f"   ✅ {material_code}: {message}")
        
        if all_success:
            print(f"🎉 生产订单 {production_order_id} 创建成功，原料库存已扣减")
        else:
            print(f"⚠️ 生产订单 {production_order_id} 部分成功，请检查库存状态")
        
        return all_success
    
    def process_all_sales_orders(self):
        """处理所有销售订单，转换为生产订单"""
        
        print("🚀 开始处理销售订单转生产订单...")
        
        # 获取销售需求
        sales_demand = self.get_sales_demand()
        
        if not sales_demand:
            print("❌ 没有找到销售订单")
            return
        
        print(f"📊 发现 {len(sales_demand)} 种产品的销售需求:")
        for product_code, total_quantity in sales_demand:
            print(f"   📦 {product_code}: {total_quantity} 件")
        
        # 为每种产品创建生产订单
        for product_code, total_quantity in sales_demand:
            self.create_production_order(product_code, total_quantity)
        
        print("\n🎯 生产订单处理完成！")
    
    def show_inventory_summary(self):
        """显示库存汇总"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        print("\n📊 当前库存状态:")
        cursor.execute('SELECT item_code, current_stock FROM inventory_items ORDER BY item_code')
        materials = cursor.fetchall()
        
        for material_code, quantity in materials:
            status = "⚠️" if quantity < 0 else "✅"
            print(f"   {status} {material_code}: {quantity}")
        
        conn.close()

def main():
    """主函数"""
    manager = ProductionOrderManager()
    
    print("=" * 60)
    print("🏭 生产订单管理系统")
    print("=" * 60)
    
    # 显示当前库存
    manager.show_inventory_summary()
    
    # 处理销售订单
    manager.process_all_sales_orders()
    
    # 显示处理后的库存
    manager.show_inventory_summary()

if __name__ == '__main__':
    main() 