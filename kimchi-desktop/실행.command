#!/bin/bash
# 김프 적립 신호 — 더블클릭 실행 (시세·계산 전용, API키 불필요)
cd "$(dirname "$0")" || exit 1

# tkinter 있는 파이썬 찾기 (macOS 시스템 파이썬 우선 — homebrew엔 tkinter 없을 때 많음)
PY=""
for cand in /usr/bin/python3 python3 python3.13 python3.12 python3.11 python3.10; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import tkinter" >/dev/null 2>&1; then
    PY="$cand"; break
  fi
done

if [ -z "$PY" ]; then
  echo "❌ tkinter가 있는 python3를 못 찾았습니다."
  echo "   해결: 터미널에서  brew install python-tk  실행 후 다시 시도"
  echo "   (또는 macOS 시스템 파이썬 /usr/bin/python3 사용)"
  read -n 1 -s -r -p "아무 키나 누르면 닫힘..."
  exit 1
fi

echo "▶ $PY 로 실행합니다…"
"$PY" kimchi_signal.py
