class UserRepository(val jdbc: JdbcTemplate) {
  fun findByName(name: String) =
    jdbc.query("SELECT id, name FROM users WHERE name LIKE '%' || ? || '%'", name)
}
