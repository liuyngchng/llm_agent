#!/bin/bash
# ==============================================================================
# init_cfg.sh - 自动创建SQLite数据库和表结构
# 作者：richard
# 版本：1.1
# 用法：./init_cfg.sh [数据库文件路径]
# ==============================================================================

set -e  # 遇到错误立即退出

# 配置参数
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCHEMA_DIR="${SCRIPT_DIR}/cfg_db_schema"
DB_FILE="${1:-${SCRIPT_DIR}/cfg.db}"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# 颜色输出函数
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查必要的工具
check_dependencies() {
    info "检查系统依赖..."
    if ! command -v sqlite3 &> /dev/null; then
        error "sqlite3 未安装，请先安装 sqlite3"
        echo "Ubuntu/Debian: sudo apt-get install sqlite3"
        echo "CentOS/RHEL: sudo yum install sqlite"
        echo "macOS: brew install sqlite"
        exit 1
    fi
    success "sqlite3 已安装"
}

# 检查SQL文件目录
check_schema_dir() {
    info "检查SQL文件目录: $SCHEMA_DIR"
    if [ ! -d "$SCHEMA_DIR" ]; then
        error "SQL文件目录不存在: $SCHEMA_DIR"
        exit 1
    fi

    local sql_count=$(find "$SCHEMA_DIR" -name "*.sql" -type f | wc -l)
    if [ "$sql_count" -eq 0 ]; then
        error "在 $SCHEMA_DIR 中未找到任何 .sql 文件"
        exit 1
    fi
    success "找到 $sql_count 个SQL文件"
}

# 备份现有数据库
backup_database() {
    if [ -f "$DB_FILE" ]; then
        info "检测到已存在的数据库文件: $DB_FILE"
        local backup_file="${DB_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        info "创建备份: $backup_file"
        cp "$DB_FILE" "$backup_file"
        success "备份完成: $backup_file"
    fi
}

# 创建数据库和表
create_database() {
    info "开始创建数据库: $DB_FILE"

    # 删除旧数据库文件（如果存在）
    if [ -f "$DB_FILE" ]; then
        warning "删除旧数据库文件"
        rm -f "$DB_FILE"
    fi

    # 创建数据库文件
    touch "$DB_FILE"

    # 获取所有SQL文件并按文件名排序
    local sql_files=()
    while IFS= read -r -d $'\0' file; do
        sql_files+=("$file")
    done < <(find "$SCHEMA_DIR" -name "*.sql" -type f -print0 | sort -z)

    if [ ${#sql_files[@]} -eq 0 ]; then
        error "没有找到SQL文件"
        return 1
    fi

    # 逐个执行所有SQL文件
    info "开始执行SQL文件..."
    for sql_file in "${sql_files[@]}"; do
        local filename=$(basename "$sql_file")
        info "执行: $filename"

        # 简单的SQL执行，不做特殊处理
        if sqlite3 "$DB_FILE" < "$sql_file" 2>&1; then
            success "✓ $filename 执行成功"
        else
            # 记录错误但继续执行下一个文件
            warning "⚠ $filename 执行遇到问题，继续执行下一个文件"
        fi
    done

    return 0
}

# 验证数据库结构
verify_database() {
    info "验证数据库结构..."

    # 检查表是否创建成功
    local tables=$(sqlite3 "$DB_FILE" ".tables" 2>/dev/null || echo "")

    if [ -z "$tables" ]; then
        warning "数据库中没有任何表"
        return
    fi

    local table_count=$(echo "$tables" | wc -w)

    info "数据库中的表 ($table_count 个):"
    echo "$tables" | tr ' ' '\n' | while read -r table; do
        echo "  - $table"
    done

    # 显示数据库信息
    info "数据库信息:"
    if [ -f "$DB_FILE" ]; then
        local db_size=$(du -h "$DB_FILE" | cut -f1)
        echo "  文件大小: $db_size"
        echo "  文件路径: $DB_FILE"
        success "数据库创建完成"
    else
        error "数据库文件未创建成功"
    fi
}

# 主函数
main() {
    echo "================================================"
    echo "    SQLite数据库初始化脚本 v1.1"
    echo "    简单模式：按文件名顺序执行所有SQL文件"
    echo "================================================"

    # 检查依赖
    check_dependencies

    # 检查SQL文件目录
    check_schema_dir

    # 备份数据库（如果存在）
    backup_database

    # 创建数据库和表
    if create_database; then
        # 验证数据库
        verify_database

        echo "================================================"
        success "数据库初始化完成!"
        info "数据库文件: $DB_FILE"
        echo "================================================"
    else
        error "数据库创建过程出现问题!"
        exit 1
    fi
}

# 脚本执行入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi