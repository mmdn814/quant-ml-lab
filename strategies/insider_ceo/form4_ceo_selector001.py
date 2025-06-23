#只负责排序；
#默认选出前 20 名；
#数据健壮性处理：即使某条记录缺少 shares 字段也不会出错；
#已完美兼容你 main.py 中的：

"""
功能模块：对已解析出的 CEO 买入数据进行排序与筛选
"""

def select_top_ceo_buys(ceo_buys, top_n=20):
    """
    按照买入数量从高到低排序，选出 Top N 个结果
    """
    # 先对买入数量做安全型排序（防止缺失数据异常）
    sorted_buys = sorted(
        ceo_buys,
        key=lambda x: x.get('shares', 0),
        reverse=True
    )

    # 只返回前 top_n 个
    return sorted_buys[:top_n]

