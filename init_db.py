from excel_processor import OrderProcessor

def init_database():
    """初始化数据库"""
    processor = OrderProcessor()
    processor.init_database()
    print("✅ 数据库初始化完成")

if __name__ == "__main__":
    init_database() 