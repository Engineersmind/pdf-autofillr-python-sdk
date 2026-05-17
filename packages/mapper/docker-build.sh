#!/bin/bash
# Build Docker image for Mapper module
# Universal image with all cloud SDKs included

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🐳 Building Mapper Docker Image${NC}"
echo "=================================="

# Configuration
IMAGE_NAME="${IMAGE_NAME:-pdf-mapper}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

# Get script directory and module root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MODULE_ROOT="$SCRIPT_DIR"

echo -e "${YELLOW}📁 Module root: $MODULE_ROOT${NC}"
echo -e "${YELLOW}🏷️  Image name: $FULL_IMAGE_NAME${NC}"

# Verify Dockerfile exists
if [ ! -f "$MODULE_ROOT/Dockerfile" ]; then
    echo -e "${RED}❌ Error: Dockerfile not found at $MODULE_ROOT/Dockerfile${NC}"
    exit 1
fi

# Verify requirements-full.txt exists
if [ ! -f "$MODULE_ROOT/requirements-full.txt" ]; then
    echo -e "${RED}❌ Error: requirements-full.txt not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites found${NC}"
echo ""

# Build image from module directory
echo -e "${GREEN}🔨 Building Docker image...${NC}"
cd "$MODULE_ROOT"

docker build \
    -t "$FULL_IMAGE_NAME" \
    -f Dockerfile \
    . \
    || { echo -e "${RED}❌ Build failed!${NC}"; exit 1; }

echo ""
echo -e "${GREEN}✅ Build complete!${NC}"
echo ""

# Display image info
echo -e "${GREEN}📊 Image Information:${NC}"
docker images "$IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
echo ""

# Quick test
echo -e "${YELLOW}🧪 Running quick test...${NC}"
if docker run --rm "$FULL_IMAGE_NAME" python -c "import src; from api_server import app; print('✅ Module imports OK')"; then
    echo -e "${GREEN}✅ Image test passed!${NC}"
else
    echo -e "${RED}❌ Image test failed!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Docker image ready!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Test locally:"
echo "     docker run -p 8000:8000 -e OPENAI_API_KEY=\$OPENAI_API_KEY $FULL_IMAGE_NAME"
echo ""
echo "  2. Test health endpoint:"
echo "     curl http://localhost:8000/health"
echo ""
echo "  3. Deploy to AWS:"
echo "     cd ../../deployment/aws/mapper && ./deploy.sh"
echo ""
echo "  4. Deploy to Azure:"
echo "     cd ../../deployment/azure/mapper && ./deploy.sh"
