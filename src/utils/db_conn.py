from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import Column, String, DateTime, Text, delete, JSON, BigInteger, Numeric, Integer, SmallInteger, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
Base = declarative_base()


# 主任务表
class AutoCrossTask(Base):
    __tablename__ = "auto_cross_task"
    id = Column(String, primary_key=True)
    product_id = Column(String, unique=True, nullable=False)
    source_url = Column(Text)
    cn_title = Column(Text)
    cn_description = Column(Text)
    ru_title = Column(Text)
    ru_description = Column(Text)
    raw_img_path = Column(Text)
    processed_img_path = Column(Text)
    sku_data = Column(JSONB, default=[])

    # =========新增选品决策字段=========
    decision = Column(String(20), default="pending")
    decision_reason = Column(Text)
    score = Column(Numeric(4,2))
    risk_flag = Column(Integer, default=0)
    market_target = Column(JSONB, default=[])

    task_status = Column(String)
    error_msg = Column(Text)
    erp_goods_id = Column(String(128))
    ozon_goods_id = Column(String(128))
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# 风控拦截日志表
class ProductRiskLog(Base):
    __tablename__ = "product_risk_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_id = Column(String(128), nullable=False)
    agent_name = Column(String(64))
    risk_level = Column(String(32))
    risk_reason = Column(Text)
    risk_detail = Column(JSONB)
    create_time = Column(DateTime, default=datetime.now)


# Ozon热搜飙升词库
class OzonHotKeyword(Base):
    __tablename__ = "ozon_hot_keyword"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False)
    category_id = Column(String(100))
    heat_score = Column(Numeric(10, 2))
    trend_type = Column(String(32))
    crawl_time = Column(DateTime, default=datetime.now)


# 竞品基础数据表
class OzonCompetitor(Base):
    __tablename__ = "ozon_competitor"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ozon_item_id = Column(String(128))
    title = Column(Text)
    category_id = Column(String(100))
    price = Column(Numeric(12, 2))
    sales_count = Column(Integer, default=0)
    review_count = Column(Integer, default=0)
    item_url = Column(Text)
    crawl_time = Column(DateTime, default=datetime.now)


# 竞品差评、风险标签表
class CompetitorReview(Base):
    __tablename__ = "competitor_review"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    competitor_id = Column(BigInteger, ForeignKey("ozon_competitor.id"))
    review_content = Column(Text)
    star = Column(SmallInteger)
    risk_tags = Column(JSONB)
    crawl_time = Column(DateTime, default=datetime.now)


# --------数据库连接与工具函数--------
PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")

DATABASE_URL = f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def task_is_exist(product_id: str) -> bool:
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        stmt = select(AutoCrossTask).where(AutoCrossTask.product_id == product_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none() is not None


async def get_one_task(product_id: str):
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        stmt = select(AutoCrossTask).where(AutoCrossTask.product_id == product_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()


async def save_or_update_task(state: dict):
    """保存/更新auto_cross_task，完整接收LangGraph state全部字段，包含选品decision相关字段"""
    pid = state["product_id"]
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        stmt = select(AutoCrossTask).where(AutoCrossTask.product_id == pid)
        row = await session.execute(stmt)
        task = row.scalar_one_or_none()
        if not task:
            task = AutoCrossTask(id=pid, product_id=pid)

        # 兜底逻辑：cn_title为空，自动读取raw_title
        task.cn_title = state.get("cn_title") or state.get("raw_title")
        task.cn_description = state.get("cn_description") or state.get("raw_desc")

        task.source_url = state.get("source_url")
        task.ru_title = state.get("ru_title")
        task.ru_description = state.get("ru_description")
        task.raw_img_path = ",".join(state.get("raw_img_list", []))
        task.processed_img_path = ",".join(state.get("processed_img_list", []))
        task.sku_data = state.get("raw_sku_list", [])

        # =========写入选品决策字段=========
        task.decision = state.get("decision", "pending")
        task.decision_reason = state.get("decision_reason", "")
        task.score = state.get("score")
        task.risk_flag = 1 if bool(state.get("risk_flag")) else 0
        task.market_target = state.get("market_target", [])

        task.task_status = state.get("status", "pending")
        task.error_msg = state.get("error_msg")
        task.erp_goods_id = state.get("miaoshou_task_id")
        task.ozon_goods_id = state.get("ozon_goods_id")

        session.add(task)
        await session.commit()


async def del_one_task(product_id: str):
    async with AsyncSessionLocal() as session:
        stmt = delete(AutoCrossTask).where(AutoCrossTask.product_id == product_id)
        await session.execute(stmt)
        await session.commit()


# 写入风控日志
async def insert_risk_log(product_id: str, agent_name: str, risk_level: str, risk_reason: str, risk_detail: dict):
    async with AsyncSessionLocal() as session:
        log = ProductRiskLog(
            product_id=product_id,
            agent_name=agent_name,
            risk_level=risk_level,
            risk_reason=risk_reason,
            risk_detail=risk_detail
        )
        session.add(log)
        await session.commit()


# 查询商品全部风险日志
async def get_product_risk_logs(product_id: str):
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        stmt = select(ProductRiskLog).where(ProductRiskLog.product_id == product_id).order_by(ProductRiskLog.create_time.desc())
        res = await session.execute(stmt)
        return res.scalars().all()