# folio_items_by_hrid.py
# -*- coding: utf-8 -*-
"""
Lee un archivo de texto con una columna de instance.hrid (HRID de FOLIO) y, para cada uno:
  1. HRID -> instance UUID        GET /instance-storage/instances?query=hrid=="..."
  2. instance UUID -> holdings    GET /holdings-storage/holdings
     (match exacto permanentLocationId == LOCATION_ID)
  3. holdings -> items            GET /inventory/items?query=holdingsRecordId=="..."
     y extrae barcode + title.

Salida: CSV con instance_hrid, instance_id, holdings_id, item_id, barcode, title.

Uso:
    python folio_items_by_hrid.py hrids.txt --library usb
    python folio_items_by_hrid.py hrids.txt --library usb -o salida.csv -c instance.hrid \
        --customers C:\\migration_tools\\runenv\\okapi_customers.json
"""
import argparse
import csv
import logging
import sys

# folio_login_module.py vive en C:\migration_tools\runenv
sys.path.insert(0, r"C:\migration_tools\runenv")
from folio_login_module import folio_login_module  # noqa: E402

LOCATION_ID = "8b584ac4-9760-4760-9c86-34a3f74f41b2"
PAGE = 1000


def fetch_all(client, endpoint, cql, key):
    """GET paginado con CQL; devuelve la lista completa bajo `key`."""
    out, offset = [], 0
    while True:
        r = client.get(endpoint, params={"query": cql, "limit": PAGE, "offset": offset})
        r.raise_for_status()
        batch = r.json().get(key, [])
        out.extend(batch)
        if len(batch) < PAGE:
            return out
        offset += PAGE


def read_hrids(path, column):
    """Lee la columna `column` (o la primera si no hay encabezado). Sin duplicados."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(f, dialect))
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    if column in header:
        idx, data = header.index(column), rows[1:]
    else:
        idx, data = 0, rows
    hrids = [r[idx].strip() for r in data if len(r) > idx and r[idx].strip()]
    hrids = [h for h in hrids if h != column]
    return list(dict.fromkeys(hrids))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="archivo de texto con los HRID")
    ap.add_argument("--library", required=True, help="libraryName en okapi_customers.json")
    ap.add_argument("--customers", default=r"C:\migration_tools\runenv\okapi_customers.json")
    ap.add_argument("-o", "--output", default="items_por_hrid.csv")
    ap.add_argument("-c", "--column", default="instance.hrid")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    client = folio_login_module(args.library, customers_json_path=args.customers)

    hrids = read_hrids(args.input, args.column)
    print(f"{len(hrids)} HRID a procesar")

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["instance_hrid", "instance_id", "holdings_id", "item_id", "barcode", "title"])
        for hrid in hrids:
            try:
                inst = fetch_all(client, "/instance-storage/instances", f'hrid=="{hrid}"', "instances")
                if not inst:
                    print(f"[{hrid}] instancia no encontrada")
                    continue
                inst_id = inst[0]["id"]

                holdings = fetch_all(
                    client, "/holdings-storage/holdings",
                    f'instanceId=="{inst_id}" and permanentLocationId=="{LOCATION_ID}"',
                    "holdingsRecords",
                )
                if not holdings:
                    print(f"[{hrid}] sin holdings con permanentLocationId={LOCATION_ID}")
                    continue

                for h in holdings:
                    items = fetch_all(
                        client, "/inventory/items", f'holdingsRecordId=="{h["id"]}"', "items"
                    )
                    for it in items:
                        w.writerow([hrid, inst_id, h["id"], it.get("id", ""),
                                    it.get("barcode", ""), it.get("title", "")])
            except Exception as e:  # noqa: BLE001 - continuar con el siguiente HRID
                print(f"[{hrid}] error: {e}")
    print(f"Listo: {args.output}")


if __name__ == "__main__":
    main()
