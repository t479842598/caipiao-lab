#!/usr/bin/env bash
# SQLite 热备份 + 轮转：sqlite3 .backup 走 WAL 安全快照，不用停服务。
# 用法：
#   ./scripts/backup.sh               备份到 backup/，保留最近 14 份
#   KEEP=30 ./scripts/backup.sh       保留 30 份
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="${DB_PATH:-$ROOT/data/lottery.db}"
OUT="${BACKUP_DIR:-$ROOT/backup}"
KEEP="${KEEP:-14}"

[[ -f "$DB" ]] || { echo "找不到数据库 $DB" >&2; exit 1; }
mkdir -p "$OUT"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$OUT/lottery-$STAMP.db"

# sqlite3 的 .backup 参数需要被单引号包住路径，这里用一个临时命令文件避开 shell 引号地狱
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
printf '.backup "%s"\n' "$TARGET" > "$TMP"
sqlite3 "$DB" < "$TMP"
rm -f "$TMP"
trap - EXIT
gzip -f "$TARGET"
echo "已备份：$TARGET.gz ($(du -h "$TARGET.gz" | cut -f1))"

ls -1t "$OUT"/lottery-*.db.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f "$old"
  echo "已清理旧备份：$(basename "$old")"
done