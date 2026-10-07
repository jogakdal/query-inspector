from django.shortcuts import render

from .models import Order


def recent_paid(request):
    # WHERE status = ? ORDER BY created_at DESC
    # -> orders(status, created_at) 인덱스 없음 -> missing_index + order_by_filesort
    orders = Order.objects.filter(status="paid").order_by("-created_at")
    lines = []
    for o in orders:            # N+1: 루프에서 o.user 접근인데 select_related("user") 누락
        lines.append(o.user.name)
    return render(request, "orders.html", {"lines": lines})


def search_by_name(request, q):
    # user__name__icontains -> LIKE '%q%' (선행 와일드카드) + 상위 테이블 JOIN
    return Order.objects.filter(user__name__icontains=q)


def unsafe_raw(request, name):
    # f-string 보간 -> string_substitution(SQL 인젝션 + 플랜 캐시 오염) + SELECT * -> select_star
    # 안전: Order.objects.raw("SELECT id, status FROM orders WHERE status = %s", [name])
    return Order.objects.raw(f"SELECT * FROM orders WHERE status = '{name}'")
