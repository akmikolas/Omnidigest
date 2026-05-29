#!/bin/bash
set -e

# ===========================================
# OmniDigest 开发/测试/发布一体化构建脚本
#
# 开发迭代:
#   ./dev-build.sh                    构建 + 启动 + 健康检查
#   ./dev-build.sh --backend-only      仅重建后端
#   ./dev-build.sh --frontend-only     仅重建前端
#   ./dev-build.sh --skip-build        跳过构建，仅启动测试
#
# 基础设施:
#   ./dev-build.sh --infra            启动/重启基础设施
#
# 发布:
#   ./dev-build.sh --release v2.3.15  构建 → 测试 → 推送 Harbor
#
# 清理:
#   ./dev-build.sh --down             停止应用容器（保留基础设施）
#   ./dev-build.sh --down-all         停止全部（含基础设施）
# ===========================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# ---- 自动检测 docker compose / docker-compose ----
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    echo "错误: 未找到 docker compose 或 docker-compose"
    exit 1
fi
echo "使用: $DC"

# ---- 加载 common.sh ----
if [ -f "$PROJECT_ROOT/deployment/scripts/common.sh" ]; then
    source "$PROJECT_ROOT/deployment/scripts/common.sh"
else
    # 内联定义（防止 common.sh 不存在时脚本不可用）
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
    log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
    log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
    log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
    log_step()  { echo -e "${CYAN}[STEP]${NC}  $1"; }
    is_container_healthy() {
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' "$1" 2>/dev/null || echo "none")
        [ "$status" = "healthy" ]
    }
    wait_for_container_healthy() {
        local name=$1 timeout=${2:-60} interval=2 elapsed=0
        while [ $elapsed -lt $timeout ]; do
            is_container_healthy "$name" && return 0
            sleep $interval; elapsed=$((elapsed + interval))
        done
        return 1
    }
    get_current_branch() { git branch --show-current 2>/dev/null || echo "unknown"; }
fi

INFRA_FILE="$PROJECT_ROOT/docker-compose.infra.yml"
APP_FILE="$PROJECT_ROOT/docker-compose.yml"

# ---- 默认值 ----
MODE="dev"
VERSION="dev"
BACKEND_ONLY=false
FRONTEND_ONLY=false
SKIP_BUILD=false
SKIP_TEST=false
INFRA_ONLY=false
DOWN_MODE=false
DOWN_ALL=false
FORCE=false

# ---- 参数解析 ----
while [[ $# -gt 0 ]]; do
    case $1 in
        --release)
            MODE="release"
            if [[ "$2" =~ ^v[0-9] ]]; then VERSION="$2"; shift; fi
            ;;
        --backend-only)  BACKEND_ONLY=true ;;
        --frontend-only) FRONTEND_ONLY=true ;;
        --skip-build)    SKIP_BUILD=true ;;
        --skip-test)     SKIP_TEST=true ;;
        --infra)         INFRA_ONLY=true ;;
        --down)          DOWN_MODE=true ;;
        --down-all)      DOWN_ALL=true ;;
        --force|-f)      FORCE=true ;;
        --help|-h)
            cat <<EOF
用法: $0 [选项]

开发迭代:
  (无参数)            构建全部 + 启动 + 健康检查
  --backend-only      仅重建后端
  --frontend-only     仅重建前端
  --skip-build        跳过构建，仅启动/测试已有镜像
  --skip-test         跳过健康检查

基础设施:
  --infra             启动/重启基础设施 (postgres, redis, dgraph)

发布:
  --release <ver>     发布模式: 构建 → 测试 → 推送 Harbor (例如 --release v2.3.15)
  --force             发布时强制覆盖 Harbor 已有版本

清理:
  --down              停止应用容器 (保留基础设施)
  --down-all          停止全部容器 (含基础设施)
EOF
            exit 0
            ;;
        *) log_error "未知选项: $1"; exit 1 ;;
    esac
    shift
done

# ---- 步骤 0: 停止模式 ----
if [ "$DOWN_ALL" = true ]; then
    log_step "停止全部容器..."
    $DC -f "$APP_FILE" down 2>/dev/null || true
    $DC -f "$INFRA_FILE" down 2>/dev/null || true
    log_info "全部容器已停止"
    exit 0
fi

if [ "$DOWN_MODE" = true ]; then
    log_step "停止应用容器..."
    $DC -f "$APP_FILE" down 2>/dev/null || true
    log_info "应用容器已停止 (基础设施不受影响)"
    exit 0
fi

# ---- 步骤 1: 基础设施 ----
if [ "$INFRA_ONLY" = true ]; then
    log_step "启动/重启基础设施..."
    $DC -f "$INFRA_FILE" up -d --remove-orphans
    log_info "等待基础设施健康检查 (最长 120s)..."
    wait_for_container_healthy "omnidigest_postgres" 60 || log_warn "PostgreSQL 尚未 healthy"
    wait_for_container_healthy "omnidigest_redis"   30 || log_warn "Redis 尚未 healthy"
    echo ""
    log_info "基础设施状态:"
    $DC -f "$INFRA_FILE" ps --format "table {{.Name}}\t{{.Status}}"
    exit 0
fi

# 确保基础设施运行
if ! is_container_healthy "omnidigest_postgres" 2>/dev/null; then
    log_step "基础设施未运行，正在启动..."
    $DC -f "$INFRA_FILE" up -d --remove-orphans
    wait_for_container_healthy "omnidigest_postgres" 60 || {
        log_error "PostgreSQL 启动失败"
        $DC -f "$INFRA_FILE" logs postgres --tail 20
        exit 1
    }
    wait_for_container_healthy "omnidigest_redis" 30
    log_info "基础设施已就绪"
fi

# ---- 步骤 2: 构建 ----
if [ "$SKIP_BUILD" != true ]; then
    if [ "$MODE" = "release" ]; then
        log_step "检出 git tag: $VERSION"
        CURRENT_BRANCH=$(get_current_branch)
        git fetch --tags --quiet 2>/dev/null || true
        git checkout "$VERSION" 2>/dev/null || {
            log_error "Tag $VERSION 不存在"
            exit 1
        }
        trap "git checkout '$CURRENT_BRANCH' 2>/dev/null || true" EXIT
        log_info "已切换到 $VERSION"
    fi

    log_step "构建镜像 (模式: $MODE)..."
    BUILD_ARGS=""
    [ "$BACKEND_ONLY" = true ]  && BUILD_ARGS="backend"
    [ "$FRONTEND_ONLY" = true ] && BUILD_ARGS="frontend"

    $DC -f "$APP_FILE" build $BUILD_ARGS

    if [ "$MODE" = "release" ]; then
        log_info "标记 Harbor 镜像..."
        BACKEND_LOCAL="omnidigest-backend:dev"
        FRONTEND_LOCAL="omnidigest-frontend:dev"
        docker tag "$BACKEND_LOCAL"  "${HARBOR_IMAGE_BACKEND}:${VERSION}"
        docker tag "$FRONTEND_LOCAL" "${HARBOR_IMAGE_FRONTEND}:${VERSION}"
        log_info "  ${HARBOR_IMAGE_BACKEND}:${VERSION}"
        log_info "  ${HARBOR_IMAGE_FRONTEND}:${VERSION}"
    fi
else
    log_info "跳过构建 (--skip-build)"
fi

# ---- 步骤 3: 启动 + 健康检查 ----
if [ "$SKIP_TEST" != true ]; then
    log_step "启动应用容器..."

    $DC -f "$APP_FILE" down 2>/dev/null || true
    $DC -f "$APP_FILE" up -d --remove-orphans

    log_info "等待后端 healthy (最长 120s)..."
    if ! wait_for_container_healthy "omnidigest_app" 120; then
        log_error "后端健康检查超时"
        echo ""
        $DC -f "$APP_FILE" logs backend --tail 50
        exit 1
    fi
    log_info "后端 healthy ✓"

    log_info "等待前端 healthy (最长 60s)..."
    if ! wait_for_container_healthy "omnidigest_frontend" 60; then
        log_error "前端健康检查超时"
        echo ""
        $DC -f "$APP_FILE" logs frontend --tail 30
        exit 1
    fi
    log_info "前端 healthy ✓"

    # ---- 显示 Bootstrap 信息 ----
    API_KEY=$($DC -f "$APP_FILE" exec -T backend cat /data/init_api_key.txt 2>/dev/null || echo "")
    if [ -n "$API_KEY" ]; then
        log_info "============================================"
        log_info "  首次启动 API Key:"
        log_info "  $API_KEY"
        log_info "--------------------------------------------"
        log_info "  后端 : http://localhost:7080"
        log_info "  前端 : http://localhost:3000"
        log_info "============================================"
    else
        echo ""
        log_info "============================================"
        log_info "  启动成功"
        log_info "  后端 : http://localhost:7080/api/health"
        log_info "  前端 : http://localhost:3000"
        log_info "  (API Key 已存在，未重新生成)"
        log_info "============================================"
    fi
fi

# ---- 步骤 4: 推送 Harbor (仅 release) ----
if [ "$MODE" = "release" ] && [ "$SKIP_TEST" != true ]; then
    log_step "推送镜像到 Harbor..."
    if [ "$FORCE" != true ]; then
        log_info "检查 Harbor 上是否已存在版本 $VERSION ..."
        BACKEND_EXISTS=$(curl -s -o /dev/null -w "%{http_code}" \
            "https://${HARBOR_URL}/api/v2.0/projects/${HARBOR_PROJECT}/repositories/omnidigest/artifacts/${VERSION}" \
            --connect-timeout 10 2>/dev/null || echo "000")
        if [ "$BACKEND_EXISTS" = "200" ]; then
            log_error "版本 ${VERSION} 已存在于 Harbor"
            log_error "使用 --force 强制覆盖"
            exit 1
        fi
        log_info "检查通过"
    else
        log_warn "强制模式，将覆盖已有镜像"
    fi

    docker push "${HARBOR_IMAGE_BACKEND}:${VERSION}"
    docker push "${HARBOR_IMAGE_FRONTEND}:${VERSION}"
    echo ""
    log_info "推送完成:"
    log_info "  ${HARBOR_IMAGE_BACKEND}:${VERSION}"
    log_info "  ${HARBOR_IMAGE_FRONTEND}:${VERSION}"
fi

log_info "完成"
