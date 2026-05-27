#!/bin/bash
# Cloudflare Pages 배포 — 더블클릭 실행
# 처음 1회만 브라우저로 Cloudflare 로그인, 이후엔 그냥 더블클릭하면 자동 재배포
set -e
cd "$(dirname "$0")" || exit 1
PROJECT="${CF_PROJECT:-port}"

echo "🌐 Cloudflare Pages 배포"
echo "   대상: https://$PROJECT.pages.dev"
echo ""

# wrangler 로그인 확인
if ! npx --yes wrangler whoami 2>&1 | grep -qE "associated|Cloudflare Account"; then
  echo "▶ 처음이면 Cloudflare 로그인이 필요합니다."
  echo "  곧 브라우저가 열립니다. 로그인을 마치면 이 창으로 돌아오세요."
  echo ""
  npx --yes wrangler login
fi

# 임시 배포 폴더 (필요한 정적파일만)
DEPLOY_DIR=".cf_deploy"
rm -rf "$DEPLOY_DIR"
mkdir "$DEPLOY_DIR"
cp index.html manifest.json icon.svg icon-maskable.svg "$DEPLOY_DIR/" 2>/dev/null || true

# 프로젝트 생성 시도 (이미 있으면 조용히 무시)
echo "▶ 프로젝트 '$PROJECT' 생성/확인..."
npx --yes wrangler pages project create "$PROJECT" --production-branch=main 2>&1 | tail -5 || true

# 배포
echo ""
echo "▶ 업로드..."
npx --yes wrangler pages deploy "$DEPLOY_DIR" \
  --project-name="$PROJECT" \
  --branch=main \
  --commit-dirty=true

rm -rf "$DEPLOY_DIR"
echo ""
echo "✅ 완료 — 1~2분 안에 라이브:"
echo "   https://$PROJECT.pages.dev"
echo ""
echo "다른 이름으로 배포하려면:"
echo "   CF_PROJECT=내이름 ./cloudflare-deploy.command"
echo ""
read -n 1 -s -r -p "아무 키나 누르면 닫혀요..."
