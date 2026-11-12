#!/usr/bin/env bash
# SmartStock AI - Diagnóstico completo
# Ejecuta este script para diagnosticar problemas con el catálogo de productos

set -e

echo "🔍 SmartStock AI - Diagnóstico del Catálogo de Productos"
echo "========================================================="
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para verificar si un comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Verificar Docker
echo "1️⃣  Verificando Docker..."
if command_exists docker; then
    echo -e "   ${GREEN}✓${NC} Docker encontrado: $(docker --version)"
else
    echo -e "   ${RED}✗${NC} Docker NO encontrado en PATH"
    echo "      Instala Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
    echo -e "   ${GREEN}✓${NC} Docker Compose disponible"
else
    echo -e "   ${RED}✗${NC} Docker Compose NO disponible"
    exit 1
fi
echo ""

# 2. Verificar estado de contenedores
echo "2️⃣  Estado de contenedores (docker-compose ps):"
cd "$(dirname "$0")"
docker-compose ps
echo ""

# 3. Verificar API Health
echo "3️⃣  Probando endpoint /health..."
if curl -s -f http://localhost:8000/health > /tmp/health.json 2>&1; then
    echo -e "   ${GREEN}✓${NC} API responde en puerto 8000"
    cat /tmp/health.json | jq . 2>/dev/null || cat /tmp/health.json
else
    echo -e "   ${RED}✗${NC} API NO responde en http://localhost:8000/health"
    echo "      ¿Están los contenedores levantados? Ejecuta: docker-compose up -d"
fi
echo ""

# 4. Verificar endpoint /products
echo "4️⃣  Probando endpoint /products..."
if curl -s -f http://localhost:8000/products > /tmp/products.json 2>&1; then
    COUNT=$(cat /tmp/products.json | jq 'length' 2>/dev/null || echo "?")
    echo -e "   ${GREEN}✓${NC} Endpoint /products responde - $COUNT productos"
    echo "   Primeros 3 productos:"
    cat /tmp/products.json | jq '.[:3]' 2>/dev/null || cat /tmp/products.json
else
    echo -e "   ${RED}✗${NC} Endpoint /products FALLA"
    echo "      Response:"
    cat /tmp/products.json
fi
echo ""

# 5. Verificar CORS
echo "5️⃣  Verificando CORS (preflight OPTIONS)..."
CORS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Origin: http://localhost:4200" \
    -H "Access-Control-Request-Method: GET" \
    -X OPTIONS http://localhost:8000/products)
if [ "$CORS_RESPONSE" = "200" ] || [ "$CORS_RESPONSE" = "204" ]; then
    echo -e "   ${GREEN}✓${NC} CORS preflight OK (status: $CORS_RESPONSE)"
else
    echo -e "   ${YELLOW}⚠${NC} CORS preflight status: $CORS_RESPONSE (puede ser OK si no hay preflight)"
fi
echo ""

# 6. Verificar base de datos MySQL
echo "6️⃣  Verificando base de datos MySQL..."
if docker exec smartstock_db mysqladmin ping -h localhost -u smartstock -psmartstock_pass >/dev/null 2>&1; then
    echo -e "   ${GREEN}✓${NC} MySQL responde"

    # Contar productos
    PRODUCT_COUNT=$(docker exec smartstock_db mysql -u smartstock -psmartstock_pass -D smartstock -sN -e "SELECT COUNT(*) FROM productos WHERE activo = 1;" 2>/dev/null || echo "ERROR")
    echo -e "   Productos activos en BD: ${PRODUCT_COUNT}"

    if [ "$PRODUCT_COUNT" = "0" ] || [ "$PRODUCT_COUNT" = "ERROR" ]; then
        echo -e "   ${YELLOW}⚠${NC} No hay productos o error en consulta"
        echo "      Ejecuta: make db-ingest && make db-train"
    fi
else
    echo -e "   ${RED}✗${NC} MySQL NO responde"
    echo "      Verifica: docker logs smartstock_db"
fi
echo ""

# 7. Verificar logs de la API
echo "7️⃣  Últimos logs de la API (errores):"
docker logs smartstock_api --tail 30 2>&1 | grep -iE "(error|exception|failed|products)" || echo "   (No hay errores recientes visibles)"
echo ""

# 8. Verificar configuración frontend
echo "8️⃣  Configuración frontend (environment.ts):"
cat front-app/src/environments/environment.ts
echo ""

echo "========================================================="
echo "📋 RESUMEN DE PRÓXIMOS PASOS:"
echo ""
if [ ! -f /tmp/products.json ] || [ "$(cat /tmp/products.json | jq 'length' 2>/dev/null || echo 0)" = "0" ]; then
    echo -e "${YELLOW}1.${NC} No hay productos en la BD → Ejecuta:"
    echo "   cd Back && python -m src.data.ingest --dias 730"
    echo "   cd Back && python -m src.models.train"
    echo ""
    echo -e "${YELLOW}2.${NC} O usa el Makefile:"
    echo "   make db-reset   # Reset completo: BD + datos + modelo"
fi

if ! curl -s -f http://localhost:8000/health >/dev/null 2>&1; then
    echo -e "${RED}3.${NC} API no responde → Levantar servicios:"
    echo "   docker-compose up -d"
    echo "   docker-compose logs -f api"
fi

echo ""
echo -e "${GREEN}✅ Diagnóstico completado${NC}"