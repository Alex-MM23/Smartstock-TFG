# Back/models.py
"""SQLAlchemy models matching the legacy database schema."""
import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class ProductModel(Base):
    __tablename__ = "productos"

    id_producto = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, index=True, nullable=False)
    nombre = Column(String(255), nullable=False)
    descripcion = Column(String(500), nullable=True)
    precio_unitario = Column(Float, nullable=False)
    costo_unitario = Column(Float, nullable=True)
    stock_actual = Column(Integer, default=0)
    stock_seguridad_minimo = Column(Integer, nullable=True)
    id_categoria = Column(Integer, ForeignKey("categorias.id_categoria"), nullable=True)
    imagen_url = Column(String(500), nullable=True)
    activo = Column(Integer, default=1)
    id_proveedor = Column(Integer, ForeignKey("proveedores.id_proveedor"), nullable=True)


class OrderModel(Base):
    """Legacy 'pedidos' table - uses id_pedido as primary key."""
    __tablename__ = "pedidos"

    id_pedido = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, nullable=False)
    total = Column(Float, nullable=False)
    estado = Column(String(50), default="Completado")
    fecha_pedido = Column(DateTime, default=datetime.datetime.utcnow)


class OrderDetailModel(Base):
    """Legacy 'detalle_pedido' table."""
    __tablename__ = "detalle_pedido"

    id_detalle = Column(Integer, primary_key=True, index=True)
    id_pedido = Column(Integer, ForeignKey("pedidos.id_pedido"), nullable=False)
    id_producto = Column(Integer, ForeignKey("productos.id_producto"), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Float, nullable=False)

    order = relationship("OrderModel", backref="items")
    product = relationship("ProductModel")


class CategoriaModel(Base):
    """Categorías de productos."""
    __tablename__ = "categorias"

    id_categoria = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)
    id_categoria_padre = Column(Integer, ForeignKey("categorias.id_categoria"), nullable=True)


class ProveedorModel(Base):
    """Proveedores."""
    __tablename__ = "proveedores"

    id_proveedor = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False, unique=True)
    contacto_email = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    plazo_entrega_dias = Column(Integer, default=7)


class PurchaseOrderModel(Base):
    """Órdenes de compra a proveedores (generadas por IA o manuales)."""
    __tablename__ = "purchase_orders"

    id_orden_compra = Column(Integer, primary_key=True, index=True)
    id_proveedor = Column(Integer, ForeignKey("proveedores.id_proveedor"), nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    estado = Column(String(50), default="Pendiente")  # Pendiente, Aprobada, Recibida
    generada_por_ia = Column(Integer, default=0)  # 0 = manual, 1 = IA
    total_unidades = Column(Integer, default=0)

    supplier = relationship("ProveedorModel", backref="purchase_orders")
    items = relationship("PurchaseOrderItemModel", back_populates="order")


class PurchaseOrderItemModel(Base):
    """Items de una orden de compra."""
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)
    id_orden_compra = Column(Integer, ForeignKey("purchase_orders.id_orden_compra"), nullable=False)
    id_producto = Column(Integer, ForeignKey("productos.id_producto"), nullable=False)
    cantidad = Column(Integer, nullable=False)

    order = relationship("PurchaseOrderModel", back_populates="items")
    product = relationship("ProductModel")


class HistoricoVentasModel(Base):
    """Histórico de ventas diarias por producto."""
    __tablename__ = "historico_ventas"

    id = Column(Integer, primary_key=True, index=True)
    id_producto = Column(Integer, ForeignKey("productos.id_producto"), nullable=False)
    fecha = Column(DateTime, nullable=False)
    cantidad_vendida = Column(Integer, nullable=False)
    precio_venta = Column(Float, nullable=False)


class PrediccionDemandaModel(Base):
    """Predicciones de demanda."""
    __tablename__ = "predicciones_demanda"

    id = Column(Integer, primary_key=True, index=True)
    id_producto = Column(Integer, ForeignKey("productos.id_producto"), nullable=False)
    fecha_prediccion = Column(DateTime, nullable=False)
    demanda_estimada = Column(Float, nullable=False)
    stock_recomendado = Column(Integer, nullable=False)
    modelo_version = Column(String(50), nullable=False)

