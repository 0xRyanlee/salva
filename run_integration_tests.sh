#!/bin/bash
# Salva Runtime Integration Test Runner
#
# 啟動方式:
#   1. 先啟動 Salva API:  python3 -m uvicorn apps.api.main:app --port 8000
#   2. 執行測試:          python3 run_integration_tests.py
#
# 環境變數:
#   SALVA_API_URL    - API URL (預設 http://127.0.0.1:8000)
#   SALVA_API_KEY    - API Key (可選)

set -e

echo "=== Salva Runtime Integration Tests ==="

# 檢查 API 是否運行
if ! curl -s --max-time 2 http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "ERROR: Salva API not running on http://127.0.0.1:8000"
    echo "Please start: python3 -m uvicorn apps.api.main:app --port 8000"
    exit 1
fi

echo "✓ API is running"

# 執行測試
echo ""
echo "Running integration tests..."
python3 -m pytest tests/test_integration_real_calls.py -v --tb=short "$@"

echo ""
echo "=== Tests Complete ==="