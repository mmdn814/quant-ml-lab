#暂时并未影响主流程；
#未来若你做全美市场公司名 → Ticker → CIK 完整映射时可直接接入；
#保留为后续模型扩展预留接口 ✅

import os
import json

def load_latest_cik_mapping():
    """
    预留的 CIK 编号映射读取（目前暂未用）
    未来当我们做完整历史数据建模时可自动拉取公司基本信息做补充特征
    """
    mapping_file = "data/company_cik_mapping.json"

    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            return mapping
        except Exception as e:
            print(f"载入 CIK Mapping 失败: {e}")
            return {}

    else:
        return {}
