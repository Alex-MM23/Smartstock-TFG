"""Database migrations and view creation for SmartStock AI.

This module creates the necessary database views and ensures
the schema is compatible with the API expectations.
"""

from sqlalchemy import text, inspect

from src.config import get_engine


def create_views(engine) -> None:
    """Create or replace the v_stock_alerta view used by /stock/status endpoint."""
    # SQLite doesn't support CREATE OR REPLACE VIEW, so we drop first
    drop_sql = "DROP VIEW IF EXISTS v_stock_alerta"
    view_sql = """
    CREATE VIEW v_stock_alerta AS
    SELECT
        p.id_producto,
        p.sku,
        p.nombre,
        c.nombre AS categoria,
        p.stock_actual,
        COALESCE(p.stock_seguridad_minimo, 0) AS stock_seguridad_minimo,
        CASE
            WHEN p.stock_actual <= COALESCE(p.stock_seguridad_minimo, 0) THEN 1
            ELSE 0
        END AS bajo_minimo
    FROM productos p
    LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
    WHERE p.activo = 1
    """

    with engine.begin() as conn:
        conn.execute(text(drop_sql))
        conn.execute(text(view_sql))


def ensure_tables_exist(engine) -> None:
    """Verify that all required tables exist."""
    required_tables = [
        'productos',
        'categorias',
        'proveedores',
        'historico_ventas',
        'pedidos',
        'detalle_pedido',
        'predicciones_demanda',
        'users',
        'purchase_orders',
        'purchase_order_items'
    ]

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    for table in required_tables:
        if table not in existing_tables:
            print(f"Warning: Table '{table}' does not exist")
        else:
            print(f"Table '{table}' exists")


def run_migrations() -> None:
    """Run all migrations."""
    engine = get_engine()

    ensure_tables_exist(engine)
    create_views(engine)


if __name__ == "__main__":
    run_migrations()