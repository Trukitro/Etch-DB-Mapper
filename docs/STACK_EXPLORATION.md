# Exploración de Stack — Etch-DB-Mapper

Documento vivo para dialogar la pregunta de fondo: ¿seguimos con
CustomTkinter/Tkinter, o migramos a otra cosa?

> ## ✅ Decisión (2.0.0): migración completa a pywebview + HTML/CSS/JS
>
> Se eligió una variante de la **Opción B** sin servidor: la UI completa se
> reescribió en HTML, CSS y JS vanilla y corre dentro de una ventana
> **pywebview** (Edge WebView2 en Windows), hablando con Python por el puente
> `js_api` — sin Flask ni puertos abiertos. La Opción C (híbrido) se descartó
> porque mezclar dos UIs habría dejado lo peor de ambos mundos; la D, porque
> igual había que integrar un motor de grafos.
>
> - **Mapa**: Cytoscape.js + layout `fcose` (vendorizados, 100 % offline) en
>   lugar del Canvas de Tkinter dibujado a mano. Resuelve el «caos» de 171
>   tablas con alcance «relacionadas / todas / vecindad», colores por grupo,
>   modo foco y posiciones persistentes.
> - **Backend**: `core/` se conserva (pyDAL, JSON local) y se reescribió el
>   scanner para ser agnóstico de motor y de 4 consultas en total.
> - **Empaquetado**: sigue siendo PyInstaller + Inno Setup; la UI viaja como
>   archivos dentro del `.exe`.
> - **Linux**: ahora es viable (WebKit2GTK o Qt) — ver [`LINUX_PLAN.md`](LINUX_PLAN.md).
>
> Los 3 bugs tácticos de abajo quedaron resueltos por la nueva arquitectura
> (toasts flotantes, escaneo en 4 consultas + progreso, renombrar conexiones).
> Detalle en [`ARCHITECTURE.md`](ARCHITECTURE.md). El resto de este documento
> se conserva como registro del razonamiento original.

## Motivación / contexto

Probando contra una base SQL Server real de trabajo (171 tablas, 1972
columnas, 44 relaciones, 121 tablas huérfanas), aparecieron dos tipos de
problemas:

1. **Bugs concretos y arreglables sin cambiar nada de arquitectura** (ver
   sección siguiente).
2. **Una duda de fondo**: ¿es CustomTkinter/Tkinter la herramienta correcta
   para esto? La sensación es que la UI no tiene la fluidez de una app web,
   y que el Mapa Relacional en particular se ve caótico con un esquema de
   este tamaño.

## Bugs concretos identificados (documentados, sin implementar todavía)

### 1. Notificaciones dejan un espacio vacío al desaparecer
El banner de notificación vive en un frame reservado en el layout
(`self.notifications_frame`, fila 0 del grid). Cuando el banner se
autodestruye, el espacio que ocupaba no se recupera del todo — queda un
hueco vacío entre la barra de título y el resto de la UI.

**Dirección de arreglo**: dejar de usar un frame fijo en el grid y pasar a
notificaciones flotantes tipo "toast" (SweetAlert / flash de web2py):
un contenedor posicionado con `.place()` (no `.grid()`/`.pack()`) que
flota sobre el resto de la UI, con ancho fijo (no ocupa todo el ancho de
la ventana), y no reserva espacio en el layout — al desaparecer, no deja
hueco porque nunca "empujó" nada.

### 2. La app se pone "Non Responding" en escaneos grandes
**Causa raíz encontrada**: `core/scanner.py` hace **3 consultas SQL por
cada tabla** (columnas, Foreign Keys, Primary Keys) — para 171 tablas,
eso son **513 round-trips secuenciales** al servidor. A ~90ms promedio
por consulta, da los ~48 segundos que se ven en la captura. Esto es un
bug de patrón N+1, no necesariamente un problema de Tkinter en sí.

**Dirección de arreglo**:
- Reescribir `run_db_scan()` para traer TODO de una sola vez: 1 consulta
  para todas las columnas de todas las tablas, 1 para todas las FKs, 1
  para todas las PKs (agrupando por tabla en Python después) — de 513
  consultas a 4, sin importar cuántas tablas tenga la base.
- Igual agregar un indicador visual de progreso (spinner/barra
  indeterminada tipo `CTkProgressBar(mode="indeterminate")`) mientras el
  escaneo está en curso, para que quede claro que la app sigue viva —
  útil incluso después de optimizar las queries, para bases muy grandes
  o conexiones lentas.

### 3. No se puede renombrar una conexión guardada
Hoy el alias de una conexión (la clave en `history`/`db_maps.json`) se
define una sola vez al crearla. No hay forma de cambiarle el nombre sin
editar el JSON a mano.

**Dirección de arreglo**: agregar una acción "✏️ Renombrar" (ej. en el
Historial de DBs o en el editor de URI) que mueva la entrada a una nueva
clave en `self.history`, preservando `data`/`uri`/`status`/etc., y
actualice `current_db_name` si es la conexión activa.

## La pregunta de fondo: ¿cambiar de stack?

### Opción A — Quedarse con CustomTkinter/Tkinter
- **A favor**: ya está construido y funcionando; `.exe` standalone simple
  vía PyInstaller; no depende de navegador ni de un servidor corriendo;
  offline nativo.
- **En contra**: el Canvas de Tkinter es "dibujá vos mismo cada línea" —
  no hay librerías de grafos maduras para Tkinter (layouts force-directed
  reales, clustering, minimap, etc. hay que programarlos a mano); el
  look-and-feel es notoriamente menos "fluido" que una UI web moderna.

### Opción B — Migrar a un stack web local (Flask/FastAPI + HTML/JS), abierto en navegador o en un webview embebido
- **A favor**: acceso a librerías de grafos maduras y batalladas
  (Cytoscape.js, vis-network, D3, Sigma.js) con layouts ya resueltos
  (force-directed, dagre, elk.js), zoom/pan/clustering/búsqueda de
  fábrica; UI realmente responsive con CSS moderno; mucho más fácil de
  expandir visualmente a futuro.
- **En contra**: reescritura completa de la UI (Explorador, Historial,
  formularios, diálogos de Ayuda/Acerca de, todo); empaquetado a `.exe`
  más complejo (embeber un server + servir assets + probablemente un
  webview embebido); se descarta la mayor parte del trabajo de UI ya
  invertido en CustomTkinter.

### Opción C — Híbrido: mantener el shell en Tkinter, embeber un webview SOLO para el Mapa Relacional
Mantener Historial, Explorador, formularios, diálogos tal cual están
(ya funcionan bien), y para el Mapa Relacional específicamente —el punto
de mayor dolor— embeber un componente webview (ej. `pywebview`, o un
widget tipo `tkinterweb`/`cefpython3` según qué tan pesado se banque el
`.exe`) que renderice una librería JS de grafos (Cytoscape.js o
vis-network) con el JSON del esquema ya escaneado.
- **A favor**: ataca directamente el problema más grande (el mapa) sin
  descartar nada de lo ya construido; alcance y riesgo mucho menores que
  una migración completa; se puede probar como spike aislado sin tocar
  el resto de la app.
- **En contra**: mezcla dos paradigmas de UI en la misma app (cierta
  inconsistencia visual entre el shell Tkinter y el mapa embebido); hay
  que resolver un canal de comunicación Python↔JS (liviano — alcanza con
  pasarle el JSON del grafo y escuchar clicks/eventos de vuelta).

### Opción D — Reescribir todo con un framework Python "más web" sin HTML/JS manual (NiceGUI, Flet, etc.)
- **A favor**: look-and-feel mucho más moderno sin escribir HTML/CSS/JS a
  mano, sigue siendo Python puro de punta a punta.
- **En contra**: para el grafo relacional en particular, de todos modos
  hay que integrar (o construir) algo con la calidad de Cytoscape — no
  viene resuelto de fábrica; sigue siendo una reescritura completa de la
  UI, con el mismo costo que la Opción B en ese sentido.

## Mi lectura (para seguir discutiendo, no es la última palabra)
El dolor más grande y concreto que describiste es el Mapa Relacional
"caótico" con una base de 171 tablas. La Opción C ataca eso puntualmente
con el menor riesgo: no se tira nada de lo construido, y se puede probar
como una rama de exploración aislada antes de comprometerse a nada. Si
ese spike resuelve bien el mapa y además se siente mejor en general,
ahí se podría evaluar si vale la pena extender el mismo enfoque (webview)
a más partes de la UI — pero esa sería una decisión posterior, con datos
reales del spike en mano, no una apuesta a ciegas ahora.

Los 3 bugs tácticos (notificaciones, progreso, renombrar) y la
optimización de queries convendría arreglarlos independientemente de qué
se decida acá — son de bajo riesgo, alto valor, y no se pierde nada si
después migramos.

## Próximos pasos
- [x] Dialogar la decisión → migración completa (ver recuadro de arriba).
- [x] Verificar que `pywebview` + Cytoscape.js se empaquetan con PyInstaller
      con assets 100 % locales (el `.exe` 2.0.0 corre sin internet).
- [x] Arreglar los 3 bugs tácticos y la optimización de queries (2.0.0).
- [ ] Probar el empaquetado en Linux (ver `LINUX_PLAN.md`).
