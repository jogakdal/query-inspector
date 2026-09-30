from django.db import models


class User(models.Model):
    name = models.CharField(max_length=100)


class Order(models.Model):
    # FK -> Django가 기본 인덱스를 생성하므로 user_id는 missing_index가 아니다.
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField()

    class Meta:
        # (status, created_at) 복합 인덱스 없음 -> 아래 쿼리에서 missing_index.
        indexes = []
