from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from backend.db.session import get_db
from backend.db.models import Task
from backend.queue.post_queue import PostQueueManager

app = FastAPI()

class TaskStats(BaseModel):
    total_tasks: int
    done: int
    list_result_done: List[str]
    pending: int
    failed: int
    queue_size: int
    completion_percentage: float

@app.get("/tasks/rx/stats", response_model=TaskStats)
def get_rx_task_stats(thread_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get RX task statistics: total count, completed count, and results list
    Can be filtered by thread_id if provided
    """
    # Tạo filter cơ bản cho RX tasks
    base_filter = [Task.task == "RX"]
    
    # Thêm filter theo thread_id nếu có
    if thread_id:
        base_filter.append(Task.threadId == thread_id)
    
    # Lấy tổng số task RX
    total_count = db.query(func.count(Task.id)).filter(*base_filter).scalar() or 0
    
    # Lấy số task đã hoàn thành
    done_filter = base_filter.copy()
    done_filter.append(Task.status == 1)  # 1: hoàn thành
    done_count = db.query(func.count(Task.id)).filter(*done_filter).scalar() or 0
    
    # Lấy số task đang chờ
    pending_filter = base_filter.copy()
    pending_filter.append(Task.status == 0)  # 0: đang chờ/đang làm
    pending_count = db.query(func.count(Task.id)).filter(*pending_filter).scalar() or 0
    
    # Lấy số task thất bại
    failed_filter = base_filter.copy()
    failed_filter.append(Task.status == 2)  # 2: thất bại
    failed_count = db.query(func.count(Task.id)).filter(*failed_filter).scalar() or 0
    
    # Lấy các task đã hoàn thành
    completed_tasks_filter = base_filter.copy()
    completed_tasks_filter.append(Task.status == 1)
    completed_tasks = db.query(Task).filter(
        *completed_tasks_filter
    ).order_by(Task.updatedAt.desc()).limit(10).all()
    
    # Trích xuất kết quả
    result_links = [task.results for task in completed_tasks if task.results]
    
    # Lấy kích thước queue
    queue_manager = PostQueueManager()
    queue_size = queue_manager.get_queue_size()
    
    # Tính tỉ lệ hoàn thành
    completion_percentage = (done_count / total_count * 100) if total_count > 0 else 0
    
    return {
        "total_tasks": total_count,
        "done": done_count,
        "list_result_done": result_links,
        "pending": pending_count,
        "failed": failed_count,
        "queue_size": queue_size,
        "completion_percentage": completion_percentage
    }

class PostRequest(BaseModel):
    content: str
    access_token: str
    x_id: str
    thread_id: Optional[str] = None,

class TaskResponse(BaseModel):
    task_id: str
    status: str

@app.post("/tasks/rx/enqueue", response_model=TaskResponse)
def enqueue_rx_post(request: PostRequest):
    """
    Thêm một post vào queue xử lý
    """
    queue_manager = PostQueueManager()
    task_id = queue_manager.enqueue_post(
        content=request.content,
        access_token=request.access_token,
        x_id=request.x_id,
        thread_id=request.thread_id
    )
    
    return {"task_id": task_id, "status": "queued"}