import time
from celery import shared_task

@shared_task(bind=True)
def heavy_task(self, task_id):
    print(f"[{self.request.hostname}] STARTED Heavy Task {task_id} (will take 8s)...")
    time.sleep(8)
    print(f"[{self.request.hostname}] FINISHED Heavy Task {task_id}!")
    return f"heavy_{task_id}"

@shared_task(bind=True)
def quick_task(self, task_id):
    print(f"[{self.request.hostname}] QUICK Task {task_id} DONE in 0.1s!")
    return f"quick_{task_id}"