import pandas as pd

def load_local_csv(path: str) -> pd.DataFrame:
    """
    从本地 CSV 文件中加载数据。

    参数:
        path (str): 文件路径

    返回:
        pd.DataFrame: 加载的数据内容
    """
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        print(f"读取失败：{e}")
        return pd.DataFrame()
