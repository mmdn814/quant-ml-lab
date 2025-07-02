# ✅ 文件：shared/daily_index_parser.py
# 功能：用于解析 SEC 每日 master.idx 文件，提取 Form 4 filing 的 accession 列表

import os
import requests
from datetime import datetime
from typing import List, Tuple

def get_form4_accessions_from_index(date: datetime, cache_dir: str = ".cache") -> List[Tuple[str, str, str]]:
    """
    获取指定日期所有 Form 4 报告的 CIK、Accession 和完整 filing URL
    返回：List[(CIK, Accession, Filing URL)]
    """
    quarter = f"Q{((date.month - 1) // 3) + 1}"
    url = f"https://www.sec.gov/Archives/edgar/daily-index/{date.year}/{quarter}/master.{date.strftime('%Y%m%d')}.idx"

    headers = {"User-Agent": "quant-ml-lab/1.0 (mmdn814@gmail.com)"}
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"master.{date.strftime('%Y%m%d')}.idx")

    if os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            lines = f.readlines()
    else:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            lines = res.text.splitlines()
            with open(cache_path, "w") as f:
                f.write(res.text)
        except requests.RequestException:
            return []

    start = False
    results = []
    for line in lines:
        if not start:
            if line.strip().startswith("CIK|Company Name"):
                start = True
            continue

        parts = line.strip().split("|")
        if len(parts) != 5:
            continue
        cik, name, form_type, filed_date, filename = parts
        if form_type.strip() != "4":
            continue

        accession = filename.split("/")[-1].replace(".txt", "")
        url = f"https://www.sec.gov/Archives/{filename}"
        results.append((cik.zfill(10), accession, url))

    return results
