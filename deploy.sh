#!/bin/bash

# ===========================================
# PhisGuard Production Deployment Script
# ===========================================
# This script handles both development and production deployment
# ===========================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="phisguard-backend"
PYTHON_PATH="/home/ayush/phisgaurd-backend"
PORT=5000
ENV_FILE=".env"
PRODUCTION_ENV_FILE=".env.production"
LOG_FILE="logs/phisguard.log"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if environment file exists
check_env_file() {
    if [ "$DEPLOYMENT_MODE" = "production" ]; then
        if [ ! -f "$PRODUCTION_ENV_FILE" ]; then
            print_error "Production environment file '$PRODUCTION_ENV_FILE' not found!"
            print_error "Please copy .env.production to $PRODUCTION_ENV_FILE and configure it."
            exit 1
        fi
        ENV_FILE="$PRODUCTION_ENV_FILE"
        print_status "Using production environment configuration"
    else
        if [ ! -f "$ENV_FILE" ]; then
            print_warning "Environment file '$ENV_FILE' not found. Creating from template..."
            if [ -f ".env.example" ]; then
                cp .env.example "$ENV_FILE"
                print_warning "Please configure $ENV_FILE with your actual values"
            else
                print_error ".env.example template not found!"
                exit 1
            fi
        fi
        print_status "Using development environment configuration"
    fi
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    mkdir -p logs
    mkdir -p data
    mkdir -p /tmp/phisguard
}

# Function to check dependencies
check_dependencies() {
    print_status "Checking dependencies..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 is not installed"
        exit 1
    fi
    
    # Check if requirements.txt exists
    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found"
        exit 1
    fi
    
    # Install/update dependencies if needed
    print_status "Installing/updating dependencies..."
    pip3 install -r requirements.txt
    
    # Install Gunicorn for production
    if [ "$DEPLOYMENT_MODE" = "production" ]; then
        pip3 install gunicorn gevent
        print_status "Production dependencies installed"
    fi
}

# Function to run tests
run_tests() {
    print_status "Running tests..."
    if [ -f "test_app.py" ]; then
        python3 test_app.py
        if [ $? -eq 0 ]; then
            print_status "✅ All tests passed"
        else
            print_error "❌ Some tests failed"
            if [ "$DEPLOYMENT_MODE" = "production" ]; then
                exit 1
            fi
        fi
    else
        print_warning "test_app.py not found, skipping tests"
    fi
}

# Function to start development server
start_development() {
    print_status "Starting development server..."
    export FLASK_ENV=development
    export FLASK_DEBUG=True
    python3 app.py
}

# Function to start production server
start_production() {
    print_status "Starting production server with Gunicorn..."
    
    # Load production environment
    export FLASK_ENV=production
    export FLASK_DEBUG=False
    
    # Check if Gunicorn is available
    if ! command -v gunicorn &> /dev/null; then
        print_error "Gunicorn not installed. Installing..."
        pip3 install gunicorn gevent
    fi
    
    # Start with Gunicorn
    print_status "Starting PhisGuard production server..."
    gunicorn \
        --config gunicorn_config.py \
        --bind 0.0.0.0:$PORT \
        --workers $(($(nproc) * 2 + 1)) \
        --worker-class gevent \
        --worker-connections 1000 \
        --timeout 30 \
        --keepalive 2 \
        --max-requests 1000 \
        --max-requests-jitter 50 \
        --preload-app \
        --access-logfile - \
        --error-logfile - \
        --loglevel info \
        app:app
}

# Function to start with Docker
start_docker() {
    print_status "Starting with Docker..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    
    print_status "Building and starting Docker containers..."
    docker-compose up --build -d
    
    print_status "Docker containers started. Check logs with: docker-compose logs -f"
}

# Function to show help
show_help() {
    echo -e "${BLUE}PhisGuard Deployment Script${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -d, --dev          Start in development mode (default)"
    echo "  -p, --prod         Start in production mode"
    echo "  -t, --test         Run tests only"
    echo "  -b, --build        Build Docker containers"
    echo "  -u, --up           Start with Docker Compose"
    echo "  --down             Stop Docker Compose"
    echo "  --logs             Show Docker logs"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --dev           # Start development server"
    echo "  $0 --prod          # Start production server with Gunicorn"
    echo "  $0 --test          # Run tests only"
    echo "  $0 --up            # Start with Docker"
    echo ""
    echo "Environment:"
    echo "  DEPLOYMENT_MODE    Set to 'production' for production deployment"
    echo "  FLASK_ENV          Set to 'development' or 'production'"
}

# Function to stop Docker
stop_docker() {
    print_status "Stopping Docker containers..."
    docker-compose down
    print_status "Docker containers stopped"
}

# Function to show logs
show_logs() {
    print_status "Showing Docker logs (press Ctrl+C to exit)..."
    docker-compose logs -f
}

# Main script logic
main() {
    # Parse command line arguments
    DEPLOYMENT_MODE="development"
    ACTION="start"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--dev)
                DEPLOYMENT_MODE="development"
                ACTION="start"
                shift
                ;;
            -p|--prod)
                DEPLOYMENT_MODE="production"
                ACTION="start"
                shift
                ;;
            -t|--test)
                ACTION="test"
                shift
                ;;
            -b|--build)
                ACTION="build"
                shift
                ;;
            -u|--up)
                ACTION="docker_up"
                shift
                ;;
            --down)
                ACTION="docker_down"
                shift
                ;;
            --logs)
                ACTION="docker_logs"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Change to app directory
    cd "$PYTHON_PATH" || exit 1
    
    # Execute requested action
    case $ACTION in
        "test")
            check_env_file
            create_directories
            check_dependencies
            run_tests
            ;;
        "build")
            print_status "Building Docker containers..."
            docker-compose build
            ;;
        "docker_up")
            check_env_file
            create_directories
            start_docker
            ;;
        "docker_down")
            stop_docker
            ;;
        "docker_logs")
            show_logs
            ;;
        "start")
            check_env_file
            create_directories
            check_dependencies
            run_tests
            
            if [ "$DEPLOYMENT_MODE" = "production" ]; then
                start_production
            else
                start_development
            fi
            ;;
        *)
            print_error "Unknown action: $ACTION"
            exit 1
            ;;
    esac
}

# Trap signals for graceful shutdown
trap 'print_warning "Received interrupt signal, shutting down..."; exit 0' INT TERM

# Run main function
main "$@"