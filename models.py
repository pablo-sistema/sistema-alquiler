from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Propiedad(Base):
    __tablename__ = "propiedades"
    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)
    numero = Column(String, nullable=False)
    precio = Column(Float, default=0.0)
    estado = Column(String, default="libre")  # libre/ocupado

    contratos = relationship("Contrato", back_populates="propiedad")


class Inquilino(Base):
    __tablename__ = "inquilinos"
    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    telefono = Column(String, default="")
    whatsapp = Column(String, default="")
    estado = Column(String, default="Activo")

    contratos = relationship("Contrato", back_populates="inquilino")


class Contrato(Base):
    __tablename__ = "contratos"
    id = Column(Integer, primary_key=True, index=True)
    propiedad_id = Column(Integer, ForeignKey("propiedades.id"))
    inquilino_id = Column(Integer, ForeignKey("inquilinos.id"))
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)
    monto_mensual = Column(Float, default=0.0)
    estado = Column(String, default="Activo")  # Activo/Inactivo

    # NUEVO: mensual / diario
    tipo_alquiler = Column(String, default="mensual")

    propiedad = relationship("Propiedad", back_populates="contratos")
    inquilino = relationship("Inquilino", back_populates="contratos")

    cargos = relationship("Cargo", back_populates="contrato")
    pagos = relationship("Pago", back_populates="contrato")
    lecturas = relationship("Lectura", back_populates="contrato")


class Cargo(Base):
    __tablename__ = "cargos"
    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"))
    concepto = Column(String, nullable=False)      # ALQUILER_MENSUAL / ALQUILER_DIARIO / Agua / Luz...
    periodo = Column(String, nullable=False)       # 2026-02 o 2026-02-01_2026-02-10
    monto = Column(Float, default=0.0)
    vencimiento = Column(Date, nullable=False)
    estado = Column(String, default="Pendiente")   # Pendiente/Parcial/Pagado

    # NUEVO: acumulado pagado para saldo automático
    pagado_acumulado = Column(Float, default=0.0)

    contrato = relationship("Contrato", back_populates="cargos")
    pagos = relationship("Pago", back_populates="cargo")


class Pago(Base):
    __tablename__ = "pagos"
    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"))
    cargo_id = Column(Integer, ForeignKey("cargos.id"), nullable=True)

    monto = Column(Float, default=0.0)
    fecha_pago = Column(Date, nullable=False)
    metodo = Column(String, default="Efectivo")

    contrato = relationship("Contrato", back_populates="pagos")
    cargo = relationship("Cargo", back_populates="pagos")


class Lectura(Base):
    __tablename__ = "lecturas"
    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"))

    servicio = Column(String, nullable=False)      # Agua/Luz
    periodo = Column(String, nullable=False)       # 2026-02
    lectura_anterior = Column(Float, default=0.0)
    lectura_actual = Column(Float, default=0.0)
    consumo = Column(Float, default=0.0)
    tarifa = Column(Float, default=0.0)
    monto = Column(Float, default=0.0)
    fecha_registro = Column(Date, nullable=False)

    contrato = relationship("Contrato", back_populates="lecturas")