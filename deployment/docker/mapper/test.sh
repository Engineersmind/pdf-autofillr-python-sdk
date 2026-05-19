#!/bin/bash
# Test Docker image locally with different sources
# This script helps verify the universal image works with all cloud providers

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🧪 Testing Mapper Docker Image${NC}"
echo "================================"

IMAGE_NAME="${IMAGE_NAME:-pdf-mapper:latest}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Creating from template...${NC}"
    cp .env.example .env
    echo -e "${RED}❌ Please edit .env file with your credentials before testing${NC}"
    exit 1
fi

# Load environment variables
source .env

# Check required variables
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-your-openai-key-here" ]; then
    echo -e "${RED}❌ Error: OPENAI_API_KEY not set in .env${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment variables loaded${NC}"
echo ""

# Function to test with a specific source
test_source() {
    local SOURCE=$1
    local PORT=$2
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Testing with SOURCE_TYPE=$SOURCE${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Start container
    echo -e "${YELLOW}🚀 Starting container...${NC}"
    
    CONTAINER_ID=$(docker run -d \
        -p "$PORT:8000" \
        -e SOURCE_TYPE="$SOURCE" \
        -e OPENAI_API_KEY="$OPENAI_API_KEY" \
        -e AWS_REGION="$AWS_REGION" \
        -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
        -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
        -e AZURE_STORAGE_CONNECTION_STRING="$AZURE_STORAGE_CONNECTION_STRING" \
        -e GOOGLE_CLOUD_PROJECT="$GOOGLE_CLOUD_PROJECT" \
        -e LOG_LEVEL="INFO" \
        -v "$(pwd)/../../../data:/data" \
        "$IMAGE_NAME")
    
    echo -e "${GREEN}✅ Container started: $CONTAINER_ID${NC}"
    
    # Wait for container to be ready
    echo -e "${YELLOW}⏳ Waiting for service to be ready...${NC}"
    sleep 5
    
    # Test health endpoint
    echo -e "${YELLOW}🏥 Testing health endpoint...${NC}"
    for i in {1..10}; do
        if curl -f -s "http://localhost:$PORT/health" > /dev/null; then
            echo -e "${GREEN}✅ Health check passed!${NC}"
            
            # Show health response
            HEALTH_RESPONSE=$(curl -s "http://localhost:$PORT/health")
            echo -e "${GREEN}Response: $HEALTH_RESPONSE${NC}"
            break
        else
            if [ $i -eq 10 ]; then
                echo -e "${RED}❌ Health check failed after 10 attempts${NC}"
                docker logs "$CONTAINER_ID"
                docker stop "$CONTAINER_ID" > /dev/null
                docker rm "$CONTAINER_ID" > /dev/null
                return 1
            fi
            echo -e "${YELLOW}   Attempt $i/10...${NC}"
            sleep 2
        fi
    done
    
    # Show container logs
    echo ""
    echo -e "${YELLOW}📋 Container logs:${NC}"
    docker logs "$CONTAINER_ID" 2>&1 | tail -20
    
    # Stop container
    echo ""
    echo -e "${YELLOW}🛑 Stopping container...${NC}"
    docker stop "$CONTAINER_ID" > /dev/null
    docker rm "$CONTAINER_ID" > /dev/null
    
    echo -e "${GREEN}✅ Test completed for SOURCE_TYPE=$SOURCE${NC}"
    echo ""
}

# Main test sequence
echo -e "${YELLOW}Starting test sequence...${NC}"
echo ""

# Test 1: Local source
test_source "local" 8001

# Test 2: AWS source (if credentials are set)
if [ -n "$AWS_ACCESS_KEY_ID" ] && [ "$AWS_ACCESS_KEY_ID" != "" ]; then
    test_source "aws" 8002
else
    echo -e "${YELLOW}⏭️  Skipping AWS test (credentials not set)${NC}"
    echo ""
fi

# Test 3: Azure source (if credentials are set)
if [ -n "$AZURE_STORAGE_CONNECTION_STRING" ] && [ "$AZURE_STORAGE_CONNECTION_STRING" != "" ]; then
    test_source "azure" 8003
else
    echo -e "${YELLOW}⏭️  Skipping Azure test (credentials not set)${NC}"
    echo ""
fi

# Test 4: GCP source (if credentials are set)
if [ -n "$GOOGLE_CLOUD_PROJECT" ] && [ "$GOOGLE_CLOUD_PROJECT" != "" ]; then
    test_source "gcp" 8004
else
    echo -e "${YELLOW}⏭️  Skipping GCP test (credentials not set)${NC}"
    echo ""
fi

echo ""
echo -e "${GREEN}🎉 All tests completed!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Run with docker-compose:"
echo "     docker-compose up"
echo ""
echo "  2. Test mapping endpoint:"
echo "     curl -X POST http://localhost:8000/map -F 'pdf=@../../../data/packages/mapper_sample/input/small_4page.pdf'"
echo ""
echo "  3. Deploy to cloud:"
echo "     cd ../../aws/mapper && ./deploy.sh"
