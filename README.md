# 订单二维码查询系统

一个完整的销售订单二维码生成和查询系统，支持Excel数据导入、二维码生成、后端API服务和手机友好的前端查询界面。

## 功能特点

- 📊 **Excel数据处理**: 自动读取Excel订单数据并导入数据库
- 🔍 **二维码生成**: 为每个订单自动生成二维码
- 🚀 **REST API**: 提供订单查询API接口
- 📱 **响应式前端**: 手机友好的查询界面
- 💾 **数据库存储**: 使用SQLite存储订单数据
- 🎨 **美观界面**: 现代化的Bootstrap设计
- 🔒 **订单号防重复**: 智能检测并处理重复订单号
- 📄 **分页显示**: 订单列表分页显示，每页9条记录
- 🖨️ **多种打印方式**: 支持Excel导出打印和网页直接打印

## 系统架构

```
订单二维码系统
├── excel_processor.py   # Excel数据处理和二维码生成
├── app.py              # Flask后端API服务
├── templates/          # HTML模板文件
│   └── index.html      # 前端查询界面
├── qrcodes/           # 二维码图片存储目录
├── orders.xlsx        # Excel订单数据文件
├── orders.db          # SQLite数据库
└── requirements.txt   # Python依赖包
```

## 快速开始

### 1. 环境准备

确保安装了Python 3.7+，然后安装依赖：

```bash
pip install -r requirements.txt
```

### 2. 数据准备

系统会自动创建示例Excel文件，或者您可以准备自己的Excel文件，格式如下：

| 订单号 | 客户姓名 | 订单日期 | 金额 | 产品详情 |
|--------|----------|----------|------|----------|
| ORD001 | 张三     | 2024-01-15 | 1500.50 | 苹果iPhone 15 Pro |
| ORD002 | 李四     | 2024-01-16 | 2300.00 | 小米笔记本Air |

### 3. 运行系统

#### 🚀 推荐方式：一键启动（Windows）

```bash
# 双击运行
启动系统.bat
```

或者手动运行：
```bash
python run.py
# 选择"1. 一键启动完整系统"
```

#### 🔧 分步运行（高级用户）

**步骤1: 处理Excel数据并生成二维码**

```bash
python excel_processor.py
```

这将：
- 读取Excel文件（如果不存在会创建示例文件）
- 创建SQLite数据库
- 导入订单数据
- 自动获取本机IP地址
- 为每个订单生成包含正确IP的二维码

**步骤2: 启动Web服务**

```bash
python app.py
```

系统启动后会显示：
- 💻 电脑端访问：http://localhost:5000
- 📱 手机端访问：http://[您的IP]:5000

## ⚠️ 重要：网络配置要求

**手机扫码功能需要手机与电脑在同一WiFi网络下！**

### 🔧 网络配置步骤

1. **网络连接**：确保电脑和手机连接同一WiFi网络
2. **启动系统**：运行系统时会自动显示手机访问地址
3. **测试连接**：手机浏览器先访问显示的IP地址测试连通性
4. **扫码使用**：网络正常后直接扫描二维码即可

### 📋 网络环境支持

✅ **支持的网络环境**：
- 家庭WiFi网络
- 办公室局域网
- 公共WiFi（如允许设备间通信）

❌ **不支持的网络环境**：
- 手机流量网络
- 不同WiFi网络
- 有设备隔离的企业网络

🔍 **遇到网络问题？** 查看项目中的"网络配置指南.txt"获取详细解决方案。

### 4. 使用系统

1. **扫描二维码**: 用手机扫描生成的二维码即可查看订单详情
2. **手动查询**: 在网页上输入订单号查询
3. **浏览所有订单**: 查看系统中所有订单列表

## API接口

### 查询订单详情
```
GET /order?order_id=ORD001
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "order_id": "ORD001",
    "customer_name": "张三",
    "order_date": "2024-01-15",
    "amount": 1500.50,
    "product_details": "苹果iPhone 15 Pro - 256GB 深空黑色"
  }
}
```

### 获取所有订单
```
GET /orders
```

### 获取订单二维码
```
GET /qrcode/ORD001
```

### 删除重复订单
```
DELETE /api/duplicates
Content-Type: application/json

{
  "order_ids": ["ORD001", "ORD002"]
}
```

### 导出Excel打印文件
```
GET /export/qrcodes
```
**功能**: 导出包含二维码图片的Excel文件，用于批量打印

**特点**:
- 包含完整订单信息和二维码图片
- 格式化的打印布局
- 支持Excel的页面设置和打印预览

### 网页打印预览
```
GET /print?order_id=ORD001&order_id=ORD002
```
**功能**: 打开网页打印预览窗口

**特点**:
- 专业的打印样式设计
- 支持选择性打印
- 浏览器直接打印，无需额外软件

### 健康检查
```
GET /health
```

## 文件结构说明

- **excel_processor.py**: 核心数据处理脚本
  - Excel文件读取和验证
  - 数据库初始化和数据导入
  - 二维码批量生成

- **app.py**: Flask Web服务器
  - RESTful API接口
  - 订单查询和列表
  - 二维码图片服务
  - 错误处理

- **templates/index.html**: 前端界面
  - 响应式设计
  - 订单搜索功能
  - 订单详情展示
  - 二维码显示

## 自定义配置

### 修改基础URL

在`excel_processor.py`中修改`base_url`参数：

```python
processor = OrderProcessor(base_url="https://yourdomain.com")
```

### 修改Excel文件路径

```python
processor = OrderProcessor(excel_file="your_orders.xlsx")
```

### 修改数据库文件

```python
processor = OrderProcessor(db_file="your_orders.db")
```

## Excel文件要求

Excel文件必须包含以下列（区分大小写）：

- **订单号**: 唯一订单标识（**必须唯一，不能重复**）
- **客户姓名**: 客户名称
- **订单日期**: 订单创建日期
- **金额**: 订单金额（数字）
- **产品详情**: 产品描述

### 🔒 订单号重复检测

系统会自动检测以下类型的重复：
- **Excel内部重复**: 同一个Excel文件中的重复订单号
- **数据库重复**: 与已存在订单的重复订单号

如果检测到重复，系统将：
1. 显示详细的重复订单号列表
2. 提供一键删除重复订单的选项
3. 允许用户选择保留哪些订单数据

### 🖨️ 二维码打印功能

系统提供两种打印方式：

#### 方式一：Excel导出打印（推荐）
- **操作步骤**：
  1. 点击"Excel打印"按钮
  2. 下载生成的Excel文件
  3. 使用Excel打开文件
  4. 通过Excel的打印功能进行打印
  
- **优势**：
  - 二维码图片质量高，打印清晰
  - 支持Excel的所有打印设置（纸张、边距、缩放等）
  - 可以保存文件用于后续打印
  - 支持批量处理大量订单

#### 方式二：网页直接打印
- **操作步骤**：
  1. 选择要打印的订单（勾选复选框）
  2. 点击"网页打印"按钮
  3. 在弹出的预览窗口中点击"打印"
  4. 选择打印机完成打印
  
- **优势**：
  - 操作简单，即选即打
  - 支持选择性打印
  - 无需下载文件
  - 适合少量订单的快速打印

## 部署说明

### 本地测试

1. 按照"快速开始"步骤运行
2. 访问 http://localhost:5000
3. 扫描qrcodes文件夹中的二维码测试

### 生产部署

1. **使用Gunicorn部署**:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

2. **Nginx反向代理**:
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;
       
       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **环境变量配置**:
   ```bash
   export FLASK_ENV=production
   export DATABASE_URL=sqlite:///orders.db
   ```

## 故障排除

### 📱 网络相关问题

1. **手机无法访问电脑IP地址**
   - ✅ 确保手机和电脑连接同一WiFi网络
   - ✅ 检查Windows防火墙，允许Python程序通过防火墙
   - ✅ 确认路由器没有开启AP隔离功能
   - ✅ 尝试临时关闭防火墙测试

2. **系统显示IP为127.0.0.1**
   - ✅ 检查电脑是否已连接网络
   - ✅ 重启系统让其重新获取IP地址
   - ✅ 检查网络适配器设置

3. **手机扫码后显示"网络错误"**
   - ✅ 手机浏览器先直接访问IP地址测试
   - ✅ 确认二维码内容包含正确的IP地址
   - ✅ 检查企业网络是否有设备间通信限制

### 🔧 常见技术问题

1. **"模块未找到"错误**
   ```bash
   pip install -r requirements.txt
   ```
   或使用：
   ```bash
   # 双击运行
   安装依赖.bat
   ```

2. **Excel文件读取错误**
   - 检查文件路径是否正确
   - 确认Excel列名格式正确（订单号、客户姓名、订单日期、金额、产品详情）
   - 验证数据类型（金额必须是数字）

3. **二维码生成失败**
   - 检查qrcodes目录权限
   - 确认PIL库正确安装
   - 验证订单号格式正确

4. **数据库连接错误**
   - 检查数据库文件权限
   - 确认SQLite可写
   - 重新运行初始化脚本

### 调试模式

启用Flask调试模式：
```bash
export FLASK_DEBUG=1
python app.py
```

## 技术栈

- **后端**: Python 3.7+, Flask 2.3+
- **数据库**: SQLite 3
- **前端**: HTML5, Bootstrap 5, JavaScript ES6
- **数据处理**: Pandas, openpyxl
- **二维码**: qrcode[pil]
- **HTTP**: Flask-CORS

## 许可证

本项目采用MIT许可证。

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 更新日志

### v1.0.0 (2024-01-20)
- 初始版本发布
- 基础Excel处理功能
- 二维码生成功能
- Flask API服务
- 响应式前端界面 