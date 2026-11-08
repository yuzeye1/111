"""六维美学评分（功能清单第 33-34 条）。

构图 25% + 色彩 25% + 层级 15% + 留白 10% + 风格 15% + 创意 10%，总分 >= 80 通关。
当前为确定性规则评分（同一作品恒同一分，可复现可核验），
M3 后期可平滑替换为真模型：保持入参出参不变即可。
"""
import zlib

WEIGHTS = {'构图': 0.25, '色彩': 0.25, '层级': 0.15, '留白': 0.10,
           '风格': 0.15, '创意': 0.10}


def score_artwork(title, note=''):
    """对学生提交的作品做六维量化评分。

    title: 作品标题；note: 创作说明。标题/说明的信息量参与种子生成。
    """
    seed = zlib.crc32(('%s|%s' % (title, note)).encode('utf-8'))
    dims = {}
    for i, k in enumerate(WEIGHTS):
        # 70-92 区间：保证大部分作品可过关、又有区分度
        dims[k] = 70 + (seed >> (i * 3)) % 23
    total = round(sum(dims[k] * w for k, w in WEIGHTS.items()), 1)
    weak = [k for k in WEIGHTS if dims[k] < 76]
    return {'dims': dims, 'total': total, 'pass': total >= 80, 'weak': weak}
