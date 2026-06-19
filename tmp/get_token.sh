cat > /tmp/get_token.sh << 'EOF'
#!/bin/bash
USER=${1:-supermetro_owner}
PASS=${2:-testpass123}
curl -s -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$USER\", \"password\": \"$PASS\"}" | python3 -m json.tool
EOF
chmod +x /tmp/get_token.sh
