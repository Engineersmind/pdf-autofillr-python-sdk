#!/bin/bash
# Run Mapper Docker container with local volume mounts
# This script demonstrates how to run the mapper with local data access

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starting Mapper Docker with Local Volume Mounts${NC}"
echo "=================================================="

IMAGE_NAME="${IMAGE_NAME:-pdf-mapper:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-mapper}"
PORT="${PORT:-8000}"

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

# Default data directory
DATA_DIR="${DATA_DIR:-$HOME/Documents/pdf-autofiller-data}"

# Create data directories if they don't exist
echo -e "${YELLOW}📁 Setting up data directories...${NC}"
mkdir -p "$DATA_DIR"/{input,output,temp}

echo -e "${GREEN}✅ Data directories ready:${NC}"
echo -e "   Input:  $DATA_DIR/input"
echo -e "   Output: $DATA_DIR/output"
echo -e "   Temp:   $DATA_DIR/temp"
echo ""

# Stop existing container if running
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${YELLOW}⚠️  Stopping existing container...${NC}"
    docker stop "$CONTAINER_NAME" > /dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" > /dev/null 2>&1 || true
fi

# Start container with volume mounts
echo -e "${YELLOW}🚀 Starting container...${NC}"
docker run -d \
    --name "$CONTAINER_NAME" \
    -p "$PORT:8000" \
    -v "$DATA_DIR:/app/data" \
    -e SOURCE_TYPE=local \
    -e OPENAI_API_KEY="$OPENAI_API_KEY" \
    -e LOG_LEVEL="${LOG_LEVEL:-INFO}" \
    "$IMAGE_NAME"

echo -e "${GREEN}✅ Container started successfully!${NC}"
echo ""

# Wait for service to be ready
echo -e "${YELLOW}⏳ Waiting for service to be ready...${NC}"
for i in {1..15}; do
    if curl -f -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Service is ready!${NC}"
        break
    fi
    
    if [ $i -eq 15 ]; then
        echo -e "${RED}❌ Service failed to start${NC}"
        echo -e "${YELLOW}Container logs:${NC}"
        docker logs "$CONTAINER_NAME"
        exit 1
    fi
    
    sleep 1
done

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Mapper is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📊 Container Information:${NC}"
echo -e "   Name:          $CONTAINER_NAME"
echo -e "   Image:         $IMAGE_NAME"
echo -e "   API URL:       http://localhost:$PORT"
echo -e "   API Docs:      http://localhost:$PORT/docs"
echo ""
echo -e "${BLUE}📁 Volume Mounts:${NC}"
echo -e "   Local:         $DATA_DIR"
echo -e "   Container:     /app/data"
echo ""
echo -e "${BLUE}📂 Directory Mapping:${NC}"
echo -e "   Local Input:   $DATA_DIR/input  → /app/data/input"
echo -e "   Local Output:  $DATA_DIR/output → /app/data/output"
echo -e "   Local Temp:    $DATA_DIR/temp   → /app/data/temp"
echo ""
echo -e "${YELLOW}💡 Quick Start:${NC}"
echo ""
echo -e "1. Put your files in the input directory:"
echo -e "   cp your-form.pdf $DATA_DIR/input/"
echo -e "   cp your-data.json $DATA_DIR/input/"
echo ""
echo -e "2. Test the API:"
echo -e "   curl http://localhost:$PORT/health"
echo ""
echo -e "3. Process a PDF (example):"
cat << 'EOF'
   curl -X POST http://localhost:8000/mapper/run-all \
     -H "Content-Type: application/json" \
     -d '{
       "pdf_path": "/app/data/input/your-form.pdf",
       "input_json_path": "/app/data/input/your-data.json",
       "user_id": 1,
       "pdf_doc_id": 100
     }'
EOF
echo ""
echo -e "4. Get results from output directory:"
echo -e "   ls -lh $DATA_DIR/output/"
echo ""
echo -e "${YELLOW}📝 Useful Commands:${NC}"
echo -e "   View logs:     docker logs -f $CONTAINER_NAME"
echo -e "   Stop:          docker stop $CONTAINER_NAME"
echo -e "   Restart:       docker restart $CONTAINER_NAME"
echo -e "   Shell access:  docker exec -it $CONTAINER_NAME /bin/bash"
echo -e "   Verify mount:  docker exec $CONTAINER_NAME ls -lh /app/data/input"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
