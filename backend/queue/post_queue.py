import queue
import threading
import time
from datetime import datetime
import uuid
from rAgent.utils import Logger
from backend.db.session import get_db_session
from backend.db.models import Task

# Singleton queue cho task post
post_queue = queue.Queue()

class PostQueueManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PostQueueManager, cls).__new__(cls)
            cls._instance.queue = post_queue
            cls._instance.worker_thread = None
            cls._instance.is_running = False
        return cls._instance
    
    def enqueue_post(self, content, access_token,x_id, thread_id=None):
        """
        Thêm post vào queue và tạo task trong database
        """
        # Tạo task ID mới
        task_id = str(uuid.uuid4())
        
        # Tạo task trong database
        db = get_db_session()
        try:
            task = Task(
                id=task_id,
                task="RX",  # Loại task RX
                description=content[:50] + "..." if len(content) > 50 else content,
                x_id=x_id,
                status=0,  # 0: đang chờ/đang làm
                threadId=thread_id or str(uuid.uuid4()),  # Sử dụng thread_id nếu có hoặc tạo mới
                num_loop=0,
                metadata_={"content": content}
            )
            db.add(task)
            db.commit()
            Logger.info(f"Created task {task_id} in database")
        except Exception as e:
            db.rollback()
            Logger.error(f"Error creating task: {str(e)}")
            raise
        finally:
            db.close()
            
        # Thêm vào queue
        self.queue.put({
            "task_id": task_id,
            "content": content,
            "access_token": access_token,
            "x_id": x_id
        })
        
        # Đảm bảo worker đang chạy
        self.start_worker()
        
        return task_id
    
    def start_worker(self):
        """Bắt đầu worker thread nếu chưa chạy"""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            from backend.queue.worker import process_queue
            self.is_running = True
            self.worker_thread = threading.Thread(target=process_queue, args=(self.queue, self.is_running))
            self.worker_thread.daemon = True
            self.worker_thread.start()
            Logger.info("Post queue worker started")
    
    def get_queue_size(self):
        """Lấy kích thước hiện tại của queue"""
        return self.queue.qsize()