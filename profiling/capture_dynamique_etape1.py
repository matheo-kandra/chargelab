#!/usr/bin/env python3
"""Capture du flux IRVE dynamique (consolidation PAN beta).

Objectif de l'etape 1 : mesurer la cadence de rafraichissement reelle du flux.
Le script interroge la ressource toutes les INTERVAL secondes, journalise
systematiquement (horodatage de capture, code HTTP, taille, hash SHA256 du
corps, horodatage de consolidation lu dans content-disposition, en-tetes
last-modified / etag) et n'archive le corps que lorsque le hash change.

Aucune donnee n'est corrigee ni deduite : on stocke le brut tel quel.
"""
import argparse
import csv
import gzip
import hashlib
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://transport.data.gouv.fr/resources/84098/download"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "dynamique"
LOG = ROOT / "data" / "raw" / "journal_dynamique.csv"
FIELDS = [
    "capture_utc", "http_status", "bytes", "sha256", "consolidation_utc",
    "last_modified", "etag", "elapsed_s", "archived_path", "erreur",
]
RE_TS = re.compile(r"consolidation-nationale-irve-dynamique-(.+?)\.csv")


def now_utc():
    return datetime.now(timezone.utc)


def append_log(row):
    exists = LOG.exists()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerow(row)


def last_hash():
    if not LOG.exists():
        return None
    prev = None
    with LOG.open(encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            if rec.get("sha256"):
                prev = rec["sha256"]
    return prev


def capture(keep_all=False):
    t0 = time.time()
    stamp = now_utc()
    row = {k: "" for k in FIELDS}
    row["capture_utc"] = stamp.isoformat()
    try:
        req = Request(URL, headers={"User-Agent": "chargelab-profiling/0.1 (etape 1, profilage)"})
        with urlopen(req, timeout=180) as resp:
            body = resp.read()
            hdr = resp.headers
            row["http_status"] = resp.status
            row["bytes"] = len(body)
            row["sha256"] = hashlib.sha256(body).hexdigest()
            cd = hdr.get("content-disposition", "") or ""
            m = RE_TS.search(cd)
            row["consolidation_utc"] = m.group(1) if m else ""
            row["last_modified"] = hdr.get("last-modified", "") or ""
            row["etag"] = hdr.get("etag", "") or ""
    except Exception as exc:  # noqa: BLE001
        row["erreur"] = f"{type(exc).__name__}: {exc}"
        row["elapsed_s"] = f"{time.time() - t0:.2f}"
        append_log(row)
        return row

    if keep_all or row["sha256"] != last_hash():
        day = stamp.strftime("%Y-%m-%d")
        out = RAW / day / (stamp.strftime("%H%M%S") + ".csv.gz")
        out.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(out, "wb", compresslevel=6) as fh:
            fh.write(body)
        row["archived_path"] = str(out.relative_to(ROOT))
    row["elapsed_s"] = f"{time.time() - t0:.2f}"
    append_log(row)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=300, help="secondes entre deux sondages")
    ap.add_argument("--duration", type=int, default=0, help="duree totale en secondes (0 = sans fin)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--keep-all", action="store_true", help="archiver meme si le hash est inchange")
    args = ap.parse_args()

    start = time.time()
    while True:
        row = capture(keep_all=args.keep_all)
        print(f"{row['capture_utc']} status={row['http_status']} bytes={row['bytes']} "
              f"consolidation={row['consolidation_utc']} archive={row['archived_path']} {row['erreur']}",
              flush=True)
        if args.once:
            return
        if args.duration and time.time() - start >= args.duration:
            return
        time.sleep(max(5, args.interval - (time.time() % args.interval) % args.interval))


if __name__ == "__main__":
    sys.exit(main())
