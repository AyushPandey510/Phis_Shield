#!/bin/bash

# ===========================================
# PhisGuard Production Deployment Script
# ===========================================

set -e  # Exit on any error

echo "🚀 PhisGuard Production Deployment Script"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [[ ! -f "app.py" ]] || [[ ! -f "docker-compose.yml" ]]; then
    print_error "Please run this script from the PhisGuard root directory"
    exit 1
fi

print_status "Starting production deployment process..."

# 1. Check Docker and Docker Compose
print_status "Checking Docker availability..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_success "Docker and Docker Compose are available"

# 2. Create production .env if it doesn't exist
print_status "Setting up production environment..."
if [[ ! -f ".env.production" ]]; then
    print_warning "No .env.production file found. Creating from template..."
    cp .env.example .env.production
    
    # Generate secure values
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    API_KEY=$(python3 -c "import secrets; print(secrets.token_hex(16))")
    ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
    
    # Update .env.production with secure values
    sed -i "s/your-super-secret-key-change-this-in-production/$SECRET_KEY/" .env.production
    sed -i "s/your-phisguard-api-key-change-this-in-production/$API_KEY/" .env.production
    sed -i "s/your-admin-password-change-this-in-production/$ADMIN_PASSWORD/" .env.production
    sed -i "s/FLASK_DEBUG=True/FLASK_DEBUG=False/" .env.production
    
    print_success "Production .env file created with secure values"
else
    print_status "Production .env file already exists"
fi

# 3. Set production environment
print_status "Setting production environment..."
export $(cat .env.production | grep -v '^#' | xargs)

# 4. Stop existing containers
print_status "Stopping existing containers..."
if docker-compose ps | grep -q "Up"; then
    docker-compose down
    print_success "Existing containers stopped"
else
    print_status "No running containers found"
fi

# 5. Build and start services
print_status "Building Docker images..."
docker-compose build --no-cache

print_status "Starting services..."
docker-compose up -d

# 6. Wait for services to be healthy
print_status "Waiting for services to be healthy..."
sleep 10

# Check Redis
print_status "Checking Redis service..."
if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
    print_success "Redis is running"
else
    print_error "Redis is not responding"
    exit 1
fi

# Check application health
print_status "Checking application health..."
max_attempts=30
attempt=1
while [[ $attempt -le $max_attempts ]]; do
    if curl -f -s http://localhost:5000/health > /dev/null 2>&1; then
        print_success "Application is healthy and responding"
        break
    else
        if [[ $attempt -eq $max_attempts ]]; then
            print_error "Application health check failed after $max_attempts attempts"
            print_status "Showing application logs:"
            docker-compose logs phisguard-backend
            exit 1
        fi
        print_status "Waiting for application to start (attempt $attempt/$max_attempts)..."
        sleep 5
        ((attempt++))
    fi
done

# 7. Run basic API tests
print_status "Running basic API tests..."
if curl -f -s http://localhost:5000/health | grep -q "healthy"; then
    print_success "Health endpoint working"
else
    print_warning "Health endpoint test failed"
fi

# 8. Display deployment information
print_success "🎉 PhisGuard deployed successfully!"
echo ""
echo "📊 Deployment Summary:"
echo "===================="
echo "🌐 Application URL: http://localhost:5000"
echo "🔗 Health Check: http://localhost:5000/health"
echo "📖 API Documentation: http://localhost:5000"
echo "🗄️ Redis URL: redis://localhost:6379"
echo ""
echo "📝 Next Steps:"
echo "============="
echo "1. Update Chrome extension API URLs to point to production"
echo "2. Configure SSL/TLS certificates for HTTPS"
echo "3. Set up monitoring and logging"
echo "4. Configure backup strategies"
echo "5. Review and update API keys"
echo ""
echo "🔧 Management Commands:"
echo "======================"
echo "View logs: docker-compose logs -f"
echo "Stop services: docker-compose down"
echo "Restart services: docker-compose restart"
echo "Update application: git pull && docker-compose up -d --build"
echo ""
print_success "Production deployment completed successfully!"

# 9. Optional: Create backup of current state
if [[ "$1" == "--backup" ]]; then
    print_status "Creating backup of deployment..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    docker-compose exec -T phisguard-backend tar czf - /app > "phisguard_backup_$timestamp.tar.gz"
    print_success "Backup created: phisguard_backup_$timestamp.tar.gz"
fi