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

    # Log solo por pantalla (stdout), sin archivo
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        stream=sys.stdout,
    )
    log = logging.getLogger("folio_items_by_hrid")
    client = folio_login_module(args.library, customers_json_path=args.customers)

    hrids = read_hrids(args.input, args.column)
    total = len(hrids)
    log.info("%d HRID a procesar (ubicación %s)", total, LOCATION_ID)

    st = {
        "ok": 0,                 # HRID con al menos 1 item
        "sin_instancia": [],     # HRID sin instancia en FOLIO
        "sin_holdings": [],      # instancia sin holdings en la ubicación
        "sin_items": [],         # holdings sin items
        "errores": [],           # (hrid, mensaje)
        "holdings": 0,
        "items": 0,
        "items_sin_barcode": 0,
    }

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["instance_hrid", "instance_id", "holdings_id", "item_id", "barcode", "title"])
        for n, hrid in enumerate(hrids, 1):
            prefix = f"[{n}/{total}] {hrid}"
            try:
                inst = fetch_all(client, "/instance-storage/instances", f'hrid=="{hrid}"', "instances")
                if not inst:
                    log.warning("%s: instancia NO encontrada", prefix)
                    st["sin_instancia"].append(hrid)
                    continue
                inst_id = inst[0]["id"]
                if len(inst) > 1:
                    log.warning("%s: %d instancias con el mismo HRID, se usa la primera", prefix, len(inst))

                holdings = fetch_all(
                    client, "/holdings-storage/holdings",
                    f'instanceId=="{inst_id}" and permanentLocationId=="{LOCATION_ID}"',
                    "holdingsRecords",
                )
                if not holdings:
                    log.warning("%s: sin holdings en la ubicación", prefix)
                    st["sin_holdings"].append(hrid)
                    continue
                st["holdings"] += len(holdings)

                n_items = 0
                for h in holdings:
                    items = fetch_all(
                        client, "/inventory/items", f'holdingsRecordId=="{h["id"]}"', "items"
                    )
                    for it in items:
                        if not it.get("barcode"):
                            st["items_sin_barcode"] += 1
                            log.warning("%s: item %s sin barcode", prefix, it.get("id"))
                        w.writerow([hrid, inst_id, h["id"], it.get("id", ""),
                                    it.get("barcode", ""), it.get("title", "")])
                    n_items += len(items)
                if n_items:
                    st["ok"] += 1
                    st["items"] += n_items
                    log.info("%s: %d holdings, %d items", prefix, len(holdings), n_items)
                else:
                    log.warning("%s: %d holdings pero 0 items", prefix, len(holdings))
                    st["sin_items"].append(hrid)
            except Exception as e:  # noqa: BLE001 - continuar con el siguiente HRID
                log.error("%s: %s", prefix, e)
                st["errores"].append((hrid, str(e)))

    sep = "=" * 60
    print(f"\n{sep}\nREPORTE FINAL\n{sep}")
    print(f"HRID procesados              : {total}")
    print(f"  con items (OK)             : {st['ok']}")
    print(f"  sin instancia              : {len(st['sin_instancia'])}")
    print(f"  sin holdings en ubicación  : {len(st['sin_holdings'])}")
    print(f"  holdings sin items         : {len(st['sin_items'])}")
    print(f"  con error                  : {len(st['errores'])}")
    print(f"Holdings encontrados         : {st['holdings']}")
    print(f"Items escritos al CSV        : {st['items']}")
    print(f"Items sin barcode            : {st['items_sin_barcode']}")
    for label, key in (("Sin instancia", "sin_instancia"), ("Sin holdings", "sin_holdings"),
                       ("Holdings sin items", "sin_items")):
        if st[key]:
            print(f"\n{label}: {', '.join(st[key])}")
    if st["errores"]:
        print("\nErrores:")
        for hrid, msg in st["errores"]:
            print(f"  {hrid}: {msg}")
    print(f"{sep}\nSalida: {args.output}")


if __name__ == "__main__":
    main()
