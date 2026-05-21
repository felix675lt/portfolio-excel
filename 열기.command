#!/bin/bash
# Portfolio.xlsx 로컬 실행기 — 더블클릭하면 로컬 서버를 띄우고 브라우저로 엽니다.
cd "$(dirname "$0")" || exit 1

PORT=8777
# 포트가 이미 쓰이면 다음 포트로 이동
while lsof -i :"$PORT" >/dev/null 2>&1; do PORT=$((PORT+1)); done

PY=""
command -v python3 >/dev/null 2>&1 && PY="python3"
[ -z "$PY" ] && command -v python >/dev/null 2>&1 && PY="python"

if [ -n "$PY" ]; then
  echo "▶ 로컬 서버 시작: http://localhost:$PORT"
  "$PY" -m http.server "$PORT" >/dev/null 2>&1 &
  SRV=$!
  trap 'kill $SRV 2>/dev/null' EXIT
  sleep 1
  open "http://localhost:$PORT/"
  echo "✅ 브라우저가 열렸습니다."
  echo "   ⚠️ 이 검정 창을 닫으면 서버가 종료됩니다. 사용하는 동안 열어두세요."
  wait $SRV
else
  echo "python 이 없어 파일을 직접 엽니다 (file:// 방식)."
  open index.html
fi
