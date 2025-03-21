from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, Boolean, Integer, Text, event, create_engine
from sqlalchemy.orm import declarative_base, relationship
import uuid
from datetime import datetime

# Tạo lớp Base
Base = declarative_base()

# Model bảng users
class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String, unique=True, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column("metadata", JSON, nullable=True, default={})  # ✅ Đảm bảo giá trị mặc định {}

    threads = relationship("Thread", back_populates="user")

# Model bảng threads
class Thread(Base):
    __tablename__ = 'threads'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    createdAt = Column(DateTime, default=datetime.utcnow)
    name = Column(String)
    userId = Column(String, ForeignKey("users.id", ondelete="CASCADE"))
    userIdentifier = Column(String)
    tags = Column(JSON, default=[])  # ✅ Đảm bảo tags có giá trị mặc định là danh sách rỗng []
    metadata_ = Column("metadata", JSON, nullable=True, default={})  # ✅ Đảm bảo metadata có giá trị mặc định {}

    user = relationship("User", back_populates="threads")
    steps = relationship("Step", back_populates="thread", cascade="all, delete")
    tasks = relationship("Task", back_populates="thread", cascade="all, delete")  # Thêm relationship với Task

# Model bảng steps
class Step(Base):
    __tablename__ = 'steps'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    threadId = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    parentId = Column(String, ForeignKey("steps.id"))
    streaming = Column(Boolean, nullable=False, default=False)
    waitForAnswer = Column(Boolean)
    isError = Column(Boolean, default=False)
    metadata_ = Column("metadata", JSON, nullable=True, default={})  # ✅ Thêm giá trị mặc định {}
    tags = Column(JSON, default=[])
    input = Column(Text)
    output = Column(Text)
    createdAt = Column(DateTime, default=datetime.utcnow)
    start = Column(DateTime)
    end = Column(DateTime)
    defaultOpen = Column(Boolean, default=False)  # ✅ Đảm bảo có giá trị mặc định False
    generation = Column(JSON, default={})  # ✅ Đảm bảo có giá trị mặc định {}
    showInput = Column(Text)
    language = Column(String)
    indent = Column(Integer)

    thread = relationship("Thread", back_populates="steps")


# Model bảng tasks
class Task(Base):
    __tablename__ = 'tasks'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task = Column(String, nullable=False)  # RX, RC, RD hoặc 1, 2, 3, 4
    description = Column(Text)  # Mô tả task, ví dụ: "post + content"
    results = Column(Text)  # Kết quả của task, ví dụ: link tới bài viết
    status = Column(Integer, default=0)  # 0: doing, 1: done
    num_loop = Column(Integer, default=0)  # Số vòng lặp khi task được schedule
    threadId = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    x_id = Column(String)  # ID của x account trên X
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_ = Column("metadata", JSON, nullable=True, default={})

    thread = relationship("Thread", back_populates="tasks")

# Model bảng elements
class Element(Base):
    __tablename__ = 'elements'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    threadId = Column(String, ForeignKey("threads.id", ondelete="CASCADE"))
    type = Column(String)
    url = Column(String)
    chainlitKey = Column(String)
    name = Column(String, nullable=False)
    display = Column(String)
    objectKey = Column(String)
    size = Column(String)
    page = Column(Integer)
    language = Column(String)
    forId = Column(String)
    mime = Column(String)
    props = Column(JSON, default={})  # ✅ Đảm bảo props có giá trị mặc định {}

# Model bảng feedbacks
class Feedback(Base):
    __tablename__ = 'feedbacks'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    forId = Column(String, nullable=False)
    threadId = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    value = Column(Integer, nullable=False)
    comment = Column(Text)



# Kích hoạt hỗ trợ khóa ngoại trong SQLite
@event.listens_for(create_engine("sqlite:///rome.db"), "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
