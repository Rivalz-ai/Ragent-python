import time
from datetime import datetime
from rAgent.utils import Logger
from backend.db.session import get_db_session
from backend.db.models import Task
from rAgent.ragents.x_tool import post_to_X  # Giả định bạn có hàm này
import queue
import random
from backend.utils import TASK_STATUS_MAP
def process_queue(queues, is_running):
    """
    Xử lý các items trong queue
    """
    Logger.info("Starting post queue worker")
    
    while is_running:
        try:
            # Lấy item từ queue với timeout 5s
            try:
                item = queues.get(timeout=5)
            except queue.Empty:
                continue
            
            # Lấy thông tin task
            task_id = item["task_id"]
            content = item["content"]
            access_token = item["access_token"]
            x_id = item["x_id"]
            
            Logger.info(f"Processing task {task_id}")
            
            # Đăng bài lên X/Twitter
            result = post_to_X(content, access_token)
            
            # Cập nhật trạng thái task trong database
            update_task_status(task_id, x_id,result)
            
            # Đánh dấu task đã hoàn thành trong queue
            queues.task_done()
            num_sleep  = random.randint(1, 5)
            Logger.info(f"Sleeping for {num_sleep} seconds")
            time.sleep(num_sleep)
            
        except Exception as e:
            Logger.error(f"Error processing queue item: {str(e)}")
            time.sleep(5)  # Chờ trước khi thử lại

def update_task_status(task_id,x_id, result):
    """
    Cập nhật trạng thái task trong database
    """
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            Logger.error(f"Task {task_id} not found")
            return
        
        # Kiểm tra xem post có thành công không
        if "https://twitter.com/i/web/status" in result:
            task.status = 1  # 1: hoàn thành
            task.results = result
        else:
            task.status = 2  # 2: thất bại
            task.results = f"Failed: {result}"
        
        task.updatedAt = datetime.utcnow()
        db.commit()
        Logger.info(f"Updated task {task_id},  and x_id is {x_id} status to {TASK_STATUS_MAP[task.status]}")
    except Exception as e:
        db.rollback()
        Logger.error(f"Error updating task status: {str(e)}")
    finally:
        db.close()