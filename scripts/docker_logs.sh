#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

# Check if docker-compose file exists
COMPOSE_FILE="docker.compose.yaml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Error: $COMPOSE_FILE not found in $(pwd)"
    exit 1
fi

# Check Docker CLI
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    echo "Error: Neither 'docker compose' nor 'docker-compose' found"
    exit 1
fi

# Parse arguments
SERVICE="${1:-}"
FOLLOW="${2:-}"
DEBUG="${3:-}"

echo "Using compose file: $COMPOSE_FILE"
echo "Using CLI: $DC"

# Show available services
echo
echo "Available services:"
$DC -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# Diagnostic checks if --debug is specified
if [[ "$DEBUG" == "--debug" ]]; then
    echo
    echo "🔍 Running diagnostic checks..."
    
    # Check if containers are running
    echo "📋 Container Status:"
    docker ps --filter "name=bms-" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
    
    # Check .env file
    echo
    echo "📄 Environment file:"
    if [[ -f .env ]]; then
        echo "✅ .env file exists"
        echo "   Size: $(ls -lh .env | awk '{print $5}')"
        echo "   Variables: $(grep -c '=' .env || echo '0')"
    else
        echo "❌ .env file missing"
    fi
    
    # Check container processes
    echo
    echo "⚙️  Container Processes:"
    for container in bms-bot bms-worker-sample; do
        if docker ps --format "{{.Names}}" | grep -q "$container"; then
            echo "✅ $container:"
            docker exec "$container" ps aux --no-headers | head -3
        else
            echo "❌ $container: Not running"
        fi
    done
    
    # Check Python imports
    echo
    echo "🐍 Python Module Tests:"
    for container in bms-bot bms-worker-sample; do
        if docker ps --format "{{.Names}}" | grep -q "$container"; then
            echo "Testing $container:"
            if docker exec "$container" python -c "import config; print('  ✅ config module')" 2>/dev/null; then
                :
            else
                echo "  ❌ config module failed"
            fi
            
            if [[ "$container" == "bms-bot" ]]; then
                if docker exec "$container" python -c "from bot.app import main; print('  ✅ bot module')" 2>/dev/null; then
                    :
                else
                    echo "  ❌ bot module failed"
                fi
            fi
            
            if [[ "$container" == "bms-worker-sample" ]]; then
                if docker exec "$container" python -c "from services.driver_manager import DriverManager; print('  ✅ driver_manager module')" 2>/dev/null; then
                    :
                else
                    echo "  ❌ driver_manager module failed"
                fi
            fi
        fi
    done
    
    # Check recent logs
    echo
    echo "📝 Recent Logs (last 10 lines):"
    for container in bms-bot bms-worker-sample; do
        if docker ps --format "{{.Names}}" | grep -q "$container"; then
            echo "--- $container ---"
            docker logs --tail 10 "$container" 2>/dev/null || echo "  No logs available"
        fi
    done
    
    echo
    echo "🔍 Diagnostic checks completed."
    echo
fi

echo
echo "Usage examples:"
echo "  $0                    # Show all logs"
echo "  $0 bot               # Show bot logs"
echo "  $0 worker-sample     # Show worker logs"
echo "  $0 bot -f            # Follow bot logs"
echo "  $0 worker-sample -f  # Follow worker logs"
echo "  $0 --debug           # Run diagnostic checks"
echo "  $0 bot --debug       # Show bot logs + diagnostics"
echo

# Build the command
CMD="$DC -f \"$COMPOSE_FILE\" logs"
if [[ "$FOLLOW" == "-f" || "$FOLLOW" == "--follow" ]]; then
    CMD="$CMD -f"
fi

if [[ -n "$SERVICE" && "$SERVICE" != "--debug" ]]; then
    CMD="$CMD $SERVICE"
fi

echo "Running: $CMD"
echo "Press Ctrl+C to stop following logs"
echo "----------------------------------------"
eval $CMD
