#!/bin/bash
# Test Mapper Docker image with different sources

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🧪 Testing Mapper Docker Image${NC}"
echo "================================"

IMAGE_NAME="${IMAGE_NAME:-pdf-mapper:latest}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if image exists
if ! docker images "$IMAGE_NAME" --format "{{.Repository}}:{{.Tag}}" | grep -q "$IMAGE_NAME"; then
    echo -e "${RED}❌ Error: Image $IMAGE_NAME not found${NC}"
    echo -e "${YELLOW}Build it first: ./docker-build.sh${NC}"
    exit 1
fi

# Check for OPENAI_API_KEY
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}❌ Error: OPENAI_API_KEY environment variable not set${NC}"
    echo -e "${YELLOW}Set it: export OPENAI_API_KEY=sk-...${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites OK${NC}"
echo ""

# Test function
test_container() {
    local SOURCE_TYPE=$1
    local PORT=$2
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Testing SOURCE_TYPE=$SOURCE_TYPE${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Start container
    echo -e "${YELLOW}🚀 Starting container on port $PORT...${NC}"
    
    CONTAINER_ID=$(docker run -d \
        -p "$PORT:8000" \
        -e SOURCE_TYPE="$SOURCE_TYPE" \
        -e OPENAI_API_KEY="$OPENAI_API_KEY" \
        -e LOG_LEVEL="INFO" \
        "$IMAGE_NAME")
    
    echo -e "${GREEN}✅ Container started: ${CONTAINER_ID:0:12}${NC}"
    
    # Wait for ready
    echo -e "${YELLOW}⏳ Waiting for service...${NC}"
    sleep 5
    
    # Test health endpoint
    echo -e "${YELLOW}🏥 Testing health endpoint...${NC}"
    for i in {1..10}; do
        if curl -f -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            HEALTH=$(curl -s "http://localhost:$PORT/health")
            echo -e "${GREEN}✅ Health check passed!${NC}"
            echo -e "${GREEN}   Response: $HEALTH${NC}"
            
            # Stop container
            docker stop "$CONTAINER_ID" > /dev/null 2>&1
            docker rm "$CONTAINER_ID" > /dev/null 2>&1
            
            echo -e "${GREEN}✅ Test passed for SOURCE_TYPE=$SOURCE_TYPE${NC}"
            echo ""
            return 0
        fi
        
        if [ $i -eq 10 ]; then
            echo -e "${RED}❌ Health check failed${NC}"
            echo -e "${YELLOW}Container logs:${NC}"
            docker logs "$CONTAINER_ID" 2>&1 | tail -20
            docker stop "$CONTAINER_ID" > /dev/null 2>&1
            docker rm "$CONTAINER_ID" > /dev/null 2>&1
            return 1
        fi
        
        echo -e "${YELLOW}   Attempt $i/10...${NC}"
        sleep 2
    done
}

# Run tests
echo -e "${YELLOW}Starting test sequence...${NC}"
echo ""

# Test local source
test_container "local" 8001

echo ""
echo -e "${GREEN}🎉 All tests passed!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Run interactively:"
echo "     docker run -it -p 8000:8000 -e SOURCE_TYPE=local -e OPENAI_API_KEY=\$OPENAI_API_KEY $IMAGE_NAME"
echo ""
echo "  2. Test API endpoints:"
echo "     curl http://localhost:8000/health"
echo "     curl http://localhost:8000/docs"
echo ""
echo "  3. Deploy to cloud:"
echo "     cd ../../deployment/aws/mapper && ./deploy.sh"
