# PDFKatana + Nginx Proxy Manager Setup

## 🎯 **Perfect for NPM Users!**

Since you're using Nginx Proxy Manager (NPM) centrally, you don't need any proxy configuration in the PDFKatana stack itself.

## 📋 **What You Need**

### 1. **Use `portainer-stack-npm.yml`** ⭐ **RECOMMENDED**
- Clean, no Traefik labels
- No external port exposure
- Perfect for NPM integration

### 2. **Key Changes Made**
- ❌ **Removed**: `ports: - "8000:8000"`
- ✅ **Added**: `expose: - "8000"` (internal only)
- ❌ **Removed**: All Traefik labels
- ✅ **Kept**: Health checks, resource limits, volumes

## 🚀 **Deployment Steps**

### Step 1: Deploy Stack
1. Copy `portainer-stack-npm.yml` content
2. Paste into Portainer stack editor
3. Deploy the stack

### Step 2: Configure NPM
1. **Add Proxy Host** in NPM
2. **Domain**: `pdfkatana.yourdomain.com` (or whatever you want)
3. **Scheme**: `http`
4. **Forward Hostname/IP**: `pdfkatana-prod` (container name)
5. **Forward Port**: `8000`
6. **Enable SSL** (Let's Encrypt or custom)
7. **Enable Force SSL** and **HTTP/2**

## 🔧 **NPM Configuration Example**

| Setting | Value |
|---------|-------|
| Domain Names | `pdfkatana.yourdomain.com` |
| Scheme | `http` |
| Forward Hostname/IP | `pdfkatana-prod` |
| Forward Port | `8000` |
| Cache Assets | ✅ Enabled |
| Block Common Exploits | ✅ Enabled |
| Websockets Support | ✅ Enabled |
| Access List | Your choice |

## 🌐 **Network Benefits**

### **Security**
- **No external ports** exposed on host
- **Container isolation** maintained
- **NPM handles** all external traffic

### **Flexibility**
- **Easy SSL management** through NPM
- **Centralized logging** and monitoring
- **Simple domain changes** without redeploying

## 📊 **Health Check Access**

### **From Host**
```bash
# Test health check
curl http://localhost:8000/v1/health

# Test readiness
curl http://localhost:8000/v1/ready
```

### **From NPM**
```bash
# Test through your domain
curl https://pdfkatana.yourdomain.com/v1/health
```

## 🚨 **Troubleshooting**

### **Container Won't Start**
```bash
# Check if port 8000 is free
netstat -tulpn | grep 8000

# Should show nothing (no external binding)
```

### **NPM Can't Connect**
```bash
# Verify container is running
docker ps | grep pdfkatana

# Check container logs
docker logs pdfkatana-prod

# Test internal connectivity
docker exec pdfkatana-prod curl -f http://localhost:8000/v1/health
```

### **Network Issues**
```bash
# Check if containers are on same network
docker network ls
docker network inspect pdfkatana_pdfkatana_network
```

## 🎉 **Result**

- **Clean stack** without proxy complexity
- **Centralized SSL** management through NPM
- **Easy monitoring** and logging
- **Professional setup** with minimal configuration

---

**Perfect for production use with NPM! 🚀**
