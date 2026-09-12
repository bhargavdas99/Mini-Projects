from django.urls import path
from django.http import JsonResponse
from core.tasks import heavy_task, quick_task


def trigger_workload(request):
    # Queue 4 heavy tasks, followed by 4 quick tasks
    for i in range(4):
        heavy_task.delay(i)
    for i in range(4):
        quick_task.delay(i)
    return JsonResponse({"status": "Batch submitted to RabbitMQ"})


urlpatterns = [
    path("trigger/", trigger_workload),
]
