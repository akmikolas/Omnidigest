#!/bin/bash
# Redis 缓存性能测试脚本
# 测试缓存端点 vs 非缓存端点的响应时间

BACKEND_URL="http://localhost:7080"
HOST_HEADER="omnidigest.franklinworksite.top"
ITERATIONS="${ITERATIONS:-5}"

echo "=========================================="
echo "OmniDigest API 响应时间测试"
echo "=========================================="
echo "Backend: $BACKEND_URL"
echo "迭代次数: $ITERATIONS"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试函数
test_endpoint() {
    local method=$1
    local endpoint=$2
    local name=$3
    local cached=$4  # "cached" or "uncached"

    local total=0
    local times=()

    for i in $(seq 1 $ITERATIONS); do
        local start=$(date +%s%N)
        if [ "$method" = "GET" ]; then
            curl -s -o /dev/null -w "%{http_code}" -H "Host: $HOST_HEADER" "$BACKEND_URL$endpoint" > /dev/null
        else
            curl -s -o /dev/null -w "%{http_code}" -X "$method" -H "Host: $HOST_HEADER" "$BACKEND_URL$endpoint" > /dev/null
        fi
        local end=$(date +%s%N)
        local elapsed=$(( (end - start) / 1000000 ))  # ms
        times+=($elapsed)
        total=$(( total + elapsed ))
    done

    local avg=$(( total / ITERATIONS ))
    local min=$(printf '%s\n' "${times[@]}" | sort -n | head -1)
    local max=$(printf '%s\n' "${times[@]}" | sort -n | tail -1)

    local color=$YELLOW
    if [ "$cached" = "cached" ]; then
        color=$GREEN
    fi

    printf "${color}%-50s${NC} | Avg: %4dms | Min: %4dms | Max: %4dms | %s\n" \
        "$name ($endpoint)" $avg $min $max "$cached"
}

echo "=========================================="
echo "有缓存的端点 (Cached Endpoints)"
echo "=========================================="
test_endpoint GET "/stats/breaking" "Stats Breaking" "cached"
test_endpoint GET "/token-stats" "Token Stats" "cached"
test_endpoint GET "/astock/quotes" "AStock Quotes" "cached"
test_endpoint GET "/astock/sectors" "AStock Sectors" "cached"
test_endpoint GET "/kg/status" "KG Status" "cached"
test_endpoint GET "/stats/overview" "Stats Overview" "cached"

echo ""
echo "=========================================="
echo "无缓存的端点 (Uncached Endpoints)"
echo "=========================================="
test_endpoint GET "/sources" "Sources (RSS)" "uncached"
test_endpoint GET "/config" "Config" "uncached"
test_endpoint GET "/auth/keys" "Auth Keys" "uncached"
test_endpoint GET "/health" "Health" "uncached"

echo ""
echo "=========================================="
echo "测试完成"
echo "=========================================="
