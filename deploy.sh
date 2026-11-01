#!/bin/bash
set -e

echo "🚀 PGSync Admin - Production Deployment"
echo "========================================"

# Configuration
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="pgsync-admin"

# Pre-flight checks
echo "✓ Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Install Docker first."
    exit 1
fi

echo "✓ Checking Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Install Docker Compose first."
    exit 1
fi

# Build images
echo ""
echo "📦 Building Docker images..."
docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME build

# Start services
echo ""
echo "🚀 Starting services..."
docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d

# Wait for services
echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Health checks
echo ""
echo "🏥 Health checks..."
docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Access PGSync Admin:"
echo "  Frontend: http://localhost:80"
echo "  Backend API: http://localhost:8000"
echo "  ClickHouse: http://localhost:8123"
echo ""
echo "View logs:"
echo "  docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f"
echo ""
echo "Stop services:"
echo "  docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down"
