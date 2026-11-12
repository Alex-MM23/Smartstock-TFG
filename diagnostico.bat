@echo off
REM SmartStock AI - Diagnóstico completo (Windows)
REM Ejecuta este script para diagnosticar problemas con el catálogo de productos

echo 🔍 SmartStock AI - Diagnóstico del Catálogo de Productos
echo =========================================================
echo.

REM 1. Verificar Docker
echo 1️⃣  Verificando Docker...
docker --version >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ Docker encontrado
    docker --version
) else (
    echo    ✗ Docker NO encontrado en PATH
    echo       Instala Docker Desktop: https://www.docker.com/products/docker-desktop
    goto :end
)

docker compose version >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ Docker Compose disponible
) else (
    echo    ✗ Docker Compose NO disponible
    goto :end
)
echo.

REM 2. Verificar estado de contenedores
echo 2️⃣  Estado de contenedores:
docker-compose ps
echo.

REM 3. Verificar API Health
echo 3️⃣  Probando endpoint /health...
curl -s -f http://localhost:8000/health > %TEMP%\health.json 2>&1
if %errorlevel% equ 0 (
    echo    ✓ API responde en puerto 8000
    type %TEMP%\health.json
) else (
    echo    ✗ API NO responde en http://localhost:8000/health
    echo       ¿Están los contenedores levantados? Ejecuta: docker-compose up -d
)
echo.

REM 4. Verificar endpoint /products
echo 4️⃣  Probando endpoint /products...
curl -s -f http://localhost:8000/products > %TEMP%\products.json 2>&1
if %errorlevel% equ 0 (
    echo    ✓ Endpoint /products responde
    type %TEMP%\products.json
) else (
    echo    ✗ Endpoint /products FALLA
    type %TEMP%\products.json
)
echo.

REM 5. Verificar base de datos MySQL
echo 5️⃣  Verificando base de datos MySQL...
docker exec smartstock_db mysqladmin ping -h localhost -u smartstock -psmartstock_pass >nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ MySQL responde

    REM Contar productos
    for /f "delims=" %%a in ('docker exec smartstock_db mysql -u smartstock -psmartstock_pass -D smartstock -sN -e "SELECT COUNT(*) FROM productos WHERE activo = 1;" 2^>nul') do set PRODUCT_COUNT=%%a
    echo    Productos activos en BD: %PRODUCT_COUNT%

    if "%PRODUCT_COUNT%"=="0" (
        echo    ⚠ No hay productos en la BD
        echo       Ejecuta: cd Back && python -m src.data.ingest --dias 730
    )
) else (
    echo    ✗ MySQL NO responde
    echo       Verifica: docker logs smartstock_db
)
echo.

REM 6. Verificar logs de la API
echo 6️⃣  Últimos logs de la API (filtrando errores):
docker logs smartstock_api --tail 30 2>&1 | findstr /i "error exception failed products"
if %errorlevel% neq 0 (
    echo    (No hay errores recientes visibles)
)
echo.

REM 7. Verificar configuración frontend
echo 7️⃣  Configuración frontend (environment.ts):
type front-app\src\environments\environment.ts
echo.

echo =========================================================
echo 📋 RESUMEN DE PRÓXIMOS PASOS:
echo.

if not exist %TEMP%\products.json (
    echo 1. No hay productos en la BD → Ejecuta:
    echo    cd Back && python -m src.data.ingest --dias 730
    echo    cd Back && python -m src.models.train
    echo.
    echo 2. O usa el Makefile:
    echo    make db-reset   ^<-- Reset completo: BD + datos + modelo
    echo.
)

curl -s -f http://localhost:8000/health >nul 2>&1
if %errorlevel% neq 0 (
    echo 3. API no responde → Levantar servicios:
    echo    docker-compose up -d
    echo    docker-compose logs -f api
    echo.
)

echo ✅ Diagnóstico completado

:end
pause