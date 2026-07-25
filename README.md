# fgrr-notice-analysis

## DB 백업 / 복구

DB: PostgreSQL, DB명 `research`, 테이블 `fgrr_notices`
접속 정보는 `.env`의 `DATABASE_URL` 참고.

백업 파일은 `schema/backups/` 에 저장하며, 해당 경로는 `.gitignore`에 의해
git에 커밋되지 않는다 (용량이 크고 민감 데이터 포함 가능).

### 백업

```bash
PGPASSWORD=<비밀번호> pg_dump -h localhost -p 5432 -U postgres -d research \
  -Fc -f "schema/backups/fgrr_notices_backup_$(date +%Y%m%d).dump"
```

- `-Fc`: custom format (압축, `pg_restore` 전용 포맷)
- 파일명은 `fgrr_notices_backup_YYYYMMDD.dump` 형식 유지

### 복구

**같은 DB에 복구 (기존 테이블 덮어쓰기)**

```bash
PGPASSWORD=<비밀번호> pg_restore -h localhost -p 5432 -U postgres -d research \
  --clean --if-exists \
  "schema/backups/fgrr_notices_backup_YYYYMMDD.dump"
```

- `--clean --if-exists`: 복구 전 기존 테이블/객체 삭제 후 재생성

**새 DB에 복구 (검증용)**

```bash
createdb -h localhost -p 5432 -U postgres research_restore_test
PGPASSWORD=<비밀번호> pg_restore -h localhost -p 5432 -U postgres -d research_restore_test \
  "schema/backups/fgrr_notices_backup_YYYYMMDD.dump"
```

### 확인

```bash
PGPASSWORD=<비밀번호> psql -h localhost -p 5432 -U postgres -d research -c "SELECT count(*) FROM fgrr_notices;"
```
