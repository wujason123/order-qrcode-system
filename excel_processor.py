#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单Excel数据处理和二维码生成脚本
"""

import pandas as pd
import qrcode
import os
import sqlite3
from datetime import datetime
import random

# 导入生产订单管理器
try:
    from production_order_manager import ProductionOrderManager
    PRODUCTION_MANAGER_AVAILABLE = True
except ImportError:
    PRODUCTION_MANAGER_AVAILABLE = False
    print("⚠️ 生产订单管理器未正确导入，将跳过原料库存扣减")

class OrderProcessor:
    def __init__(self, excel_file="orders.xlsx", db_file="orders.db", base_url=None):
        self.excel_file = excel_file
        self.db_file = db_file
        
        # 如果没有提供base_url，自动获取本机IP
        if base_url is None:
            self.base_url = self._get_base_url()
        else:
            self.base_url = base_url
            
        self.qr_output_dir = "qrcodes"
        
        # 确保输出目录存在
        if not os.path.exists(self.qr_output_dir):
            os.makedirs(self.qr_output_dir)
    
    def _get_base_url(self):
        """自动获取本机IP地址并生成base_url"""
        import socket
        try:
            # 连接到一个远程地址来获取本机IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            base_url = f"http://{local_ip}:5000"
            print(f"自动检测到本机IP地址: {local_ip}")
            print(f"二维码将使用URL: {base_url}")
            return base_url
        except Exception as e:
            print(f"获取IP地址失败，使用localhost: {e}")
            return "http://localhost:5000"
    
    def _check_duplicate_orders(self, df):
        """检查Excel中的重复订单号"""
        try:
            # 检查Excel内部重复
            order_ids = df["订单号"].astype(str).str.strip()
            duplicates_in_excel = order_ids[order_ids.duplicated()].unique()
            
            if len(duplicates_in_excel) > 0:
                error_msg = f"Excel文件中发现重复的订单号: {', '.join(duplicates_in_excel)}"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg, "duplicates": duplicates_in_excel.tolist()}
            
            # 检查与数据库中现有订单的重复
            if os.path.exists(self.db_file):
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                
                # 获取数据库中现有的订单号
                cursor.execute("SELECT order_id FROM orders")
                existing_orders = {row[0] for row in cursor.fetchall()}
                conn.close()
                
                # 检查新订单号是否与现有订单重复
                new_order_ids = set(order_ids.tolist())
                duplicates_with_db = new_order_ids.intersection(existing_orders)
                
                if duplicates_with_db:
                    error_msg = f"以下订单号在数据库中已存在: {', '.join(duplicates_with_db)}"
                    print(f"❌ {error_msg}")
                    return {
                        "success": False, 
                        "error": error_msg, 
                        "duplicates": list(duplicates_with_db),
                        "type": "database_duplicate"
                    }
            
            print("✅ 订单号重复检查通过")
            return {"success": True}
            
        except Exception as e:
            error_msg = f"检查订单号重复时出错: {str(e)}"
            print(error_msg)
            return {"success": False, "error": error_msg}
    
    def init_database(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 创建库存物料表（支持原料和产品）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inventory_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_code TEXT UNIQUE NOT NULL,
                    item_name TEXT NOT NULL,
                    item_category TEXT NOT NULL,  -- '原材料', '包装', '配件', '产品'
                    unit TEXT NOT NULL,
                    current_stock REAL DEFAULT 0,
                    weighted_avg_price REAL DEFAULT 0,
                    total_value REAL DEFAULT 0,
                    low_stock_threshold INTEGER DEFAULT 100,
                    warning_stock_threshold INTEGER DEFAULT 200,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建订单表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL,
                    order_date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    product_details TEXT NOT NULL,
                    product_code TEXT,
                    quantity INTEGER DEFAULT 1,
                    unit_cost REAL DEFAULT 0,
                    total_cost REAL DEFAULT 0,
                    profit REAL DEFAULT 0,
                    profit_status TEXT DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_code) REFERENCES inventory_items (item_code)
                )
            ''')
            
            # 创建采购记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS purchase_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchase_id TEXT UNIQUE NOT NULL,
                    item_code TEXT NOT NULL,
                    supplier_name TEXT NOT NULL,
                    purchase_date TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    unit_price REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    other_fees REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_code) REFERENCES inventory_items (item_code)
                )
            ''')
            
            # 创建BOM物料清单表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bom_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_code TEXT NOT NULL,
                    material_code TEXT NOT NULL,
                    required_quantity REAL NOT NULL,
                    unit TEXT NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_code) REFERENCES inventory_items (item_code),
                    FOREIGN KEY (material_code) REFERENCES inventory_items (item_code)
                )
            ''')
            
            # 创建成本配置项表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cost_config_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    item_type TEXT NOT NULL,  -- 'fixed' or 'percentage'
                    default_value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建成本配置表（兼容旧版本）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cost_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_type TEXT UNIQUE NOT NULL,
                    config_value REAL NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建库存变动记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inventory_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_code TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,  -- 'in' or 'out'
                    quantity REAL NOT NULL,
                    unit_price REAL,
                    total_amount REAL,
                    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (item_code) REFERENCES inventory_items (item_code)
                )
            ''')

            # 创建生产成本记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS production_costs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cost_id TEXT UNIQUE NOT NULL,
                    product_code TEXT NOT NULL,
                    material_cost REAL NOT NULL,
                    labor_cost REAL NOT NULL,
                    management_cost REAL NOT NULL,
                    transport_cost REAL NOT NULL,
                    other_cost REAL NOT NULL,
                    tax_cost REAL NOT NULL,
                    total_cost REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_cost REAL NOT NULL,
                    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_code) REFERENCES inventory_items (item_code)
                )
            ''')
            
            # 检查是否需要初始化默认成本配置项
            cursor.execute('SELECT COUNT(*) FROM cost_config_items')
            if cursor.fetchone()[0] == 0:
                # 插入默认成本配置项
                default_configs = [
                    ('人工费率', 'fixed', 60.0, '元/小时', '按工时计算的人工成本费率'),
                    ('管理费率', 'percentage', 15.0, '%', '管理成本费率（占材料成本的百分比）'),
                    ('运输费率', 'percentage', 5.0, '%', '运输成本费率（占材料成本的百分比）'),
                    ('税费', 'percentage', 13.0, '%', '增值税等税费'),
                    ('其他费用', 'fixed', 0.0, '元', '固定的其他费用')
                ]
                
                cursor.executemany('''
                    INSERT INTO cost_config_items 
                    (item_name, item_type, default_value, unit, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', default_configs)
                
                print("✅ 初始化默认成本配置项完成")
            
            conn.commit()
            conn.close()
            print("✅ 数据库初始化完成")
            return True
            
        except Exception as e:
            print(f"❌ 数据库初始化失败: {str(e)}")
            if conn:
                conn.rollback()
                conn.close()
            return False

    def _add_column_if_not_exists(self, cursor, table_name, column_name, column_definition):
        """安全添加数据库列"""
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
        except sqlite3.OperationalError:
            pass  # 列已存在

    def process_excel(self):
        """处理Excel文件并导入数据库"""
        try:
            # 读取Excel文件
            df = pd.read_excel(self.excel_file)
            print(f"读取Excel文件: {self.excel_file}")
            print(f"共读取 {len(df)} 条订单记录")
            
            # 打印列名，便于调试
            print("Excel列名:", df.columns.tolist())
            
            # 连接数据库
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 清空现有数据（可选）
            cursor.execute("DELETE FROM orders")
            
            # 插入数据
            for index, row in df.iterrows():
                try:
                    order_id = str(row["订单号"])
                    customer_name = str(row["客户姓名"])
                    order_date = str(row["订单日期"])
                    amount = float(row["金额"])
                    product_details = str(row["产品详情"])
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO orders 
                        (order_id, customer_name, order_date, amount, product_details)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (order_id, customer_name, order_date, amount, product_details))
                    
                    print(f"处理订单: {order_id}")
                    
                except Exception as e:
                    print(f"处理第 {index+1} 行数据时出错: {e}")
                    continue
            
            conn.commit()
            conn.close()
            print("数据导入完成")
            return True
            
        except Exception as e:
            print(f"处理Excel文件时出错: {e}")
            return False

    def process_excel_data(self):
        """处理Excel文件并导入数据库（返回详细状态）"""
        conn = None
        try:
            # 读取Excel文件
            df = pd.read_excel(self.excel_file)
            total_rows = len(df)
            print(f"📋 读取销售订单Excel文件: {self.excel_file}")
            print(f"📦 共读取 {total_rows} 条销售订单记录")
            
            # 检查必需的列 - 新格式支持盈亏计算
            required_columns = ["订单号", "客户姓名", "订单日期", "产品编码", "产品名称", "数量", "销售单价"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                error_msg = f"销售订单Excel文件缺少必需的列: {', '.join(missing_columns)}"
                print(f"❌ {error_msg}")
                print("💡 新格式应包含：订单号、客户姓名、订单日期、产品编码、产品名称、数量、销售单价")
                return {"success": False, "error": error_msg}
            
            # 检查订单号重复
            duplicate_check = self._check_duplicate_orders(df)
            if not duplicate_check["success"]:
                return duplicate_check
            
            # 连接数据库
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 插入数据并计算盈亏
            success_count = 0
            for index, row in df.iterrows():
                try:
                    order_id = str(row["订单号"]).strip()
                    customer_name = str(row["客户姓名"]).strip()
                    order_date = str(row["订单日期"]).strip()
                    product_code = str(row["产品编码"]).strip()
                    product_name = str(row["产品名称"]).strip()
                    quantity = float(row["数量"])
                    sale_unit_price = float(row["销售单价"])
                    
                    # 基本验证
                    if not order_id or order_id == 'nan':
                        print(f"⚠️ 第 {index+1} 行：订单号为空，跳过")
                        continue
                    
                    # 计算销售总额
                    sale_total_amount = quantity * sale_unit_price
                    
                    # 检查成品库存状态
                    cursor.execute('''
                        SELECT current_stock
                        FROM inventory_items
                        WHERE item_code = ? AND item_category = '产品'
                    ''', (product_code,))
                    
                    product_stock_result = cursor.fetchone()
                    
                    if product_stock_result:
                        current_product_stock = product_stock_result[0] or 0
                        
                        # 检查成品库存是否充足（不阻止导入，只提示）
                        if current_product_stock < quantity:
                            shortage = quantity - current_product_stock
                            print(f"⚠️ 订单 {order_id} 成品库存不足（允许负库存）:")
                            print(f"   📉 {product_code}: 需要{quantity}个, 库存{current_product_stock}个, 缺少{shortage}个")
                        else:
                            print(f"✅ 订单 {order_id} 成品库存充足")
                        
                        # 🔥 重要：销售订单应该扣减成品库存，而不是原料库存
                        print(f"📦 开始扣减订单 {order_id} 的成品库存...")
                        
                        # 扣减成品库存
                        success = self.record_inventory_transaction(
                            item_code=product_code,
                            transaction_type='out',
                            quantity=quantity,
                            notes=f'销售订单 {order_id} 出库',
                            conn=conn
                        )
                        
                        if not success:
                            raise Exception(f"成品 {product_code} 出库失败")
                        
                        print(f"📦 成品出库: {product_code} × {quantity}")
                        print(f"✅ 订单 {order_id} 成品库存扣减完成")
                    else:
                        # 如果成品不存在于库存中，创建成品库存记录
                        print(f"⚠️ 成品 {product_code} 不存在于库存中，创建库存记录...")
                        
                        cursor.execute('''
                            INSERT INTO inventory_items 
                            (item_code, item_name, item_category, unit,
                             current_stock, weighted_avg_price, total_value,
                             low_stock_threshold, warning_stock_threshold)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            product_code, product_name, '产品', '个',
                            0, 0, 0, 10, 20  # 产品默认阈值
                        ))
                        
                        # 扣减成品库存（允许负库存）
                        success = self.record_inventory_transaction(
                            item_code=product_code,
                            transaction_type='out',
                            quantity=quantity,
                            notes=f'销售订单 {order_id} 出库',
                            conn=conn
                        )
                        
                        if not success:
                            raise Exception(f"成品 {product_code} 出库失败")
                        
                        print(f"📦 成品出库: {product_code} × {quantity} （库存不足，允许负库存）")
                        print(f"✅ 订单 {order_id} 成品库存扣减完成")
                    
                    # 计算产品成本（独立于库存扣减）
                    cost_result = self.calculate_product_cost(product_code, quantity, conn=conn)
                    
                    unit_cost = 0
                    total_cost = 0
                    profit = 0
                    profit_status = 'unknown'
                    
                    if cost_result['success']:
                        unit_cost = cost_result['cost_breakdown']['unit_cost']
                        total_cost = cost_result['cost_breakdown']['total_cost']
                        profit = sale_total_amount - total_cost
                        
                        # 判断盈亏状态
                        if profit > 0:
                            profit_status = 'profit'
                        elif profit < 0:
                            profit_status = 'loss'
                        else:
                            profit_status = 'break_even'
                            
                        print(f"💰 {order_id}: 销售额¥{sale_total_amount:.2f}, 成本¥{total_cost:.2f}, {'盈利' if profit > 0 else '亏损' if profit < 0 else '保本'}¥{abs(profit):.2f}")
                    else:
                        print(f"⚠️ {order_id}: 无法计算成本 - {cost_result.get('error', '未知错误')}，但库存已正确扣减")
                    
                    # 构建产品详情描述
                    product_details = f"{product_name} (编码: {product_code})"
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO orders 
                        (order_id, customer_name, order_date, amount, product_details, 
                         product_code, quantity, unit_cost, total_cost, profit, profit_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (order_id, customer_name, order_date, sale_total_amount, product_details,
                          product_code, quantity, unit_cost, total_cost, profit, profit_status))
                    
                    success_count += 1
                    print(f"✅ 处理销售订单: {order_id} - {product_name}")
                    
                except Exception as e:
                    print(f"❌ 处理第 {index+1} 行销售订单数据时出错: {e}")
                    continue
            
            conn.commit()
            
            if success_count == 0:
                return {"success": False, "error": "没有成功处理任何销售订单数据"}
            
            print(f"🎉 销售订单导入完成，成功处理 {success_count} 条订单，已自动计算盈亏状态")
            
            # 🔥 重要：销售订单处理完成后，自动转换为生产订单并扣减原料库存
            if PRODUCTION_MANAGER_AVAILABLE and success_count > 0:
                print("\n🏭 开始自动处理生产订单，扣减原料库存...")
                try:
                    production_manager = ProductionOrderManager(self.db_file)
                    production_manager.process_all_sales_orders()
                    print("✅ 生产订单处理完成，原料库存已自动扣减")
                except Exception as e:
                    print(f"⚠️ 生产订单处理失败: {e}，但销售订单导入成功")
            
            return {
                "success": True, 
                "processed_orders": total_rows,
                "success_count": success_count, 
                "failed_count": total_rows - success_count,
                "count": success_count, 
                "total": total_rows,
                "production_processed": PRODUCTION_MANAGER_AVAILABLE and success_count > 0
            }
            
        except Exception as e:
            error_msg = f"处理销售订单Excel文件时出错: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def generate_qrcodes(self):
        """为所有订单生成二维码"""
        try:
            # 从数据库读取订单数据
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT order_id FROM orders")
            orders = cursor.fetchall()
            conn.close()
            
            print(f"开始生成 {len(orders)} 个二维码...")
            
            for order in orders:
                order_id = order[0]
                # 生成查询URL - 指向公共查询页面
                url = f"{self.base_url}/public?order_id={order_id}"
                
                # 创建二维码
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(url)
                qr.make(fit=True)
                
                # 生成图片
                img = qr.make_image(fill_color="black", back_color="white")
                
                # 保存图片
                img_path = f"{self.qr_output_dir}/order_{order_id}.png"
                img.save(img_path)
                print(f"生成二维码: {img_path}")
            
            print("所有二维码生成完成！")
            return True
            
        except Exception as e:
            print(f"生成二维码时出错: {e}")
            return False

    def generate_qr_codes(self):
        """为所有订单生成二维码（返回详细状态）"""
        try:
            # 从数据库读取订单数据
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT order_id FROM orders")
            orders = cursor.fetchall()
            conn.close()
            
            total_orders = len(orders)
            if total_orders == 0:
                return {"success": False, "error": "数据库中没有找到订单数据"}
            
            print(f"开始生成 {total_orders} 个二维码...")
            
            success_count = 0
            for order in orders:
                order_id = order[0]
                try:
                    # 生成查询URL - 指向公共查询页面
                    url = f"{self.base_url}/public?order_id={order_id}"
                    
                    # 创建二维码
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(url)
                    qr.make(fit=True)
                    
                    # 生成图片
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    # 保存图片
                    img_path = f"{self.qr_output_dir}/order_{order_id}.png"
                    img.save(img_path)
                    success_count += 1
                    print(f"生成二维码: {img_path}")
                    
                except Exception as e:
                    print(f"为订单 {order_id} 生成二维码时出错: {e}")
                    continue
            
            if success_count == 0:
                return {"success": False, "error": "没有成功生成任何二维码"}
            
            print(f"二维码生成完成，成功生成 {success_count} 个二维码")
            return {"success": True, "count": success_count, "total": total_orders}
            
        except Exception as e:
            error_msg = f"生成二维码时出错: {str(e)}"
            print(error_msg)
            return {"success": False, "error": error_msg}
    
    def create_sample_excel(self, filename="orders.xlsx"):
        """创建示例Excel文件"""
        sample_data = {
            "订单号": ["ORD001", "ORD002", "ORD003", "ORD004", "ORD005"],
            "客户姓名": ["张三", "李四", "王五", "赵六", "钱七"],
            "订单日期": ["2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19"],
            "产品编码": ["PROD001", "PROD002", "PROD001", "PROD002", "PROD001"],
            "产品名称": ["智能手机", "平板电脑", "智能手机", "平板电脑", "智能手机"],
            "数量": [1, 1, 2, 1, 1],
            "销售单价": [2000.00, 3500.00, 1800.00, 3200.00, 2100.00]
        }
        
        df = pd.DataFrame(sample_data)
        df.to_excel(filename, index=False)
        print(f"示例Excel文件已创建: {filename}")
        return filename
    
    def run_full_process(self):
        """运行完整流程"""
        print("=== 订单二维码生成系统 ===")
        
        # 检查Excel文件是否存在
        if not os.path.exists(self.excel_file):
            print(f"Excel文件 {self.excel_file} 不存在，创建示例文件...")
            self.create_sales_order_sample_excel(self.excel_file)
        
        # 初始化数据库
        self.init_database()
        
        # 处理Excel数据 - 使用新的支持盈亏计算的函数
        result = self.process_excel_data()
        if result["success"]:
            # 生成二维码
            self.generate_qrcodes()
            print("\n=== 处理完成 ===")
            print(f"数据库文件: {self.db_file}")
            print(f"二维码目录: {self.qr_output_dir}")
        else:
            print(f"❌ 处理失败：{result.get('error', '未知错误')}")

    def process_purchase_orders(self, purchase_excel_file):
        """处理采购订单Excel文件并更新库存"""
        try:
            df = pd.read_excel(purchase_excel_file)
            total_rows = len(df)
            print(f"📥 读取采购订单Excel文件: {purchase_excel_file}")
            print(f"📦 共读取 {total_rows} 条采购记录")
            
            # 检查必需的列
            required_columns = ["采购单号", "物品编码", "物品名称", "供应商", "采购日期", "数量", "单价"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                error_msg = f"采购订单Excel文件缺少必需的列: {', '.join(missing_columns)}"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}
            
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            success_count = 0
            for index, row in df.iterrows():
                try:
                    purchase_id = str(row["采购单号"]).strip()
                    item_code = str(row["物品编码"]).strip()
                    item_name = str(row["物品名称"]).strip()
                    supplier_name = str(row["供应商"]).strip()
                    purchase_date = str(row["采购日期"]).strip()
                    quantity = float(row["数量"])
                    unit_price = float(row["单价"])
                    other_fees = float(row["其他费用"]) if "其他费用" in df.columns else 0
                    unit = str(row["单位"]) if "单位" in df.columns else "个"
                    category = str(row["分类"]) if "分类" in df.columns else "原材料"
                    
                    if not purchase_id or purchase_id == 'nan':
                        print(f"⚠️ 第 {index+1} 行：采购单号为空，跳过")
                        continue
                    
                    total_amount = quantity * unit_price + other_fees
                    
                    # 1. 更新或创建库存物品
                    self._update_inventory_item(cursor, item_code, item_name, category, unit)
                    
                    # 2. 记录采购记录
                    cursor.execute('''
                        INSERT OR REPLACE INTO purchase_records 
                        (purchase_id, item_code, supplier_name, purchase_date, 
                         quantity, unit_price, total_amount, other_fees)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (purchase_id, item_code, supplier_name, purchase_date, 
                          quantity, unit_price, total_amount, other_fees))
                    
                    # 3. 更新库存数量和加权平均价格
                    self._update_weighted_avg_price(cursor, item_code, quantity, unit_price, other_fees)
                    
                    success_count += 1
                    print(f"✅ 处理采购订单: {purchase_id} - {item_name}")
                    
                except Exception as e:
                    print(f"❌ 处理第 {index+1} 行采购数据时出错: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            if success_count == 0:
                return {"success": False, "error": "没有成功处理任何采购订单数据"}
            
            print(f"🎉 采购订单导入完成，成功处理 {success_count} 条记录")
            return {"success": True, "count": success_count, "total": total_rows}
            
        except Exception as e:
            error_msg = f"处理采购订单Excel文件时出错: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    def _update_inventory_item(self, cursor, item_code, item_name, category, unit):
        """更新或创建库存物品"""
        # 检查物品是否已存在
        cursor.execute('''
            SELECT current_stock, weighted_avg_price, total_value, 
                   low_stock_threshold, warning_stock_threshold
            FROM inventory_items 
            WHERE item_code = ?
        ''', (item_code,))
        
        existing = cursor.fetchone()
        
        if existing:
            # 如果物品已存在，只更新名称、分类和单位，保留库存相关信息
            cursor.execute('''
                UPDATE inventory_items 
                SET item_name = ?,
                    item_category = ?,
                    unit = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE item_code = ?
            ''', (item_name, category, unit, item_code))
            print(f"📝 更新物品信息: {item_code} - {item_name} ({category})")
        else:
            # 如果物品不存在，创建新记录
            cursor.execute('''
                INSERT INTO inventory_items 
                (item_code, item_name, item_category, unit,
                 current_stock, weighted_avg_price, total_value,
                 low_stock_threshold, warning_stock_threshold)
                VALUES (?, ?, ?, ?, 0, 0, 0, ?, ?)
            ''', (
                item_code, item_name, category, unit,
                100 if category != '产品' else 10,  # 默认低库存阈值
                200 if category != '产品' else 20   # 默认警告阈值
            ))
            print(f"✨ 创建新物品: {item_code} - {item_name} ({category})")

    def _update_weighted_avg_price(self, cursor, item_code, new_quantity, new_price, other_fees=0):
        """更新库存的加权平均价格"""
        # 获取当前库存信息
        cursor.execute('''
            SELECT current_stock, weighted_avg_price, total_value
            FROM inventory_items WHERE item_code = ?
        ''', (item_code,))
        
        result = cursor.fetchone()
        if result:
            current_stock, current_avg_price, current_total_value = result
            
            # 计算新的加权平均价格
            new_item_total_cost = new_quantity * new_price + other_fees
            new_total_stock = current_stock + new_quantity
            new_total_value = current_total_value + new_item_total_cost
            
            if new_total_stock > 0:
                new_weighted_avg_price = new_total_value / new_total_stock
            else:
                new_weighted_avg_price = 0
            
            # 更新库存信息
            cursor.execute('''
                UPDATE inventory_items 
                SET current_stock = ?, 
                    weighted_avg_price = ?, 
                    total_value = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE item_code = ?
            ''', (new_total_stock, new_weighted_avg_price, new_total_value, item_code))
            
            print(f"📈 更新库存 {item_code}: 数量{current_stock}→{new_total_stock}, 均价¥{current_avg_price:.2f}→¥{new_weighted_avg_price:.2f}")

    def process_bom_data(self, bom_excel_file):
        """处理BOM物料清单Excel文件"""
        try:
            df = pd.read_excel(bom_excel_file)
            total_rows = len(df)
            print(f"📋 读取BOM Excel文件: {bom_excel_file}")
            print(f"🔧 共读取 {total_rows} 条BOM记录")
            
            # 检查必需的列
            required_columns = ["产品编码", "原料编码", "需求数量"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                error_msg = f"BOM Excel文件缺少必需的列: {', '.join(missing_columns)}"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}
            
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 检查并删除重复的(product_code, material_code)组合，保留数据内容最新的记录
            print("🔍 检查并清理重复的BOM记录...")
            cursor.execute("""
                DELETE FROM bom_items 
                WHERE id NOT IN (
                    SELECT MAX(id) 
                    FROM bom_items 
                    GROUP BY product_code, material_code
                )
            """)
            cleaned_count = cursor.rowcount
            if cleaned_count > 0:
                print(f"🗑️ 已清理 {cleaned_count} 条重复的BOM记录")
            
            # 自动注册产品
            print("📝 自动注册产品...")
            unique_products = df['产品编码'].unique()
            for product_code in unique_products:
                # 检查产品是否已存在
                cursor.execute('SELECT item_code FROM inventory_items WHERE item_code = ?', (product_code,))
                if not cursor.fetchone():
                    # 获取产品名称（如果Excel中有这一列）
                    product_name = product_code
                    if '产品名称' in df.columns:
                        product_name = df[df['产品编码'] == product_code]['产品名称'].iloc[0]
                    
                    # 插入新产品
                    cursor.execute('''
                        INSERT INTO inventory_items (
                            item_code, 
                            item_name, 
                            item_category,
                            unit,
                            current_stock,
                            weighted_avg_price,
                            total_value,
                            low_stock_threshold,
                            warning_stock_threshold
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        product_code,
                        product_name,
                        '产品',
                        '个',
                        0,  # 初始库存
                        0,  # 初始平均价格
                        0,  # 初始总价值
                        10, # 默认低库存阈值
                        20  # 默认警告阈值
                    ))
                    print(f"✅ 自动注册产品: {product_code} - {product_name}")
            
            # 自动注册原料
            print("📝 自动注册原料...")
            unique_materials = df['原料编码'].unique()
            for material_code in unique_materials:
                # 检查原料是否已存在
                cursor.execute('SELECT item_code FROM inventory_items WHERE item_code = ?', (material_code,))
                if not cursor.fetchone():
                    # 获取原料名称和分类（如果Excel中有这些列）
                    material_name = material_code
                    material_category = '原材料'  # 默认分类
                    
                    if '原料名称' in df.columns:
                        material_name = df[df['原料编码'] == material_code]['原料名称'].iloc[0]
                    if '分类' in df.columns:
                        material_category = df[df['原料编码'] == material_code]['分类'].iloc[0]
                    
                    # 获取单位（如果Excel中有这一列）
                    unit = '个'  # 默认单位
                    if '单位' in df.columns:
                        unit = df[df['原料编码'] == material_code]['单位'].iloc[0]
                    
                    # 插入新原料
                    cursor.execute('''
                        INSERT INTO inventory_items (
                            item_code, 
                            item_name, 
                            item_category,
                            unit,
                            current_stock,
                            weighted_avg_price,
                            total_value,
                            low_stock_threshold,
                            warning_stock_threshold
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        material_code,
                        material_name,
                        material_category,
                        unit,
                        0,  # 初始库存
                        0,  # 初始平均价格
                        0,  # 初始总价值
                        100, # 默认低库存阈值
                        200  # 默认警告阈值
                    ))
                    print(f"✅ 自动注册原料: {material_code} - {material_name} ({material_category})")
            
            success_count = 0
            update_count = 0
            
            for index, row in df.iterrows():
                try:
                    product_code = str(row["产品编码"]).strip()
                    material_code = str(row["原料编码"]).strip()
                    required_quantity = float(row["需求数量"])
                    unit = str(row["单位"]) if "单位" in df.columns else "个"
                    notes = str(row["备注"]) if "备注" in df.columns else ""
                    
                    if not product_code or not material_code:
                        print(f"⚠️ 第 {index+1} 行：产品编码或原料编码为空，跳过")
                        continue
                    
                    # 检查是否已存在相同的(product_code, material_code)组合
                    cursor.execute('''
                        SELECT id, required_quantity, unit, notes 
                        FROM bom_items 
                        WHERE product_code = ? AND material_code = ?
                    ''', (product_code, material_code))
                    
                    existing = cursor.fetchone()
                    
                    if existing:
                        # 更新现有记录
                        cursor.execute('''
                            UPDATE bom_items 
                            SET required_quantity = ?, unit = ?, notes = ?
                            WHERE product_code = ? AND material_code = ?
                        ''', (required_quantity, unit, notes, product_code, material_code))
                        update_count += 1
                        print(f"🔄 更新BOM: {product_code} 需要 {material_code} × {required_quantity} (原{existing[1]})")
                    else:
                        # 插入新记录
                        cursor.execute('''
                            INSERT INTO bom_items 
                            (product_code, material_code, required_quantity, unit, notes)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (product_code, material_code, required_quantity, unit, notes))
                        success_count += 1
                        print(f"✅ 新增BOM: {product_code} 需要 {material_code} × {required_quantity}")
                    
                except Exception as e:
                    print(f"❌ 处理第 {index+1} 行BOM数据时出错: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            total_processed = success_count + update_count
            if total_processed == 0:
                return {"success": False, "error": "没有成功处理任何BOM数据"}
            
            print(f"🎉 BOM数据导入完成，新增 {success_count} 条，更新 {update_count} 条记录")
            return {"success": True, "count": total_processed, "new": success_count, "updated": update_count, "total": total_rows}
            
        except Exception as e:
            error_msg = f"处理BOM Excel文件时出错: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    def calculate_product_cost(self, product_code, quantity=1, labor_hours=0, conn=None):
        """计算产品的完整成本"""
        close_conn = False
        try:
            if conn is None:
                conn = sqlite3.connect(self.db_file)
                close_conn = True
            cursor = conn.cursor()
            
            print(f"💰 开始计算产品 {product_code} 的成本 (数量: {quantity})")
            
            # 1. 计算材料成本
            material_cost = self._calculate_material_cost(cursor, product_code, quantity)
            
            # 2. 获取所有成本配置项
            cursor.execute('''
                SELECT item_name, item_type, default_value 
                FROM cost_config_items 
                WHERE is_active = 1
            ''')
            configs = cursor.fetchall()
            
            # 3. 初始化成本字典
            costs = {
                'material_cost': material_cost,
                'labor_cost': 0,
                'management_cost': 0,
                'transport_cost': 0,
                'other_costs': {},
                'tax_cost': 0
            }
            
            # 4. 处理每个成本配置项
            for config in configs:
                name = config[0]
                cost_type = config[1]
                value = float(config[2])
                
                # 如果是税费，先跳过，最后计算
                if name == '税费':
                    tax_rate = value / 100 if cost_type == 'percentage' else value
                    continue
                    
                # 根据配置项类型计算成本
                if name == '人工费率':
                    if cost_type == 'fixed':
                        costs['labor_cost'] = labor_hours * value
                    else:
                        costs['labor_cost'] = material_cost * (value / 100)
                elif name == '管理费率':
                    if cost_type == 'fixed':
                        costs['management_cost'] = value
                    else:
                        costs['management_cost'] = material_cost * (value / 100)
                elif name == '运输费率':
                    if cost_type == 'fixed':
                        costs['transport_cost'] = value
                    else:
                        costs['transport_cost'] = material_cost * (value / 100)
                else:  # 处理其他所有成本项（包括设备折旧费等）
                    if cost_type == 'fixed':
                        costs['other_costs'][name] = value
                    else:
                        costs['other_costs'][name] = material_cost * (value / 100)
            
            # 5. 计算不含税总成本
            subtotal_cost = (
                costs['material_cost'] +
                costs['labor_cost'] +
                costs['management_cost'] +
                costs['transport_cost'] +
                sum(costs['other_costs'].values())
            )
            
            # 6. 计算税费（如果有）
            tax_rate = None  # 初始化税率
            if 'tax_rate' in locals():
                costs['tax_cost'] = subtotal_cost * tax_rate
            else:
                costs['tax_cost'] = 0
            
            # 7. 计算总成本
            total_cost = subtotal_cost + costs['tax_cost']
            unit_cost = total_cost / quantity if quantity > 0 else 0
            
            # 提取各项成本值
            material_cost = costs['material_cost']
            labor_cost = costs['labor_cost'] 
            management_cost = costs['management_cost']
            transport_cost = costs['transport_cost']
            tax_cost = costs['tax_cost']
            other_cost = sum(costs['other_costs'].values())
            
            # 4. 保存成本记录
            cost_id = f"{product_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"
            cursor.execute('''
                INSERT INTO production_costs 
                (cost_id, product_code, material_cost, labor_cost, management_cost, 
                 transport_cost, tax_cost, other_cost, total_cost, quantity, unit_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (cost_id, product_code, material_cost, labor_cost, management_cost,
                  transport_cost, tax_cost, other_cost, total_cost, quantity, unit_cost))
            
            if close_conn:
                conn.commit()
            
            cost_breakdown = {
                'product_code': product_code,
                'quantity': quantity,
                'material_cost': round(material_cost, 2),
                'labor_cost': round(labor_cost, 2),
                'management_cost': round(management_cost, 2),
                'transport_cost': round(transport_cost, 2),
                'tax_cost': round(tax_cost, 2),
                'other_cost': round(other_cost, 2),
                'total_cost': round(total_cost, 2),
                'unit_cost': round(unit_cost, 2)
            }
            
            print(f"✅ 成本计算完成:")
            print(f"   📦 材料成本: ¥{material_cost:.2f}")
            print(f"   👷 人工成本: ¥{labor_cost:.2f}")
            print(f"   🏢 管理成本: ¥{management_cost:.2f}")
            print(f"   🚚 运输成本: ¥{transport_cost:.2f}")
            print(f"   💰 税费: ¥{tax_cost:.2f}")
            print(f"   💰 其他成本: ¥{other_cost:.2f}")
            print(f"   💯 总成本: ¥{total_cost:.2f}")
            print(f"   💰 单位成本: ¥{unit_cost:.2f}")
            
            return {"success": True, "cost_breakdown": cost_breakdown}
            
        except Exception as e:
            error_msg = f"计算产品成本时出错: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}
        finally:
            if close_conn and conn:
                try:
                    conn.close()
                except:
                    pass

    def _calculate_material_cost(self, cursor, product_code, quantity):
        """计算材料成本（递归计算BOM）"""
        material_cost = 0
        
        # 获取该产品的BOM
        cursor.execute('''
            SELECT bi.material_code, bi.required_quantity, bi.unit,
                   ii.weighted_avg_price, ii.current_stock
            FROM bom_items bi
            LEFT JOIN inventory_items ii ON bi.material_code = ii.item_code
            WHERE bi.product_code = ?
        ''', (product_code,))
        
        bom_items = cursor.fetchall()
        
        if not bom_items:
            print(f"   ⚠️ {product_code}: 未找到BOM清单")
            return 0
        
        for item in bom_items:
            material_code = item[0]
            required_qty = item[1]
            unit = item[2]
            avg_price = item[3] or 0
            stock = item[4] or 0
            
            total_required = required_qty * quantity
            cost = total_required * avg_price
            material_cost += cost
            
            if stock >= total_required:
                print(f"   🔧 {material_code}: {total_required}{unit} × ¥{avg_price:.2f} = ¥{cost:.2f} (库存充足)")
            elif stock > 0:
                shortage = total_required - stock
                print(f"   📉 {material_code}: {total_required}{unit} × ¥{avg_price:.2f} = ¥{cost:.2f} (库存不足{shortage}{unit})")
            else:
                print(f"   🚫 {material_code}: {total_required}{unit} × ¥{avg_price:.2f} = ¥{cost:.2f} (库存为0或负数)")
            
            # 无论库存是否充足，都按价格计算成本
        
        return material_cost

    def create_purchase_sample_excel(self, filename="purchase_template.xlsx"):
        """创建采购订单示例Excel文件"""
        sample_data = {
            "采购单号": ["PO001", "PO002", "PO003", "PO004", "PO005"],
            "物品编码": ["MAT001", "MAT002", "MAT003", "MAT004", "MAT005"],
            "物品名称": ["钢材", "铝材", "塑料粒", "螺丝", "包装盒"],
            "分类": ["原材料", "原材料", "原材料", "配件", "包装"],
            "供应商": ["钢材供应商A", "铝材供应商B", "塑料供应商C", "五金供应商D", "包装供应商E"],
            "采购日期": ["2024-01-10", "2024-01-11", "2024-01-12", "2024-01-13", "2024-01-14"],
            "数量": [100, 50, 200, 1000, 500],
            "单位": ["公斤", "公斤", "公斤", "个", "个"],
            "单价": [12.50, 18.00, 5.20, 0.15, 2.80],
            "其他费用": [50.00, 30.00, 20.00, 10.00, 15.00]
        }
        
        df = pd.DataFrame(sample_data)
        df.to_excel(filename, index=False)
        print(f"📄 采购订单示例Excel文件已创建: {filename}")
        return filename

    def create_bom_sample_excel(self, filename="bom_template.xlsx"):
        """创建BOM物料清单示例Excel文件"""
        sample_data = {
            "产品编码": ["PROD001", "PROD001", "PROD001", "PROD002", "PROD002"],
            "原料编码": ["MAT001", "MAT002", "MAT004", "MAT001", "MAT003"],
            "需求数量": [2.5, 1.0, 4, 1.8, 3.2],
            "单位": ["公斤", "公斤", "个", "公斤", "公斤"],
            "备注": ["主要材料", "辅助材料", "紧固件", "主要材料", "成型材料"]
        }
        
        df = pd.DataFrame(sample_data)
        df.to_excel(filename, index=False)
        print(f"📄 BOM物料清单示例Excel文件已创建: {filename}")
        return filename

    def create_sales_order_sample_excel(self, filename="template_orders.xlsx"):
        """创建销售订单示例Excel文件（支持盈亏计算）"""
        sample_data = {
            "订单号": ["ORD001", "ORD002", "ORD003", "ORD004", "ORD005"],
            "客户姓名": ["张三", "李四", "王五", "张2", "李3"],
            "订单日期": ["2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19"],
            "产品编码": ["PROD001", "PROD002", "PROD001", "PROD001", "PROD002"],
            "产品名称": ["智能手机", "平板电脑", "智能手机", "智能手机", "平板电脑"],
            "数量": [1, 1, 2, 1, 1],
            "销售单价": [2000.00, 3500.00, 1800.00, 2100.00, 3200.00]
        }
        
        df = pd.DataFrame(sample_data)
        df.to_excel(filename, index=False)
        print(f"📄 销售订单示例Excel文件已创建: {filename}")
        return filename

    def get_inventory_summary(self):
        """获取库存汇总信息"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 获取库存统计（包含负库存）
            cursor.execute('''
                SELECT 
                    item_category,
                    COUNT(*) as item_count,
                    SUM(current_stock) as total_stock,
                    SUM(total_value) as total_value,
                    AVG(weighted_avg_price) as avg_price
                FROM inventory_items 
                GROUP BY item_category
                ORDER BY total_value DESC
            ''')
            
            category_stats = cursor.fetchall()
            
            # 获取库存不足的物品（使用每个物品的实际阈值）
            cursor.execute('''
                SELECT item_code, item_name, current_stock, weighted_avg_price, 
                       low_stock_threshold, warning_stock_threshold
                FROM inventory_items 
                WHERE current_stock < COALESCE(low_stock_threshold, 100)
                ORDER BY current_stock ASC
            ''')
            
            low_stock_items = cursor.fetchall()
            
            # 获取总体统计（包含负库存）
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_items,
                    SUM(current_stock) as total_stock,
                    SUM(total_value) as total_value,
                    COUNT(DISTINCT item_category) as total_categories
                FROM inventory_items
            ''')
            
            overall_stats = cursor.fetchone()
            
            conn.close()
            
            # 格式化分类数据 - 匹配前端期望的格式
            categories = []
            for stat in category_stats:
                categories.append({
                    "category": stat[0] or "未分类",
                    "item_count": stat[1],
                    "total_stock": float(stat[2] or 0),
                    "total_value": float(stat[3] or 0),
                    "avg_price": float(stat[4] or 0)
                })
            
            # 格式化库存不足物品 - 匹配前端期望的格式
            low_stock_formatted = []
            for item in low_stock_items:
                low_stock_formatted.append({
                    "item_code": item[0],
                    "item_name": item[1],
                    "current_stock": float(item[2] or 0),
                    "weighted_avg_price": float(item[3] or 0),
                    "low_stock_threshold": int(item[4] or 100),
                    "warning_stock_threshold": int(item[5] or 200)
                })
            
            return {
                "success": True,
                "total_categories": overall_stats[3] or 0,
                "total_stock": float(overall_stats[1] or 0),
                "total_value": float(overall_stats[2] or 0),
                "categories": categories,
                "low_stock_items": low_stock_formatted
            }
            
        except Exception as e:
            error_msg = f"获取库存汇总时出错: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    def get_cost_analysis_report(self):
        """获取成本分析报告"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 获取最近的成本计算记录
            cursor.execute('''
                SELECT 
                    product_code,
                    material_cost,
                    labor_cost,
                    management_cost,
                    transport_cost,
                    total_cost,
                    unit_cost,
                    quantity,
                    calculation_date
                FROM production_costs 
                ORDER BY calculation_date DESC
                LIMIT 50
            ''')
            
            recent_costs = cursor.fetchall()
            
            # 获取成本配置
            cursor.execute('SELECT config_type, config_value, description FROM cost_config')
            cost_configs = cursor.fetchall()
            
            conn.close()
            
            return {
                "success": True,
                "recent_calculations": [
                    {
                        "product_code": cost[0],
                        "material_cost": float(cost[1] or 0),
                        "labor_cost": float(cost[2] or 0),
                        "management_cost": float(cost[3] or 0),
                        "transport_cost": float(cost[4] or 0),
                        "total_cost": float(cost[5] or 0),
                        "unit_cost": float(cost[6] or 0),
                        "quantity": float(cost[7] or 0),
                        "calculation_date": cost[8]
                    }
                    for cost in recent_costs
                ],
                "cost_configs": [
                    {
                        "config_type": config[0],
                        "config_value": float(config[1]),
                        "description": config[2]
                    }
                    for config in cost_configs
                ]
            }
            
        except Exception as e:
            error_msg = f"获取成本分析报告时出错: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    def update_cost_config(self, config_type, config_value):
        """更新成本配置"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE cost_config 
                SET config_value = ?, last_updated = CURRENT_TIMESTAMP
                WHERE config_type = ?
            ''', (config_value, config_type))
            
            if cursor.rowcount == 0:
                return {"success": False, "error": f"配置项 {config_type} 不存在"}
            
            conn.commit()
            conn.close()
            
            print(f"✅ 成本配置已更新: {config_type} = {config_value}")
            return {"success": True, "message": f"成本配置 {config_type} 已更新为 {config_value}"}
            
        except Exception as e:
            error_msg = f"更新成本配置时出错: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    def get_inventory_items(self, category=None):
        """获取库存物品详情"""
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if category:
                cursor.execute('''
                    SELECT 
                        id,
                        item_code, 
                        item_name, 
                        item_category,
                        unit,
                        current_stock, 
                        weighted_avg_price, 
                        total_value,
                        low_stock_threshold,
                        warning_stock_threshold,
                        last_updated
                    FROM inventory_items 
                    WHERE item_category = ?
                    ORDER BY current_stock ASC
                ''', (category,))
            else:
                cursor.execute('''
                    SELECT 
                        id,
                        item_code, 
                        item_name, 
                        item_category,
                        unit,
                        current_stock, 
                        weighted_avg_price, 
                        total_value,
                        low_stock_threshold,
                        warning_stock_threshold,
                        last_updated
                    FROM inventory_items 
                    ORDER BY item_category, current_stock ASC
                ''')
            
            items = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return {
                'success': True,
                'items': items
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'获取库存物品失败: {str(e)}'
            }

    def update_item_thresholds(self, item_id, low_threshold, warning_threshold):
        """更新物料阈值"""
        try:
            if low_threshold >= warning_threshold:
                return {
                    'success': False,
                    'error': '库存不足阈值必须小于库存警告阈值'
                }
            
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE inventory_items 
                SET low_stock_threshold = ?, 
                    warning_stock_threshold = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (low_threshold, warning_threshold, item_id))
            
            if cursor.rowcount == 0:
                conn.close()
                return {
                    'success': False,
                    'error': '物料不存在'
                }
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'message': '阈值更新成功'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'更新阈值失败: {str(e)}'
            }

    def get_products_with_bom(self):
        """获取有BOM清单的产品列表"""
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row  # 设置 row_factory
            cursor = conn.cursor()
            
            # 获取有BOM清单的产品列表
            cursor.execute('''
                SELECT 
                    product_code,
                    COUNT(material_code) as bom_items_count
                FROM bom_items
                GROUP BY product_code
                ORDER BY product_code
            ''')
            
            products = cursor.fetchall()
            
            if not products:
                print("⚠️ 没有找到任何有BOM清单的产品")
                return {
                    'success': True,
                    'products': [],
                    'count': 0
                }
            
            products_list = []
            for product in products:
                products_list.append({
                    'code': product['product_code'],
                    'name': product['product_code'],  # 直接使用产品编码作为名称
                    'bom_items_count': product['bom_items_count']
                })
            
            print(f"✅ 找到 {len(products_list)} 个有BOM清单的产品")
            for product in products_list:
                print(f"   - {product['code']} ({product['bom_items_count']}个物料)")
            
            return {
                'success': True,
                'products': products_list,
                'count': len(products_list)
            }
            
        except Exception as e:
            error_msg = f"获取产品列表失败: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        finally:
            if conn:
                conn.close()

    def record_inventory_transaction(self, item_code, transaction_type, quantity, unit_price=None, notes=None, conn=None):
        """记录库存变动"""
        close_conn = False
        try:
            if conn is None:
                conn = sqlite3.connect(self.db_file)
                close_conn = True
            cursor = conn.cursor()
            
            # 计算总金额
            total_amount = unit_price * quantity if unit_price is not None else None
            
            # 记录库存变动
            cursor.execute('''
                INSERT INTO inventory_transactions (
                    item_code,
                    transaction_type,
                    quantity,
                    unit_price,
                    total_amount,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                item_code,
                transaction_type,
                quantity,
                unit_price,
                total_amount,
                notes
            ))
            
            # 更新库存数量和价值
            if transaction_type == 'in':
                # 入库：增加库存，更新加权平均价格
                if unit_price is not None:
                    cursor.execute('''
                        UPDATE inventory_items
                        SET 
                            current_stock = current_stock + ?,
                            weighted_avg_price = CASE
                                WHEN current_stock = 0 THEN ?
                                ELSE (weighted_avg_price * current_stock + ? * ?) / (current_stock + ?)
                            END,
                            total_value = (current_stock + ?) * weighted_avg_price,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE item_code = ?
                    ''', (quantity, unit_price, quantity, unit_price, quantity, quantity, item_code))
                else:
                    cursor.execute('''
                        UPDATE inventory_items
                        SET 
                            current_stock = current_stock + ?,
                            total_value = (current_stock + ?) * weighted_avg_price,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE item_code = ?
                    ''', (quantity, quantity, item_code))
            else:
                # 出库：减少库存，保持加权平均价格不变
                cursor.execute('''
                    UPDATE inventory_items
                    SET 
                        current_stock = current_stock - ?,
                        total_value = (current_stock - ?) * weighted_avg_price,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE item_code = ?
                ''', (quantity, quantity, item_code))
            
            if close_conn:
                conn.commit()
                conn.close()
            
            return True
            
        except Exception as e:
            print(f"❌ 记录库存变动失败: {str(e)}")
            if close_conn:
                conn.rollback()
                conn.close()
            return False

    def update_product_stock(self, product_code, quantity, unit_price=None, notes=None):
        """更新产品库存"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 记录产品入库
            success = self.record_inventory_transaction(
                item_code=product_code,
                transaction_type='in',
                quantity=quantity,
                unit_price=unit_price,
                notes=notes,
                conn=conn
            )
            
            if success:
                conn.commit()
                print(f"✅ 产品 {product_code} 入库成功：{quantity}个")
            else:
                conn.rollback()
                print(f"❌ 产品 {product_code} 入库失败")
            
            conn.close()
            return success
            
        except Exception as e:
            print(f"❌ 更新产品库存失败: {str(e)}")
            return False

    def init_sample_data(self):
        """初始化示例数据"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 检查是否已有数据
            cursor.execute('SELECT COUNT(*) FROM inventory_items')
            if cursor.fetchone()[0] > 0:
                conn.close()
                return True
            
            # 插入示例物料数据
            sample_items = [
                ('RAW001', '铝合金', '原材料', '千克', 700, 8.5, 5950.0, 100, 200),
                ('RAW002', '钢材', '原材料', '千克', 500, 12.0, 6000.0, 100, 200),
                ('RAW003', '塑料粒子', '原材料', '千克', 300, 15.0, 4500.0, 100, 200),
                ('PKG001', '包装盒', '包装', '个', 1000, 2.83, 2830.0, 200, 500),
                ('PART001', '螺丝', '配件', '个', 2000, 0.16, 320.0, 500, 1000),
                ('PROD001', '智能手机', '产品', '个', 0, 0, 0, 10, 20),
                ('PROD002', '平板电脑', '产品', '个', 0, 0, 0, 10, 20)
            ]
            
            cursor.executemany('''
                INSERT INTO inventory_items 
                (item_code, item_name, item_category, unit, current_stock, 
                 weighted_avg_price, total_value, low_stock_threshold, warning_stock_threshold)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', sample_items)
            
            # 插入示例BOM数据
            sample_bom = [
                ('PROD001', 'RAW001', 0.5, '千克', '产品A主体材料'),
                ('PROD001', 'RAW002', 0.3, '千克', '产品A加固件'),
                ('PROD001', 'PKG001', 1, '个', '产品A包装'),
                ('PROD001', 'PART001', 4, '个', '产品A固定螺丝'),
                ('PROD002', 'RAW002', 0.8, '千克', '产品B主体材料'),
                ('PROD002', 'RAW003', 0.2, '千克', '产品B外壳'),
                ('PROD002', 'PKG001', 1, '个', '产品B包装'),
                ('PROD002', 'PART001', 6, '个', '产品B固定螺丝')
            ]
            
            cursor.executemany('''
                INSERT INTO bom_items 
                (product_code, material_code, required_quantity, unit, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', sample_bom)
            
            conn.commit()
            conn.close()
            print("✅ 初始化示例数据完成")
            return True
            
        except Exception as e:
            print(f"❌ 初始化示例数据失败: {str(e)}")
            if conn:
                conn.rollback()
                conn.close()
            return False

if __name__ == "__main__":
    processor = OrderProcessor()
    processor.run_full_process() 