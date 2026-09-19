#!/bin/bash
# NotaryMindAi API Test Suite
# Run this to verify the server is working correctly
# Usage: bash test_api.sh [port]

PORT=${1:-8787}
BASE_URL="http://localhost:$PORT"

echo "🧪 NotaryMindAi API Test Suite"
echo "================================"
echo "Server: $BASE_URL"
echo

set -e

# Color output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

test_count=0
pass_count=0

test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    
    test_count=$((test_count + 1))
    echo -n "[$test_count] $name ... "
    
    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint" \
            -H "Content-Type: application/json")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -n -1)
    
    if [[ "$http_code" =~ ^[2][0-9]{2}$ ]]; then
        echo -e "${GREEN}✓${NC} (HTTP $http_code)"
        pass_count=$((pass_count + 1))
        if echo "$body" | grep -q "error"; then
            echo "  ⚠️  Response contains error field: $body" | head -c 100
            echo
        fi
    else
        echo -e "${RED}✗${NC} (HTTP $http_code)"
        echo "  Error: $body" | head -c 200
        echo
    fi
}

# Health check
echo "=== 1. Health Check ==="
test_endpoint "Server running" "GET" "/api/projects"
echo

# List projects
echo "=== 2. Projects Management ==="
test_endpoint "List projects" "GET" "/api/projects"
test_endpoint "Create test project" "POST" "/api/projects" \
    '{"name":"test_api_project_001","displayName":"API Test"}'
test_endpoint "Create duplicate (should fail)" "POST" "/api/projects" \
    '{"name":"test_api_project_001","displayName":"Duplicate"}'
test_endpoint "Create with invalid name (should fail)" "POST" "/api/projects" \
    '{"name":"../../../etc/passwd","displayName":"Hack"}'
echo

# File operations
echo "=== 3. File Operations ==="
test_endpoint "Get project data (cotimos)" "GET" "/api/projects/cotimos/data"
test_endpoint "Read metadata file" "GET" "/api/projects/cotimos/raw?path=docs_logical.json"
test_endpoint "Read nonexistent file (should fail)" "GET" "/api/projects/cotimos/raw?path=nonexistent.json"
echo

# Agent query
echo "=== 4. Query-Only Agent ==="
test_endpoint "Query: Bernardo Dias" "POST" "/api/agent/query" \
    '{"project":"cotimos","question":"Bernardo Dias"}'
test_endpoint "Query: empty question (should fail)" "POST" "/api/agent/query" \
    '{"project":"cotimos","question":""}'
test_endpoint "Query: nonexistent project" "POST" "/api/agent/query" \
    '{"project":"nonexistent","question":"test"}'
echo

# Static files
echo "=== 5. Static Files ==="
test_endpoint "Serve UI main page" "GET" "/ui/main.html"
test_endpoint "Serve config file" "GET" "/ui/schema.json"
echo

# Summary
echo "=== Summary ==="
echo "Tests passed: $pass_count / $test_count"

if [ $pass_count -eq $test_count ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
