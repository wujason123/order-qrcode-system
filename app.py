#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单查询Flask后端服务
"""

from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, flash
from flask_cors import CORS
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime
from excel_processor import OrderProcessor

app = Flask(__name__)
CORS(app)  # 允许跨域请求
app.secret_key = 'your-secret-key-change-in-production'  # 用于flash消息

# 配置
DB_FILE = "orders.db"
QR_DIR = "qrcodes"
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# 确保上传目录存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # 使返回结果可以像字典一样访问
    return conn

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/print')
def print_page():
    """打印预览页面"""
    return render_template('print.html')

@app.route('/order')
def get_order():
    """获取订单信息API"""
    order_id = request.args.get('order_id')
    
    if not order_id:
        return jsonify({
            'error': '缺少订单号参数',
            'message': '请提供order_id参数'
        }), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 查询订单信息
        cursor.execute('''
            SELECT order_id, customer_name, order_date, amount, product_details, created_at
            FROM orders 
            WHERE order_id = ?
        ''', (order_id,))
        
        order = cursor.fetchone()
        conn.close()
        
        if order:
            # 转换为字典格式
            order_data = {
                'order_id': order['order_id'],
                'customer_name': order['customer_name'],
                'order_date': order['order_date'],
                'amount': order['amount'],
                'product_details': order['product_details'],
                'created_at': order['created_at']
            }
            
            return jsonify({
                'success': True,
                'data': order_data
            })
        else:
            return jsonify({
                'error': '订单不存在',
                'message': f'未找到订单号为 {order_id} 的订单'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': '服务器错误',
            'message': str(e)
        }), 500

@app.route('/orders')
def list_orders():
    """获取所有订单列表（管理用）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT order_id, customer_name, order_date, amount, product_details
            FROM orders 
            ORDER BY order_date DESC
        ''')
        
        orders = cursor.fetchall()
        conn.close()
        
        orders_list = []
        for order in orders:
            orders_list.append({
                'order_id': order['order_id'],
                'customer_name': order['customer_name'],
                'order_date': order['order_date'],
                'amount': order['amount'],
                'product_details': order['product_details']
            })
        
        return jsonify({
            'success': True,
            'data': orders_list,
            'count': len(orders_list)
        })
        
    except Exception as e:
        return jsonify({
            'error': '服务器错误',
            'message': str(e)
        }), 500

@app.route('/qrcode/<order_id>')
def get_qrcode(order_id):
    """获取订单二维码图片"""
    try:
        filename = f"order_{order_id}.png"
        return send_from_directory(QR_DIR, filename)
    except Exception as e:
        return jsonify({
            'error': '二维码不存在',
            'message': f'订单 {order_id} 的二维码不存在'
        }), 404

@app.route('/health')
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    """上传Excel文件并处理"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有选择文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        if file and allowed_file(file.filename):
            # 保存上传的文件
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # 获取本机IP地址用于生成二维码
            import socket
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                base_url = f"http://{local_ip}:5000"
            except:
                base_url = "http://localhost:5000"
            
            # 处理Excel文件
            processor = OrderProcessor(excel_file=filepath, base_url=base_url)
            processor.init_database()
            result = processor.process_excel_data()
            
            if result['success']:
                # 生成二维码
                qr_result = processor.generate_qr_codes()
                if qr_result['success']:
                    return jsonify({
                        'success': True,
                        'message': f'成功处理 {result["count"]} 条订单数据，生成 {qr_result["count"]} 个二维码',
                        'orders_count': result['count'],
                        'qr_count': qr_result['count']
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'数据导入成功但二维码生成失败: {qr_result["error"]}'
                    }), 500
            else:
                # 返回详细的错误信息，包括重复订单号
                error_response = {
                    'success': False,
                    'error': result["error"]
                }
                
                # 如果有重复订单号信息，也一并返回
                if 'duplicates' in result:
                    error_response['duplicates'] = result['duplicates']
                    error_response['duplicate_type'] = result.get('type', 'excel_duplicate')
                
                return jsonify(error_response), 400
        else:
            return jsonify({'error': '文件格式不支持，请上传.xlsx或.xls文件'}), 400
            
    except Exception as e:
        return jsonify({'error': f'上传处理失败: {str(e)}'}), 500

@app.route('/api/orders')
def get_all_orders():
    """获取所有订单列表API"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders ORDER BY order_date DESC')
        orders = cursor.fetchall()
        conn.close()
        
        orders_list = []
        for order in orders:
            orders_list.append({
                'order_id': order['order_id'],
                'customer_name': order['customer_name'],
                'order_date': order['order_date'],
                'amount': order['amount'],
                'product_details': order['product_details']
            })
        
        return jsonify({
            'success': True,
            'orders': orders_list,
            'count': len(orders_list)
        })
        
    except Exception as e:
        return jsonify({'error': f'获取订单列表失败: {str(e)}'}), 500

@app.route('/api/qrcodes')
def get_qr_codes():
    """获取二维码文件列表API"""
    try:
        if os.path.exists(QR_DIR):
            qr_files = [f for f in os.listdir(QR_DIR) if f.endswith('.png')]
            qr_list = []
            for qr_file in qr_files:
                order_id = qr_file.replace('order_', '').replace('.png', '')
                qr_list.append({
                    'order_id': order_id,
                    'filename': qr_file,
                    'url': f'/qrcode/{order_id}'
                })
            
            return jsonify({
                'success': True,
                'qrcodes': qr_list,
                'count': len(qr_list)
            })
        else:
            return jsonify({
                'success': True,
                'qrcodes': [],
                'count': 0
            })
            
    except Exception as e:
        return jsonify({'error': f'获取二维码列表失败: {str(e)}'}), 500

@app.route('/api/duplicates', methods=['DELETE'])
def delete_duplicate_orders():
    """删除指定的重复订单"""
    try:
        data = request.get_json()
        if not data or 'order_ids' not in data:
            return jsonify({'error': '缺少order_ids参数'}), 400
        
        order_ids = data['order_ids']
        if not isinstance(order_ids, list) or len(order_ids) == 0:
            return jsonify({'error': 'order_ids必须是非空数组'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 删除指定的订单
        placeholders = ','.join(['?' for _ in order_ids])
        cursor.execute(f'DELETE FROM orders WHERE order_id IN ({placeholders})', order_ids)
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        # 同时删除对应的二维码文件
        for order_id in order_ids:
            qr_file = f"{QR_DIR}/order_{order_id}.png"
            if os.path.exists(qr_file):
                os.remove(qr_file)
        
        return jsonify({
            'success': True,
            'message': f'成功删除 {deleted_count} 个重复订单',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        return jsonify({'error': f'删除订单失败: {str(e)}'}), 500

@app.route('/download/template')
def download_template():
    """下载Excel模板文件"""
    try:
        from excel_processor import OrderProcessor
        
        # 创建示例Excel文件
        processor = OrderProcessor()
        template_file = "template_orders.xlsx"
        
        # 创建模板数据
        import pandas as pd
        template_data = {
            "订单号": ["ORD001", "ORD002", "ORD003"],
            "客户姓名": ["张三", "李四", "王五"],
            "订单日期": ["2024-01-15", "2024-01-16", "2024-01-17"],
            "金额": [1500.50, 2300.00, 800.75],
            "产品详情": [
                "苹果iPhone 15 Pro - 256GB 深空黑色",
                "小米笔记本Air 13.3英寸 - 银色版",
                "华为FreeBuds Pro 3 - 陶瓷白"
            ]
        }
        
        df = pd.DataFrame(template_data)
        df.to_excel(template_file, index=False)
        
        return send_from_directory('.', template_file, as_attachment=True, 
                                 download_name='订单模板.xlsx')
        
    except Exception as e:
        return jsonify({'error': f'下载模板失败: {str(e)}'}), 500

@app.route('/export/qrcodes')
def export_qrcodes_excel():
    """导出带二维码的Excel文件用于打印"""
    try:
        from excel_processor import OrderProcessor
        import pandas as pd
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, Border, Side
        from openpyxl.utils.dataframe import dataframe_to_rows
        import io
        import tempfile
        
        # 尝试导入Image类，提供兼容性处理
        try:
            from openpyxl.drawing.image import Image as OpenpyxlImage
        except ImportError:
            try:
                from openpyxl.drawing import Image as OpenpyxlImage
            except ImportError:
                OpenpyxlImage = None
        
        # 获取所有订单数据
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT order_id, customer_name, order_date, amount, product_details
            FROM orders 
            ORDER BY order_date DESC
        ''')
        orders = cursor.fetchall()
        conn.close()
        
        if not orders:
            return jsonify({'error': '没有订单数据可导出'}), 404
        
        # 创建工作簿
        wb = Workbook()
        ws = wb.active
        ws.title = "订单二维码打印表"
        
        # 设置列宽
        ws.column_dimensions['A'].width = 15  # 订单号
        ws.column_dimensions['B'].width = 12  # 客户姓名
        ws.column_dimensions['C'].width = 12  # 订单日期
        ws.column_dimensions['D'].width = 12  # 金额
        ws.column_dimensions['E'].width = 30  # 产品详情
        ws.column_dimensions['F'].width = 20  # 二维码
        
        # 设置标题行
        headers = ['订单号', '客户姓名', '订单日期', '金额', '产品详情', '二维码']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, size=12)
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # 设置行高
        ws.row_dimensions[1].height = 30
        
        # 填充数据和插入二维码
        current_row = 2
        for order in orders:
            order_id, customer_name, order_date, amount, product_details = order
            
            # 填充文本数据
            ws.cell(row=current_row, column=1, value=order_id)
            ws.cell(row=current_row, column=2, value=customer_name)
            ws.cell(row=current_row, column=3, value=order_date)
            ws.cell(row=current_row, column=4, value=f'¥{amount:.2f}')
            ws.cell(row=current_row, column=5, value=product_details)
            
            # 插入二维码图片
            qr_file = f"{QR_DIR}/order_{order_id}.png"
            if OpenpyxlImage is None:
                # 如果无法导入Image类，显示文本提示
                ws.cell(row=current_row, column=6, value=f'二维码: {order_id}')
            elif os.path.exists(qr_file):
                try:
                    img = OpenpyxlImage(qr_file)
                    # 调整图片大小（适合打印）
                    img.width = 80
                    img.height = 80
                    # 定位到F列
                    img.anchor = f'F{current_row}'
                    ws.add_image(img)
                except Exception as e:
                    print(f"插入二维码图片失败: {e}")
                    ws.cell(row=current_row, column=6, value=f'二维码: {order_id}')
            else:
                ws.cell(row=current_row, column=6, value=f'二维码: {order_id}')
            
            # 设置行高（如果有图片则高一些，否则正常高度）
            if OpenpyxlImage is not None and os.path.exists(qr_file):
                ws.row_dimensions[current_row].height = 65
            else:
                ws.row_dimensions[current_row].height = 30
            
            # 设置单元格对齐
            for col in range(1, 7):
                cell = ws.cell(row=current_row, column=col)
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            
            current_row += 1
        
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        wb.save(temp_file.name)
        temp_file.close()
        
        # 生成下载文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_name = f'订单二维码打印表_{timestamp}.xlsx'
        
        return send_from_directory(
            os.path.dirname(temp_file.name), 
            os.path.basename(temp_file.name),
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"Excel导出错误: {e}")
        # 如果标准导出失败，尝试简化版本
        try:
            return export_simple_excel()
        except Exception as e2:
            return jsonify({'error': f'导出Excel失败: {str(e)}'}), 500

def export_simple_excel():
    """简化版Excel导出（不包含图片）"""
    try:
        import pandas as pd
        
        # 获取所有订单数据
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT order_id, customer_name, order_date, amount, product_details
            FROM orders 
            ORDER BY order_date DESC
        ''')
        orders = cursor.fetchall()
        conn.close()
        
        if not orders:
            return jsonify({'error': '没有订单数据可导出'}), 404
        
        # 创建DataFrame
        df_data = []
        for order in orders:
            order_id, customer_name, order_date, amount, product_details = order
            df_data.append({
                '订单号': order_id,
                '客户姓名': customer_name,
                '订单日期': order_date,
                '金额': f'¥{amount:.2f}',
                '产品详情': product_details,
                '二维码文件': f'qrcodes/order_{order_id}.png',
                '查询链接': f'http://localhost:5000/order?order_id={order_id}'
            })
        
        df = pd.DataFrame(df_data)
        
        # 创建临时文件
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        df.to_excel(temp_file.name, index=False, engine='openpyxl')
        temp_file.close()
        
        # 生成下载文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_name = f'订单列表_{timestamp}.xlsx'
        
        return send_from_directory(
            os.path.dirname(temp_file.name), 
            os.path.basename(temp_file.name),
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        return jsonify({'error': f'简化Excel导出失败: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return jsonify({
        'error': '页面不存在',
        'message': '请求的资源未找到'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    return jsonify({
        'error': '服务器内部错误',
        'message': '服务器遇到了意外情况'
    }), 500

if __name__ == '__main__':
    import socket
    import os
    
    # 获取本机IP地址
    def get_local_ip():
        try:
            # 连接到一个远程地址来获取本机IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
    
    # 检查数据库文件是否存在
    if not os.path.exists(DB_FILE):
        print(f"警告: 数据库文件 {DB_FILE} 不存在！")
        print("请先运行 excel_processor.py 来创建数据库和处理数据")
    
    # 确保二维码目录存在
    if not os.path.exists(QR_DIR):
        os.makedirs(QR_DIR)
        print(f"创建二维码目录: {QR_DIR}")
    
    # 云部署环境检测
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0' if 'PORT' in os.environ else '0.0.0.0'
    debug = os.environ.get('FLASK_ENV', 'development') != 'production'
    
    if 'PORT' in os.environ:
        # 云部署环境
        print("🌐 检测到云部署环境，启动生产模式...")
        print(f"🚀 应用将在端口 {port} 启动")
        print("📱 部署完成后，您将获得一个公网访问URL")
    else:
        # 本地开发环境
        local_ip = get_local_ip()
        
        print("🚀 订单二维码查询系统启动中...")
        print("=" * 50)
        print(f"💻 电脑端访问: http://localhost:{port}")
        print(f"💻 电脑端访问: http://127.0.0.1:{port}")
        print(f"📱 手机端访问: http://{local_ip}:{port}")
        print(f"🌐 局域网访问: http://{local_ip}:{port}")
        print("=" * 50)
        print()
        print("📱 手机使用步骤:")
        print("1. 确保手机和电脑连接同一WiFi网络")
        print(f"2. 手机浏览器输入: {local_ip}:{port}")
        print("3. 或直接扫描生成的二维码")
        print()
        print("🔧 功能特性:")
        print("  📊 Excel文件上传处理")
        print("  🔗 自动生成订单二维码")
        print("  📱 手机扫码查询订单")
        print("  🔍 网页手动查询订单")
        print()
        print("📡 API端点:")
        print("  - GET  /order?order_id=XXX  查询订单")
        print("  - GET  /orders             查看所有订单")
        print("  - GET  /qrcode/<order_id>  获取二维码")
        print("  - POST /upload             上传Excel文件")
        print("  - GET  /health             健康检查")
        print()
        print(f"⚠️  防火墙提示：如果手机无法访问，请确保Windows防火墙允许Python访问网络")
        print()
    
    app.run(debug=debug, host=host, port=port) 