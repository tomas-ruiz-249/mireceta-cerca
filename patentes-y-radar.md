# MiReceta Cerca: relación con las patentes y el radar de innovación

## Proyecto

Sistema que da seguimiento al flujo y la disponibilidad de medicamentos, con una aplicación web que le indica al paciente **dónde** puede retirar su medicamento recetado y **cuándo** estará listo.

**Trabajo por hacer (JTBD):** "Cuando recibo una receta, quiero saber qué farmacia tiene mi medicamento y cuándo puedo retirarlo, para no hacer un viaje en vano."

El prototipo (`index.html`) es una maqueta navegable. Todos los datos son de ejemplo y no hay sistemas reales conectados.

## Radar de innovación

| Criterio | Puntaje | Qué significa para el prototipo |
|---|:-:|---|
| Canal | 5 | Aplicación web: el paciente consulta la disponibilidad antes de desplazarse |
| Experiencia de cliente | 5 | Una respuesta clara (farmacia, stock y mostrador) en pocos clics |
| Proceso | 5 | El stock se actualiza con cada movimiento verificado, para no mostrar información equivocada |
| Soluciones | 4 | Recomendación de la mejor farmacia según stock, distancia y horario |
| Cliente | 4 | Perfil familiar para consultar por otros miembros del hogar |
| Comunicación | 3 | Avisos de estado y aviso de "receta lista" |
| Ecosistema | 3 | Varias farmacias en la misma búsqueda |
| Cadena de suministro | 3 | Fecha de reposición cuando una farmacia no tiene stock |
| Plataforma | 2 | Fuera del alcance: sin API abierta ni marketplace |
| Gestión | 2 | Fuera del alcance: sin panel administrativo |
| Producto | 1 | No se modifica el medicamento |
| Captura de valor | 1 | Sin pagos en la app; se paga en la farmacia al retirar |

**Prioridades principales:** Canal, Experiencia de cliente y Proceso.

## Patentes utilizadas

### US8099339B1 · McKesson · *Pharmacy inventory management*

- **Qué hace:** usa el "switch" de reclamaciones de recetas (el intermediario entre la farmacia y la aseguradora) para llevar un inventario continuo de cada farmacia. Cada reclamación aprobada descuenta stock y cada reversión lo repone. Al bajar de un umbral, genera automáticamente un pedido al proveedor.
- **Elemento tomado:** inventario actualizado por eventos (venta, devolución, ingreso) y reposición automática con fecha de llegada.
- **Criterios del radar:** Proceso (5), Cadena de suministro (3).
- **Dónde aparece en el prototipo:**
  - Distintivo "Stock verificado hace X min" en cada farmacia.
  - Tabla "Últimos movimientos" en el detalle de la farmacia.
  - Aviso "Reposición programada: llega el jueves" en la farmacia sin stock.

### US7689318B2 · Lonnie Draper · *Inventory control and prescription dispensing system*

- **Qué hace:** bóveda robótica de dispensación con base de datos de ubicación por producto y verificación múltiple (código de barras, RFID, reconocimiento óptico, biometría).
- **Elemento tomado:** cada unidad está ubicada y verificada por escaneo, así el número mostrado coincide con el estante.
- **Criterios del radar:** Proceso (5).
- **Dónde aparece en el prototipo:** "Venta verificada por escaneo" en el historial de movimientos, y "Caja escaneada y lista" en el historial de la reserva.

### US8364504B1 · Walgreens · *Pharmacy network management system and method for ordering prescriptions*

- **Qué hace:** integra el sitio web de la farmacia con su red interna y su base de datos de clientes. Los pedidos llegan directo a la tienda y el cliente ve su historial de recetas.
- **Elemento tomado:** un portal web que lee directamente los datos de la farmacia, sin fax ni llamadas.
- **Criterios del radar:** Canal (5).
- **Dónde aparece en el prototipo:** la página de inicio con las recetas activas y la búsqueda conectada a la disponibilidad real de cada farmacia.

### US10430556B2 · Walgreens · *Location triggering for prescription ready notifications*

- **Qué hace:** cuando el teléfono del cliente detecta un beacon de la farmacia, el sistema le avisa si su receta está lista y en qué mostrador retirarla.
- **Elemento tomado:** aviso de "receta lista" que indica el mostrador exacto, y aviso de llegada del paciente.
- **Criterios del radar:** Experiencia de cliente (5), Comunicación (3).
- **Dónde aparece en el prototipo:**
  - Notificación emergente "Tu receta está lista… Mostrador 2".
  - Botón "Avisar que llegué", que en la versión web reemplaza la detección automática por beacon.
  - Código de retiro con QR.

### US20240038352A1 · Pirani y Thompson · *Method and apparatus for prescription management* (solicitud, no concedida)

- **Qué hace:** plataforma en la nube que conecta pacientes, médicos, farmacias y aseguradoras. Incluye enrutamiento de recetas con aprendizaje automático, seguimiento de estados, pagos, entregas y perfiles familiares.
- **Elementos tomados:**
  - recomendación de farmacia;
  - seguimiento del estado del pedido en tiempo real;
  - perfil familiar.
- **Elemento excluido:** los pagos, porque Captura de valor tiene puntaje 1.
- **Criterios del radar:** Soluciones (4), Cliente (4), Comunicación (3).
- **Dónde aparece en el prototipo:**
  - Etiqueta "Mejor opción" y orden de los resultados.
  - Selector "Consultar para: Yo / Rosa (mamá)".
  - Barra de estado de la reserva: recibida, en preparación, lista y retirada.

## Recorrido del prototipo y su relación con las patentes

| Pantalla | Qué ve el paciente | Criterios | Patentes |
|---|---|---|---|
| Inicio | Recetas activas, búsqueda y perfil familiar | Canal, Cliente | US8364504B1, US20240038352A1 |
| Disponibilidad | Lista y mapa de farmacias con stock, frescura del dato y reposición | Proceso, Canal, Soluciones, Cadena de suministro | US8099339B1, US20240038352A1 |
| Farmacia | Stock verificado, historial de movimientos y reserva | Experiencia, Proceso | US7689318B2, US8099339B1 |
| Reserva y retiro | Estado del pedido, aviso de receta lista, mostrador y código | Experiencia, Comunicación | US20240038352A1, US10430556B2 |

## Nota

Tomar ideas de estas patentes para un prototipo académico no presenta problema. Un producto comercial requeriría antes un análisis de libertad de operación, un estudio legal que confirma que el producto no infringe patentes vigentes. US7689318B2, por ejemplo, sigue vigente hasta aproximadamente 2028.
