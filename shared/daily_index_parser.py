# ✅ 文件：shared/daily_index_parser.py
# 功能：用于解析 SEC 每日 master.idx 文件，提取 Form 4 filing 的 accession 列表（支持单日或多日）

import os
import requests
from datetime import datetime, timedelta
from typing import List, Tuple

def get_form4_accessions_from_index(date: datetime, cache_dir: str = ".cache") -> List[Tuple[str, str, str]]:
    """
    获取指定日期所有 Form 4 报告的 CIK、Accession 和完整 filing URL。

    参数：
        date (datetime): 指定日期（例如 datetime(2025, 7, 2)）
        cache_dir (str): 本地缓存目录，避免重复下载 idx 文件

    返回：
        List[(CIK, Accession, Filing URL)]
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

def get_form4_accessions_range(days_back: int, cache_dir: str = ".cache") -> List[Tuple[str, str, str]]:
    """
    获取过去 days_back 天内的所有 Form 4 报告（含去重）。

    参数：
        days_back (int): 向前回溯的天数，例如 3 表示今天、昨天、前天
        cache_dir (str): idx 文件缓存目录，默认 .cache

    返回：
        List[(CIK, Accession, Filing URL)]
    """
    all_results = []
    seen = set()  # 用于去重 accession
    for i in range(days_back):
        date = datetime.now() - timedelta(days=i)
        daily_results = get_form4_accessions_from_index(date, cache_dir=cache_dir)
        for cik, accession, url in daily_results:
            if accession not in seen:
                seen.add(accession)
                all_results.append((cik, accession, url))
    return all_results
