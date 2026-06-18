#!/usr/bin/env python3
"""
Importar servicios desde CSV a la base de datos SQLite.
Uso: python scripts/importar_servicios.py [archivo.csv]

Formato CSV esperado:
nombre,categoria,precio,duracion_min,descripcion
Alisado Brasileño Corto,Alisados,85,120,Ideal para pelo corto
"""

import csv
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "chatbot.db"


def import_services(csv_path: str, clear_existing: bool = False) -> int:
    """Import services from CSV into the database. Returns count of imported rows."""
    if not Path(csv_path).exists():
        print(f"❌ Archivo no encontrado: {csv_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if clear_existing:
        cursor.execute("DELETE FROM services")
        print("🧹 Catálogo anterior eliminado.")

    count = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                cursor.execute(
                    """INSERT INTO services (name, category, price, duration_min, description)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        row["nombre"].strip(),
                        row["categoria"].strip(),
                        float(row["precio"]),
                        int(row["duracion_min"]),
                        row.get("descripcion", "").strip(),
                    ),
                )
                count += 1
            except (KeyError, ValueError) as e:
                print(f"⚠️ Error en fila: {row} → {e}")
                continue

    conn.commit()
    conn.close()

    print(f"✅ Importados {count} servicios en {DB_PATH}")
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Importar servicios desde CSV a la BD del chatbot"
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        default="data/servicios.csv",
        help="Ruta al archivo CSV (default: data/servicios.csv)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Borrar el catálogo existente antes de importar",
    )
    args = parser.parse_args()

    import_services(args.csv_file, clear_existing=args.clear)
