package com.acme.order

import org.springframework.data.jpa.repository.*
import java.time.Instant

interface OrderRepository : JpaRepository<Order, Long> {

    // 파생 메서드 → SELECT ... WHERE status=? AND created_at>? ORDER BY created_at DESC
    // 기대: orders(status, created_at) 인덱스 없음 → missing_index + order_by_filesort
    fun findByStatusAndCreatedAtAfterOrderByCreatedAtDesc(status: String, from: Instant): List<Order>

    // 파생 메서드 → WHERE user_id = ?  (FK 인덱스 확인 대상)
    fun findByUserId(userId: Long): List<Order>

    // JPQL @Query — 연관 경로 o.user.name (조인). LIKE 선행 와일드카드.
    // 기대: leading_wildcard_like
    @Query("select o from Order o where o.user.name like %:name%")
    fun searchByUserName(name: String): List<Order>
}
