# PDFKatana Production Deployment Guide

## 🚀 Quick Start for Portainer

### Option 1: Simple Deployment (Recommended for testing)
Copy and paste the contents of `portainer-stack-simple.yml` into Portainer's stack editor.

### Option 2: Production with Nginx
1. Copy `portainer-stack-prod.yml` 
2. Uncomment the nginx service section
3. Copy `nginx-prod.conf` to your server
4. Create SSL certificates directory

## 📋 Prerequisites

### 1. Build the Docker Image
```bash
# In your PDFKatana project directory
docker build -t pdfkatana:latest .
```

### 2. Push to Registry (Optional)
```bash
# Tag for your registry
docker tag pdfkatana:latest your-registry.com/pdfkatana:latest
docker push your-registry.com/pdfkatana:latest

# Update the image name in the YAML files
```

## 🔧 Configuration Options

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE_MB` | 100 | Maximum PDF file size in MB |
| `MAX_PAGES` | 100 | Maximum pages per PDF |
| `TEMP_RETENTION_MIN` | 60 | Minutes to keep temporary files |
| `MAX_WORKERS` | 2 | Number of Gunicorn workers |
| `LOG_LEVEL` | info | Logging level (debug, info, warning, error) |

### Resource Limits
- **Memory**: 256M reserved, 512M limit
- **CPU**: 0.25 cores reserved, 0.5 cores limit
- **Port**: 8000 (internal), customizable (external)

## 🌐 Network Configuration

### Default Network
- **Subnet**: 172.20.0.0/16
- **Driver**: Bridge
- **Isolation**: Container-level

### Custom Network (Optional)
```yaml
networks:
  pdfkatana_network:
    external: true
    name: your-custom-network
```

## 📊 Health Checks

### Built-in Health Check
- **Endpoint**: `/v1/health`
- **Interval**: 30 seconds
- **Timeout**: 10 seconds
- **Retries**: 3
- **Start Period**: 40 seconds

### Manual Testing
```bash
# Health check
curl http://your-server:8000/v1/health

# Readiness probe
curl http://your-server:8000/v1/ready

# API documentation
curl http://your-server:8000/docs
```

## 🔒 Security Considerations

### 1. Network Access
- **Internal**: Only accessible within Docker network
- **External**: Expose only necessary ports
- **Firewall**: Restrict access to trusted IPs

### 2. Rate Limiting (with Nginx)
- **API endpoints**: 10 requests/second
- **File uploads**: 2 requests/second
- **Burst allowance**: 20 requests

### 3. SSL/TLS
- **Required**: For production use
- **Certificates**: Let's Encrypt or custom CA
- **Protocols**: TLS 1.2+ only

## 📁 Volume Management

### Temporary Files
- **Path**: `/app/src/tmp`
- **Purpose**: PDF processing
- **Cleanup**: Automatic (60 minutes)
- **Size**: Monitor for disk space

### Logs
- **Path**: `/app/src/logs`
- **Rotation**: Configure in your logging solution
- **Retention**: 30-90 days recommended

## 🚨 Troubleshooting

### Common Issues

#### 1. Container Won't Start
```bash
# Check logs
docker logs pdfkatana-prod

# Verify image exists
docker images | grep pdfkatana

# Check port conflicts
netstat -tulpn | grep 8000
```

#### 2. Health Check Fails
```bash
# Test endpoint directly
curl -f http://localhost:8000/v1/health

# Check container status
docker ps -a | grep pdfkatana

# Verify network connectivity
docker exec pdfkatana-prod curl -f http://localhost:8000/v1/health
```

#### 3. Memory Issues
```bash
# Monitor resource usage
docker stats pdfkatana-prod

# Check memory limits
docker inspect pdfkatana-prod | grep -A 10 "HostConfig"
```

### Performance Tuning

#### Worker Configuration
```yaml
environment:
  - MAX_WORKERS=4  # Increase for more CPU cores
  - LOG_LEVEL=warning  # Reduce logging overhead
```

#### Resource Allocation
```yaml
deploy:
  resources:
    limits:
      memory: 1G  # Increase for larger PDFs
      cpus: '1.0'  # Full CPU core
```

## 📈 Monitoring

### Metrics Endpoint
- **URL**: `/metrics`
- **Format**: Prometheus
- **Access**: Internal network only
- **Data**: Request duration, page counts, error rates

### Log Aggregation
- **Format**: JSON structured logging
- **Fields**: timestamp, level, message, request_id
- **Integration**: ELK stack, Graylog, or similar

## 🔄 Updates and Maintenance

### Rolling Updates
```bash
# Pull new image
docker pull pdfkatana:latest

# Update stack
docker stack deploy -c portainer-stack-prod.yml pdfkatana
```

### Backup Strategy
- **Volumes**: Regular backups of persistent data
- **Configuration**: Version control for YAML files
- **Images**: Tagged releases for rollback

## 📞 Support

### Log Locations
- **Container logs**: `docker logs pdfkatana-prod`
- **Application logs**: `/app/src/logs/`
- **Nginx logs**: `/var/log/nginx/`

### Debug Mode
```yaml
environment:
  - LOG_LEVEL=debug
  - PYTHONUNBUFFERED=1
```

---

**Happy Deploying! 🎉**

For issues or questions, check the logs first, then refer to the troubleshooting section above.
