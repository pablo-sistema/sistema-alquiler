from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date
from sqlalchemy.orm import relationship
from database import Base


class Propiedad(Base):
    __tablename__ = "propiedades"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)
    numero = Column(String, nullable=False)
    precio = Column(Float, nullable=False)
    estado = Column(String, default="libre")


class Inquilino(Base):
    __tablename__ = "inquilinos"

    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=False)
    whatsapp = Column(String, nullable=False)
    estado = Column(String, default="Activo")


class Contrato(Base):
    __tablename__ = "contratos"

    id = Column(Integer, primary_key=True, index=True)
    propiedad_id = Column(Integer, ForeignKey("propiedades.id"), nullable=False)
    inquilino_id = Column(Integer, ForeignKey("inquilinos.id"), nullable=False)

    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)
    monto_mensual = Column(Float, nullable=False)
    estado = Column(String, default="Activo")

    propiedad = relationship("Propiedad")
    inquilino = relationship("Inquilino")


class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)

    monto = Column(Float, nullable=False)
    fecha_pago = Column(Date, nullable=False)
    metodo = Column(String, nullable=False)

    contrato = relationship("Contrato")


class Cargo(Base):
    __tablename__ = "cargos"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)

    concepto = Column(String, nullable=False)   # ALQUILER_PRORRATA, ALQUILER, LUZ, AGUA, INTERNET, MORA
    periodo = Column(String, nullable=False)    # "YYYY-MM"
    monto = Column(Float, nullable=False)

    vencimiento = Column(Date, nullable=False)  # normalmente día 25
    estado = Column(String, default="Pendiente")  # Pendiente / Pagado / Parcial

    contrato = relationship("Contrato")

class Lectura(Base):
    __tablename__ = "lecturas"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)

    servicio = Column(String, nullable=False)        # LUZ o AGUA
    periodo = Column(String, nullable=False)         # "YYYY-MM"
    lectura_anterior = Column(Float, nullable=False)
    lectura_actual = Column(Float, nullable=False)
    consumo = Column(Float, nullable=False)
    tarifa = Column(Float, nullable=False)
    monto = Column(Float, nullable=False)

    fecha_registro = Column(Date, nullable=False)
    contrato = relationship("Contrato")
    