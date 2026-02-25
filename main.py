from datetime import date, timedelta

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import joinedload

from database import engine, Base, SessionLocal
from models import Propiedad, Inquilino, Contrato, Pago, Cargo, Lectura
from sqlalchemy import func

# ----------------------------
# Config app
# ----------------------------
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Crea tablas si no existen
Base.metadata.create_all(bind=engine)

# ----------------------------
# Reglas de negocio: prorrata día 25
# ----------------------------
DIA_CORTE = 25


def ultimo_dia_mes(anio: int, mes: int) -> int:
    d = date(anio, mes, 28) + timedelta(days=4)
    return (d - timedelta(days=d.day)).day


def sumar_mes(fecha: date) -> date:
    anio = fecha.year + (1 if fecha.month == 12 else 0)
    mes = 1 if fecha.month == 12 else fecha.month + 1
    dia = min(fecha.day, ultimo_dia_mes(anio, mes))
    return date(anio, mes, dia)


def fecha_corte(fecha_inicio: date) -> date:
    """Devuelve el próximo corte día 25. Si ingreso es después del 25, devuelve 25 del siguiente mes."""
    if fecha_inicio.day <= DIA_CORTE:
        return date(fecha_inicio.year, fecha_inicio.month, DIA_CORTE)

    prox = sumar_mes(date(fecha_inicio.year, fecha_inicio.month, 1))
    return date(prox.year, prox.month, DIA_CORTE)


def calcular_prorrata(monto_mensual: float, fecha_inicio: date):
    """Prorrata desde fecha_inicio hasta el corte (sin incluir el día 25). diario = mensual/30."""
    corte = fecha_corte(fecha_inicio)
    dias = (corte - fecha_inicio).days
    if dias < 0:
        dias = 0
    diario = monto_mensual / 30.0
    monto = round(dias * diario, 2)
    return dias, monto, corte


def generar_cargos_mensuales(db, hoy: date):
    """
    Genera ALQUILER_MENSUAL para todos los contratos activos
    cuando hoy es día 25 o más.
    No duplica: si ya existe el cargo del periodo, lo omite.
    """
    if hoy.day < DIA_CORTE:
        return  # aún no toca generar

    venc = date(hoy.year, hoy.month, DIA_CORTE)
    periodo = f"{venc.year:04d}-{venc.month:02d}"

    contratos = db.query(Contrato).filter(Contrato.estado == "Activo").all()

    for contrato in contratos:
        existe = db.query(Cargo).filter(
            Cargo.contrato_id == contrato.id,
            Cargo.concepto == "ALQUILER_MENSUAL",
            Cargo.periodo == periodo
        ).first()

        if existe:
            continue

        nuevo_cargo = Cargo(
            contrato_id=contrato.id,
            concepto="ALQUILER_MENSUAL",
            periodo=periodo,
            monto=contrato.monto_mensual,
            vencimiento=venc,
            estado="Pendiente"
        )
        db.add(nuevo_cargo)


# ----------------------------
# DASHBOARD (HOME)
# ----------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    db = SessionLocal()
    try:
        hoy = date.today()
        generar_cargos_mensuales(db, hoy)
        db.commit
        mes_inicio = date(hoy.year, hoy.month, 1)

        # Propiedades
        total_propiedades = db.query(func.count(Propiedad.id)).scalar() or 0
        ocupadas = db.query(func.count(Propiedad.id)).filter(Propiedad.estado == "ocupado").scalar() or 0
        libres = db.query(func.count(Propiedad.id)).filter(Propiedad.estado == "libre").scalar() or 0

        # Inquilinos / contratos
        total_inquilinos = db.query(func.count(Inquilino.id)).scalar() or 0
        contratos_activos = db.query(func.count(Contrato.id)).filter(Contrato.estado == "Activo").scalar() or 0

        # Cargos
        cargos_pendientes = db.query(func.count(Cargo.id)).filter(Cargo.estado.in_(["Pendiente", "Parcial"])).scalar() or 0
        deuda_total = db.query(func.coalesce(func.sum(Cargo.monto), 0.0)).filter(Cargo.estado.in_(["Pendiente", "Parcial"])).scalar() or 0.0

        # Morosos: cargos vencidos (vencimiento < hoy) y aún pendientes/parciales
        morosos = db.query(func.count(Cargo.id)).filter(
            Cargo.estado.in_(["Pendiente", "Parcial"]),
            Cargo.vencimiento < hoy
        ).scalar() or 0

        # Pagos del mes
        ingresos_mes = db.query(func.coalesce(func.sum(Pago.monto), 0.0)).filter(
            Pago.fecha_pago >= mes_inicio,
            Pago.fecha_pago <= hoy
        ).scalar() or 0.0

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "total_propiedades": total_propiedades,
            "ocupadas": ocupadas,
            "libres": libres,
            "total_inquilinos": total_inquilinos,
            "contratos_activos": contratos_activos,
            "cargos_pendientes": cargos_pendientes,
            "deuda_total": round(float(deuda_total), 2),
            "morosos": morosos,
            "ingresos_mes": round(float(ingresos_mes), 2),
        })
    finally:
        db.close()


# ----------------------------
# MÓDULO: PROPIEDADES
# ----------------------------
@app.get("/propiedades", response_class=HTMLResponse)
def ver_propiedades(request: Request):
    db = SessionLocal()
    try:
        propiedades = db.query(Propiedad).all()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "propiedades": propiedades
        })
    finally:
        db.close()


@app.post("/agregar")
def agregar(tipo: str = Form(...), numero: str = Form(...), precio: float = Form(...)):
    db = SessionLocal()
    try:
        nueva = Propiedad(tipo=tipo, numero=numero, precio=precio)
        db.add(nueva)
        db.commit()
        return RedirectResponse(url="/propiedades", status_code=303)
    finally:
        db.close()


# ----------------------------
# MÓDULO: INQUILINOS
# ----------------------------
@app.get("/inquilinos", response_class=HTMLResponse)
def ver_inquilinos(request: Request):
    db = SessionLocal()
    try:
        inquilinos = db.query(Inquilino).all()
        return templates.TemplateResponse("inquilinos.html", {
            "request": request,
            "inquilinos": inquilinos
        })
    finally:
        db.close()


@app.get("/nuevo_inquilino", response_class=HTMLResponse)
def nuevo_inquilino(request: Request):
    return templates.TemplateResponse("nuevo_inquilino.html", {"request": request})


@app.post("/guardar_inquilino")
def guardar_inquilino(
    dni: str = Form(...),
    nombre: str = Form(...),
    telefono: str = Form(...),
    whatsapp: str = Form(...),
    estado: str = Form(...)
):
    db = SessionLocal()
    try:
        nuevo = Inquilino(
            dni=dni,
            nombre=nombre,
            telefono=telefono,
            whatsapp=whatsapp,
            estado=estado
        )
        db.add(nuevo)
        db.commit()
        return RedirectResponse(url="/inquilinos", status_code=303)
    finally:
        db.close()


# ----------------------------
# MÓDULO: CONTRATOS (+ cargo prorrata automático)
# ----------------------------
@app.get("/contratos", response_class=HTMLResponse)
def ver_contratos(request: Request):
    db = SessionLocal()
    try:
        contratos = db.query(Contrato).options(
            joinedload(Contrato.propiedad),
            joinedload(Contrato.inquilino)
        ).all()

        propiedades = db.query(Propiedad).all()
        inquilinos = db.query(Inquilino).all()

        return templates.TemplateResponse("contratos.html", {
            "request": request,
            "contratos": contratos,
            "propiedades": propiedades,
            "inquilinos": inquilinos
        })
    finally:
        db.close()


@app.post("/crear_contrato")
def crear_contrato(
    inquilino_id: int = Form(...),
    propiedad_id: int = Form(...),
    fecha_inicio: date = Form(...),
    fecha_fin: date = Form(...),
    monto_mensual: float = Form(...)
):
    db = SessionLocal()
    try:
        # 1) Crear contrato
        nuevo_contrato = Contrato(
            inquilino_id=inquilino_id,
            propiedad_id=propiedad_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            monto_mensual=monto_mensual,
            estado="Activo"
        )
        db.add(nuevo_contrato)
        db.flush()  # obtiene ID del contrato

        # 2) Marcar propiedad como ocupada
        propiedad = db.query(Propiedad).filter(Propiedad.id == propiedad_id).first()
        if propiedad:
            propiedad.estado = "ocupado"

        # 3) Generar primer cargo prorrateado hasta el día 25
        _, monto_prorrata, venc = calcular_prorrata(monto_mensual, fecha_inicio)
        periodo = f"{venc.year:04d}-{venc.month:02d}"

        cargo_inicial = Cargo(
            contrato_id=nuevo_contrato.id,
            concepto="ALQUILER_PRORRATA",
            periodo=periodo,
            monto=monto_prorrata,
            vencimiento=venc,
            estado="Pendiente"
        )
        db.add(cargo_inicial)

        db.commit()
        return RedirectResponse(url="/contratos", status_code=303)
    finally:
        db.close()


# ----------------------------
# MÓDULO: PAGOS
# ----------------------------
@app.get("/pagos", response_class=HTMLResponse)
def ver_pagos(request: Request):
    db = SessionLocal()
    try:
        # Pagos existentes (para historial)
        pagos = db.query(Pago).options(
            joinedload(Pago.contrato).joinedload(Contrato.inquilino),
            joinedload(Pago.contrato).joinedload(Contrato.propiedad)
        ).order_by(Pago.fecha_pago.desc()).all()

        # Cargos pendientes o parciales
        cargos_pendientes = db.query(Cargo).options(
            joinedload(Cargo.contrato).joinedload(Contrato.inquilino),
            joinedload(Cargo.contrato).joinedload(Contrato.propiedad)
        ).filter(Cargo.estado.in_(["Pendiente", "Parcial"])) \
         .order_by(Cargo.vencimiento.asc()).all()

        return templates.TemplateResponse("pagos.html", {
            "request": request,
            "pagos": pagos,
            "cargos_pendientes": cargos_pendientes
        })
    finally:
        db.close()


@app.post("/crear_pago")
def crear_pago(
    cargo_id: int = Form(...),
    monto: float = Form(...),
    fecha_pago: str = Form(...),
    metodo: str = Form(...)
):
    db = SessionLocal()
    try:
        cargo = db.query(Cargo).filter(Cargo.id == cargo_id).first()
        if not cargo:
            return {"error": "Cargo no encontrado"}

        # Registrar pago asociado al contrato del cargo
        pago = Pago(
            contrato_id=cargo.contrato_id,
            monto=monto,
            fecha_pago=date.fromisoformat(fecha_pago),
            metodo=metodo
        )
        db.add(pago)

        # Calcular total pagado para ese cargo (simple: sumamos pagos del contrato el mismo día NO es exacto)
        # Mejor: marcamos Pagado si monto >= cargo.monto, Parcial si monto < cargo.monto
        if monto >= cargo.monto:
            cargo.estado = "Pagado"
        else:
            cargo.estado = "Parcial"
            # Opcional: crear cargo por saldo pendiente
            saldo = round(cargo.monto - monto, 2)
            cargo_saldo = Cargo(
                contrato_id=cargo.contrato_id,
                concepto=f"SALDO_{cargo.concepto}",
                periodo=cargo.periodo,
                monto=saldo,
                vencimiento=cargo.vencimiento,
                estado="Pendiente"
            )
            db.add(cargo_saldo)
            cargo.estado = "Pagado"  # el original queda cancelado y el saldo queda como nuevo cargo pendiente

        db.commit()
        return RedirectResponse(url="/pagos", status_code=303)
    finally:
        db.close()


# ----------------------------
# MÓDULO: CARGOS
# ----------------------------
@app.get("/cargos", response_class=HTMLResponse)
def ver_cargos(request: Request):
    db = SessionLocal()
    try:
        cargos = db.query(Cargo).options(
            joinedload(Cargo.contrato).joinedload(Contrato.inquilino),
            joinedload(Cargo.contrato).joinedload(Contrato.propiedad)
        ).order_by(Cargo.vencimiento.desc()).all()

        return templates.TemplateResponse("cargos.html", {
            "request": request,
            "cargos": cargos
        })
    finally:
        db.close()
@app.post("/generar_cargos_mensuales")
def generar_cargos_manual():
    db = SessionLocal()
    try:
        hoy = date.today()
        generar_cargos_mensuales(db, hoy)
        db.commit()
        return RedirectResponse(url="/cargos", status_code=303)
    finally:
        db.close()

@app.get("/lecturas", response_class=HTMLResponse)
def ver_lecturas(request: Request):
    db = SessionLocal()
    try:
        hoy = date.today()
        periodo = f"{hoy.year:04d}-{hoy.month:02d}"

        contratos = db.query(Contrato).options(
            joinedload(Contrato.inquilino),
            joinedload(Contrato.propiedad)
        ).filter(Contrato.estado == "Activo").all()

        lecturas = db.query(Lectura).options(
            joinedload(Lectura.contrato).joinedload(Contrato.inquilino),
            joinedload(Lectura.contrato).joinedload(Contrato.propiedad)
        ).order_by(Lectura.fecha_registro.desc()).all()

        return templates.TemplateResponse("lecturas.html", {
            "request": request,
            "contratos": contratos,
            "lecturas": lecturas,
            "periodo": periodo
        })
    finally:
        db.close()


@app.post("/registrar_lectura")
def registrar_lectura(
    contrato_id: int = Form(...),
    servicio: str = Form(...),              # "LUZ" o "AGUA"
    periodo: str = Form(...),               # "YYYY-MM"
    lectura_anterior: float = Form(...),
    lectura_actual: float = Form(...),
    tarifa: float = Form(...)
):
    db = SessionLocal()
    try:
        if lectura_actual < lectura_anterior:
            return {"error": "La lectura actual no puede ser menor que la anterior."}

        consumo = round(lectura_actual - lectura_anterior, 2)
        monto = round(consumo * tarifa, 2)

        # Evitar duplicar lectura del mismo servicio/periodo/contrato
        existe = db.query(Lectura).filter(
            Lectura.contrato_id == contrato_id,
            Lectura.servicio == servicio,
            Lectura.periodo == periodo
        ).first()
        if existe:
            return {"error": f"Ya existe lectura {servicio} para ese contrato en {periodo}."}

        lectura = Lectura(
            contrato_id=contrato_id,
            servicio=servicio,
            periodo=periodo,
            lectura_anterior=lectura_anterior,
            lectura_actual=lectura_actual,
            consumo=consumo,
            tarifa=tarifa,
            monto=monto,
            fecha_registro=date.today()
        )
        db.add(lectura)

        # Generar cargo (vence el 25)
        y, m = periodo.split("-")
        venc = date(int(y), int(m), DIA_CORTE)

        cargo = Cargo(
            contrato_id=contrato_id,
            concepto=servicio,     # "LUZ" o "AGUA"
            periodo=periodo,
            monto=monto,
            vencimiento=venc,
            estado="Pendiente"
        )
        db.add(cargo)

        db.commit()
        return RedirectResponse(url="/lecturas", status_code=303)
    finally:
        db.close()


@app.post("/generar_internet")
def generar_internet(
    contrato_id: int = Form(...),
    periodo: str = Form(...),
    monto: float = Form(...)
):
    db = SessionLocal()
    try:
        # Evitar duplicar
        existe = db.query(Cargo).filter(
            Cargo.contrato_id == contrato_id,
            Cargo.concepto == "INTERNET",
            Cargo.periodo == periodo
        ).first()
        if existe:
            return {"error": f"Ya existe INTERNET para ese contrato en {periodo}."}

        y, m = periodo.split("-")
        venc = date(int(y), int(m), DIA_CORTE)

        cargo = Cargo(
            contrato_id=contrato_id,
            concepto="INTERNET",
            periodo=periodo,
            monto=round(monto, 2),
            vencimiento=venc,
            estado="Pendiente"
        )
        db.add(cargo)

        db.commit()
        return RedirectResponse(url="/lecturas", status_code=303)
    finally:
        db.close()