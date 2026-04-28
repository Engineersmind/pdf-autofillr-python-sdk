#!/bin/bash
# Build Docker image for Mapper module
# Universal image supporting all cloud providers

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐳 Building Mapper Docker Image${NC}"
echo "=================================="

# Configuration
IMAGE_NAME="${IMAGE_NAME:-pdf-mapper}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

# Get repository root (3 levels up from this script)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo -e "${YELLOW}📁 Repository root: $REPO_ROOT${NC}"
echo -e "${YELLOW}🏷️  Image name: $FULL_IMAGE_NAME${NC}"

# Check if Dockerfile exists
DOCKERFILE="$SCRIPT_DIR/Dockerfile"
if [ ! -f "$DOCKERFILE" ]; then
    echo -e "${RED}❌ Error: Dockerfile not found at $DOCKERFILE${NC}"
    exit 1
fi

# Check if requirements files exist
REQUIREMENTS_DIR="$REPO_ROOT/packages/mapper"
if [ ! -f "$REQUIREMENTS_DIR/requirements.txt" ]; then
    echo -e "${RED}❌ Error: requirements.txt not found at $REQUIREMENTS_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites found${NC}"
echo ""

# Build image
echo -e "${GREEN}🔨 Building Docker image...${NC}"
docker build \
    -f "$DOCKERFILE" \
    -t "$FULL_IMAGE_NAME" \
    "$REPO_ROOT" \
    || { echo -e "${RED}❌ Build failed!${NC}"; exit 1; }

echo ""
echo -e "${GREEN}✅ Build complete!${NC}"
echo ""

# Display image info
echo -e "${GREEN}📊 Image Information:${NC}"
docker images "$IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
echo ""

# Display image size
IMAGE_SIZE=$(docker images "$FULL_IMAGE_NAME" --format "{{.Size}}")
echo -e "${GREEN}📦 Image size: $IMAGE_SIZE${NC}"
echo ""

# Test image
echo -e "${YELLOW}🧪 Running quick test...${NC}"
if docker run --rm "$FULL_IMAGE_NAME" python -c "import src; print('✅ Mapper module imports successfully')"; then
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
echo "     cd $SCRIPT_DIR"
echo "     docker-compose up"
echo ""
echo "  2. Test with different sources:"
echo "     docker run -p 8000:8000 -e SOURCE_TYPE=local -e OPENAI_API_KEY=\$OPENAI_API_KEY $FULL_IMAGE_NAME"
echo ""
echo "  3. Push to registry:"
echo "     docker tag $FULL_IMAGE_NAME <registry>/$FULL_IMAGE_NAME"
echo "     docker push <registry>/$FULL_IMAGE_NAME"
echo ""
echo "  4. Deploy to AWS Lambda:"
echo "     cd ../../../deployment/aws/mapper"
echo "     ./deploy.sh"
