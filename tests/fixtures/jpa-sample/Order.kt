package com.acme.order

import jakarta.persistence.*
import java.time.Instant

// JPA 어댑터 fixture — 인덱스 미정의 + LAZY 연관으로 missing_index·n_plus_one 재현
@Entity
@Table(name = "orders")            // ← @Table(indexes = ...) 없음: status/created_at 인덱스 미정의
class Order(
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    val id: Long = 0,

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")  // ← FK user_id 인덱스 확인 대상
    val user: User,

    @Column(nullable = false)
    val status: String,

    @Column(nullable = false)
    val amount: java.math.BigDecimal,

    @Column(name = "created_at", nullable = false)
    val createdAt: Instant,
)
