---
title: Value Compass
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8501
pinned: false
tags:
  - streamlit
---

# Value Compass

Aplicación modular para:

1. ejecutar un cribado periódico de todas las compañías de un índice o universo;
2. ordenar el universo por valoración, calidad, caja, balance, crecimiento, riesgo y confianza;
3. detectar candidatas preliminares de entrada sin convertir el scoring en una recomendación definitiva;
4. abrir una ficha individual y realizar una valoración DCF configurable;
5. conservar histórico, exportar resultados y ampliar proveedores o métricas sin rehacer la interfaz.

## Advertencia

El proveedor Yahoo incluido es una fuente gratuita de **precarga**. No debe sustituir los informes oficiales, reguladores ni relaciones con inversores para decisiones definitivas. La aplicación bloquea las recomendaciones de entrada cuando la completitud del dato es baja.

## Arquitectura

```text
app.py                          Interfaz Streamlit
run_screening.py                Ejecución sin interfaz / automatización
config/
  settings.yaml                 Pesos, umbrales y parámetros
  universes.yaml                Índices y listas de tickers
src/
  providers/                    Proveedores intercambiables de datos
  scoring/                      Motor de scoring
  valuation/                    DCF y futuras valoraciones
  services/                     Orquestación del cribado
  storage/                      Persistencia SQLite
  models.py                     Contratos de datos
data/
  exports/                      CSV, Excel y JSON por ejecución
.github/workflows/              Automatización diaria con GitHub Actions
tests/                          Pruebas automáticas
```

## Instalación local

### Windows

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

### macOS o Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Después abre `http://localhost:8501`.

## Primera ejecución recomendada

1. Abre **Radar del índice**.
2. Elige IBEX 35.
3. Revisa la lista de tickers, porque la composición de los índices cambia.
4. Pulsa **Ejecutar cribado ahora**.
5. Ordena por `global_score`, pero revisa también `valuation`, `quality`, `balance` y `confidence`.
6. Abre las candidatas en **Análisis individual**.
7. Verifica las cifras materiales en documentación oficial.
8. Usa **Valoración DCF** con FCF normalizado, no necesariamente con el FCF bruto descargado.

## Ejecutar el radar desde terminal

```bash
python run_screening.py --universe IBEX35
```

Se crean:

- base SQLite: `data/value_compass.db`;
- CSV diario;
- Excel diario;
- JSON diario.

## Crear o modificar un universo

Edita `config/universes.yaml`:

```yaml
EUROSTOXX_CUSTOM:
  label: Mi universo europeo
  currency: EUR
  tickers:
    - ASML.AS
    - SAP.DE
    - MC.PA
```

Luego ejecuta:

```bash
python run_screening.py --universe EUROSTOXX_CUSTOM
```

## Despliegue gratuito recomendado

### Opción principal: GitHub + Streamlit Community Cloud + GitHub Actions

Esta combinación separa correctamente las funciones:

- GitHub guarda y versiona el código;
- Streamlit Community Cloud muestra la aplicación;
- GitHub Actions ejecuta el cribado diario aunque nadie abra la app;
- SQLite y los archivos diarios quedan en el repositorio como histórico sencillo.

### Pasos

1. Crea una cuenta de GitHub.
2. Crea un repositorio nuevo.
3. Descomprime este proyecto y sube todo su contenido al repositorio.
4. En GitHub, abre **Actions** y habilita los workflows.
5. Abre el workflow **Daily index screening** y ejecuta `Run workflow` una primera vez.
6. Comprueba que aparecen archivos en `data/exports`.
7. Crea una cuenta en Streamlit Community Cloud usando GitHub.
8. Pulsa **Create app**.
9. Selecciona tu repositorio, la rama principal y `app.py` como archivo de entrada.
10. Despliega la aplicación.

El cron incluido se ejecuta de lunes a viernes a las 17:30 UTC. En horario peninsular español equivale normalmente a las 18:30 en invierno y 19:30 en verano. Modifica el cron según el mercado y el momento de cierre que prefieras.

## Consideraciones del alojamiento gratuito

- Un repositorio público simplifica la gratuidad de GitHub Actions, pero deja visibles el código y los datos guardados.
- No guardes claves en el código. Usa GitHub Secrets y Streamlit Secrets.
- Los workflows programados de repositorios públicos pueden desactivarse tras periodos prolongados sin actividad.
- El horario cron de GitHub Actions no garantiza ejecución al segundo; puede sufrir retrasos.
- La persistencia local del servidor de Streamlit no debe usarse como base maestra. Por eso el workflow escribe en GitHub.

## Alternativa gratuita

Hugging Face Spaces puede alojar una interfaz pública, pero su almacenamiento local gratuito es efímero. Para este proyecto sigue siendo necesario guardar el histórico fuera del contenedor, por ejemplo en GitHub o en una base externa.

## Cómo ampliar la aplicación

### Nuevo proveedor

Crea una clase en `src/providers/` que implemente:

```python
class MiProveedor(MarketDataProvider):
    def get_snapshot(self, ticker: str) -> CompanySnapshot:
        ...
```

Puede añadirse después:

- Financial Modeling Prep, Alpha Vantage o EODHD mediante API;
- SEC, CNMV y relaciones con inversores como fuentes oficiales;
- un proveedor específico de consenso;
- importación manual desde Excel;
- extracción de informes anuales.

### Nuevas funciones previstas

La arquitectura permite incorporar sin rehacer el núcleo:

- históricos de tres ejercicios;
- normalización de FCF y owner earnings;
- ROIC y ROIC incremental;
- valor razonable por escenarios;
- múltiplos históricos y percentiles;
- modelos sectoriales para bancos, aseguradoras y REIT;
- cartera personal y precio medio;
- alertas por email o Telegram;
- revisión de nuevas cuentas y guidance;
- scoring de moat y capital allocation;
- panel de incidencias y fuentes;
- selección humana de finalistas para análisis completo.

## Principios del scoring

La nota global nunca debe usarse sola. Una entrada automática exige simultáneamente:

- score global suficiente;
- valoración suficiente;
- balance no débil;
- confianza mínima en el dato.

Los valores ausentes reciben una puntuación neutral, pero reducen la confianza. Esto evita premiar o castigar artificialmente una compañía solo por falta de información.

## Pruebas

```bash
pytest -q
```

## Docker

```bash
docker build -t value-compass .
docker run --rm -p 8501:8501 value-compass
```
