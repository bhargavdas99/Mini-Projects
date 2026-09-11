import time  # for ttl most probably
from django.http import JsonResponse
from django.core.cache import cache


def get_user_profile_view(request, user_id):
    cache_key = f"user_profile:{user_id}"

    # 1. Look for cached data first (Cache Hit)
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse({"source": "CACHE (Redis)", "data": cached_data})

    # 2. Simulate an expensive Database query (Cache Miss)
    time.sleep(2)  # Simulates 2-second DB query latency
    db_data = {
        "id": user_id,
        "username": f"developer_{user_id}",
        "role": "Backend Engineer",
        "status": "Active",
    }

    # 3. Store result in Redis with a 30-second TTL
    cache.set(cache_key, db_data, timeout=30)

    return JsonResponse({"source": "DATABASE (Simulated)", "data": db_data})


def send_notification_vue(request):
    user_id = request.GET.get("user_id", "101")
    lock_key = f"lock:send_notification:{user_id}"

    # Try to acquire an atomic distributed lock for 10 seconds.
    # cache.add() uses 'SET NX' under the hood for Redis.
    acquired_redis_lock = cache.add(lock_key, lock_key, timeout=120)
    # the name acquired_redis_lock means, did i(current worker) acquire the lock?
    # If True: i did acquire it and its available to process
    # False: i couldn't acquire it as some other worker is already processing it.

    if not acquired_redis_lock:
        return JsonResponse(
            {
                "status": "error",
                "message": f"Notification processing already in progress for user {user_id}. Request ignored.",
            },
            status=429,
        )

    # If True:
    # Simulate an expensive communication operation (e.g., WhatsApp API call)
    time.sleep(3)
    return JsonResponse(
        {
            "status": "success",
            "message": f"Notification successfully sent to user: {user_id}!",
        }
    )
