#!/usr/bin/env bash
# 압축 해제 후 실행 권한을 맞추고 배포 리비전을 기록합니다.
set -e
cd __DIR__
chmod +x bin/*.sh scripts/ops/*.sh scripts/ops/remote/*.sh setup.sh rag/test-search.sh 2>/dev/null || true
echo "__BRANCH__@__REV__" > .deploy-rev
echo "deployed $(cat .deploy-rev)"
