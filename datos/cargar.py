# -*- coding: utf-8 -*-
"""Carga los CSV de Olist a DuckDB y comprueba que no se perdió ninguna fila.

Uso (desde la raíz del proyecto):
    .venv/Scripts/python.exe -I datos/cargar.py datos/crudos datos/olist.duckdb

Qué hace:
  1. Extrae cada .zip de la carpeta de crudos en su propia subcarpeta (solo los .csv).
  2. Crea una tabla por CSV. El nombre sale del archivo, sin el prefijo `olist_` ni el
     sufijo `_dataset` (olist_orders_dataset.csv -> orders).
  3. Cuenta los registros de cada CSV con el módulo csv de Python, aparte de DuckDB, y
     compara. Si un solo archivo no cuadra, termina con error: una carga incompleta
     invalida todo lo que se calcule después.

Los CSV vienen de internet: se leen como datos, nunca se ejecutan, y este script se corre
con `-I` para que Python no importe nada desde la carpeta de los datos.
"""
import csv
import re
import sys
import zipfile
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")


def extraer_zips(crudos: Path) -> None:
    """Extrae solo los .csv de cada zip, cada zip en su propia carpeta."""
    for z in sorted(crudos.glob("*.zip")):
        destino = crudos / z.stem
        destino.mkdir(exist_ok=True)
        with zipfile.ZipFile(z) as zf:
            for m in zf.infolist():
                nombre = Path(m.filename).name
                if m.is_dir() or not nombre.lower().endswith(".csv"):
                    continue
                salida = destino / nombre          # se aplana: sin rutas del zip
                if not salida.exists():
                    salida.write_bytes(zf.read(m))


def nombre_tabla(archivo: Path) -> str:
    n = archivo.stem.lower()
    n = re.sub(r"^olist_", "", n)
    n = re.sub(r"_dataset$", "", n)
    n = re.sub(r"[^a-z0-9_]", "_", n)
    return n


def contar_registros(archivo: Path) -> int:
    """Registros del CSV sin contar el encabezado. Respeta saltos de línea entre comillas."""
    csv.field_size_limit(10_000_000)
    with archivo.open(newline="", encoding="utf-8-sig") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    crudos, salida = Path(sys.argv[1]), Path(sys.argv[2])
    extraer_zips(crudos)
    archivos = sorted(crudos.rglob("*.csv"))
    if not archivos:
        print(f"No hay ningún CSV en {crudos}. Faltan los .zip de Kaggle.")
        return 1

    if salida.exists():
        salida.unlink()
    con = duckdb.connect(str(salida))
    fallas = 0
    print(f"{'tabla':<40}{'filas CSV':>12}{'filas DuckDB':>14}  columnas")
    for a in archivos:
        tabla = nombre_tabla(a)
        con.execute(
            f'CREATE TABLE "{tabla}" AS SELECT * FROM read_csv(?, header = true, sample_size = -1)',
            [str(a)],
        )
        en_db = con.execute(f'SELECT count(*) FROM "{tabla}"').fetchone()[0]
        en_csv = contar_registros(a)
        cols = [c[0] for c in con.execute(f'DESCRIBE "{tabla}"').fetchall()]
        marca = "" if en_db == en_csv else "   <-- NO CUADRA"
        fallas += en_db != en_csv
        print(f"{tabla:<40}{en_csv:>12,}{en_db:>14,}  {len(cols)}{marca}")
    con.close()

    if fallas:
        print(f"\nERROR: {fallas} tabla(s) no cuadran con su CSV.")
        return 1
    print(f"\nOK: {len(archivos)} tablas cargadas en {salida}, todas cuadran con su CSV.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
