#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT_DIR/ccproxy.pid"
LOG_FILE="$ROOT_DIR/ccproxy.log"
CONFIG_FILE="$ROOT_DIR/config.json"

start() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "ccproxy already running (pid $(cat "$PID_FILE"))"
    exit 0
  fi
  nohup python3 "$ROOT_DIR/ccproxy.py" --config "$CONFIG_FILE" >"$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "ccproxy started (pid $!)"
}

stop() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    kill "$(cat "$PID_FILE")"
    rm -f "$PID_FILE"
    echo "ccproxy stopped"
  else
    echo "ccproxy not running"
  fi
}

status() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "ccproxy running (pid $(cat "$PID_FILE"))"
  else
    echo "ccproxy not running"
  fi
}

restart() {
  stop
  start
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) restart ;;
  status) status ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
 esac
