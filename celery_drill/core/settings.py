import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'drill-secret-key'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'core',
]

ROOT_URLCONF = 'core.urls'

# Celery Broker
CELERY_BROKER_URL = 'amqp://guest:guest@rabbitmq:5672//'
CELERY_RESULT_BACKEND = 'rpc://'
# fixes
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True